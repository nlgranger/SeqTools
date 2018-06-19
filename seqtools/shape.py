from typing import Sequence
import array
import bisect
from logging import warning
import itertools
try:
    from itertools import izip as zip  # pylint: disable=redefined-builtin
except ImportError:
    pass
from .utils import isint, clip, basic_getitem, basic_setitem


class Collation(Sequence):
    def __init__(self, sequences):
        self.sequences = sequences

        if not all([len(s) == len(self.sequences[0])
                    for s in self.sequences]):
            raise ValueError("all sequences should have the same length")

    def __len__(self):
        return len(self.sequences[0])

    @basic_getitem
    def __getitem__(self, item):
        return tuple([s[item] for s in self.sequences])

    @basic_setitem
    def __setitem__(self, key, value):
        for s, v in zip(self.sequences, value):
            s[key] = v

    def __iter__(self):
        return zip(*self.sequences)


def collate(sequences):
    """Returns a view on the collated/pasted/stacked sequences.

    The n'th element is a tuple of the n'th elements from each sequence.

    Example:

    >>> arr = collate([[1, 2, 3, 4], ['a', 'b', 'c', 'd'], [5, 6, 7, 8]])
    >>> arr[2]
    (3, 'c', 7)

    .. image:: collate.png
       :alt: collate
       :width: 50%
       :align: center
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

    @basic_getitem
    def __getitem__(self, key):
        s = bisect.bisect(self.offsets, key) - 1
        return self.sequences[s][key - self.offsets[s]]

    @basic_setitem
    def __setitem__(self, key, value):
        s = bisect.bisect(self.offsets, key) - 1
        self.sequences[s][key - self.offsets[s]] = value

    def __iter__(self):
        return itertools.chain(*self.sequences)


def concatenate(sequences):
    """Returns a view on the concatenated sequences.

    .. image:: concatenate.png
       :alt: concatenate
       :width: 25%
       :align: center
    """
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

    @basic_getitem
    def __getitem__(self, key):
        result = self.sequence[key * self.k:(key + 1) * self.k]

        if key == len(self.sequence) // self.k and self.pad is not None:
            pad_size = (self.k - len(self.sequence) % self.k)
            result = concatenate((result, [self.pad] * pad_size))

        if self.collate_fn is not None:
            result = self.collate_fn(result)

        return result

    @basic_setitem
    def __setitem__(self, key, value):
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


def batch(sequence, k, drop_last=False, pad=None, collate_fn=None):
    """Returns a view of a sequence in groups of k items.

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
        an optional function that takes a sequence of items and
        returns a consolidated batch.

    .. image:: batch.png
       :alt: batch
       :width: 25%
       :align: center
    """
    return BatchView(sequence, k, drop_last, pad, collate_fn)


class Unbatching:
    def __init__(self, sequence, batch_size, last_batch_size=None):
        self.sequence = sequence
        self.batch_size = batch_size
        self.last_batch_size = last_batch_size or batch_size

    def __len__(self):
        return max(0, len(self.sequence) - 1) * self.batch_size \
            + self.last_batch_size

    @basic_getitem
    def __getitem__(self, key):
        b, i = key // self.batch_size, key % self.batch_size
        return self.sequence[b][i]

    def __iter__(self):
        for b in self.sequence:
            for v in b:
                yield v


def unbatch(sequence, batch_size, last_batch_size=None):
    """Recomposes a sequence of batched items.

    :param sequence:
        A sequence of batches
    :param batch_size:
        The size of the batches, except for the last one which can be smaller.
    :param last_batch_size:
        The size for the last batch if it is smaller than `batch_size`
    """
    return Unbatching(sequence, batch_size, last_batch_size)


class Split(Sequence):
    def __init__(self, sequence, edges):
        n = len(sequence)

        if isint(edges):
            if n / (edges + 1) % 1 != 0:
                raise ValueError("edges must divide the size of the sequence")
            step = n // (edges + 1)
            self.starts = array.array('L', range(0, n, step))
            self.stops = array.array('L', range(step, n + 1, step))

        elif isint(edges[0]):
            self.starts = array.array('L')
            self.stops = array.array('L')
            for e in edges:
                start = self.stops[-1] if len(self.stops) > 0 else 0
                stop = e

                self.starts.append(clip(start, 0, n - 1))
                self.stops.append(clip(stop, 0, n))

            self.starts.append(self.stops[-1])
            self.stops.append(n)

        else:
            self.starts = array.array('L')
            self.stops = array.array('L')
            for start, stop in edges:
                self.starts.append(clip(start, 0, n - 1))
                self.stops.append(clip(stop, 0, n))

        self.sequence = sequence

    def __len__(self):
        return len(self.starts)

    @basic_getitem
    def __getitem__(self, key):
        return self.sequence[self.starts[key]:self.stops[key]]

    @basic_setitem
    def __setitem__(self, key, value):
        start, stop = self.starts[key], self.stops[key]
        if len(value) != stop - start:
            raise ValueError(
                self.__class__.__name__ +
                " only supports one-to-one assignment")

        self.sequence[start:stop] = value


def split(sequence, edges):
    """Splits a sequence into a succession of subsequences.

    :param sequence:
        Input sequence.
    :param edges:
        `edges` specifies how to split the sequence:

        - a 1D array that contains the indexes where the sequence should be
          cut, the beginning and the end of the sequence are implicit.
        - an int specifies how many cuts of equal size should be done, in which
          case `edges + 1` must divide the length of the sequence.
        - an sequence of int tuples specifies the limits of subsequences.
    """
    return Split(sequence, edges)
