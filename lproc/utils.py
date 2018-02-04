from typing import Sequence, Union
import array
import bisect

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
