import multiprocessing
import threading
import queue
import pickle as pkl
import sys
from collections import OrderedDict
from typing import Sequence
from tblib import Traceback
from .common import basic_getitem, basic_setitem


class CachedSequence(Sequence):
    def __init__(self, sequence, cache_size=1):
        self.sequence = sequence
        self.cache = OrderedDict()
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
                self.cache.popitem()
            self.cache[key] = value
            return value

    @basic_setitem
    def __setitem__(self, key, value):
        self.sequence[key] = value
        if key in self.cache.keys():
            self.cache[key] = value

    def __iter__(self):
        # Bypass cache as it will be useless
        return iter(self.sequence)


def add_cache(arr, cache_size=1):
    """Add cache to skip evaluation for the most recently accessed items.

    :param arr:
        Sequence to provide a cache for.
    :param cache_size:
        Maximum number of cached values.
    """
    return CachedSequence(arr, cache_size)


class EagerAccessException(RuntimeError):
    pass


def iter_worker(sequence, q_in, q_out):
    while True:
        si = q_in.get()
        if si is None:  # stop on sentinel value
            return

        try:
            v = sequence[si]

        except Exception:
            try:  # try to add information
                _, ev, tb = sys.exc_info()
                ev = pkl.loads(pkl.dumps(ev))
                tb = pkl.loads(pkl.dumps(Traceback(tb)))

            except Exception:  # nothing more we can do
                q_out.put((None, (si, None, None)))
                return

            else:
                q_out.put((None, (si, ev, tb)))
                return

        else:
            q_out.put((si, v))


def eager_iter(sequence, nworkers=None, max_buffered=None, method='thread'):
    """Return an iterator over the sequence backed by multiple workers in order
    to fetch values ahead.

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

        - `'basic'` reverts back to a simple iterator, for debugging mostly
        - `'thread'` uses `threading.Thread` which is prefereable when many
          operations realeasing the GIL such as IO operations are involved.
          However only one thread is active at any given time
        - `'proc'` uses `multiprocessing.Process` which provides full
          parallelism but induces extra cpu and memory operations because the
          results must be serialized and copied from the workers back to main
          thread.
        - a tuple of a specified `queue.Queue`-like type and
          `threading.Thread`-like type to use.

    .. note::
        Unless the basic method is used, exceptions raised in the workers while
        reading the sequence values will trigger an
        :class:`EagerAccessException`. When possible, information on the cause
        of failure will be provided in the exception message.
    """
    if nworkers <= 0:
        nworkers = multiprocessing.cpu_count() - nworkers
    max_buffered = len(sequence) if max_buffered is None else max_buffered
    if max_buffered < 1:
        raise ValueError("max_buffered must be at least 1")

    nworkers = min(nworkers, max_buffered)

    if method == 'thread':
        queue_type = queue.Queue
        worker_type = threading.Thread

    elif method == 'proc':
        queue_type = multiprocessing.Queue
        worker_type = multiprocessing.Process

    elif method == 'basic':
        for y in sequence:
            yield y

        raise StopIteration

    else:
        queue_type, worker_type = method

    q_in = queue_type(max_buffered)
    q_out = queue_type(max_buffered)

    buffer = [None] * max_buffered  # storage for result values
    done = [False] * max_buffered
    n = len(sequence)
    workers = []

    try:
        if method == 'thread':
            for _ in range(nworkers):
                workers.append(worker_type(
                    target=iter_worker, args=(sequence, q_in, q_out)))
        else:
            for _ in range(nworkers):
                workers.append(worker_type(
                    target=iter_worker, args=(sequence, q_in, q_out)))

        for w in workers:
            w.start()

        for j in range(min(max_buffered, n)):
            q_in.put(j)

        i = 0  # sequence index
        while i < n:
            si_, v = q_out.get()

            if si_ is None:
                si_, ev, tb = v

                if ev is not None:
                    raise EagerAccessException(
                        "failed to get item {}".format(si_)) \
                        from ev.with_traceback(tb.as_traceback())

                else:
                    raise EagerAccessException(
                        "failed to get item {}".format(si_))

            buffer[si_ % max_buffered] = v
            done[si_ % max_buffered] = True

            # Return computed values
            while done[i % max_buffered]:
                yield buffer[i % max_buffered]
                done[i % max_buffered] = False

                # schedule next value in released slot
                if i + max_buffered < n:
                    q_in.put(i + max_buffered)

                i += 1

    except Exception as e:
        raise e

    finally:  # make sure workers are stopped in all cases
        while not q_out.empty():  # drain active jobs
            q_out.get()
        for _ in range(nworkers):  # inject sentinel values
            q_in.put(None)
        for p in workers:  # wait for termination
            p.join()
