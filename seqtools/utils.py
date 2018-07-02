import ctypes
import struct
import numbers
from typing import Sequence
import queue
import multiprocessing
from multiprocessing.sharedctypes import RawArray, RawValue


def isint(x):
    return isinstance(x, numbers.Integral)


def clip(x, a, b):
    return max(a, min(x, b))


def basic_getitem(func):
    """Decorator that adds slicing support for a __getitem__.

    Args:
        func (Callable[[MutableSequence, int], Any]):
            A `__getitem__` method that only accepts positive integer
            indices.

    Returns:
        A `__getitem__` method that accepts negative indexing and
        slicing.
    """
    def getitem(self, key):
        if isinstance(key, slice):
            return SeqSlice(self, key)

        elif isint(key):
            if key < -len(self) or key >= len(self):
                raise IndexError(
                    self.__class__.__name__ + " index out of range")

            if key < 0:
                key = len(self) + key

            return func(self, key)

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)

    return getitem


def basic_setitem(func):
    """Decorator that adds slicing support for a __setitem__.

    Args:
        func (Callable[[MutableSequence, int, Any]]):
            A `__setitem__` method that only accepts positive integer
            indices.

    Returns:
        A `__setitem__` method that accepts negative indexing and
        slicing.
    """
    def setitem(self, key, value):
        if isinstance(key, slice):
            slice_view = SeqSlice(self, key)

            if len(slice_view) != len(value):
                raise ValueError(
                    self.__class__.__name__ +
                    " only supports one-to-one assignment")

            for i, val in enumerate(value):
                slice_view[i] = val

        elif isint(key):
            if key < -len(self) or key >= len(self):
                raise IndexError(
                    self.__class__.__name__ + " index out of range")

            if key < 0:
                key = len(self) + key

            func(self, key, value)

        else:
            raise TypeError(
                self.__class__.__name__ + " indices must be integers or "
                "slices, not " + key.__class__.__name__)

    return setitem


def normalize_slice(start, stop, step, size):
    """Normalize slice parameters so that start and stop are positive
    integers and the base index can be easily computed by
    :code:`start + i * step`.

    Args:
        start (Optional[int]): start index
        stop (Optional[int]): stop index
        step (Optional[int]): step size
        size (int): size of the sliced sequence

    Returns:
        (int, int, int): a triplet of integers start, stop, step with
    """
    if step is None:
        step = 1
    elif step == 0:
        raise ValueError("slice step cannot be 0")

    if start is None:
        start = 0 if step > 0 else size - 1
    elif start >= 0:
        start = min(start, size - 1)
    else:
        start = max(0, size + start)

    if stop is None:
        stop = size if step > 0 else -1
    elif stop >= 0:
        stop = min(stop, size)
    else:
        stop = max(-1, size + stop)

    if (stop - start) / step < 0:
        stop = start

    size = abs(stop - start) - 1
    abs_step = abs(step)
    numel = (size + abs_step - (size % abs_step)) // abs_step
    stop = start + numel * step

    return start, stop, step


class SeqSlice(Sequence):
    def __init__(self, sequence, key):
        if isinstance(sequence, SeqSlice):
            key_start, key_stop, key_step = normalize_slice(
                key.start, key.stop, key.step, len(sequence))
            numel = abs(key_stop - key_start) // abs(key_step)
            start = sequence.start + key_start * sequence.step
            step = key_step * sequence.step
            stop = start + step * numel
            sequence = sequence.sequence

        else:
            start, stop, step = normalize_slice(
                key.start, key.stop, key.step, len(sequence))

        self.sequence = sequence
        self.start = start
        self.stop = stop
        self.step = step

    def __len__(self):
        return abs(self.stop - self.start) // abs(self.step)

    @basic_getitem
    def __getitem__(self, key):
        return self.sequence[self.start + key * self.step]

    @basic_setitem
    def __setitem__(self, key, value):
        self.sequence[self.start + key * self.step] = value


class SharedCtypeQueue:
    """Simplified multiprocessing queue for `struct` entities."""
    def __init__(self, fmt, maxsize):
        self.fmt = fmt
        self.itemsize = struct.calcsize(fmt)
        self.maxsize = maxsize
        self.values = memoryview(RawArray("b", maxsize * self.itemsize))
        self.start = RawValue(ctypes.c_longlong, 0)
        self.startlock = multiprocessing.Lock()
        self.getsem = multiprocessing.Semaphore(0)
        self.stop = RawValue(ctypes.c_longlong, 0)
        self.stoplock = multiprocessing.Lock()
        self.putsem = multiprocessing.Semaphore(maxsize)

    def get(self, blocking=True, timeout=None):
        # wait for something to read
        if not self.getsem.acquire(blocking, timeout):
            raise queue.Empty()

        with self.startlock:  # no timeout but should go unnoticed
            offset = (self.start.value % self.maxsize) * self.itemsize
            self.start.value += 1

            # copy value
            buf = self.values[offset:offset + self.itemsize]

            try:
                value = struct.unpack(self.fmt, buf)
            except Exception:
                raise
            finally:
                # release buffer slot for writing
                self.putsem.release()

        return value

    def get_nowait(self):
        return self.get(blocking=False)

    def put(self, value, blocking=True, timeout=None):
        # wait for an empty slot
        if not self.putsem.acquire(blocking, timeout):
            raise queue.Full()

        # take specific slot
        with self.stoplock:  # no timeout but should go unnoticed
            offset = (self.stop.value % self.maxsize) * self.itemsize

            try:  # transfer values and update state
                struct.pack_into(self.fmt, self.values, offset, *value)
            except Exception:
                raise
            else:
                self.stop.value += 1
                self.getsem.release()

    def put_nowait(self, value):
        self.put(value, blocking=False)

    def empty(self):
        return self.stop.value == self.start.value
