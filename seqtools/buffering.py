"""Tools related to buffering operations."""

import sys
from collections import OrderedDict
import queue
import signal
import threading
import multiprocessing
from multiprocessing.sharedctypes import RawArray
try:
    from weakref import finalize
except ImportError:
    from backports.weakref import finalize

import tblib
from future.utils import raise_from
try:
    import numpy as np
except ImportError:
    np = None

from .utils import basic_getitem, basic_setitem, get_logger
from .evaluation import JobStatus
from .errors import EvaluationError, format_stack, with_traceback, \
    seterr, passthrough


# -----------------------------------------------------------------------------

class NumpyBuffers(object):
    def __init__(self, nslots, sample):
        nbytes = [field.nbytes for field in sample]
        dtypes = [field.dtype for field in sample]
        shapes = [field.shape for field in sample]
        self.buffers = [RawArray('b', nslots * nb) for nb in nbytes]
        self.slots = [
            tuple(np.frombuffer(buf, t).reshape((nslots,) + s)[k]
                  for buf, t, s in zip(self.buffers, dtypes, shapes))
            for k in range(nslots)]

    def __getitem__(self, item):
        return self.slots[item]

    def __setitem__(self, key, value):
        for field, field_value in zip(self.slots[key], value):
            field[...] = field_value


class GenericBuffers(object):
    def __init__(self, nslots, sample):
        sample = [memoryview(field) for field in sample]
        nbytes = [field.nbytes for field in sample]
        formats = [field.format for field in sample]
        shapes = [field.shape for field in sample]
        buffers = [RawArray('b', nslots * nb) for nb in nbytes]
        self.raw_slots = [
            tuple(memoryview(buf).cast('b')[k * nb:(k + 1) * nb]
                  for buf, nb, s in zip(buffers, nbytes, shapes))
            for k in range(nslots)]
        self.slots = [
            tuple(field.cast(f, s)
                  for field, f, s in zip(slot, formats, shapes))
            for slot in self.raw_slots]

    def __getitem__(self, item):
        return self.slots[item]

    def __setitem__(self, key, value):
        for field, field_value in zip(self.raw_slots[key], value):
            field[:] = memoryview(field_value).cast('b')


# -----------------------------------------------------------------------------

class BufferLoader(object):
    def __init__(self, func, max_cached=2,
                 nworkers=0, timeout=1., start_hook=None):
        if nworkers < 1:
            nworkers += multiprocessing.cpu_count()
        if nworkers <= 0:
            raise ValueError("need at least one worker")

        self.generate = func
        self.n_workers = nworkers
        self.timeout = timeout
        self.start_hook = start_hook
        self.stack = format_stack(2)

        # prepare buffers
        sample = func()  # TODO: save this value
        self.value_slots = self._make_buffers(max_cached, sample)

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
        finalize(self, BufferLoader._finalize, self)

    @staticmethod
    def _make_buffers(max_cached, sample):
        if np is not None and all(isinstance(f, np.ndarray) for f in sample):
            return NumpyBuffers(max_cached, sample)
        elif sys.version_info[:2] >= (3, 5):
            try:
                for f in sample:
                    memoryview(f)
            except TypeError:
                raise TypeError("Unsupported data type.")
            else:
                return GenericBuffers(max_cached, sample)
        else:
            raise TypeError("Unsupported data type.")

    @staticmethod
    def _finalize(obj):
        while True:  # clear job submission queue
            try:
                obj.job_queue.get(timeout=0.05)
            except (queue.Empty, IOError, EOFError):
                break

        for _ in obj.workers:
            try:
                obj.job_queue.put(-1)
            except (IOError, EOFError):
                pass

        for worker in obj.workers:
            worker.join()

    def _start_worker(self, i):
        if self.workers[i] is not None:
            self.workers[i].join()

        self.workers[i] = multiprocessing.Process(
            target=self.target,
            args=(i, self.generate, self.value_slots, self.job_errors,
                  self.job_queue, self.done_queue,
                  self.timeout, self.start_hook))
        old_sig_hdl = signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.workers[i].start()
        signal.signal(signal.SIGINT, old_sig_hdl)

    def __iter__(self):
        return self

    def __next__(self):
        # assume last job is consumed, enqueue new one
        self.job_queue.put(self.next_in_queue)
        done_slot, status = self.done_queue.get()

        # wait for job completion
        while done_slot < 0:  # worker went to sleep
            self._start_worker(-done_slot - 1)
            done_slot, status = self.done_queue.get()

        self.next_in_queue = done_slot

        # return result
        if status == JobStatus.DONE:
            return self.value_slots[done_slot]

        else:  # deal with error
            msg = "Failed to evaluate {} in {} created at:\n{}".format(
                self.generate, self.__class__.__name__, self.stack)
            cause, trace_dump = self.job_errors[done_slot]
            if cause is None:
                raise EvaluationError(msg)
            else:
                cause = with_traceback(cause, trace_dump.as_traceback())
                if passthrough() or isinstance(cause, EvaluationError):
                    raise cause
                else:
                    raise_from(EvaluationError(msg), cause)

    next = __next__

    @staticmethod
    def target(pid, func, value_slots, error_slots,
               job_queue, done_queue, timeout, start_hook):
        logger = get_logger(__name__)

        seterr(evaluation='passthrough')
        if start_hook is not None:
            start_hook()

        logger.debug("worker %d: starting", pid)

        # make 1D bytes views of the buffer slots
        while True:
            try:  # acquire job
                slot = job_queue.get(timeout=timeout)

            except queue.Empty:  # or go to sleep
                try:  # notify parent
                    done_queue.put((-pid - 1, 0))
                finally:
                    logger.debug("worker %d: timeout, exiting", pid)
                    return

            except IOError:  # parent probably died
                logger.debug("worker %d: parent died, exiting", pid)
                return

            if slot < 0:
                logger.debug("worker %d: clean termination", pid)
                return

            try:  # generate and store value
                value_slots[slot] = func()
                job_status = JobStatus.DONE

            except Exception as error:  # save error informations if any
                try:
                    trace_dump = tblib.Traceback(sys.exc_info()[2])
                    error_slots[slot] = error, trace_dump
                except Exception:
                    error_slots[slot] = None, None

                job_status = JobStatus.FAILED

            try:  # notify about job termination
                done_queue.put((slot, job_status))
            except IOError:  # parent process died unexpectedly
                logger.debug("worker %d: parent died, exiting", pid)
                return


def load_buffers(func, max_cached=2,
                 nworkers=0, timeout=1., start_hook=None):
    """Repetitively run `func` in background workers to fill memory buffers.

    Can be used to quickly generate random minibatches of data.

    Args:
        func (Callable[, Tuple]):
            A function that returns a tuple of arrays. Currently supported
            array types are: :class:`numpy:numpy.ndarray`, and
            :class:`python:array.array` (which are wrapped into
            :class:`Memoryviews <python:memoryview>`).
        max_cached (int):
            Maximum number of precomputed values/memory slots (default 2).
        nworkers (int):
            Number of workers, negative values or zero indicate the number of
            cpu cores to spare (default 0).
        timeout (float):
            Number of seconds before idle workers go to sleep.
        start_hook (Optional[Callable]]):
            Optional function to be run by each worker on startup, for example
            :func:`python:random.seed`.

    Return:
        Iterator[Tuple]:
            An iterator on buffer slots updated with the outputs of `func`.

    Notes:
        - The shapes and types of `func` outputs must remain consistent
          across calls.
        - The buffers are reused between iterations, their content
          should therefore be considered undefined except for the last
          returned one.

    Example:
       >>> import numpy as np
       >>>
       >>> def make_sample():
       ...     return 2 * np.random.rand(5, 3), np.arange(5)
       >>>
       >>> # start workers, making sure their random seeds are different
       >>> sample_iter = load_buffers(make_sample, start_hook=np.random.seed)
       >>>
       >>> x, y = np.zeros((5, 3)), np.zeros((5,))
       >>> for _ in range(10000):
       ...     # grab next available sample
       ...     x_, y_ = next(sample_iter)
       ...
       ...     # don't keep references of x_ and y_,
       ...     # just use them before the next iteration:
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
    return BufferLoader(func, max_cached, nworkers, timeout, start_hook)


# -----------------------------------------------------------------------------

class CachedSequence(object):
    def __init__(self, sequence, cache_size=1, cache=None):
        self.sequence = sequence
        self.cache = OrderedDict() if cache is None else cache
        self.cache_size = cache_size
        self.lock = threading.Lock()

    def __len__(self):
        return len(self.sequence)

    def __iter__(self):
        # bypass cache as it will be useless
        return iter(self.sequence)

    @basic_getitem
    def __getitem__(self, key):
        with self.lock:
            if key in self.cache.keys():
                return self.cache[key]
            else:
                value = self.sequence[key]
                if len(self.cache) >= self.cache_size:
                    self.cache.popitem(False)
                self.cache[key] = value
                return value

    @basic_setitem
    def __setitem__(self, key, value):
        with self.lock:
            self.sequence[key] = value
            if key in self.cache.keys():
                self.cache[key] = value


def add_cache(arr, cache_size=1, cache=None):
    """
    Add a caching mechanism over a sequence.

    A *reference* of the most recently accessed items will be kept and
    reused when possible.

    Args:
        arr (Sequence): Sequence to provide a cache for.
        cache_size (int): Maximum number of cached values (default 1).
        cache (Optional[Dict[int, Any]]): Dictionary-like container to use as
            cache. Defaults to a standard :class:`python:dict`.

    Return:
        (Sequence): The sequence wrapped with a cache.

    Notes:
        The default cache is thread safe but won't help when multiple processes
        try to use it.

    Example:

        >>> def process(x):
        ...     print("working")
        ...     return x * 2
        >>>
        >>> data = [0, 1, 2, 3, 4, 5, 6]
        >>> result = seqtools.smap(process, data)
        >>> cached = seqtools.add_cache(result)
        >>> result[3]
        working
        6
        >>> result[3]  # smap uses systematic on-demand computations
        working
        6
        >>> cached[3]
        working
        6
        >>> cached[3]  # skips computation
        6
    """
    return CachedSequence(arr, cache_size, cache)
