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
from numbers import Integral

try:
    import tblib
except ImportError:
    tblib = None

from future.utils import raise_from, raise_with_traceback

from .utils import basic_getitem, basic_setitem, SharedCtypeQueue


# ---------------------------------------------------------------------------------------

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
    """Adds cache to skip evaluation for the most recently accessed items.

    :param arr:
        Sequence to provide a cache for.
    :param cache_size:
        Maximum number of cached values.
    :param cache:
        The container to use as cache
    """
    return CachedSequence(arr, cache_size, cache)


# ---------------------------------------------------------------------------------------

class PrefetchException(RuntimeError):
    pass


class JobStatus(IntEnum):
    QUEUED = 1,
    DONE = 2,
    FAILED = 3,


class ThreadedSequence(Sequence):
    def __init__(self, sequence, buffer_size, nworkers=0, timeout=1):
        if buffer_size < 1:
            raise ValueError("buffer size must be stricly positive")

        if nworkers <= 0:
            nworkers = multiprocessing.cpu_count() - nworkers

        self.nworkers = min(nworkers, buffer_size)

        self.sequence = sequence
        self.buffer = [None] * buffer_size
        self.errors = [None] * buffer_size
        self.q_in = queue.Queue(maxsize=buffer_size)
        self.q_out = queue.Queue(maxsize=buffer_size)
        self.manager = OOODataManager(len(sequence), buffer_size,
                                      self.add_job, self.wait, self.reraise)
        self.workers = []
        self.timeout = timeout

        # start workers
        for _ in range(nworkers):
            w = threading.Thread(
                target=self.__class__.target,
                args=(self.sequence, self.buffer, self.errors,
                      self.q_in, self.q_out, self.timeout))
            w.start()
            self.workers.append(w)

        # ensure proper termination in any situation
        finalize(self, ThreadedSequence.finalize, self.q_in, nworkers)

    def __len__(self):
        return len(self.sequence)

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.__class__(
                self.sequence[key], len(self.buffer), len(self.nworkers))

        if not isinstance(key, Integral):
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)

        if key < -len(self) or key >= len(self):
            raise IndexError(
                self.__class__.__name__ + " index out of range")

        if key < 0:
            key = len(self) + key

        return self.buffer[self.manager.prepare(key)]

    def add_job(self, item, slot):
        self.q_in.put_nowait((item, slot))

    def wait(self):
        while True:
            try:
                return self.q_out.get(timeout=self.timeout)

            except queue.Empty:
                for i, w in enumerate(self.workers):
                    if not w.is_alive():
                        w = threading.Thread(
                            target=self.__class__.target,
                            args=(self.sequence, self.buffer, self.errors,
                                  self.q_in, self.q_out, self.timeout))
                        w.start()
                        self.workers[i] = w

    def reraise(self, slot):
        et, ev, tb = self.errors[slot]
        if ev is not None:
            raise_with_traceback(ev, tb.as_traceback())
        else:
            raise RuntimeError(tb)

    @staticmethod
    def target(sequence, buffer, errors, q_in, q_out, timeout):
        while True:
            try:
                item, slot = q_in.get(timeout=timeout)
            except queue.Empty:
                return
            if slot < 0:
                return

            # noinspection PyBroadException
            try:
                buffer[slot] = sequence[item]

            except Exception:
                et, ev, tb = sys.exc_info()
                tb = tblib.Traceback(tb)
                errors[slot] = (et, ev, tb)
                q_out.put((item, slot, JobStatus.FAILED))

            else:
                q_out.put((item, slot, JobStatus.DONE))

    @staticmethod
    def finalize(q_in, n_workers):
        # drain input queue
        while not q_in.empty():
            try:
                q_in.get_nowait()
            except queue.Empty:
                pass

        # send termination signals
        for _ in range(n_workers):
            q_in.put((0, -1))


class MultiprocessSequence(Sequence):
    def __init__(self, sequence, buffer_size, nworkers=0, timeout=1):
        if buffer_size < 1:
            raise ValueError("buffer size must be stricly positive")

        if nworkers <= 0:
            nworkers = multiprocessing.cpu_count() - nworkers

        nworkers = min(nworkers, buffer_size)

        self.sequence = sequence
        manager = multiprocessing.Manager()
        self.buffer = manager.list([None] * buffer_size)
        self.errors = manager.list([None, None, ""] * buffer_size)
        self.q_in = SharedCtypeQueue("Ll", maxsize=buffer_size)
        self.q_out = SharedCtypeQueue("LLb", maxsize=buffer_size)
        self.manager = OOODataManager(len(sequence), buffer_size,
                                      self.add_job, self.wait, self.reraise)
        self.workers = []
        self.timeout = timeout

        # start workers
        for i in range(nworkers):
            w = multiprocessing.Process(
                target=self.__class__.target,
                args=(self.sequence, self.buffer, self.errors,
                      self.q_in, self.q_out, self.timeout))
            w.start()
            self.workers.append(w)

        # ensure proper termination in any situation
        finalize(self, self.__class__.finalize, self.q_in, nworkers)

    def __len__(self):
        return len(self.sequence)

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.__class__(
                self.sequence[key], len(self.buffer), len(self.workers), self.timeout)

        if not isinstance(key, Integral):
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)

        if key < -len(self) or key >= len(self):
            raise IndexError(
                self.__class__.__name__ + " index out of range")

        if key < 0:
            key = len(self) + key

        return self.buffer[self.manager.prepare(key)]

    def add_job(self, item, slot):
        self.q_in.put_nowait((item, slot))

    def wait(self):
        while True:
            try:
                return self.q_out.get(timeout=self.timeout)

            except queue.Empty:
                for i, w in enumerate(self.workers):
                    if not w.is_alive():
                        w = multiprocessing.Process(
                            target=self.__class__.target,
                            args=(self.sequence, self.buffer, self.errors,
                                  self.q_in, self.q_out, self.timeout))
                        w.start()
                        self.workers[i] = w

    def reraise(self, slot):
        et, ev, tb = self.errors[slot]
        self.errors[slot] = (None, None, "")
        if ev is not None:
            raise_with_traceback(ev, tb.as_traceback())
        else:
            raise RuntimeError(tb)

    @staticmethod
    def target(sequence, buffer, errors, q_in, q_out, timeout):
        try:
            while True:
                try:
                    item, slot = q_in.get(timeout=timeout)
                except queue.Empty:
                    return
                if slot < 0:
                    return

                # noinspection PyBroadException
                try:
                    buffer[slot] = sequence[item]

                except Exception:
                    et, ev, tb = sys.exc_info()
                    tb = tblib.Traceback(tb)
                    tb_str = traceback.format_exc(20)
                    # noinspection PyBroadException
                    try:  # this one may fail if ev is not picklable
                        errors[slot] = et, ev, tb
                    except Exception:
                        errors[slot] = None, None, tb_str

                    q_out.put_nowait((item, slot, JobStatus.FAILED))

                else:
                    q_out.put_nowait((item, slot, JobStatus.DONE))

        except IOError:
            return  # parent probably died

    @staticmethod
    def finalize(q_in, n_workers):
        # drain input queue
        while not q_in.empty():
            try:
                q_in.get_nowait()
            except queue.Empty:
                pass

        # send termination signals
        for _ in range(n_workers):
            q_in.put((0, -1))


class OOODataManager:
    """A manager for data stores accessible via job submission and asynchronous reads,
    assumes a local buffer is available to save some values in cache.
    It will schedule up to `buffer_size` jobs to try to anticipate future requests.

    :param size:
        size of the dataset
    :param buffer_size:
        limit over the number of locally stored values
    :param add_job:
        a function that triggers the computation of an item, takes the item index
        and the buffer slot where the result should be go.
    :param wait:
        a function that blocks execution until any job is completed, must return the
        index if the computed item, the buffer slot and the completion status: either
        `JobStatus.DONE` or `JobStatus.FAILED`.
    :param reraise:
        (optional) a function that reraises the error from a failed job, should take
        the buffer slot of that job as argument.
    """
    def __init__(self, size, buffer_size, add_job, wait, reraise=None):
        if buffer_size < 1:
            raise ValueError("max_buffered must be at least 1")

        self.size = size
        self.max_queued = buffer_size
        self.add_job = add_job
        self.wait = wait
        self.reraise = reraise

        # enqueue initial jobs
        for i in range(0, self.max_queued):
            add_job(i % size, i % size)

        # items computed or enqueued or soon to be enqueued
        self.todo = array.array('l', list(range(buffer_size)))
        # next item to queue
        self.todo_next = 0
        # computed values
        self.status = array.array('b', [JobStatus.QUEUED] * buffer_size)
        # slot containing the expected next read
        self.next_read_slot = 0

        self.todo_next = buffer_size % size

    def prepare(self, item):
        """Computes specified item and returns its buffer slot."""

        # reassign previously returned slot if any
        if self.status[self.next_read_slot] == JobStatus.DONE:
            self.status[self.next_read_slot] = JobStatus.QUEUED
            self.todo[self.next_read_slot] = self.todo_next
            self.add_job(self.todo_next, self.next_read_slot)

            self.todo_next = (self.todo_next + 1) % self.size
            self.next_read_slot = (self.next_read_slot + 1) % self.max_queued

        if item != self.todo[self.next_read_slot]:  # unexpected request
            # reassign targets
            for i in range(self.max_queued):
                self.todo[i] = (item + i) % self.size
                if self.status[i] == JobStatus.DONE:
                    self.add_job(self.todo[i], i)
                self.status[i] = JobStatus.QUEUED

            self.todo_next = (item + self.max_queued) % self.size
            self.next_read_slot = 0

        # fetch results until we have the requested one
        while not self.status[self.next_read_slot] != JobStatus.QUEUED:
            idx, slot, status = self.wait()
            if idx != self.todo[slot]:  # slot reassigned
                self.add_job(self.todo[slot], slot)
            else:
                self.status[slot] = status

        # handle errors
        if self.status[self.next_read_slot] == JobStatus.FAILED:
                e = PrefetchException(
                    "failed to get item {}".format(self.todo[self.next_read_slot]))
                if self.reraise is not None:
                    try:
                        self.reraise(self.next_read_slot)
                    except Exception as e_reason:
                        raise_from(e, e_reason)

                raise e

        # return buffer slot
        else:
            return self.next_read_slot


def prefetch(sequence, nworkers=None, max_buffered=None, method='thread', timeout=1):
    """Returns a view over the sequence backed by multiple workers in order to
    fetch values ahead.

    :param sequence:
        a sequence of values to iterate over
    :param nworkers:
        number of workers if positive or number of cpu cores to spare if
        negative or null, defaults to the number of cpu cores
    :param max_buffered:
        maximum number of values waiting to be consumed, set to `None` to
        remove the limit
    :param method:
        type of workers:

        - `'thread'` uses `threading.Thread` which is prefereable when many
          operations realeasing the GIL such as IO operations are involved.
          However only one thread is active at any given time.
        - `'process'` uses `multiprocessing.Process` which provides full
          parallelism but induces extra cpu and memory operations because the
          results must be serialized and copied from the workers back to main
          thread.
    :param timeout:
        minimum duration after which workers may go to sleep, may incur slowdown on the
        next requests.

    .. note::
        Exceptions raised in the workers while reading the sequence values will
        trigger an :class:`EagerAccessException`. When possible, information on
        the cause of failure will be provided in the exception message.
    """
    if method == "thread":
        return ThreadedSequence(sequence, max_buffered, nworkers, timeout)
    elif method == "process" or method == "proc":
        return MultiprocessSequence(sequence, max_buffered, nworkers, timeout)
    else:
        raise ValueError("unsupported method")


def eager_iter(sequence, nworkers=None, max_buffered=None, method='thread'):
    logging.warning(
        "Call to deprecated function eager_iter, use prefetch instead",
        category=DeprecationWarning,
        stacklevel=2)
    return iter(prefetch(sequence, nworkers, max_buffered, method))
