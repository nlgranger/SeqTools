import functools
import struct
import pickle as pkl
import gc
import os
import queue
import signal
import threading
import time
from abc import ABC, abstractmethod
import weakref

try:
    from torch import multiprocessing
    from torch.multiprocessing import sharedctype
except ImportError:
    import multiprocessing
    from multiprocessing import sharedctypes
from tblib import pickling_support

from .errors import format_stack, EvaluationError, seterr
from .memory import packed_size, pack, unpack
from .utils import get_logger
from .C.refcountedbuffer import RefCountedBuffer


pickling_support.install()


# Asynchronous item fetching backends -----------------------------------------

class AsyncWorker(ABC):
    @abstractmethod
    def submit_job(self, item):
        raise NotImplementedError

    @abstractmethod
    def wait_completion(self):
        raise NotImplementedError


class ProcessBackend(AsyncWorker):
    """Process-based workers communicating values with pipes."""
    def __init__(self, seq, num_workers=0, init_fn=None):
        if num_workers <= 0:
            num_workers = multiprocessing.cpu_count() - num_workers
        if num_workers <= 0:
            raise ValueError("at least one worker required")

        self.job_queue = multiprocessing.Queue()
        self.result_pipes = []

        self.workers = []
        for _ in range(num_workers):
            rx, tx = multiprocessing.Pipe(duplex=False)
            worker = multiprocessing.Process(
                target=self.__class__.worker,
                args=(seq, self.job_queue, tx, init_fn),
                daemon=True)

            old_sig_hdl = signal.signal(signal.SIGINT, signal.SIG_IGN)
            worker.start()
            signal.signal(signal.SIGINT, old_sig_hdl)
            tx.close()
            self.result_pipes.append(rx)
            self.workers.append(worker)

        # monitor workers
        self.worker_died = threading.Event()
        worker_monitor = threading.Thread(target=ProcessBackend.monitor_workers,
                                          args=(self.workers, self.worker_died),
                                          daemon=True)
        worker_monitor.start()

        # set cleanup hooks
        weakref.finalize(self, ProcessBackend.cleanup,
                         self.job_queue, self.workers, worker_monitor)

    def submit_job(self, item):
        self.job_queue.put(item)

    def wait_completion(self):
        while True:
            p = multiprocessing.connection.wait(self.result_pipes, timeout=1)
            if len(p) > 0:
                try:
                    return p[0].recv()
                except EOFError:
                    self.worker_died.set()

            if self.worker_died.is_set():
                raise RuntimeError("worker died unexpetedly")

    @staticmethod
    def worker(seq, job_queue, result_pipe, init_fn):
        logger = get_logger(__name__)
        ppid = os.getppid()
        logger.debug("worker started")

        if init_fn is not None:
            init_fn()

        seterr('passthrough')

        while True:
            # acquire job
            while True:
                try:
                    idx = job_queue.get(timeout=1)
                    break
                except queue.Empty:
                    if os.getppid() != ppid:  # parent died
                        logger.debug("worker stopping because parent crashed")
                        return

            if idx < 0:  # stop on sentinel value
                logger.debug("worker stopping")
                return

            # collect value (or error trying)
            try:
                value = seq[idx]
            except Exception as e:
                value = e
                success = False
            else:
                success = True

            # send it
            try:
                result_pipe.send((idx, success, value))

            except Exception as e:
                if success:  # can't send it, this becomes an error case
                    msg = ("failed to send item {} to parent process, ".format(idx)
                           + "is it picklable? Error message was:\n{}".format(e))
                    value = ValueError(msg)
                    success = False

                else:  # can't send the error, fallback to a simplified feedback
                    value = str(e)

                try:
                    result_pipe.send((idx, success, value))
                except BrokenPipeError:  # parent died unexpectedly
                    logger.debug("worker stopping because pipe closed")
                    return

    @staticmethod
    def monitor_workers(workers, worker_died):
        while True:
            for w in workers:
                if not w.is_alive():
                    worker_died.set()
                    return

            time.sleep(1)

    @staticmethod
    def cleanup(job_queue, workers, monitor):
        for _ in workers:
            job_queue.put(-1)
        for w in workers:
            if w.is_alive():
                w.join()
        monitor.join()


class BufferRecycler:
    def __init__(self, buffers):
        self.buffers = buffers
        self.buffer_queue = queue.Queue(maxsize=len(buffers))
        for i, buf in enumerate(buffers):
            cb = functools.partial(
                BufferRecycler.recycle,
                buffer_idx=i,
                buffer_queue=self.buffer_queue)
            rcbuf = RefCountedBuffer(buf, cb)
            self.buffer_queue.put((i, rcbuf))

    def fetch(self):
        try:
            i, buf = self.buffer_queue.get_nowait()
        except queue.Empty:
            pass
        else:
            return i, memoryview(buf)

        gc.collect()
        try:
            i, buf = self.buffer_queue.get_nowait()
        except queue.Empty:
            raise MemoryError("none of the buffers has been release yet.") from None
        else:
            return i, memoryview(buf)

    @staticmethod
    def recycle(buffer, buffer_idx, buffer_queue):
        buffer_queue.put_nowait((buffer_idx, buffer))


class SHMProcessBacked(AsyncWorker):
    """Process-based workers communicating values via shared memory."""
    def __init__(self, seq, num_workers=0, buffer_size=20, init_fn=None):
        if num_workers <= 0:
            num_workers = multiprocessing.cpu_count() - num_workers
        if num_workers <= 0:
            raise ValueError("at least one worker required")
        if buffer_size < num_workers:
            raise ValueError("at least one buffer slot required by worker")

        self.sample = seq[0]
        sample_size = packed_size(self.sample)

        self.job_queue = multiprocessing.Queue()
        self.result_pipes = []
        shm = memoryview(sharedctypes.RawArray('b', sample_size * buffer_size))
        buffers = [shm[i * sample_size:(i + 1) * sample_size]
                   for i in range(buffer_size)]
        self.buffer_recycler = BufferRecycler(buffers)
        self.result_buffers = {}

        self.workers = []
        for _ in range(num_workers):
            rx, tx = multiprocessing.Pipe(duplex=False)

            worker = multiprocessing.Process(
                target=self.__class__.worker,
                args=(seq, self.job_queue, buffers, tx, init_fn),
                daemon=True)
            old_sig_hdl = signal.signal(signal.SIGINT, signal.SIG_IGN)
            worker.start()
            signal.signal(signal.SIGINT, old_sig_hdl)
            tx.close()

            self.result_pipes.append(rx)
            self.workers.append(worker)

        # monitor workers
        self.worker_died = threading.Event()
        worker_monitor = threading.Thread(target=ProcessBackend.monitor_workers,
                                          args=(self.workers, self.worker_died),
                                          daemon=True)
        worker_monitor.start()

        # set cleanup hooks
        weakref.finalize(self, SHMProcessBacked.cleanup,
                         self.job_queue, self.workers, worker_monitor)

    def submit_job(self, item):
        try:
            slot, self.result_buffers[item] = self.buffer_recycler.fetch()
        except MemoryError as e:
            if any(not w.is_alive() for w in self.workers):
                raise RuntimeError("worker died unexpetedly")
            raise e
        else:
            self.job_queue.put((item, slot))

    def wait_completion(self):
        while True:
            p = multiprocessing.connection.wait(self.result_pipes, timeout=1)
            if len(p) > 0:
                try:
                    idx, success, error = struct.unpack('L?L', p[0].recv_bytes(24))
                    if not success:
                        error = pkl.loads(p[0].recv_bytes(error))
                except EOFError:
                    self.worker_died.set()
                    raise RuntimeError("worker died unexpectedly")
                else:
                    break

            elif self.worker_died.is_set():
                raise RuntimeError("worker died unexpetedly")

        if success:
            value, _ = unpack(self.sample, self.result_buffers.pop(idx))
            return idx, success, value
        else:
            self.result_buffers.pop(idx)
            return idx, success, error

    @staticmethod
    def worker(seq, job_queue, buffers, result_pipe, init_fn):
        ppid = os.getppid()
        logger = get_logger(__name__)
        logger.debug("worker started")

        if init_fn is not None:
            init_fn()

        seterr('passthrough')

        while True:
            # acquire job
            while True:
                try:
                    idx, buffer_idx = job_queue.get(timeout=1)
                    break
                except queue.Empty:
                    if os.getppid() != ppid:  # parent died
                        logger.debug("worker stopping because parent crashed")
                        return

            if idx < 0:  # stop on sentinel value
                return

            # collect value (or error trying)
            try:
                payload = seq[idx]
            except Exception as e:
                payload = e
                success = False
            else:
                success = True

            # send it
            if success:
                try:
                    pack(payload, buffers[buffer_idx])
                    result_pipe.send_bytes(struct.pack('L?L', idx, success, 0))
                except Exception as e:
                    msg = ("failed to send item {} to parent process, ".format(idx)
                           + "is it packable? Error message was:\n{}".format(e))
                    payload = ValueError(msg)
                    success = False

            if not success:
                try:
                    payload = pkl.dumps(payload)
                except Exception:  # fallback to a simplified feedback
                    payload = pkl.dumps(str(payload))

                try:
                    result_pipe.send_bytes(struct.pack('L?L', idx, success, len(payload)))
                    result_pipe.send_bytes(payload)
                except BrokenPipeError:  # unrecoverable error
                    # parent died unexpectedly
                    logger.debug("worker stopping because pipe closed")
                    return

    @staticmethod
    def cleanup(job_queue, workers, monitor):
        for _ in workers:
            job_queue.put((-1, -1))
        for w in workers:
            if w.is_alive():
                w.join()
        monitor.join()


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
        return self.size

    def __iter__(self):
        for i in range(len(self)):
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


def prefetch(seq, nworkers=0, method="thread", max_buffered=10, start_hook=None):
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
            * `'sharedmem'` also uses processes but with shared memory
              between workers and the main process which features
              zero-copy transfers.
              This adds several limitations however:

              - References to the returned items must be deleted to allow
                recycling of the memory slots (for example the items can be
                read as for loop variables and therefore erase at every
                iteration).
              - All items must be buffers of identical shape and type (ex:
                :ref:`np.ndarray <numpy:arrays>`), tuples or dicts
                of buffers are also supported.
              - A fairly large value for `max_buffer` is recommended to avoid
                draining all memory slots before the garbage collector releases
                them.
        max_buffered (Optional[int]):
            limit on the number of prefetched values at any time (default 10).
        start_hook (Optional[Callable]):
            Optional callback run by workers on start.

    Returns:
        Sequence: The wrapped sequence.
    """
    if nworkers == 0:
        return seq
    elif method == "thread":
        backend = ThreadBackend(
            seq, num_workers=nworkers, init_fn=start_hook)
    elif method == "process":
        backend = ProcessBackend(
            seq, num_workers=nworkers, init_fn=start_hook)
    elif method == "sharedmem":
        backend = SHMProcessBacked(
            seq, num_workers=nworkers, buffer_size=max_buffered, init_fn=start_hook)
        max_buffered = max_buffered // 2  # limit strain on GC to recycle buffer slots
    else:
        raise ValueError("invalid prefetching method")

    return Prefetch(len(seq), backend,
                    buffer_size=max_buffered,
                    init_stack=format_stack())
