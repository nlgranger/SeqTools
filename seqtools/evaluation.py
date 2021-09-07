from abc import ABC, abstractmethod
import itertools
import multiprocessing
from multiprocessing import sharedctypes
import os
import pickle as pkl
import platform
import queue
import signal
import sys
import threading
import time
import weakref

from tblib import pickling_support

from .C.refcountedbuffer import RefCountedBuffer
from .errors import EvaluationError, format_stack, seterr
from .utils import get_logger


pickling_support.install()

logger = get_logger(__name__)


# Asynchronous item fetching backends -----------------------------------------

class AsyncWorker(ABC):
    @abstractmethod
    def submit_job(self, item):
        raise NotImplementedError

    @abstractmethod
    def wait_completion(self):
        raise NotImplementedError


class ProcessBacked(AsyncWorker):
    """Process-based workers with shared memory for zero-copy transfer."""
    def __init__(self, seq, num_workers=0, buffer_size=10, init_fn=None,
                 shm_size=0):
        if num_workers <= 0:
            num_workers = multiprocessing.cpu_count() - num_workers
        if num_workers <= 0:
            raise ValueError("at least one worker required")
        if buffer_size < num_workers:
            raise ValueError("at least one buffer slot required by worker")
        if shm_size > 0 and sys.version_info < (3, 8):
            raise NotImplementedError("shm support requires python>=3.8")
        if shm_size > 0 and platform.python_implementation() == "PyPy":
            raise NotImplementedError("shm support broken on PyPy")

        # allocate shared memory for zero-copy transfers from workers
        self.shm = sharedctypes.RawArray('B', shm_size)
        self.shm_slot_size = shm_size // buffer_size
        # shm slot are identified by their byte offset
        if shm_size > 0:
            self.free_shm_slots = {i * self.shm_slot_size for i in range(buffer_size)}
        else:
            self.free_shm_slots = set()

        # initialize workers
        self.job_queue = multiprocessing.Queue()
        self.result_pipes = []

        self.workers = []
        for _ in range(num_workers):
            rx, tx = multiprocessing.Pipe(duplex=False)

            worker = multiprocessing.Process(
                target=self.__class__.worker,
                args=(seq, self.job_queue, self.shm, self.shm_slot_size, tx, init_fn),
                daemon=True)
            old_sig_hdl = signal.signal(signal.SIGINT, signal.SIG_IGN)
            worker.start()
            signal.signal(signal.SIGINT, old_sig_hdl)
            tx.close()

            self.result_pipes.append(rx)
            self.workers.append(worker)

        # monitor workers
        self.worker_died = threading.Event()
        worker_monitor = threading.Thread(target=self.monitor_workers,
                                          args=(self.workers, self.worker_died),
                                          daemon=True)
        worker_monitor.start()

        # set cleanup hooks
        weakref.finalize(self, ProcessBacked.cleanup,
                         self.job_queue, self.workers, worker_monitor)

    @staticmethod
    def cleanup(job_queue, workers, monitor):
        for _ in workers:
            job_queue.put((-1, -1))
        for w in workers:
            if w.is_alive():
                w.join()
        monitor.join()

    @staticmethod
    def monitor_workers(workers, worker_died):
        while True:
            for w in workers:
                if not w.is_alive():
                    worker_died.set()
                    return

            time.sleep(1)

    def submit_job(self, item):
        try:
            shm_slot_start = self.free_shm_slots.pop()
        except KeyError:
            logger.warning("no free shm slots available, "
                           "make sure prefetch results are deleted")
            shm_slot_start = None

        self.job_queue.put((item, shm_slot_start))

    def wait_completion(self):
        while True:
            p = multiprocessing.connection.wait(self.result_pipes, timeout=1)
            if len(p) > 0:
                break
            if self.worker_died.is_set():
                raise RuntimeError("a worker died unexpectedly")

        try:
            item, success, shm_slot_start, buffer_regions, payload = p[0].recv()

        except EOFError:
            self.worker_died.set()
            raise RuntimeError("a worker died unexpectedly")

        if len(buffer_regions) > 0:  # shm was used to send payload
            # add refcount to shm to retrieve slot once free
            rc_shm = memoryview(RefCountedBuffer(
                self.shm, lambda _: self.free_shm_slots.add(shm_slot_start)))
            # delimit off-band pickle buffers
            buffers = [rc_shm[start:stop] for start, stop in buffer_regions]
            # deserialize payload
            value = pkl.loads(payload, buffers=buffers)
        elif shm_slot_start is not None:  # buffer hasn't been used
            self.free_shm_slots.add(shm_slot_start)
            value = pkl.loads(payload)
        else:
            value = pkl.loads(payload)

        return item, success, value

    @staticmethod
    def worker(seq, job_queue, shm, shm_slot_size, result_pipe, init_fn):
        ppid = os.getppid()
        logger.debug("worker started")

        if init_fn is not None:
            init_fn()

        seterr('passthrough')

        shm = memoryview(shm).cast('B')
        buffers_limits = []
        shm_offset = -1
        shm_slot_stop = -1

        def buffer_callback(buffer):
            nonlocal shm_offset

            data = buffer.raw()

            if shm_offset + data.nbytes > shm_slot_stop:
                logger.warning('shared memory is too small to store buffers')
                return True

            shm[shm_offset:shm_offset + data.nbytes] = data
            buffers_limits.append((shm_offset, shm_offset + data.nbytes))
            shm_offset += data.nbytes

            return False

        while True:
            # acquire job
            while True:
                try:
                    idx, shm_slot_start = job_queue.get(timeout=1)
                except queue.Empty:
                    if os.getppid() != ppid:  # parent died
                        logger.debug("worker stopping because parent crashed")
                        return
                else:
                    break

            if idx < 0:  # stop on sentinel value
                return

            # collect value (or error trying)
            try:
                value = seq[idx]
            except Exception as e:
                value = e
                success = False
            else:
                success = True

            # serialize it
            try:
                if shm_slot_start is None:
                    payload = pkl.dumps(value, protocol=-1)
                else:
                    buffers_limits.clear()
                    shm_offset = shm_slot_start
                    shm_slot_stop = shm_slot_start + shm_slot_size
                    payload = pkl.dumps(value, protocol=-1,
                                        buffer_callback=buffer_callback)

            except Exception as e:  # gracefully recover failed serialization
                if success:
                    success = False
                    msg = ("failed to send item {} to parent process, ".format(idx)
                           + "is it picklable? Error message was:\n{}".format(e))
                    payload = pkl.dumps(ValueError(msg))
                else:  # serialize error message because error can't be pickled
                    payload = pkl.dumps(str(value))

            # send it
            try:
                result_pipe.send((idx, success, shm_slot_start, buffers_limits, payload))

            except BrokenPipeError:  # unrecoverable error
                # parent died unexpectedly
                logger.debug("worker stopping because pipe closed")
                return

            except Exception as e:
                logger.debug("worker stopping due to unexpected error")
                raise e


class ThreadBackend(AsyncWorker):
    """Thread-based workers."""
    def __init__(self, seq, num_workers=0, init_fn=None):
        if num_workers <= 0:
            num_workers = multiprocessing.cpu_count() - num_workers
        if num_workers <= 0:
            raise ValueError("at least one worker required")

        self.job_queue = queue.Queue()
        self.done_queue = queue.Queue()

        self.workers = []
        for _ in range(num_workers):
            process = threading.Thread(
                target=self.__class__.worker,
                args=(seq, self.job_queue, self.done_queue, init_fn),
                daemon=True)
            process.start()
            self.workers.append(process)

        # set cleanup hooks
        def cleanup(job_queue, workers):
            for _ in workers:
                job_queue.put(-1)
            for w in workers:
                w.join()

        weakref.finalize(self, cleanup, self.job_queue, self.workers)

    def submit_job(self, item):
        self.job_queue.put(item)

    def wait_completion(self):
        return self.done_queue.get()

    @staticmethod
    def worker(seq, job_queue, done_queue, init_fn):
        if init_fn is not None:
            init_fn()

        seterr('passthrough')

        while True:
            # acquire job
            idx = job_queue.get()

            if idx < 0:  # stop on sentinel value
                return

            # collect value (or error trying)
            try:
                value = seq[idx]
            except Exception as e:
                value = e
                success = False
            else:
                success = True

            # notify about job completion
            done_queue.put((idx, success, value))


# ---------------------------------------------------------------------------------------

def reraise_err(item, error, stack_desc=None):
    """(re)Raise an evaluation error with contextual debug info."""

    msg = "failed to evaluate item {}".format(item)
    if stack_desc:
        msg += " in prefetch created at :\n{}".format(stack_desc)

    if isinstance(error, str):
        msg += "\n\noriginal error was:\n{}".format(error)
        raise EvaluationError(msg)

    elif seterr() == "passthrough":
        raise error

    else:
        raise EvaluationError(msg) from error


class Prefetch:
    """Manage asynchronous workers to expose an ordered prefetched sequence."""

    def __init__(self, size, backend, buffer_size, init_stack=None):
        self.size = size
        self.backend = backend
        self.creation_stack = init_stack

        self.jobs = []  # active jobs, queued or completed
        self.completed = {}

        for i in range(buffer_size):
            self.backend.submit_job(i)
            self.jobs.append(i)

    def __len__(self):
        if self.size is None:
            raise TypeError("object of type 'seqtools.Prefetch' has no len()")
        else:
            return self.size

    def __iter__(self):
        for i in range(self.size) if self.size else itertools.count():
            yield self[i]

    def __getitem__(self, item):
        # non-monotonic request
        if item != self.jobs[0]:
            for _ in range(len(self.jobs) - len(self.completed)):
                self.backend.wait_completion()

            self.completed.clear()

            self.jobs = list(range(item, item + len(self.jobs)))
            for i in self.jobs:
                self.backend.submit_job(i)

        # retrieve item, buffer other results
        while item not in self.completed:
            idx, success, value = self.backend.wait_completion()
            self.completed[idx] = success, value

        self.backend.submit_job(item + len(self.jobs))
        self.jobs.append(item + len(self.jobs))

        # return value
        self.jobs.pop(0)
        success, value = self.completed.pop(item)
        if success:
            return value
        else:
            reraise_err(item, value, self.creation_stack)


def prefetch(seq, nworkers=0, method="thread", max_buffered=10, start_hook=None,
             shm_size=0):
    """Wrap a sequence to prefetch values ahead using background workers.

    Every time an element of this container is accessed, the following
    ones are queued for evaluation by background workers. This is
    ideally placed at the end of a transformation pipeline when all
    items are to be evaluated in succession.

    .. image:: _static/prefetch.png
       :alt: gather
       :width: 30%
       :align: center

    Args:
        seq (Sequence):
            The data source.
        nworkers (int):
            Number of workers, negative values or zero indicate the
            number of cpu cores to spare (default 0).
        method (str):
            Type of workers (default `'thread'`):

            * `'thread'` uses :class:`python:threading.Thread` which
              has low overhead but allows only one active worker at a
              time, ideal for IO-bound operations.
            * `'process'` uses :class:`python:multiprocessing.Process`
              which provides full parallelism but adds communication
              overhead between workers and the parent process.
        max_buffered (Optional[int]):
            limit on the number of prefetched values at any time (default 10).
        start_hook (Optional[Callable]):
            Optional callback run by workers on start.
        shm_size (int):
            Size of shared memory (in bytes) to accelerate transfer of buffer
            objects (ex: np.ndarray) when *method='process'*.
            Set this to a large enough value to fit the buffers from
            *max_buffered* items. Make sure to delete or copy the returned
            items otherwise allocated shared memory will be depleted quickly.
            **Requires python >= 3.8**.

    Returns:
        Sequence: The wrapped sequence.
    """
    if max_buffered <= 0:
        raise ValueError('max_buffered must be greater than 0')

    if nworkers == 0:
        return seq
    elif method == "thread":
        backend = ThreadBackend(
            seq, num_workers=nworkers, init_fn=start_hook)
    elif method == "process":
        if max_buffered < 4:
            raise ValueError("process backend requires at least 4 buffer slots")
        backend = ProcessBacked(
            seq, num_workers=nworkers, buffer_size=max_buffered, init_fn=start_hook,
            shm_size=shm_size)
        # limit strain on GC to recycle buffer slots by limiting queued items
        max_buffered = max_buffered - 2
    else:
        raise ValueError("invalid prefetching method")

    try:
        size = len(seq)
    except TypeError:
        size = None
    return Prefetch(size, backend,
                    buffer_size=max_buffered,
                    init_stack=format_stack())
