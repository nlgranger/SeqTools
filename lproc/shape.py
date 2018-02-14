from typing import Sequence
import array
import bisect
from logging import warning
from lproc.common import SliceView
from .common import isint


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
            return SliceView(self, item)
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

    def __getitem__(self, key):
        if isinstance(key, slice):
            return SliceView(self, key)

        elif isint(key):
            if key < -len(self) or key >= len(self):
                raise IndexError(
                    self.__class__.__name__ + " index out of range")

            if key < 0:
                key = len(self) + key

            s = bisect.bisect(self.offsets, key) - 1
            return self.sequences[s][key - self.offsets[s]]

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            slice_view = SliceView(self, key)

            if len(slice_view) != len(value):
                raise ValueError(self.__class__.__name__ + " only support "
                                 "one-to-one assignment")

            for i, v in enumerate(value):
                slice_view[i] = v

        elif isint(key):
            if key < -len(self) or key >= len(self):
                raise IndexError(
                    self.__class__.__name__ + " index out of range")

            if key < 0:
                key = len(self) + key

            s = bisect.bisect(self.offsets, key) - 1
            self.sequences[s][key - self.offsets[s]] = value

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)


def concatenate(sequences):
    """Return a view on the concatenated sequences."""
    return Concatenation(sequences)


class BatchView(Sequence):
    def __init__(self, sequence, k, drop_last=False, pad=None, collate_fn=None):
        self.sequence = sequence
        self.k = k
        self.drop_last = drop_last
        self.pad = pad
        self.collate_fn = collate_fn

        if drop_last and pad is not None:
            warning("pad value is ignored because drop_last is true")

    def __len__(self):
        if len(self.sequence) % self.k > 0 and not self.drop_last:
            return len(self.sequence) // self.k + 1
        else:
            return len(self.sequence) // self.k

    def __getitem__(self, key):
        if isinstance(key, slice):
            return SliceView(self, key)

        elif isint(key):
            if key < -len(self) or key >= len(self):
                raise IndexError(
                    self.__class__.__name__ + " index out of range")

            if key < 0:
                key = len(self) + key

            result = self.sequence[key * self.k:(key + 1) * self.k]
            if key == len(self.sequence) // self.k:  # incomplete block
                if self.pad is not None:
                    result = concatenate([
                        result,
                        [self.pad] * (self.k - len(self.sequence) % self.k)])

            if self.collate_fn is not None:
                result = self.collate_fn(result)

            return result

        else:
            raise TypeError("BlockView indices must be slices or integers, "
                            "not {}".format(key.__class__.__name__))

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            slice_view = SliceView(self, key)

            if len(slice_view) != len(value):
                raise ValueError(self.__class__.__name__ + " only support "
                                 "one-to-one assignment")

            for i, v in enumerate(value):
                slice_view[i] = v

        elif isint(key):
            if key < -len(self) or key >= len(self):
                raise IndexError(
                    self.__class__.__name__ + " index out of range")

            if key < 0:
                key = len(self) + key

            start = key * self.k
            if key == len(self.sequence) // self.k:
                stop = start + len(self.sequence) % self.k
                expected_value_size = len(self.sequence) % self.k \
                    if self.pad is not None else self.k

            else:
                stop = (key + 1) * self.k
                expected_value_size = self.k

            if len(value) != expected_value_size:
                raise ValueError(self.__class__.__name__ + " only support "
                                 "one-to-one assignment")

            for i, v in zip(range(start, stop), value):
                self.sequence[i] = v

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)


def batches(sequence, k, drop_last=False, pad=None, collate_fn=None):
    """Return a view of a sequence in groups of k items.

    :param sequence:
        the input sequence
    :param k:
        number of items by block
    :param drop_last:
        wether the last block should be ignored if it contains less than k
        items.
    :param pad:
        padding item value to use in order to increase the size of the last
        block to k elements, set to `None` to prevent padding and return
        an incomplete block anyways.
    :param collate_fn:
        an optional function to apply to the list of block elements before
        returning them.
    """
    return BatchView(sequence, k, drop_last, pad, collate_fn)
