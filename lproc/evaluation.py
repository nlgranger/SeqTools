import multiprocessing
import pickle as pkl
import sys
from collections import OrderedDict
from typing import Sequence

from tblib import Traceback


class CachedSequence(Sequence):
    def __init__(self, arr, cache_size=1):
        self.arr = arr
        self.cache = OrderedDict()
        self.cache_size = cache_size

    def __len__(self):
        return len(self.arr)

    def __getitem__(self, item):
        if item in self.cache:
            return self.cache[item]
        else:
            value = self.arr[item]
            if len(self.cache) >= self.cache_size:
                self.cache.popitem()
            self.cache[item] = value
            return value

    def __iter__(self):
        return iter(self.arr)


def add_cache(arr, cache_size=1):
    """Add cache to skip evaluation for the most recently accessed items.

    :param arr:
        Sequence to provide a cache for.
    :param cache_size:
        Maximum number of cached values.
    """
    return CachedSequence(arr, cache_size)


class AccessException(RuntimeError):
    pass


class ParIterWorker:
    def __init__(self, sequence, q_in, q_out):
        self.sequence = sequence
        self.q_in = q_in
        self.q_out = q_out
        self.p = multiprocessing.Process(target=self.do)
        self.p.start()

    def do(self):
        while True:
            i = self.q_in.get()
            if i is None:  # stop on sentinel value
                return

            try:
                v = self.sequence[i]

            except:
                try:  # try to send as much picklable information as possible
                    _, ev, tb = sys.exc_info()
                    tb = Traceback(tb)
                    pkl.dumps((ev, tb))  # Check picklable
                    self.q_out.put((None, (i, ev, tb)))
                except:  # nothing more we can do
                    self.q_out.put((None, (i, None, None)))

            else:
                self.q_out.put((i, v))

    def join(self):
        self.p.join()


def par_iter(sequence, nprocs=0):
    """Return an iterator which fetches values ahead using separate
    subprocesses.

    :param sequence:
        the sequence to iterate over
    :param nprocs:
        Number of workers to use. 0 or negative values indicate the number of
        CPU cores to spare. Default: 0 (one worker by cpu core)

    This function uses sub-processes to achieve concurrency, any exception
    raised while reading source elements will be signaled by an
    :class:`lproc.AccessException` raised by this function.

    .. note::
        Due to the nature of inter-process communication, the computed values
        must be serialized before being returned to the main thread therefore
        incurring a computation and communication overhead.
    """

    if nprocs <= 0:
        nprocs += multiprocessing.cpu_count()

    q_in = multiprocessing.Queue(2 * nprocs)
    q_out = multiprocessing.Queue(2 * nprocs)
    unordered_results = {}  # temporary storage for results

    proc = [ParIterWorker(sequence, q_in, q_out) for _ in range(nprocs)]

    n_injected = 0
    n_done = 0

    try:
        while n_done < len(sequence):
            # inject arguments
            while n_injected < len(sequence) and q_in.qsize() < nprocs:
                q_in.put(n_injected)
                n_injected += 1

            idx, v = q_out.get()

            if idx is None:
                i, ev, tb = v
                if ev is not None:
                    raise AccessException(
                        "Accessing index {} failed".format(i)) \
                        from ev.with_traceback(tb.as_traceback())
                else:
                    raise AccessException(
                        "Accessing index {} failed".format(i))

            else:
                unordered_results[idx] = v

                # return them in correct order
                while n_done in unordered_results.keys():
                    yield unordered_results.pop(n_done)
                    n_done += 1

    except:
        raise

    finally:  # make sure threads are stopped in all cases
        while not q_out.empty():  # drain active jobs
            q_out.get()
        for _ in range(nprocs):  # inject sentinel values to stop threads
            q_in.put(None)
        for p in proc:
            p.join()
