import sys
from typing import Sequence, Union
import array
import bisect
import multiprocessing
from threading import Event, Thread, Semaphore
from queue import Queue
import pickle as pkl
from tblib import Traceback
from collections import OrderedDict

from .common import is_int_item


class Subset(Sequence):
    def __init__(self, sequence: Union[Sequence, 'Subset'],
                 indexes: Union[Sequence[int], slice]):
        if isinstance(sequence, Subset):  # optimize nested subsets
            try:  # let the index type handle sub-indexing if possible
                indexes = sequence.indexes[indexes]
            except Exception:
                indexes = [sequence.indexes[i] for i in indexes]
            sequence = sequence.sequence

        if isinstance(indexes, slice):
            start = indexes.start or 0
            stop = indexes.stop or len(sequence)
            step = indexes.step or 1
            if start < 0:
                start = len(sequence) + start
            if stop < 0:
                stop = len(sequence) + stop
            indexes = array.array('L', range(start, stop, step))

        self.sequence = sequence
        self.indexes = indexes

    def __len__(self):
        return len(self.indexes)

    def __getitem__(self, item):
        if is_int_item(item):
            return self.sequence[self.indexes[item]]
        else:
            # note: no magic here, we delegate indexing to data containers.
            return Subset(self.sequence[item], self.indexes[item])


def subset(sequence, indexes):
    """Return a view on a reindexed sequence.

    The indexes are either a sequence of integers or a slice.

    .. note::

        This function will try to optimize nested re-indexing to avoid
        repetitive indirections.
    """
    return Subset(sequence, indexes)


class Concatenation(Sequence):
    def __init__(self, sequences):
        self.sequences = []
        for s in sequences:
            if isinstance(s, Concatenation):
                for ss in s.sequences:
                    self.sequences.append(ss)
            else:
                self.sequences.append(s)

        self.offsets = array.array('L', [0] + [len(s) for s in sequences])
        for i in range(1, len(sequences) + 1):
            self.offsets[i] += self.offsets[i - 1]

    def __len__(self):
        return self.offsets[-1]

    def __getitem__(self, item):
        if not 0 <= item < len(self):
            raise IndexError("index out of range")

        s = bisect.bisect(self.offsets, item) - 1
        return self.sequences[s][item - self.offsets[s]]


def concatenate(sequences):
    """Return a concatenated view of a list of sequences."""
    return Concatenation(sequences)


class Collation(Sequence):
    def __init__(self, sequences):
        self.sequences = sequences

        if not all([len(s) == len(self.sequences[0])
                    for s in self.sequences]):
            raise ValueError("all sequences should have the same length")

    def __len__(self):
        return len(self.sequences[0])

    def __getitem__(self, item):
        return tuple([s[item] for s in self.sequences])

    def __iter__(self):
        return zip(*self.sequences)


def collate(sequences):
    """Stack or paste multiple sequences together.

    The n'th element is a tuple of the n'th elements from each sequence.

    Example:

    >>> arr = collate([[1, 2, 3, 4], ['a', 'b', 'c', 'd'], [5, 6, 7, 8]])
    >>> arr[2]
    (3, 'c', 7)
    """
    return Collation(sequences)


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
    """Add cache over a sequence to accelerate access to the most recently
    accessed items.

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

    .. warning::
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


def buffer_loader_worker(sources, buffers, chunk_size: int,
                         rsem: Semaphore, wsem: Semaphore,
                         end_evt: Event, end_data: Queue):
    buffer_size = min([len(b) - len(b) % chunk_size for b in buffers])

    offset = 0
    assert wsem.acquire(blocking=False)  # first block should be available
    while not end_evt.is_set():
        try:
            samples = next(sources)
            for s, b in zip(samples, buffers):
                b[offset] = s
            offset += 1
            if offset % chunk_size == 0:
                offset = offset % buffer_size
                rsem.release()
                wsem.acquire()

        except StopIteration:
            end_evt.set()
            end_data.put(offset % chunk_size)
            rsem.release()

        except Exception:
            end_evt.set()
            try:  # try to send as much picklable information as possible
                _, ev, tb = sys.exc_info()
                tb = Traceback(tb)
                pkl.dumps((ev, tb))  # Check picklable
                end_data.put((ev, tb))
            except Exception:  # nothing more we can do
                end_data.put(None)

            rsem.release()

    end_data.put(None)


def chunk_load(sources, destination, bloc_size,
               drop_last=False, pad_last=False, use_thread=True):
    """Load elements from iterables into buffers and yield a view every time a
    full chunk is ready. Typically used to generate minibatches from a dataset.

    :param sources: Sequence[Iterable]
        The data sources to read from
    :param destination: Sequence[Sequence]
        Target storage corresponding to each data source. Buffers must support
        slice-based indexing and must be able to store any element from the
        source at any location along the first axis
    :param bloc_size: int
        How many elements should be loaded before yielding a chunks
    :param drop_last: bool
        Ignore the last chunk if it is smaller than `chunk_size`.
    :param pad_last:
        If True, the last buffers will be zero-padded to chunk_size (by
        literally assigning the value `0`)

    .. warning::
        This function uses a separate thread to take advantage of any
        inactivity in the main process, any exception raised while reading
        source elements will be signaled by an :class:`lproc.AccessException`
        raised by this function.
    """

    assert(len(sources) == len(destination))
    sources = zip(*sources)

    buffer_size = min([len(b) - len(b) % bloc_size for b in destination])
    n_chunks = buffer_size // bloc_size

    # Simple version not using threads
    if not use_thread:
        offset = 0
        for samples in sources:
            for s, b in zip(samples, destination):
                b[offset] = s
            offset += 1
            if offset % bloc_size == 0:
                yield tuple([b[offset - bloc_size:offset]
                             for b in destination])
                offset = offset % buffer_size

        if offset % bloc_size != 0 and not drop_last:
            i1 = offset - offset % bloc_size
            if pad_last:
                i2 = i1 + offset
                for b in destination:
                    b[offset:i1 + bloc_size] = 0
            else:
                i2 = offset

            yield tuple([b[i1:i2] for b in destination])

        return

    # Load data using a separate thread
    rsem, wsem = Semaphore(0), Semaphore(n_chunks)
    end_evt = Event()
    end_data = Queue()

    thread = Thread(target=buffer_loader_worker,
                    args=(sources, destination, bloc_size,
                          rsem, wsem, end_evt, end_data))
    thread.start()

    try:
        offset = 0
        while True:
            rsem.acquire()

            if not end_evt.is_set():
                yield tuple([b[offset:offset + bloc_size] for b in destination])
                offset = (offset + bloc_size) % buffer_size
                wsem.release()

            elif rsem.acquire(blocking=False):  # not the last block
                rsem.release()
                yield tuple([b[offset:offset + bloc_size] for b in destination])
                offset = (offset + bloc_size) % buffer_size
                wsem.release()

            else:
                v = end_data.get()

                if isinstance(v, int) and pad_last:
                    if v == 0:
                        break
                    for b in destination:  # blank padded buffer values
                        b[offset + v:] = 0
                    yield tuple([b[offset:offset + bloc_size]
                                 for b in destination])
                    break
                elif isinstance(v, int) and not pad_last:
                    if v == 0 or (drop_last and v < bloc_size):
                        break
                    yield tuple([b[offset:offset + v] for b in destination])
                    break
                elif isinstance(v, tuple):
                    ev, tb = v
                    raise AccessException(
                        "Exception raised while reading sources") \
                        from ev.with_traceback(tb.as_traceback())
                else:
                    raise AccessException(
                        "Exception raised while reading sources")

    except:
        raise

    finally:
        end_evt.set()
        wsem.release()
        end_data.get()
        thread.join()
