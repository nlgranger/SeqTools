import numbers
from typing import Sequence


def isint(x):
    return isinstance(x, numbers.Integral)


def normalize_slice(item, n):
    start, stop, step = item.start, item.stop, item.step
    start = 0 if start is None else start
    stop = n if stop is None else stop
    step = 1 if step is None else step

    if step == 0:
        raise ValueError("Slice step cannot be 0")

    start = max(-n, min(start, n - 1))
    if start < 0:
        start += n
    stop = max(-n - 1, min(stop, n))
    if stop < 0:
        stop += n

    if (stop - start) * step <= 0:
        return slice(0, 0, 1)

    if step > 0:
        stop += (step + stop - start) % step
    else:
        stop -= (-step + start - stop) % -step

    return slice(start, stop, step)


class SliceView(Sequence):
    def __init__(self, sequence, key):
        if isinstance(sequence, SliceView):
            oldkey = slice(sequence.start, sequence.stop, sequence.step)
            key = normalize_slice(key, len(sequence))
            start = oldkey.start + key.start * oldkey.step
            stop = oldkey.start + key.stop * oldkey.step
            step = key.step * oldkey.step
            sequence = sequence.sequence
            key = slice(start, stop, step)

        self.sequence = sequence
        key = normalize_slice(key, len(sequence))
        self.start = key.start
        self.stop = key.stop
        self.step = key.step

    def __len__(self):
        return abs(self.stop - self.start) // abs(self.step)

    def __getitem__(self, key):
        if isinstance(key, slice):
            return SliceView(self, key)

        elif isint(key):
            if key < -len(self) or key >= len(self):
                raise IndexError(
                    self.__class__.__name__ + " index out of range")

            if key < 0:
                key = len(self) + key

            return self.sequence[self.start + key * self.step]

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            slice_view = SliceView(self, key)

            if len(slice_view) != len(value):
                raise ValueError("SliceView only support one-to-one "
                                 "assignment")

            for i, v in enumerate(value):
                slice_view[i] = v

        elif isint(key):
            if key < -len(self) or key >= len(self):
                raise IndexError(
                    self.__class__.__name__ + " index out of range")

            if key < 0:
                key = len(self) + key

            self.sequence[self.start + key * self.step] = value

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)
