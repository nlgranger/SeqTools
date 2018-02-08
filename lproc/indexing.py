from typing import Sequence, Iterable
from itertools import count

from .utils import is_int_item


class Slice(Sequence):
    @staticmethod
    def normalize_slice(item, n):
        start, stop, step = item.start, item.stop, item.step
        start = 0 if start is None else start
        stop = n if stop is None else stop
        step = 1 if step is None else step

        if start < -n or start >= n or stop < -n - 1 or stop > n:
            raise IndexError("Slice limits out of range")
        if step == 0:
            raise ValueError("Slice step cannot be 0")

        start = n + start if start < 0 else start
        stop = n + stop if stop < 0 else stop

        if (stop - start) * step <= 0:
            return slice(0, 0, 1)

        if step > 0:
            stop += (step + stop - start) % step
        else:
            stop -= (-step + start - stop) % -step

        return slice(start, stop, step)

    def __init__(self, sequence, slice):
        self.sequence = sequence
        slice = Slice.normalize_slice(slice, len(sequence))
        self.start = slice.start
        self.stop = slice.stop
        self.step = slice.step

    def __len__(self):
        return abs(self.stop - self.start) // abs(self.step)

    def __getitem__(self, item):
        if isinstance(item, slice):
            item = Slice.normalize_slice(item, len(self))
            start = self.start + item.start * self.step
            stop = self.start + item.stop * self.step
            if start > len(self.sequence) or stop > len(self.sequence):
                raise IndexError("Slice slice index out of range")
            step = item.step * self.step
            new_slice = Slice.normalize_slice(slice(start, stop, step),
                                              len(self.sequence))
            return Slice(self.sequence, new_slice)

        elif is_int_item(item):
            if item < -len(self) or item >= len(self):
                raise IndexError("index out of range")

            if item < 0:
                item = len(self) + item

            item = self.start + item * self.step

            return self.sequence[item]

        else:
            raise TypeError("Slice indices must be intergers or slices, not"
                            "{}".format(item.__clas__.__name__))


class Reindexing(Sequence):
    def __init__(self, sequence, indexes):
        if isinstance(sequence, Reindexing):  # optimize nested subsets
            try:  # let the index type handle sub-indexing if possible
                indexes = sequence.indexes[indexes]
            except Exception:
                indexes = [sequence.indexes[i] for i in indexes]

            sequence = sequence.sequence

        self.sequence = sequence
        self.indexes = indexes

    def __len__(self):
        return len(self.indexes)

    def __getitem__(self, item):
        if is_int_item(item):
            return self.sequence[self.indexes[item]]
        else:
            return Reindexing(self, item)


def reindex(sequence, indexes):
    """Return a view on the sequence reordered by indexes."""
    return Reindexing(sequence, indexes)


class Cycle(Sequence):
    def __init__(self, sequence, size):
        self.sequence = sequence
        self.size = int(size)

    def __len__(self):
        return self.size

    def __getitem__(self, item):
        if isinstance(item, slice):
            return Slice(self, item)

        elif not is_int_item(item):
            raise TypeError("Cycle indices must be integers or slices, not "
                            "{}".format(item.__class__.__name__))

        elif item < -self.size or item >= self.size:
            raise IndexError("Cycle index out of range")

        else:
            return self.sequence[item % len(self.sequence)]

    def __iter__(self):
        for i in range(self.size):
            yield self.sequence[i % len(self.sequence)]


class InfiniteCycle(Iterable):
    def __init__(self, sequence):
        self.sequence = sequence

    def __getitem__(self, item):
        if isinstance(item, slice):
            start, stop, step = item.start, item.stop, item.step

            if start is None:
                start = 0

            if start < 0 or stop is None or stop < 0:
                raise ValueError("InfiniteCycle has no end")

            offset = start - start % len(self.sequence)
            start -= offset
            stop -= offset
            return Cycle(self.sequence, stop)[start:stop:step]

        elif not is_int_item(item):
            raise TypeError("InfiniteCycle indices must be integers or "
                            "slices, not {}".format(item.__class__.__name__))

        elif item < 0:
            raise IndexError("InfiniteCycle does not support negative indexing")

        else:
            return self.sequence[item % len(self.sequence)]

    def __iter__(self):
        for i in count():
            yield self.sequence[i % len(self.sequence)]


def cycle(sequence, limit=None):
    """Return a view of the repeated sequence with an optional size limit."""
    if limit is None:
        return InfiniteCycle(sequence)
    else:
        return Cycle(sequence, limit)
