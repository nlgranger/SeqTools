import random
import array
from typing import Sequence


class shuffle(Sequence):
    """Shuffle the elements of an array (lazily)."""
    # TODO: add support for fixed seed
    def __init__(self, sequence: Sequence):
        self.samples = sequence
        self.order = random.shuffle(list(range(len(sequence))))

    def __len__(self):
        return len(self.order)

    def __getitem__(self, i):
        return self.samples[self.order[i]]


class subset(Sequence):
    """Wrap an array to show only a subset of its elements."""
    def __init__(self, sample: Sequence, indexes: Sequence[int]):
        if not isinstance(sample, subset):
            self.sample = sample
            self.indexes = indexes
        else:
            self.sample = sample.sample
            self.indexes = sample.indexes[indexes]

    def __len__(self):
        return len(self.indexes)

    def __getitem__(self, item):
        try:
            len(item)
        except TypeError:  # has not length
            try:
                item = int(item)  # and casts to integer
                return self.sample[self.indexes[item]]
            except TypeError:
                pass

        if isinstance(item, slice):
            start = 0 if item.start is None else item.start
            stop = len(self) if item.stop is None else item.stop
            step = 1 if item.step is None else item.step
            item = array.array('L', range(start, stop, step))

        return subset(self, item)


class rzip(Sequence):
    def __init__(self, *samples):
        self.len = min(len(s) for s in samples)
        self.samples = samples

    def __len__(self):
        return self.len

    def __getitem__(self, item):
        if isinstance(item, slice):
            return rzip(s[item] for s in self.samples)
        else:
            return tuple(s[item] for s in self.samples)


class repeat(Sequence):
    def __init__(self, value, n):
        self.value = value
        self.len = n

    def __len__(self):
        return self.len

    def __getitem__(self, item):
        del item
        return self.value
