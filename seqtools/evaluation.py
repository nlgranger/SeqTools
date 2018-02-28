import sys
from typing import Sequence
import multiprocessing
import threading
from collections import OrderedDict
import pickle as pkl
import traceback
try:
    from multiprocessing import SimpleQueue
except ImportError:
    from multiprocessing.queues import SimpleQueue
try:
    from queue import Queue
except ImportError:
    from Queue import Queue
try:
    import tblib
except ImportError:
    tblib = None

from future.utils import raise_from, raise_with_traceback

from .common import basic_getitem, basic_setitem


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
                self.cache.popitem()
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


class EagerAccessException(RuntimeError):
    pass


def iter_worker(pid, sequence, outbuf, q_in, q_out, errbuf):
    si = 0

    try:
        while True:
            # print("w{} reading value".format(pid))
            si, bi = q_in.get()
            if si < 0:  # stop on sentinel value
                return

            outbuf[bi] = sequence[si]
            q_out.put((si, bi))

    except Exception as e:
        try:  # try to add information
            et, ev, tb = sys.exc_info()
            tb = tblib.Traceback(tb)
            pkl.dumps((et, ev, tb))  # check we can transmit error

            errbuf[pid] = (et, ev, tb)
            q_out.put((-si - 1, pid))

            raise e

        except Exception as e:  # nothing more we can do
            errbuf[pid] = (None, None, traceback.format_exc(20))
            q_out.put((-si - 1, pid))

            raise e

        finally:
            return

    finally:  # silence logging since we handle errors ourselves
        return


def eager_iter(sequence, nworkers=None, max_buffered=None, method='thread'):
    """Returns an iterator over the sequence backed by multiple workers in
    order to fetch values ahead.

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
        queue_type = Queue
        worker_type = threading.Thread
        outbuf = [None] * max_buffered
        errbuf = [None] * nworkers

    elif method == 'proc':
        queue_type = SimpleQueue
        worker_type = multiprocessing.Process
        manager = multiprocessing.Manager()
        outbuf = manager.list([None] * max_buffered)
        errbuf = manager.list([None] * nworkers)

    elif method == 'basic':
        for y in sequence:
            yield y

        raise StopIteration

    else:
        queue_type, worker_type, outbuf, errbuf = method
        if len(outbuf) < max_buffered:
            raise ValueError("buffer is too small")

    q_in = queue_type()
    q_out = queue_type()

    done = [False] * max_buffered
    n = len(sequence)
    workers = []

    try:
        if method == 'thread':
            for pid in range(nworkers):
                workers.append(worker_type(
                    target=iter_worker,
                    args=(pid, sequence, outbuf, q_in, q_out, errbuf)))
        else:
            for pid in range(nworkers):
                workers.append(worker_type(
                    target=iter_worker,
                    args=(pid, sequence, outbuf, q_in, q_out, errbuf)))

        for w in workers:
            w.start()

        for j in range(min(max_buffered, n)):
            q_in.put((j, j))

        i = 0  # sequence index
        while i < n:
            si, bi = q_out.get()

            if si >= 0:
                done[si % max_buffered] = True

                # return computed values
                while done[i % max_buffered]:
                    yield outbuf[i % max_buffered]

                    # schedule next value in released slot
                    done[i % max_buffered] = False
                    if i + max_buffered < n:
                        si = i + max_buffered
                        bi = (i + max_buffered) % max_buffered
                        q_in.put((si, bi))

                    i += 1

            else:
                si = -si - 1
                et, ev, tb = errbuf[bi]

                if ev is not None:
                    try:
                        raise_with_traceback(ev, tb.as_traceback())
                    except Exception as e_reason:
                        e = EagerAccessException(
                            "failed to get item {}".format(si))
                        raise_from(e, e_reason)

                else:
                    raise EagerAccessException(
                        "failed to get item {}".format(si))

    except Exception as e:
        raise e

    finally:  # make sure workers are stopped in all cases
        while not q_out.empty():  # drain active jobs
            q_out.get()
        for _ in range(nworkers):  # inject sentinel values
            q_in.put((-1, -1))
        for p in workers:  # wait for termination
            p.join()
