from typing import Sequence, Iterable
from itertools import count
from array import array

from .common import isint, basic_getitem, basic_setitem


class Reindexing(Sequence):
    def __init__(self, sequence, indexes):
        if isinstance(sequence, Reindexing):  # optimize nested subsets
            indexes = array('L', (sequence.indexes[i] for i in indexes))
            sequence = sequence.sequence

        self.sequence = sequence
        self.indexes = indexes

    def __len__(self):
        return len(self.indexes)

    def __getitem__(self, key):
        if isinstance(key, slice):
            return Reindexing(self.sequence, self.indexes[key])

        elif isint(key):
            if key < -len(self) or key >= len(self):
                raise IndexError(
                    self.__class__.__name__ + " index out of range")

            if key < 0:
                key = len(self) + key

            return self.sequence[self.indexes[key]]

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            indexes = self.indexes[key]

            if len(indexes) != len(value):
                raise ValueError(self.__class__.__name__ + " only support "
                                 "one-to-one assignment")

            for i, v in zip(indexes, value):
                self.sequence[i] = v

        elif isint(key):
            if key < -len(self) or key >= len(self):
                raise IndexError(
                    self.__class__.__name__ + " index out of range")

            if key < 0:
                key = len(self) + key

            self.sequence[self.indexes[key]] = value

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)


def reindex(sequence, indexes):
    """Return a view on the sequence reordered by indexes."""
    return Reindexing(sequence, indexes)


class Cycle(Sequence):
    def __init__(self, sequence, size):
        self.sequence = sequence
        self.size = int(size)

    def __len__(self):
        return self.size

    @basic_getitem
    def __getitem__(self, key):
            return self.sequence[key % len(self.sequence)]

    @basic_setitem
    def __setitem__(self, key, value):
        self.sequence[key % len(self.sequence)] = value

    def __iter__(self):
        for i in range(self.size):
            yield self.sequence[i % len(self.sequence)]


class InfiniteCycle(Iterable):
    def __init__(self, sequence):
        self.sequence = sequence

    def __getitem__(self, key):
        if isinstance(key, slice):
            start, stop, step = key.start, key.stop, key.step

            if start is None:
                start = 0

            if start < 0 or stop is None or stop < 0:
                raise IndexError(
                    "Cannot use indices relative to length on "
                    + self.__class__.__name__)

            offset = start - start % len(self.sequence)
            start -= offset
            stop -= offset
            return Cycle(self.sequence, stop)[start:stop:step]

        elif isint(key):
            if key < 0:
                raise IndexError(
                    "Cannot use indices relative to length on "
                    + self.__class__.__name__)

            return self.sequence[key % len(self.sequence)]

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)

    def __iter__(self):
        for i in count():
            yield self.sequence[i % len(self.sequence)]


def cycle(sequence, limit=None):
    """Return a view of the repeated sequence with an optional size limit."""
    if limit is None:
        return InfiniteCycle(sequence)
    else:
        return Cycle(sequence, limit)
