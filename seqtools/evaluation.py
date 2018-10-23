"""Tools related to the evaluation of sequence items."""

import sys
import array
import multiprocessing
import multiprocessing.sharedctypes
import threading
import signal
import queue
from enum import IntEnum

try:
    from weakref import finalize
except ImportError:
    from backports.weakref import finalize

import tblib
from future.utils import raise_from

from .utils import isint, SharedCtypeQueue, get_logger
from .errors import EvaluationError, format_stack, with_traceback, \
    passthrough, seterr


# -----------------------------------------------------------------------------


class JobStatus(IntEnum):
    """A status descriptor for evaluated jobs."""
    QUEUED = 1
    DONE = 2
    FAILED = 3


class PrefetchedSequence(object):
    """Wraps :class:`AsyncSequence` to expose a more familiar
    :class:`python:Sequence` interface.
    """
    def __init__(self, async_seq, max_cached, timeout=1., anticipate=None):
        if max_cached < 1:
            raise ValueError("cache must contain at least one slot.")

        self.creation_stack = format_stack(2)

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

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __getitem__(self, item):
        # TODO: manage slices
        if not isint(item):
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
            msg = "failed to prefetch item {} in {} created at:\n{}".format(
                self.todo[self.first_slot],
                self.__class__.__name__,
                self.creation_stack)
            cause = self.async_seq.read_error(self.first_slot)
            if cause is not None:
                if passthrough() or isinstance(cause, EvaluationError):
                    raise cause
                else:
                    raise_from(EvaluationError(msg), cause)
            else:
                raise EvaluationError(msg)

        else:  # or return buffer slot
            out = self.async_seq.read_value(self.first_slot)
            self.first_slot = (self.first_slot + 1) % self.max_cached
            return out

    def _start_job(self, slot):
        self.async_seq.enqueue(self.todo[slot], slot)
        self.status[slot] = JobStatus.QUEUED


class AsyncSequence(object):
    """Asynchronous container with a small local buffer and multiple workers.

    Items from this container must be requested by queuing a job with
    :func:`enqueue`, they will be transfered asynchronously at the
    requested buffer slot by a background worker.

    Calling :func:`next_completion` will block until a job is
    completed, its result is then accessible using :func:`read_value`.
    """
    def __init__(self, sequence, job_queue, done_queue,
                 values_cache, errors_cache,
                 worker_t, nworkers=0, timeout=1., start_hook=None):
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
        self.values_slots = values_cache
        self.errors_slots = errors_cache

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
            except (queue.Empty, IOError, EOFError):
                break

        for _ in obj.workers:
            try:
                obj.job_queue.put((0, -1))
            except (IOError, EOFError):
                pass

        for worker in obj.workers:
            worker.join()

    def _start_worker(self, i):
        if self.workers[i] is not None:
            self.workers[i].join()
        self.workers[i] = self.worker_t(
            target=self._target,
            args=(i, self.sequence, self.values_slots, self.errors_slots,
                  self.job_queue, self.done_queue,
                  self.timeout, self.start_hook))
        old_sig_hdl = signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.workers[i].start()
        signal.signal(signal.SIGINT, old_sig_hdl)

    def __len__(self):
        return len(self.sequence)

    def enqueue(self, item, slot):
        """Request retrieval of sequence item into given buffer slot."""
        self.job_queue.put((item, slot), timeout=1)

    def next_completion(self):
        """Block until completion of any job.

        Return:
            (int, int, JobStatus): index of computed value, buffer slot,
            and job status.
        """
        idx, slot, status = self.done_queue.get()
        while slot < 0:
            self._start_worker(-slot - 1)
            idx, slot, status = self.done_queue.get()
        return idx, slot, status

    def read_value(self, slot):
        """Return the content of the buffer at the given slot."""
        return self.values_slots[slot]

    def read_error(self, slot):
        """Return the error that was raised while performing a job.

        Args:
            slot (int): the slot associated to the failed job.
        Return:
             Optional[Exception]: the exception object or `None` if it
             could not be retrieved.
        """
        error, trace_dump = self.errors_slots[slot]
        self.errors_slots[slot] = (None, None)

        if error is not None:
            return with_traceback(error, trace_dump.as_traceback())
        else:
            return None

    @staticmethod
    def _target(pid, sequence, value_slots, error_slots, job_queue, done_queue,
                timeout, start_hook):
        logger = get_logger(__name__)

        seterr(evaluation='passthrough')
        if start_hook is not None:
            start_hook()

        while True:
            try:  # acquire job
                idx, slot = job_queue.get(timeout=timeout)

            except queue.Empty:  # or go to sleep
                try:  # notify parent
                    done_queue.put((0, -pid - 1, 0))
                finally:
                    logger.debug("worker %d: timeout, exiting", pid)
                    return

            except IOError:  # parent probably died
                logger.debug("worker %d: parent died, exiting", pid)
                return

            if slot < 0:  # terminate
                logger.debug("worker %d: clean termination", pid)
                return

            try:
                value_slots[slot] = sequence[idx]
                job_status = JobStatus.DONE

            except Exception as error:  # save error informations if any
                try:
                    trace_dump = tblib.Traceback(sys.exc_info()[2])
                    error_slots[slot] = error, trace_dump
                except Exception:
                    error_slots[slot] = None, None

                job_status = JobStatus.FAILED

            try:  # notify about job termination
                done_queue.put((idx, slot, job_status))

            except IOError:  # parent process died unexpectedly
                logger.debug("worker %d: parent died, exiting", pid)
                return


def prefetch(sequence, max_buffered,
             nworkers=0, method='thread', timeout=1.,
             start_hook=None, anticipate=None):
    """Wrap a sequence to prefetch values ahead using background workers.

    This function breaks the on-demand execution principle used in this
    library but does so transparently using background workers.
    Every time an element of this container is accessed, the following ones are
    queued for computation as well and will be available sooner when needed.
    This is ideally placed at the end of a transformation pipeline
    when all items must be evaluated in succession.

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
        timeout (float):
            Maximum idling worker time in seconds, workers will be
            restarted automatically if needed (default 1).
        start_hook (Optional[Callable]):
            Optional callback run by workers on start.
        anticipate (Optional[Callable[[int], int]]):
            An optional callable which takes an index and returns the
            index which is the most likely to be requested next.

    Returns:
        Sequence: The wrapped sequence.
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
        return PrefetchedSequence(
            async_seq, max_buffered, timeout, anticipate)
    elif method in ("process", "proc"):
        job_queue = SharedCtypeQueue("Ll", maxsize=max_buffered + nworkers)
        done_queue = SharedCtypeQueue("Llb", maxsize=max_buffered + nworkers)
        manager = multiprocessing.Manager()
        values_cache = manager.list([None] * max_buffered)
        errors_cache = manager.list([None, None] * max_buffered)
        worker_t = multiprocessing.Process
        async_seq = AsyncSequence(
            sequence, job_queue, done_queue, values_cache, errors_cache,
            worker_t, nworkers, timeout, start_hook)
        return PrefetchedSequence(
            async_seq, max_buffered, timeout, anticipate)
    else:
        raise ValueError("unsupported method")


def eager_iter(sequence, nworkers=None, max_buffered=None, method='thread'):
    """Return worker-backed sequence iterator (deprecated)."""
    logger = get_logger(__name__)
    logger.warning(
        "Call to deprecated function eager_iter, use prefetch instead",
        category=DeprecationWarning,
        stacklevel=2)
    return iter(prefetch(sequence, nworkers, max_buffered, method))
