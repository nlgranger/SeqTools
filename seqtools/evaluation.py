import sys
try:
    from weakref import finalize
except ImportError:
    from backports.weakref import finalize
import array
from typing import Sequence
import multiprocessing
import multiprocessing.sharedctypes
import threading
from collections import OrderedDict
import traceback
import queue
try:
    import tblib
except ImportError:
    tblib = None

from future.utils import raise_from, raise_with_traceback

from .utils import basic_getitem, basic_setitem, SharedCtypeQueue


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


class EagerAccessException(RuntimeError):
    pass


def _worker(pid, sequence, outbuf, errbuf, q_in, q_out, idle_timout):
    si = 0

    # noinspection PyBroadException
    try:
        while True:
            try:
                si, bi = q_in.get(timeout=idle_timout)
            except queue.Empty:
                q_out.put((-1, pid))
                return

            if si < 0:  # stop on sentinel value
                return

            outbuf[bi] = sequence[si]
            q_out.put((si, bi))
            # print(' ', si, bi, '>'

    except Exception:
        # noinspection PyBroadException
        try:  # try to add information
            et, ev, tb = sys.exc_info()
            tb = tblib.Traceback(tb)
            # pkl.dumps((et, ev, tb))  # TODO: check we can transmit error?

            errbuf[pid] = (et, ev, tb)
            q_out.put((-si - 2, pid))

        except Exception:  # nothing more we can do
            errbuf[pid] = (None, None, traceback.format_exc(20))
            q_out.put((-si - 2, pid))

    finally:  # silence logging since we handle errors ourselves
        return


class Prefetcher(Sequence):
    def __init__(self, sequence, nworkers=None, max_buffered=None,
                 method='thread', direction=None, idle_timout=2):
        if nworkers <= 0:
            nworkers = multiprocessing.cpu_count() - nworkers

        max_buffered = len(sequence) if max_buffered is None else max_buffered
        if max_buffered < 1:
            raise ValueError("max_buffered must be at least 1")

        nworkers = min(nworkers, max_buffered)

        if method == 'thread':
            queue_type = queue.Queue
            worker_type = threading.Thread
            outbuf = [None] * max_buffered
            errbuf = [None] * nworkers

        elif method == 'proc':
            def queue_type():
                return SharedCtypeQueue(fmt="2i", max_size=max_buffered)

            worker_type = multiprocessing.Process
            manager = multiprocessing.Manager()
            outbuf = manager.list([None] * max_buffered)
            errbuf = manager.list([None] * nworkers)

        else:
            queue_type, worker_type, outbuf, errbuf = method
            if len(outbuf) < max_buffered:
                raise ValueError("buffer is too small")

        if direction is None:
            init, step_item = 0, lambda j: (j + 1) % len(sequence)
        else:
            init, step_item = direction

        self.sequence = sequence
        self.workers = []
        self.max_buffered = max_buffered
        self.worker_type = worker_type
        self.q_in = queue_type()
        self.q_out = queue_type()
        self.outbuf = outbuf
        self.errbuf = errbuf
        self.done = [False] * max_buffered
        self.todo = array.array('l', [-1] * max_buffered)
        self.cursor = 0  # the next slot we want to *read*
        self.step_item = step_item
        self.idle_timeout = idle_timout

        # enqueue jobs
        self.todo[0] = init
        self.q_in.put_nowait((init, 0))
        for i in range(1, max_buffered):
            self.todo[i] = self.step_item(self.todo[i - 1])
            self.q_in.put_nowait((self.todo[i], i))

        # start workers
        for pid in range(nworkers):
            w = worker_type(
                target=_worker,
                args=(pid, sequence, self.outbuf, self.errbuf,
                      self.q_in, self.q_out, self.idle_timeout))
            w.start()
            self.workers.append(w)

        # ensure proper termination in any situation
        finalize(self, Prefetcher._finalize,
                 self.workers, self.q_in, self.q_out)

    def __len__(self):
        return len(self.sequence)

    def _readone(self):
        si, bi = self.q_out.get()

        if si >= 0:
            if self.todo[bi] != si:  # not the desired item anymore
                self.q_in.put_nowait((self.todo[bi], bi))  # enqueue right one
            else:
                self.done[bi] = True

        elif si == -1:  # worker timed out, restart it
            self.workers[bi] = self.worker_type(
                target=_worker,
                args=(bi, self.sequence, self.outbuf, self.errbuf,
                      self.q_in, self.q_out, self.idle_timeout))
            self.workers[bi].start()

        else:  # handle evaluation error
            si = -si - 2
            et, ev, tb = self.errbuf[bi]

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

    @basic_getitem
    def __getitem__(self, key):
        if key != self.todo[self.cursor]:
            # cancel as many jobs as possible
            renewable = [i for i, done in enumerate(self.done) if done]
            try:
                while True:
                    renewable.append(self.q_in.get_nowait()[1])
            except queue.Empty:
                pass

            # reassign target
            self.cursor = 0
            self.done = [False] * self.max_buffered
            self.todo[0] = key
            for i in range(1, self.max_buffered):
                self.todo[i] = self.step_item(self.todo[i - 1])

            # enqueue new jobs
            for bi in renewable:
                self.q_in.put_nowait((self.todo[bi], bi))

        # reassign previously returned slot if any
        last_slot = (self.cursor - 1) % self.max_buffered
        if self.done[last_slot]:
            last_enqueued = self.todo[(self.cursor - 2) % self.max_buffered]
            self.todo[last_slot] = self.step_item(last_enqueued)
            self.done[last_slot] = False
            self.q_in.put_nowait((self.todo[last_slot], last_slot))

        # fetch results until we have requested one
        while not self.done[self.cursor]:
            self._readone()

        output = self.outbuf[self.cursor]
        self.cursor = (self.cursor + 1) % self.max_buffered
        return output

    def __iter__(self):
        yield self[0]
        last_enqueued = self.todo[-1]

        for i in range(1, len(self)):
            last_enqueued = self.step_item(last_enqueued)
            last_slot = (i - 1) % self.max_buffered
            self.todo[last_slot] = last_enqueued
            self.done[last_slot] = False
            self.q_in.put_nowait((last_enqueued, last_slot))
            self.cursor = (i + 1) % self.max_buffered
            actual_cursor = i % self.max_buffered

            # fetch results until we have requested one
            while not self.done[actual_cursor]:
                self._readone()

            yield self.outbuf[actual_cursor]

    @staticmethod
    def _finalize(workers, q_in, q_out):
        while not q_in.empty():
            q_in.get(timeout=0.05)
        while not q_out.empty():
            q_out.get(timeout=0.05)
        for _ in range(len(workers)):  # inject sentinel values
            q_in.put((-1, -1))
        for w in workers:  # wait for termination
            w.join()


def prefetch(sequence, nworkers=None, max_buffered=None,
             method='thread', direction=None, idle_timout=2):
    """Returns view over the sequence backed by multiple workers in order to
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
          However only one thread is active at any given time
        - `'proc'` uses `multiprocessing.Process` which provides full
          parallelism but induces extra cpu and memory operations because the
          results must be serialized and copied from the workers back to main
          thread.
    :param direction:
        a tuple with an initial value and a function taking the current index
        and returning the next item to prefetch. Default to monotonic
        progress with step 1.
    :param idle_timout:
        number of seconds to wait before idle workers go to sleep.

    .. note::
        Exceptions raised in the workers while reading the sequence values will
        trigger an :class:`EagerAccessException`. When possible, information on
        the cause of failure will be provided in the exception message.
    """
    return Prefetcher(sequence, nworkers, max_buffered, method,
                      direction, idle_timout)
