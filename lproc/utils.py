import sys
from typing import Sequence, Union
import pickle as pkl
import array
import multiprocessing
from threading import Event, Thread, Semaphore
from queue import Queue
from tblib import Traceback

from .common import MappingException, is_int_item


class Subset(Sequence):
    def __init__(self, sequence: Union[Sequence, 'Subset'],
                 indexes: Union[Sequence[int], slice]):
        if isinstance(sequence, Subset):  # optimize nested subsets
            try:  # let the index type handle subindexing if possible
                indexes = sequence.indexes[indexes]
            except:
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

        You can reindex a subset view with either an integer, a slice a
        sequence of integer or any supported index for the parent subset
        index. The last two cases trigger an optimization of the index to avoid
        repetitive indirections.
    """
    return Subset(sequence, indexes)


class ParIterWorker:
    def __init__(self, seq, q_in, q_out):
        self.seq = seq
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
                v = self.seq[i]

            except:
                et, ev, tb = sys.exc_info()
                tb = Traceback(tb)
                try:  # try to send as much picklable information as possible
                    pkl.loads(pkl.dumps((et, ev, tb)))
                    self.q_out.put((None, (i, ev, tb)))
                except:  # nothing more we can do
                    self.q_out.put((None, (i, None, None)))

            else:
                self.q_out.put((i, v))

    def join(self):
        self.p.join()


def par_iter(sequence, nprocs=0):
    """Return an iterator which fetches values ahead using separate subprocesses

    .. warning::
        This function uses a sub-processes to achieve concurrency, any exception raised
        while reading source elements will be signaled by a MappingExcaption raised by
        this function.

    :param sequence:
        the sequence to iterate over
    :param nprocs:
        Number of workers to use. 0 or negative values indicate the number of CPU
        cores to spare. Default: 0 (one worker by cpu core)
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
                    raise MappingException(
                        "Accessing element {} of the sequence failed".format(i)) \
                        from ev.with_traceback(tb.as_traceback())
                else:
                    raise MappingException(
                        "Accessing element {} of the sequence failed".format(i))

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

    data_iterator = iter(zip(*sources))
    offset = 0
    assert wsem.acquire(blocking=False)  # first block should be readily available
    while not end_evt.is_set():
        try:
            samples = next(data_iterator)
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

        except:
            end_evt.set()
            et, ev, tb = sys.exc_info()
            tb = Traceback(tb)
            try:  # try to send as much picklable information as possible
                pkl.loads(pkl.dumps((et, ev, tb)))
                end_data.put(ev, tb)
            except:  # nothing more we can do
                end_data.put(None)

            rsem.release()

    end_data.put(None)


def chunk_load(sources, buffers, chunk_size, pad_last=False):
    """Load elements into buffers and yield a view every time a full chunk is ready.
    Typically used to generate minibatches from a bigger dataset.

    .. warning::
        This function uses a separate thread to take advantage of any inactivity in
        the main process, any exception raised while reading source elements will
        be signaled by a MappingExcaption raised by this function.

    :param sources: Sequence[Iterable]
        The data sources to read from
    :param buffers: Sequence[Sequence]
        Target storage corresponding to each data source. Buffers must support
        slice-based indexing and must be able to store any element from the source at
        any location along the forst axis
    :param chunk_size:
        How many elements should be loaded before yielding a chunks
    :param pad_last:
        If True, the last buffers will be zero-padded to chunk_size (by literally
        assigning the value `0`)
    """
    buffer_size = min([len(b) - len(b) % chunk_size for b in buffers])
    n_chunks = buffer_size // chunk_size

    rsem, wsem = Semaphore(0), Semaphore(n_chunks)
    end_evt = Event()
    end_data = Queue()

    thread = Thread(target=buffer_loader_worker,
                    args=(sources, buffers, chunk_size, rsem, wsem, end_evt, end_data))
    thread.start()

    try:
        offset = 0
        while True:
            rsem.acquire()
            if end_evt.is_set():
                v = end_data.get()

                if isinstance(v, int) and pad_last:
                    if v == 0:
                        break
                    for b in buffers:  # blank padded buffer values
                        b[offset + v:] = 0
                    yield tuple([b[offset:offset + chunk_size] for b in buffers])
                    break
                elif isinstance(v, int) and not pad_last:
                    if v == 0:
                        break
                    yield tuple([b[offset:offset + v] for b in buffers])
                    break
                elif isinstance(v, tuple):
                    ev, tb = v
                    raise MappingException("Exception raised while reading sources") \
                        from ev.with_traceback(tb)
                else:
                    raise MappingException("Exception raised while reading sources")

            else:
                yield tuple([b[offset:offset + chunk_size] for b in buffers])
                offset = (offset + chunk_size) % buffer_size
                wsem.release()

    except:
        raise

    finally:
        end_evt.set()
        wsem.release()
        end_data.get()
        thread.join()
