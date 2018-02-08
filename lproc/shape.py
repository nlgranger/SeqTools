from typing import Sequence
import array
import bisect
from .indexing import Slice
from .utils import is_int_item


class Collation(Sequence):
    def __init__(self, sequences):
        self.sequences = sequences

        if not all([len(s) == len(self.sequences[0])
                    for s in self.sequences]):
            raise ValueError("all sequences should have the same length")

    def __len__(self):
        return len(self.sequences[0])

    def __getitem__(self, item):
        if isinstance(item, slice):
            return Slice(self, item)
        else:
            return tuple([s[item] for s in self.sequences])

    def __iter__(self):
        return zip(*self.sequences)


def collate(sequences):
    """Return a view on the collated/pasted/stacked sequences.

    The n'th element is a tuple of the n'th elements from each sequence.

    Example:

    >>> arr = collate([[1, 2, 3, 4], ['a', 'b', 'c', 'd'], [5, 6, 7, 8]])
    >>> arr[2]
    (3, 'c', 7)
    """
    return Collation(sequences)


class Concatenation(Sequence):
    def __init__(self, sequences):
        self.sequences = []
        for s in sequences:
            if isinstance(s, Concatenation):
                for ss in s.sequences:
                    self.sequences.append(ss)
            else:
                self.sequences.append(s)

        self.offsets = array.array('L', [0] + [len(s) for s in self.sequences])
        for i in range(1, len(self.sequences) + 1):
            self.offsets[i] += self.offsets[i - 1]

    def __len__(self):
        return self.offsets[-1]

    def __getitem__(self, item):
        if isinstance(item, slice):
            return Slice(self, item)
        elif not is_int_item(item):
            raise IndexError("unsupported index type")
        elif not 0 <= item < len(self):
            raise IndexError("index out of range")

        s = bisect.bisect(self.offsets, item) - 1
        return self.sequences[s][item - self.offsets[s]]


def concatenate(sequences):
    """Return a view on the concatenated sequences."""
    return Concatenation(sequences)
