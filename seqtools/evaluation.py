import sys
try:
    from weakref import finalize
except ImportError:
    from backports.weakref import finalize
import array
import multiprocessing
import multiprocessing.sharedctypes
import threading
import signal
from collections import OrderedDict
import traceback
import queue
import logging
from enum import IntEnum
from typing import Sequence
from numbers import Integral
import tblib

from future.utils import raise_from, raise_with_traceback

from .utils import basic_getitem, basic_setitem, SharedCtypeQueue

try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

logging.getLogger(__name__).addHandler(NullHandler())


# -----------------------------------------------------------------------------

class CachedSequence(Sequence):
    def __init__(self, sequence, cache_size=1, cache=None):
        self.sequence = sequence
        self.cache = cache or OrderedDict()
        self.cache_size = cache_size

    def __len__(self):
        return len(self.sequence)

    @basic_getitem
    def __getitem__(self, key):
        if key in self.cache.keys():
            return self.cache[key]
        else:
            value = self.sequence[key]
            if len(self.cache) >= self.cache_size:
                self.cache.popitem(0)
            self.cache[key] = value
            return value

    @basic_setitem
    def __setitem__(self, key, value):
        self.sequence[key] = value
        if key in self.cache.keys():
            self.cache[key] = value

    def __iter__(self):
        # bypass cache as it will be useless
        return iter(self.sequence)


def add_cache(arr, cache_size=1, cache=None):
    """Adds a caching mechanism over a sequence.

    A *reference* of the most recently accessed items will be kept and
    reused when possible.

    Args:
        arr (Sequence): Sequence to provide a cache for.
        cache_size (int): Maximum number of cached values (default 1).
        cache (Optional[Dict[int, Any]]): Dictionary-like container to
            use as cache. Defaults to a standard :class:`python:dict`.

    Returns:
        (Sequence): The sequence wrapped with a cache.
    """
    return CachedSequence(arr, cache_size, cache)


# -----------------------------------------------------------------------------

class PrefetchException(RuntimeError):
    pass


class JobStatus(IntEnum):
    """A status descriptor for evaluated jobs."""
    QUEUED = 1
    DONE = 2
    FAILED = 3


class AsyncSequenceManager(Sequence):
    """A sequence like object that wraps AsyncSequence instances.

    This class implements some generic logic to manage a sequence where
    elements are read asynchronously and out of order.

    The evaluation of selected items is managed by three means:

    - A local buffer which will store computed values.
    - An job submission queue which implements `put_nowait(job)`:
      the job is tuple with a sequence inde to be computed and a
      buffer index where the value should be written. A negative slot
      index indicates that no further jobs will come and that wrkers may
      terminate.
    - A job completion queue which implements `get(timeout)`:
      for any processed job, a triplet must be pushed containing
      the computed index in the sequence, the buffer slot where it
      resides and :attr:`JobStatus.DONE` or :attr:`JobStatus.FAILED`
      depending on the completion status. The `timeout` argument
      specifies the duration in second to wait for a value, a
      :class:`python:queue.Empty` exception should be raised past this
      delay.

    Note that the order in which jobs completed is not important.
    """
    def __init__(self, async_seq, max_cached, timeout=1, anticipate=None):
        if max_cached < 1:
            raise ValueError("cache must contain at least one slot.")

        self.async_seq = async_seq
        self.max_cached = max_cached
        self.timeout = timeout
        self.anticipate = anticipate or (lambda s: s + 1)

        # Sorting logic
        self.todo = array.array('l', [0] * max_cached)
        self.status = array.array('b', [JobStatus.DONE] * max_cached)
        self.first_slot = 0

        # Setup initial jobs
        self._start_job(0)
        for i in range(1, max_cached - 1):
            self.todo[i] = self.anticipate(self.todo[i - 1])
            self._start_job(i)

    def __len__(self):
        return len(self.async_seq)

    def __getitem__(self, item):
        # TODO: manage slices
        if not isinstance(item, Integral):
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + item.__class__.__name__)

        if item < -len(self) or item >= len(self):
            raise IndexError(
                self.__class__.__name__ + " index out of range")

        if item < 0:
            item = len(self) + item

        # unexpected request
        if item != self.todo[self.first_slot]:
            # reassign targets
            self.first_slot = 0
            self.todo[0] = item
            for i in range(1, self.max_cached):
                self.todo[i] = self.anticipate(self.todo[i - 1])
            for i in range(0, self.max_cached):
                if self.status[i] != JobStatus.QUEUED:
                    self._start_job(i)
        else:
            last_slot = (self.first_slot - 1) % self.max_cached
            todo = self.anticipate(self.todo[(last_slot - 1) % self.max_cached])
            self.todo[last_slot] = todo
            if self.status[last_slot] == JobStatus.QUEUED:
                raise AssertionError
            self._start_job(last_slot)

        # fetch results until we have the requested one
        while self.status[self.first_slot] == JobStatus.QUEUED:
            idx, slot, status = self.async_seq.next_completion()
            if idx != self.todo[slot]:  # slot was reassigned
                self._start_job(slot)
                continue
            else:
                self.status[slot] = status

        # handle errors
        if self.status[self.first_slot] == JobStatus.FAILED:
            error = PrefetchException(
                "failed to get item {}".format(self.todo[self.first_slot]))
            try:
                self.async_seq.reraise_failed_job(self.first_slot)
            except Exception as original_error:
                raise_from(error, original_error)
            finally:
                self.first_slot = (self.first_slot + 1) % self.max_cached

        else:  # or return buffer slot
            out = self.async_seq.read(self.first_slot)
            self.first_slot = (self.first_slot + 1) % self.max_cached
            return out

    def _start_job(self, slot):
        self.async_seq.enqueue(self.todo[slot], slot)
        self.status[slot] = JobStatus.QUEUED


class AsyncSequence:
    def __init__(self, sequence, job_queue, done_queue,
                 values_cache, errors_cache,
                 worker_t, nworkers=0, timeout=1, start_hook=None):
        if nworkers < 1:
            nworkers += multiprocessing.cpu_count()
        if nworkers <= 0:
            raise ValueError("need at least one worker")

        self.timeout = timeout
        self.sequence = sequence
        self.start_hook = start_hook
        self.job_queue = job_queue
        self.done_queue = done_queue

        # buffers
        self.values_cache = values_cache
        self.errors_cache = errors_cache

        # workers
        self.worker_t = worker_t
        self.workers = [None] * nworkers
        for i in range(nworkers):
            self._start_worker(i)

        # ensure clean termination in any situation
        finalize(self, AsyncSequence._finalize, self)

    @staticmethod
    def _finalize(obj):
        while True:  # clear job submission queue
            try:
                obj.job_queue.get(timeout=0.05)
            except queue.Empty:
                break

        for _ in obj.workers:
            obj.job_queue.put((0, -1))

        for w in obj.workers:
            w.join()

    def _start_worker(self, i):
        if self.workers[i] is not None:
            self.workers[i].join()
        self.workers[i] = self.worker_t(
            target=self._target,
            args=(i, self.sequence, self.values_cache, self.errors_cache,
                  self.job_queue, self.done_queue,
                  self.timeout, self.start_hook))
        old_sig_hdl = signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.workers[i].start()
        signal.signal(signal.SIGINT, old_sig_hdl)

    def __len__(self):
        return len(self.sequence)

    def enqueue(self, item, slot):
        self.job_queue.put((item, slot), timeout=1)

    def next_completion(self):
        idx, slot, status = self.done_queue.get()
        while slot < 0:
            self._start_worker(-slot - 1)
            idx, slot, status = self.done_queue.get()
        return idx, slot, status

    def read(self, slot):
        return self.values_cache[slot]

    def reraise_failed_job(self, slot):
        ev, tb = self.errors_cache[slot]
        self.errors_cache[slot] = (None, "")
        if ev is not None:
            raise_with_traceback(ev, tb.as_traceback())
        else:
            raise RuntimeError

    @staticmethod
    def _target(pid, sequence, values_buf, errors_buf, job_queue, done_queue,
                timeout, start_hook):
        logger = logging.getLogger(__name__)

        if start_hook is not None:
            start_hook()

        while True:
            try:  # acquire job
                idx, slot = job_queue.get(timeout=timeout)

            except queue.Empty:  # or go to sleep
                try:  # notify parent
                    done_queue.put((0, -pid - 1, 0))
                finally:
                    logger.debug("worker {}: timeout, exiting".format(pid))
                    return

            except Exception:  # parent probably died
                logger.debug("worker {}: parent died, exiting".format(pid))
                return

            if slot < 0:  # or terminate
                logger.debug("worker {}: exiting".format(pid))
                return

            try:
                values_buf[slot] = sequence[idx]
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
                done_queue.put((idx, slot, job_status))
            except Exception:  # parent process died unexpectedly
                logger.debug("worker {}: parent died, exiting".format(pid))
                return


def prefetch(sequence, max_buffered=None,
             nworkers=0, method='thread', timeout=1,
             start_hook=None, anticipate=None):
    """Starts multiple workers to prefetch sequence values before use.

    .. image:: _static/prefetch.png
       :alt: gather
       :width: 30%
       :align: center

    Args:
        sequence (Sequence):
            The data source.
        max_buffered (Optional[int]):
            Optional limit on the number of prefetched values at any
            time (default None).
        nworkers (int):
            Number of workers, negative values or zero indicate the
            number of cpu cores to spare (default 0).
        method (str):
            Type of workers:

            * `'thread'` uses :class:`python:threading.Thread` which
              has low overhead but allows only one active worker at a
              time, ideal for IO-bound operations.
            * `'process'` uses :class:`python:multiprocessing.Process`
              which provides full parallelism but adds communication
              overhead between workers and the parent process.

            Defaults to `'thread'`.
        timeout (int):
            Maximum idling worker time in seconds, workers will be
            restarted automatically if needed (default 1).
        start_hook (Optional[Callable]):
            Optional callback run by workers on start.
        anticipate (Optional[Callable[[int], int]]):
            An optional callable which takes an index and returns the
            index which is the most likely to be requested next.

    Returns:
        Sequence: The wrapped sequence.

    Raises:
        PrefetchError: on error while reading item from `sequence`
    """
    if method == "thread":
        job_queue = queue.Queue(maxsize=max_buffered + nworkers)
        done_queue = queue.Queue(maxsize=max_buffered + nworkers)
        values_cache = [None] * max_buffered
        errors_cache = [None] * max_buffered
        worker_t = threading.Thread
        async_seq = AsyncSequence(
            sequence, job_queue, done_queue, values_cache, errors_cache,
            worker_t, nworkers, timeout, start_hook)
        return AsyncSequenceManager(
            async_seq, max_buffered, timeout, anticipate)
    elif method in ("process", "proc"):
        job_queue = SharedCtypeQueue("Ll", maxsize=max_buffered + nworkers)
        done_queue = SharedCtypeQueue("Llb", maxsize=max_buffered + nworkers)
        manager = multiprocessing.Manager()
        values_cache = manager.list([None] * max_buffered)
        errors_cache = manager.list([None, ""] * max_buffered)
        worker_t = multiprocessing.Process
        async_seq = AsyncSequence(
            sequence, job_queue, done_queue, values_cache, errors_cache,
            worker_t, nworkers, timeout, start_hook)
        return AsyncSequenceManager(
            async_seq, max_buffered, timeout, anticipate)
    else:
        raise ValueError("unsupported method")


def eager_iter(sequence, nworkers=None, max_buffered=None, method='thread'):
    logging.warning(
        "Call to deprecated function eager_iter, use prefetch instead",
        category=DeprecationWarning,
        stacklevel=2)
    return iter(prefetch(sequence, nworkers, max_buffered, method))
