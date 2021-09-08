from array import array
import bisect
from collections import deque
import itertools
from numbers import Integral
from typing import Sequence

from .utils import basic_getitem, basic_setitem, isint, normalize_slice


class Arange:
    def __init__(self, start, stop=None, step=None):
        if stop is None and step is None:
            stop = start
            start = 0

        if step is None:
            step = 1

        if (stop - start) / step < 0:
            stop = start

        size = abs(stop - start) - 1
        abs_step = abs(step)
        numel = (size + abs_step - (size % abs_step)) // abs_step
        stop = start + step * numel

        self.start, self.stop, self.step = start, stop, step

    def __len__(self):
        return abs(self.stop - self.start) // abs(self.step)

    def __iter__(self):
        return iter(range(self.start, self.stop, self.step))

    def __getitem__(self, key):
        if isinstance(key, slice):
            start, stop, step = normalize_slice(
                key.start, key.stop, key.step, len(self))
            numel = abs(stop - start) // abs(step)

            start = self.start + self.step * start
            step = self.step * step
            stop = start + step * numel

            return Arange(start, stop, step)

        elif not isinstance(key, Integral):
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)

        return self.start + self.step * key


def arange(start, stop=None, step=None):
    """Sequential equivalent of Python built-in :class:`python:range`."""
    return Arange(start, stop, step)


class Gathering:
    def __init__(self, sequence, indexes: Sequence[int]):
        if isinstance(sequence, Gathering):  # optimize nested subsets
            self.indexes = [sequence.indexes[i] for i in indexes]
            self.sequence = sequence.sequence
        else:
            self.indexes = indexes
            self.sequence = sequence

    def __len__(self):
        return len(self.indexes)

    def __iter__(self):
        for i in self.indexes:
            yield self.sequence[i]

    def __getitem__(self, key):
        if isinstance(key, slice):
            return gather(self.sequence, self.indexes[key])

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

            for i, val in zip(indexes, value):
                self.sequence[i] = val

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
    """Return a view on the sequence reordered by indexes.

    .. image:: _static/gather.png
       :alt: gather
       :width: 15%
       :align: center

    Example:

        >>> arr = ['d', 'e', 'h', 'l', 'o', 'r', 'w', ' ']
        >>> idx = [2, 1, 3, 3, 4, 7, 6, 4, 5, 3, 0]
        >>> list(seqtools.gather(arr, idx))
        ['h', 'e', 'l', 'l', 'o', ' ', 'w', 'o', 'r', 'l', 'd']
    """
    return Gathering(sequence, indexes)


def take(sequence, indexes):
    """Alias for :func:`seqtools.gather`."""
    return gather(sequence, indexes)


class Cycle:
    def __init__(self, sequence, size):
        self.sequence = sequence
        self.size = int(size)

    def __len__(self):
        return self.size

    def __iter__(self):
        i = 0
        while True:
            for v in self.sequence:
                yield v
                i += 1
                if i == self.size:
                    return

    @basic_getitem
    def __getitem__(self, key):
        return self.sequence[key % len(self.sequence)]

    @basic_setitem
    def __setitem__(self, key, value):
        self.sequence[key % len(self.sequence)] = value


class InfiniteCycle:
    def __init__(self, sequence):
        self.sequence = sequence

    def __iter__(self):
        while True:
            for v in self.sequence:
                yield v

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


def cycle(sequence, limit=None):
    """Return repeated view of a sequence.

    Args:
        sequence (Sequence): The sequence to be repeated.
        limit (Optional[int]): An optional size limit.

    .. image:: _static/cycle.png
       :alt: collate
       :width: 10%
       :align: center

    Example:

        >>> data = ['a', 'b', 'c']
        >>> loop = seqtools.cycle(data)
        >>> loop[3]
        'a'
        >>> loop[3 * 10 ** 9 + 1]  # unbounded sequence
        'b'
        >>> loop = seqtools.cycle(data, 7)
        >>> list(loop)
        ['a', 'b', 'c', 'a', 'b', 'c', 'a']
    """
    return InfiniteCycle(sequence) if limit is None else Cycle(sequence, limit)


class Interleaving(object):
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

    def __iter__(self):
        iterators = [iter(seq) for seq in self.sequences]
        i = -1
        while len(iterators) > 0:
            i = (i + 1) % len(iterators)
            try:
                yield next(iterators[i])
            except StopIteration:
                del iterators[i]
                i -= 1

    @basic_getitem
    def __getitem__(self, key):
        seq, idx = self._convert_1d_key(key)
        return self.sequences[seq][idx]

    @basic_setitem
    def __setitem__(self, key, value):
        seq, idx = self._convert_1d_key(key)
        self.sequences[seq][idx] = value


class IterInterleaving:
    def __init__(self, sequences) -> None:
        self.sequences = sequences

    def __iter__(self):
        iterators = [iter(seq) for seq in self.sequences]
        i = -1
        while len(iterators) > 0:
            i = (i + 1) % len(iterators)
            try:
                yield next(iterators[i])
            except StopIteration:
                del iterators[i]
                i -= 1


def interleave(*sequences):
    """Interleave elements from several sequences into one.

    Sequences don't need to have the same length, the cycling will
    operate between whatever sequences are left.

    .. image:: _static/interleaving.png
       :alt: interleaving
       :width: 30%
       :align: center

    Example:

        >>> arr1 = [ 1,   2,   3,   4,   5]
        >>> arr2 = ['a', 'b', 'c']
        >>> arr3 = [.1,  .2,  .3,  .4]
        >>> list(interleave(arr1, arr2, arr3))
        [1, 'a', 0.1, 2, 'b', 0.2, 3, 'c', 0.3, 4, 0.4, 5]
    """
    try:
        for s in sequences:
            len(s)
    except TypeError:
        return IterInterleaving(sequences)
    else:
        return Interleaving(sequences)


class Repetition(object):
    def __init__(self, item, times):
        self.object = item
        self.times = times

    def __len__(self):
        return self.times

    def __iter__(self):
        return itertools.repeat(self.object, self.times)

    @basic_getitem
    def __getitem__(self, item):
        return self.object

    @basic_setitem
    def __setitem__(self, key, value):
        self.object = value


class InfiniteRepetition(object):
    def __init__(self, value):
        self.value = value

    def __iter__(self):
        return itertools.repeat(self.value)

    def __len__(self):
        return 0

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


def repeat(value, times=None):
    """Make a sequence by repeating a value.

    Args:
        value (Any): Value to be (virtually) replicated.
        times (Optional[int]): Optional size limit.

    .. image:: _static/repeat.png
       :alt: repeat
       :width: 10%
       :align: center

    Example:

        >>> item = 3
        >>> repetition = seqtools.repeat(item, 10)
        >>> list(repetition)
        [3, 3, 3, 3, 3, 3, 3, 3, 3, 3]
    """
    if isint(times) and times > 1:
        return Repetition(value, times)
    elif times is None:
        return InfiniteRepetition(value)
    else:
        raise TypeError("times must be a positive integer or None")


def switch(condition, x, y):
    """Combine the values of two sequences based on condition.

    Args:
        condition (Sequence[bool]): a sequence of booleans
        x (Sequence): values when condition is true
        y (Sequence): values when condition is false
    """
    return Case(condition, y, x)


class Case(object):
    def __init__(self, selector, *values):
        try:
            if any(len(v) != len(selector) for v in values):
                raise ValueError("all inputs must have the same size")
        except TypeError:  # object has no len()
            pass

        self.selector = selector
        self.values = values

    def __len__(self):
        return len(self.selector)

    @basic_getitem
    def __getitem__(self, item):
        return self.values[self.selector[item]][item]

    @basic_setitem
    def __setitem__(self, key, value):
        self.values[self.selector[key]][key] = value


def case(selector, *values):
    """Switch between different sequences based on selector value.

    Args:
        selector (Sequence[int]): indexes of the selected sequence
        values (Sequence): data sequences
    """
    return Case(selector, *values)


class UnIter:
    def __init__(self, iterable, cache_size=0, size=None):
        self.iterable = iterable
        self.size = size
        self.iterator = iter(iterable)
        self.next_i = 0
        self.cache = deque(maxlen=cache_size)

    @property
    def i(self):
        return self.next_i - len(self.cache)

    def __len__(self):
        if self.size is not None:
            return self.size
        else:
            raise TypeError('Unknown iterator len')

    def __getitem__(self, item):
        if item < 0 and self.size is not None:
            item += self.size
        if item < 0 and self.size is None:
            raise IndexError(
                f"cannot use negative indexing on {self.__class__.__name__} "
                "with unknown size.")
        if item < 0 or (self.size is not None and item >= self.size):
            raise IndexError(self.__class__.__name__ + " index out of range")

        if self.i <= item < self.next_i:
            return self.cache[item - self.next_i]

        if item < self.i:
            self.iterator = iter(self.iterable)
            self.next_i = 0
            self.cache.clear()

        for _ in range(item - self.next_i):
            self.cache.append(next(self.iterator))

        value = next(self.iterator)
        self.cache.append(value)
        self.next_i = item + 1

        return value


class ParallelUniter:
    def __init__(self, iterable, n_parallel=2, cache_size=0, size=None):
        self.uniterators = [UnIter(iterable, cache_size) for _ in range(n_parallel)]
        self.size = size

    def __len__(self):
        if self.size is not None:
            return self.size
        else:
            raise TypeError('Unknown iterator len')

    def __getitem__(self, item):
        if item < 0 and self.size is not None:
            item += self.size
        if item < 0 and self.size is None:
            raise IndexError(
                f"cannot use negative indexing on {self.__class__.__name__} "
                "with unknown size.")
        if item < 0 or (self.size is not None and item >= self.size):
            raise IndexError(self.__class__.__name__ + " index out of range")

        closest = 0
        for i, ui in enumerate(self.uniterators):
            if ui.i <= item:
                closest = i

        if self.uniterators[closest].i > item:  # an iterator must be restarted
            self.uniterators.insert(0, self.uniterators.pop(-1))
            closest = 0

        value = self.uniterators[closest][item]

        return value


def uniter(iterable, cache_size=0, n_parallel=1, size=None):
    """Simulate an indexable sequence from an iterable.

    Args:
        iterable: an iterable
        cache_size (int): number of cached values
        n_parallel (int): number of simultaneously active iterators
        size (int, optional):
            optional value to set `len`, otherwise `len` will raise
            `NotImplementedError`.

    .. image:: _static/uniter.png
       :alt: uniter
       :width: 15%
       :align: center

    This works by starting, incrementing and restarting one or several iterators
    to reach requested items. To avoid wasting steps, a cache is implemented
    and multiple iterators can run in parallel so that one is always closer than
    the others to requested items.

    Example:

        >>> class LineIter:
        ...     def __init__(self, filename):
        ...         self.filename = filename
        ...
        ...     def __iter__(self):
        ...         with open(self.filename) as f:
        ...             for line in f:
        ...                 yield line
        ...
        >>> readme = seqtools.uniter(LineIter("LICENSE.txt"),
        ...                          cache_size=10, n_parallel=5)
        >>> readme[3]
        '1. Definitions\\n'
        >>> readme[1]
        '==================================\\n'
    """
    if n_parallel > 1:
        return ParallelUniter(iterable, n_parallel, cache_size, size)
    else:
        return UnIter(iterable, cache_size, size)
