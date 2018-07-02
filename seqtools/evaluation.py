import sys
try:
    from weakref import finalize
except ImportError:
    from backports.weakref import finalize
import array
import multiprocessing
import multiprocessing.sharedctypes
import threading
from collections import OrderedDict
import traceback
import queue
import logging
from enum import IntEnum
from typing import Sequence
import tblib

from future.utils import raise_from, raise_with_traceback

from .utils import basic_getitem, basic_setitem, SharedCtypeQueue


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


class AsyncSequence(Sequence):
    """Abstract class to facilitate asynchronous sequence evaluation.

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

    The following methods must be overriden to provide a working
    implementation:

    - :meth:`__len__`
    - :meth:`start_workers`
    - :meth:`read_cache`
    - :meth:`reraise_failed_job` (optional but recommended)

    Args:
        max_cached (int):
            Size of the cache, must be smaller than the sequence itself.
            At any given time, no more than `max_cached` jobs will be
            queued.
        q_in:
            Job submission queue, see above description.
        q_out:
            Job completion queue, see above description.
        timeout (int):
            When waiting for a job completion, timeout specified how
            long the program should wait before attempting to restart
            possibly terminated threads with
            :func:`AsyncSequence.start_workers` (default 1).
        anticipate (Optional[Callable[[int], int]]):
            An optional callable which takes an index and returns the
            index which is the most likely to be requested next.
    """
    def __init__(self, max_cached, q_in, q_out, timeout=1, anticipate=None):
        self.q_in = q_in
        self.q_out = q_out
        self.timeout = timeout
        self.max_cached = max_cached
        if self.max_cached < 1:
            raise ValueError("cache must contain at least one slot.")
        if anticipate is not None:
            self.anticipate = anticipate
        else:
            self.anticipate = lambda s: s + 1

        # Sorting logic
        self.todo = array.array('l', [0])
        for i in range(1, self.max_cached):
            self.todo.append(self.anticipate(self.todo[-1]))
        self.status = array.array('b', [JobStatus.QUEUED] * self.max_cached)
        self.next_read_slot = 0  # slot containing the expected next read
        self.todo_next = self.anticipate(self.todo[-1])

        # Setup initial jobs
        for i in range(0, self.max_cached):
            self._start_job(i)

    def __len__(self):
        raise NotImplementedError

    def __getitem__(self, key):
        # TODO: manage slices
        # if not isinstance(key, Integral):
        #     raise TypeError(
        #         self.__class__.__name__ + " indices must be integers or "
        #         "slices, not " + key.__class__.__name__)

        if key < -len(self) or key >= len(self):
            raise IndexError(
                self.__class__.__name__ + " index out of range")

        if key < 0:
            key = len(self) + key

        return self.read_cache(self._prepare(key))

    def start_workers(self):
        """Starts workers or restarts them if they timed-out or died."""
        raise NotImplementedError

    def read_cache(self, slot):
        """Returns specified slot from the local cache."""
        raise NotImplementedError

    def reraise_failed_job(self, slot):
        """Raises encountered error or generic exception corresponding
        to the specified failed job slot.
        """
        raise RuntimeError("No information available")

    def _start_job(self, slot):
        self.q_in.put_nowait((self.todo[slot], slot))
        self.status[slot] = JobStatus.QUEUED

    def _join(self):
        while True:
            try:
                return self.q_out.get(timeout=self.timeout)

            except queue.Empty:
                self.start_workers()

    def _prepare(self, item):
        # Compute specified item and return its buffer slot.

        # reassign previously returned slot if any
        if self.status[self.next_read_slot] != JobStatus.QUEUED:
            self.todo[self.next_read_slot] = self.todo_next
            self._start_job(self.next_read_slot)

            self.todo_next = self.anticipate(self.todo_next)
            self.next_read_slot = (self.next_read_slot + 1) % self.max_cached

        # unexpected request
        if item != self.todo[self.next_read_slot]:
            # reassign targets
            self.todo[0] = item
            for i in range(1, self.max_cached):
                self.todo[i] = self.anticipate(self.todo[i - 1])

            # restart jobs
            for i in range(self.max_cached):
                if self.status[i] != JobStatus.QUEUED:
                    self._start_job(i)

            self.todo_next = self.anticipate(self.todo[self.max_cached - 1])
            self.next_read_slot = 0

        # fetch results until we have the requested one
        while not self.status[self.next_read_slot] != JobStatus.QUEUED:
            idx, slot, status = self._join()
            if idx != self.todo[slot]:  # slot reassigned
                self._start_job(slot)
            else:
                self.status[slot] = status

        # handle errors
        if self.status[self.next_read_slot] == JobStatus.FAILED:
            error = PrefetchException(
                "failed to get item {}".format(self.todo[self.next_read_slot]))
            try:
                self.reraise_failed_job(self.next_read_slot)
            except Exception as original_error:
                raise_from(error, original_error)

        # return buffer slot
        else:
            return self.next_read_slot


class ThreadedSequence(AsyncSequence):
    def __init__(self, sequence, max_cached,
                 nworkers=0, timeout=1, start_hook=None, anticipate=None):
        if nworkers <= 0:
            nworkers = max(1, multiprocessing.cpu_count() - nworkers)

        max_cached = min(max_cached, len(sequence))

        q_in = queue.Queue(maxsize=max_cached)
        q_out = queue.Queue(maxsize=max_cached)

        super(ThreadedSequence, self).__init__(
            max_cached, q_in, q_out, timeout, anticipate)

        self.sequence = sequence
        self.workers = [threading.Thread()] * nworkers
        self.values_cache = [None] * max_cached
        self.errors_cache = [(None, "")] * max_cached
        self.start_hook = start_hook

        # start working
        self.start_workers()

        # ensure proper termination in any situation
        finalize(self, ThreadedSequence._finalize, self)

    def __len__(self):
        return len(self.sequence)

    def start_workers(self):
        for i, worker in enumerate(self.workers):
            if not worker.is_alive():
                worker = threading.Thread(
                    target=self.__class__.target,
                    args=(self.sequence, self.values_cache, self.errors_cache,
                          self.q_in, self.q_out,
                          self.timeout, self.start_hook))
                worker.start()
                self.workers[i] = worker

    def read_cache(self, slot):
        return self.values_cache[slot]

    def reraise_failed_job(self, slot):
        error, trace = self.errors_cache[slot]
        self.errors_cache[slot] = (None, "")
        raise_with_traceback(error, trace)

    @staticmethod
    def target(sequence, values_cache, errors_cache, q_in, q_out,
               timeout, start_hook):
        if start_hook is not None:
            start_hook()

        while True:
            try:
                item, slot = q_in.get(timeout=timeout)
            except queue.Empty:
                return  # idling, go to sleep
            if slot < 0:
                return  # termination signal received

            try:
                values_cache[slot] = sequence[item]
            except Exception as error:
                _, _, trace = sys.exc_info()
                errors_cache[slot] = (error, trace)
                q_out.put_nowait((item, slot, JobStatus.FAILED))
            else:
                q_out.put_nowait((item, slot, JobStatus.DONE))

    @staticmethod
    def _finalize(obj):
        # drain input queue
        while not obj.q_in.empty():
            try:
                obj.q_in.get_nowait()
            except queue.Empty:
                pass

        # send termination signals
        for _ in obj.workers:
            obj.q_in.put((0, -1))

        for worker in obj.workers:
            worker.join()


class MultiprocessSequence(AsyncSequence):
    def __init__(self, sequence, max_cached,
                 nworkers=0, timeout=1, start_hook=None, anticipate=None):
        if nworkers <= 0:
            nworkers = max(1, multiprocessing.cpu_count() - nworkers)

        max_cached = min(max_cached, len(sequence))

        q_in = SharedCtypeQueue("Ll", maxsize=max_cached)
        q_out = SharedCtypeQueue("LLb", maxsize=max_cached)

        super(MultiprocessSequence, self).__init__(
            max_cached, q_in, q_out, timeout, anticipate)

        self.sequence = sequence
        self.workers = [] * nworkers
        for _ in range(nworkers):  # fill with placeholder workers
            worker = multiprocessing.Process()
            worker.start()
            self.workers.append(worker)

        manager = multiprocessing.Manager()
        self.values_cache = manager.list([None] * max_cached)
        self.errors_cache = manager.list([None, ""] * max_cached)
        self.start_hook = start_hook

        # ensure proper termination in any situation
        finalize(self, MultiprocessSequence._finalize, self)

        # start workers
        self.start_workers()

    def __len__(self):
        return len(self.sequence)

    def start_workers(self):
        for i, worker in enumerate(self.workers):
            if not worker.is_alive():
                worker.join()
                worker = multiprocessing.Process(
                    target=self.__class__.target,
                    args=(self.sequence, self.values_cache, self.errors_cache,
                          self.q_in, self.q_out,
                          self.timeout, self.start_hook))
                worker.start()
                self.workers[i] = worker

    def read_cache(self, slot):
        return self.values_cache[slot]

    def reraise_failed_job(self, slot):
        error, trace = self.errors_cache[slot]
        self.errors_cache[slot] = (None, "")
        if error is not None:
            raise_with_traceback(error, trace.as_traceback())
        else:
            raise RuntimeError(trace)

    @staticmethod
    def target(sequence, values_cache, errors_cache, q_in, q_out,
               timeout, start_hook):
        if start_hook is not None:
            start_hook()

        try:
            while True:
                try:
                    item, slot = q_in.get(timeout=timeout)
                except queue.Empty:
                    return
                if slot < 0:
                    return

                try:
                    values_cache[slot] = sequence[item]
                except Exception as error:
                    _, _, trace = sys.exc_info()
                    trace = tblib.Traceback(trace)
                    tb_str = traceback.format_exc(20)
                    # noinspection PyBroadException
                    try:  # this one may fail if ev is not picklable
                        errors_cache[slot] = error, trace
                    except Exception:
                        errors_cache[slot] = None, tb_str

                    q_out.put_nowait((item, slot, JobStatus.FAILED))

                else:
                    q_out.put_nowait((item, slot, JobStatus.DONE))

        except IOError:
            return  # parent probably died

    @staticmethod
    def _finalize(obj):
        # drain input queue
        while not obj.q_in.empty():
            try:
                obj.q_in.get_nowait()
            except queue.Empty:
                pass

        # send termination signals
        for _ in obj.workers:
            obj.q_in.put((0, -1))

        for worker in obj.workers:
            worker.join()


def prefetch(sequence, max_cached=None, nworkers=0, method='thread', timeout=1,
             start_hook=None, anticipate=None):
    """Starts multiple workers to prefetch sequence values before use.

    .. image:: _static/prefetch.png
       :alt: gather
       :width: 30%
       :align: center

    Args:
        sequence (Sequence):
            The data source.
        max_cached (Optional[int]):
            Optional limit on the number of prefetched values at any
            time (default None).
        nworkers (int):
            Number of workers, negative values or zero indicate the
            number of cpu cores to spare (default 0).
        method (str):
            Type of workers:

            * `'thread'` uses `threading.Thread` which has low overhead
              but allows only one active worker at a time, ideal for
              IO-bound operations.
            * `'process'` uses `multiprocessing.Process` which provides
              full parallelism but adds communication overhead between
              workers and the parent process.

            Defaults to 'thread'.
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

    Note:
        The wrapped sequence will raise :class:`PrefetchException` when
        accessing an item that threw an exception during evaluation.

    See also:

        * :class:`evaluation.AsyncSequence` is an abstract class that
          can facilitate the implementation of custom workers for
          prefetching.
    """
    if method == "thread":
        return ThreadedSequence(sequence,
                                max_cached, nworkers, timeout,
                                start_hook, anticipate)
    elif method == "process" or method == "proc":
        return MultiprocessSequence(sequence,
                                    max_cached, nworkers, timeout,
                                    start_hook, anticipate)
    else:
        raise ValueError("unsupported method")


def eager_iter(sequence, nworkers=None, max_buffered=None, method='thread'):
    logging.warning(
        "Call to deprecated function eager_iter, use prefetch instead",
        category=DeprecationWarning,
        stacklevel=2)
    return iter(prefetch(sequence, nworkers, max_buffered, method))
