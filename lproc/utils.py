import array
import multiprocessing
import traceback
from typing import Sequence, Union
from .common import is_int_item


class Subset(Sequence):
    def __init__(self, sequence: Union[Sequence, 'Subset'],
                 indexes: Union[Sequence[int], slice]):
        if isinstance(sequence, Subset):  # optimize nested subsets
            try:  # let the index type handle subindexing if possible
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

        You can reindex a subset view with either an integer, a slice a
        sequence of integer or any supported index for the parent subset
        index. The last two cases trigger an optimization of the index to avoid
        repetitive indirections.
    """
    return Subset(sequence, indexes)


class _par_iter_worker:
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
            else:
                try:
                    v = self.seq[i]
                except Exception:
                    self.q_out.put((None, (i, traceback.format_exc())))
                    return
                else:
                    self.q_out.put((i, v))

    def join(self):
        self.p.join()


def par_iter(sequence: Sequence, nprocs=0):
    """Return an iterator which fetches values ahead with separate threads

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

    proc = [_par_iter_worker(sequence, q_in, q_out) for _ in range(nprocs)]

    n_buffered = 0
    n_done = 0

    for i in range(len(sequence)):
        if n_buffered >= 2 * nprocs:  # fetch some results after a while
            idx, v = q_out.get()
            unordered_results[idx] = v
            n_buffered -= 1

            # return them in correct order
            while n_done in unordered_results.keys():
                yield unordered_results.pop(n_done)
                n_done += 1

        # inject arguments
        q_in.put(i)
        n_buffered += 1

    while n_buffered > 0:  # extract remaining results
        idx, v = q_out.get()
        if idx is None:
            for _ in range(nprocs):  # inject sentinel values to stop threads
                q_in.put(None)

            del proc
            raise RuntimeError("Accessing the item at index "
                               "{} failed with the following stack trace: \n{}"
                               .format(v[0], v[1]))
        unordered_results[idx] = v
        n_buffered -= 1

        while n_done in unordered_results.keys():
            yield unordered_results.pop(n_done)
            n_done += 1

    for _ in range(nprocs):  # inject sentinel values to stop threads
        q_in.put(None)

    for p in proc:
        p.join()
