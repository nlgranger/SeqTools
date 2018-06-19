from typing import Sequence, Iterable
import itertools
import bisect
from array import array
import logging
from .utils import isint, basic_getitem, basic_setitem


class Reindexing(Sequence):
    def __init__(self, sequence, indexes):
        if isinstance(sequence, Reindexing):  # optimize nested subsets
            indexes = array('l', (sequence.indexes[i] for i in indexes))
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


def gather(sequence, indexes):
    """Returns a view on the sequence reordered by indexes.

    .. image:: gather.png
       :alt: gather
       :width: 15%
       :align: center
    """
    return Reindexing(sequence, indexes)


def take(sequence, indexes):
    """Alias for :func:`seqtools.gather`."""
    return Reindexing(sequence, indexes)


def reindex(sequence, indexes):
    logging.warning(
        "Call to deprecated function reindex, use gather instead",
        category=DeprecationWarning,
        stacklevel=2)
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
        for i in itertools.count():
            yield self.sequence[i % len(self.sequence)]


def cycle(sequence, limit=None):
    """Returns a view of the repeated sequence with an optional size limit.

    .. image:: cycle.png
       :alt: collate
       :width: 10%
       :align: center
    """
    if limit is None:
        return InfiniteCycle(sequence)
    else:
        return Cycle(sequence, limit)


class Interleaving(Sequence):
    def __init__(self, sequences):
        offsets_in = [0]  # end of sequences in input indexing
        offsets_out = [0]  # end of sequences in output indexing
        whose_offset = sorted(range(len(sequences)),
                              key=lambda k: len(sequences[k]))

        for i, n_seq_left in zip(whose_offset, range(len(sequences), 0, -1)):
            n_new_out_items = (len(sequences[i]) - offsets_in[-1]) * n_seq_left
            offsets_out.append(offsets_out[-1] + n_new_out_items)
            offsets_in.append(len(sequences[i]))

        self.sequences = sequences
        self.n_seqs = len(sequences)
        self.offsets_in = array('i', offsets_in)
        self.offsets_out = array('i', offsets_out)
        self.remaining_seqs = [sorted(whose_offset[i:])
                               for i in range(len(sequences))]

    def __len__(self):
        return sum(map(len, self.sequences))

    def _convert_1d_key(self, key):
        # given index in interleaved sequences, return sequence and offset
        n_exhausted = bisect.bisect(self.offsets_out, key) - 1
        n_remaining_seqs = self.n_seqs - n_exhausted
        key -= self.offsets_out[n_exhausted]
        seq = self.remaining_seqs[n_exhausted][key % n_remaining_seqs]
        idx = self.offsets_in[n_exhausted] + key // n_remaining_seqs
        return seq, idx

    @basic_getitem
    def __getitem__(self, key):
        seq, idx = self._convert_1d_key(key)
        return self.sequences[seq][idx]

    @basic_setitem
    def __setitem__(self, key, value):
        seq, idx = self._convert_1d_key(key)
        self.sequences[seq][idx] = value

    def __iter__(self):
        iterators = [iter(s) for s in self.sequences]
        i = -1
        while len(iterators) > 0:
            i = (i + 1) % len(iterators)
            try:
                yield next(iterators[i])
            except StopIteration:
                del iterators[i]
                i -= 1


def interleave(*sequences):
    """Interleaves elements from several sequences into one.

    .. note::
       sequences don't need to have the same length, the cycling will operate
       between whatever sequences are left.

    >>> arr1 = [1, 2, 3, 4, 5]
    >>> arr2 = ['a', 'b', 'c']
    >>> arr3 = [.1, .2, .3, .4]
    >>> list(interleave(arr1, arr2, arr3))
    [1, 'a', 0.1, 2, 'b', 0.2, 3, 'c', 0.3, 4, 0.4, 5]

    .. image:: interleaving.png
       :alt: interleaving
       :width: 30%
       :align: center
    """
    return Interleaving(sequences)


class Repetition(Sequence):
    def __init__(self, item, times):
        self.object = item
        self.times = times

    def __len__(self):
        return self.times

    @basic_getitem
    def __getitem__(self, item):
        return self.object

    @basic_setitem
    def __setitem__(self, key, value):
        self.object = value

    def __iter__(self):
        return itertools.repeat(self.object, self.times)


class InfiniteRepetition(Iterable):
    def __init__(self, value):
        self.value = value

    def __getitem__(self, key):
        if isinstance(key, slice):
            start, stop, step = key.start, key.stop, key.step
            start = 0 if start is None else start
            step = 1 if step is None else step

            if start < 0 or stop is None or stop < 0:
                raise IndexError(
                    "Cannot use indices relative to length on "
                    + self.__class__.__name__)

            if step == 0:
                raise ValueError("slice step cannot be 0")

            if (stop - start) * step <= 0:
                return []

            if step > 0:
                stop += (step + stop - start) % step
            else:
                stop -= (-step + start - stop) % -step

            return repeat(self.value, (stop - start) // step)

        elif isint(key):
            if key < 0:
                raise IndexError(
                    "Cannot use indices relative to length on "
                    + self.__class__.__name__)

            return self.value

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            start, stop, step = key.start, key.stop, key.step

            step = 1 if step is None else step

            if start < 0 or stop is None or stop < 0:
                raise IndexError(
                    "Cannot use indices relative to length on "
                    + self.__class__.__name__)

            if step == 0:
                raise ValueError("slice step cannot be 0")

            if (stop - start) * step > 0:
                self.value = value[-1]

        elif isint(key):
            if key < 0:
                raise IndexError(
                    "Cannot use indices relative to length on "
                    + self.__class__.__name__)

            self.value = value

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)

    def __iter__(self):
        return itertools.repeat(self.value)


def repeat(value, times=None):
    """Returns a sequence repeating the given value with an optional size
    limit.

    .. image:: repeat.png
       :alt: repeat
       :width: 10%
       :align: center
    """
    if isint(times) and times > 1:
        return Repetition(value, times)
    elif times is None:
        return InfiniteRepetition(value)
    else:
        raise TypeError("times must be a positive integer or None")
