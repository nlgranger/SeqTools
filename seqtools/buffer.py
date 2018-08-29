import logging
import multiprocessing
import queue
import signal
import sys
import traceback
import weakref

import tblib

from seqtools import PrefetchException
from seqtools.evaluation import JobStatus


class BufferLoader:
    def __init__(self, func, wrap_slot=None, max_cached=2, nworkers=0,
                 timeout=1, start_hook=None):
        if nworkers < 1:
            nworkers += multiprocessing.cpu_count()
        if nworkers <= 0:
            raise ValueError("need at least one worker")
        wrap_slot = wrap_slot or (lambda x: x)

        self.generate = func
        self.n_workers = nworkers
        self.timeout = timeout
        self.start_hook = start_hook

        # prepare buffers
        nbytes, shapes, formats = BufferLoader._probe_type(func())

        self.buffers = []
        for f, s in zip(formats, nbytes):
            self.buffers.append(
                multiprocessing.sharedctypes.RawArray('b', max_cached * s))

        self.buffer_views = []
        for i in range(max_cached):
            view = []
            for buf, fmt, nb, s in zip(self.buffers, formats, nbytes, shapes):
                field_view = memoryview(buf)[i * nb:(i + 1) * nb]
                field_view = field_view.cast('b').cast(fmt, s)
                view.append(field_view)
            self.buffer_views.append(wrap_slot(tuple(view)))

        # job management
        self.job_queue = multiprocessing.Queue(maxsize=max_cached + nworkers)
        self.done_queue = multiprocessing.Queue(maxsize=max_cached + nworkers)
        manager = multiprocessing.Manager()
        self.job_errors = manager.list([None] * max_cached)

        # workers
        for i in range(max_cached - 1):
            self.job_queue.put(i)
        self.workers = [None] * nworkers
        for i in range(nworkers):
            self._start_worker(i)

        self.next_in_queue = max_cached - 1

        # clean destruction
        weakref.finalize(self, BufferLoader._finalize, self)

    @staticmethod
    def _probe_type(sample):
        sample = [memoryview(field) for field in sample]
        nbytes = [field.nbytes for field in sample]
        shapes = [field.shape for field in sample]
        formats = [field.format for field in sample]

        return nbytes, shapes, formats

    @staticmethod
    def _finalize(obj):
        while True:  # clear job submission queue
            try:
                obj.job_queue.get(timeout=0.05)
            except queue.Empty:
                break

        for _ in obj.workers:
            obj.job_queue.put(-1)

        for w in obj.workers:
            w.join()

    def _start_worker(self, i):
        if self.workers[i] is not None:
            self.workers[i].join()
        self.workers[i] = multiprocessing.Process(
            target=self.target,
            args=(i, self.generate, self.buffers, self.job_errors,
                  self.job_queue, self.done_queue,
                  self.timeout, self.start_hook))
        old_sig_hdl = signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.workers[i].start()
        signal.signal(signal.SIGINT, old_sig_hdl)

    def __iter__(self):
        return self

    def __next__(self):
        self.job_queue.put(self.next_in_queue)
        done_slot, status = self.done_queue.get()

        while done_slot < 0:
            self._start_worker(-done_slot - 1)
            done_slot, status = self.done_queue.get()

        self.next_in_queue = done_slot
        if status == JobStatus.FAILED:
            ev, tb = self.job_errors[done_slot]
            if ev is not None:
                ev = ev.with_traceback(tb.as_traceback())
                msg = "Error while executing {}".format(self.generate)
                raise PrefetchException(msg) from ev
            else:
                msg = "Error while executing {}:\n{}".format(self.generate, tb)
                raise PrefetchException(msg)

        else:
            return self.buffer_views[done_slot]

    @staticmethod
    def target(pid, generate, values_buf, errors_buf, job_queue, done_queue,
               timeout, start_hook):
        logger = logging.getLogger(__name__)

        if start_hook is not None:
            start_hook()

        logger.debug("worker {}: starting".format(pid))

        # make 1D bytes views of the buffer slots
        max_cached = len(errors_buf)
        values_buf = [memoryview(b) for b in values_buf]
        item_nbytes = tuple(buf.nbytes // max_cached for buf in values_buf)
        slot_views = []
        for slot in range(max_cached):
            slot_views.append(tuple(
                buf.cast('b', (buf.nbytes,))[slot * sz:(slot + 1) * sz]
                for buf, sz in zip(values_buf, item_nbytes)))

        while True:
            try:  # acquire job
                slot = job_queue.get(timeout=timeout)

            except queue.Empty:  # or go to sleep
                try:  # notify parent
                    done_queue.put((-pid - 1, 0))
                finally:
                    logger.debug("worker {}: timeout, exiting".format(pid))
                    return

            except Exception:  # parent probably died
                logger.debug("worker {}: parent died, exiting".format(pid))
                return

            if slot < 0:
                logger.debug("worker {}: exiting".format(pid))
                return

            try:  # generate and store value
                value = generate()
                value = [memoryview(field) for field in value]
                value = [field.cast('b', (field.nbytes,)) for field in value]
                for buf_view, field in zip(slot_views[slot], value):
                    buf_view[:] = field
                job_status = JobStatus.DONE

            except Exception:  # save error informations if any
                et, ev, tb = sys.exc_info()
                try:
                    errors_buf[slot] = ev, tblib.Traceback(tb)
                except Exception:
                    errors_buf[slot] = \
                        None, traceback.format_exception(et, ev, tb)
                job_status = JobStatus.FAILED

            try:  # notify about job termination
                done_queue.put((slot, job_status))
            except Exception:  # parent process died unexpectedly
                logger.debug("worker {}: parent died, exiting".format(pid))
                return


def load_buffers(func, wrap_slot=None, max_cached=2,
                 nworkers=0, timeout=1, start_hook=None):
    """
    Repetitively run `func` to fill memory buffers, uses
    multiprocessing to accelerate execution.

    (Only available for python 3.5 and above).

    Note:
        `func` will be called once to probe the value types and shapes

    Args:
        func (Callable[[], Tuple):
            A function that returns a tuple of buffer-like objects
            (for example :class:`numpy:numpy.ndarray` or
            :class:`python:array.array`), the shapes and types must
            remain consistent across calls.
        wrap_slot (Callable[Tuple, Any]):
            a function that takes a buffer slot, ie. a tuple of
            :func:`python:memoryview` matching the output of `func`,
            and wraps them into more convenient containers.
        max_cached (int):
            Maximum number of precomputed values/memory slots.
        nworkers (int):
            Number of worker processes.
        timeout (Union[int,float]):
            Number of seconds before idle workers go to sleep.
        start_hook (Callable[[], Any]):
            Function to call in each worker at startup (for example
            :func:`python:random.seed`)

    Returns:
        Iterator[Tuple]: An iterator on buffer slots updated with the
        outputs of `func`.

    Raises:
        PrefetchError: when `func` raises an error.

    Example:

       >>> import numpy as np

       >>> def make_sample():
       ...     return 2 * np.random.rand(5, 3), np.arange(5)
       >>>
       >>> def wrap_slot(slot):
       ...     slot_x, slot_y = slot
       ...     return (np.frombuffer(slot_x, np.float).reshape(slot_x.shape),
       ...             np.frombuffer(slot_y, np.int).reshape(slot_y.shape))
       >>>
       >>> # start workers, making sure their random seeds are different
       >>> sample_iter = load_buffers(
       ...     make_sample, wrap_slot, start_hook=np.random.seed)
       >>>
       >>> x, y = np.zeros((5, 3)), np.zeros((5,))
       >>> for _ in range(10000):
       ...     x_, y_ = next(sample_iter)
       ...     x += x_
       ...     y += y_
       >>>
       >>> print(np.round(x / 10000))
       [[1. 1. 1.]
        [1. 1. 1.]
        [1. 1. 1.]
        [1. 1. 1.]
        [1. 1. 1.]]
       >>> print(np.round(y / 10000))
       [0. 1. 2. 3. 4.]
    """
    return BufferLoader(func, wrap_slot,
                        max_cached, nworkers, timeout, start_hook)