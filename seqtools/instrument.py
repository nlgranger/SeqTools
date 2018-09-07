"""Debugging tools."""

try:
    from time import monotonic, perf_counter
except ImportError:
    from monotonic import monotonic
    perf_counter = monotonic

from .utils import isint, basic_getitem


class Debug(object):
    def __init__(self, sequence, func, max_calls, max_rate):
        self.sequence = sequence
        self.max_calls = max_calls
        self.max_rate = max_rate
        self.n_calls = 0
        self.last_call = monotonic()
        self.func = func

    def __len__(self):
        return len(self.sequence)

    def silence(self):
        if self.max_calls is not None:
            if self.n_calls >= self.max_calls:
                return True

        if self.max_rate is not None:
            elpapsed = monotonic() - self.last_call
            if elpapsed < (1.0 / self.max_rate):
                return True

        return False

    @basic_getitem
    def __getitem__(self, key):
        value = self.sequence[key]

        if not self.silence():
            self.func(key, value)
            self.last_call = monotonic()
            self.n_calls += 1

        return value

    def __iter__(self):
        i = 0
        seq_iter = iter(self.sequence)

        while True:
            try:
                value = next(seq_iter)
            except StopIteration:
                return

            if not self.silence():
                self.func(i, value)
                self.last_call = monotonic()
                self.n_calls += 1

            yield value


def debug(sequence, func, max_calls=None, max_rate=None):
    """Wrap a sequence to trigger a function on each read.

    Args:
        sequence (Sequence):
            Source sequence.
        func (Callable):
            A function to call whenever an item is read, must take the
            index and value of the items.
        max_calls (Optional[int]):
            An optional count limit on how many times `func` is invoked
            (default None).
        max_rate (Optional[int]):
            An optional rate limit to avoid spamming `func`.

    Returns:
        (Sequence): The wrapped sequence.

    Example:

        .. testsetup::

           from seqtools.instrument import debug

        >>> sequence = [1, 2, 3, 4, 5]
        >>> watchthis = debug(sequence, lambda i, v: print(v), 2)
        >>> x = watchthis[0]
        1
        >>> y = watchthis[2]
        3
        >>> z = watchthis[3]
    """
    return Debug(sequence, func, max_calls, max_rate)


class ThroughputMonitor(object):
    def __init__(self, sequence):
        self.sequence = sequence
        self.n_calls = 0
        self.time_spent = 0

    def reset(self):
        """Reset perf counter."""
        self.n_calls = 0
        self.time_spent = 0

    def throughput(self):
        """Returns average measured throughput."""
        if self.n_calls == 0:
            raise RuntimeError(
                "cannot measure throughput before any element was accessed")

        return self.n_calls / self.time_spent

    def read_delay(self):
        """Return average measured time spent accessing items."""
        if self.n_calls == 0:
            raise RuntimeError(
                "cannot measure read delay before any element was accessed")

        return self.time_spent / self.n_calls

    def __len__(self):
        return len(self.sequence)

    def __getitem__(self, key):
        if not isint(key):
            raise TypeError(
                self.__class__.__name__
                + " indices must be integers, not "
                + key.__class__.__name__)

        if key < -len(self) or key >= len(self):
            raise IndexError(
                self.__class__.__name__ + " index out of range")

        if key < 0:
            key = len(self) + key

        t_start = perf_counter()
        value = self.sequence[key]
        t_stop = perf_counter()
        self.time_spent += t_stop - t_start
        self.n_calls += 1
        return value

    def __iter__(self):
        seq_iter = iter(self.sequence)

        t_start = perf_counter()
        for value in seq_iter:
            t_stop = perf_counter()
            self.time_spent += t_stop - t_start
            self.n_calls += 1

            yield value

            t_start = perf_counter()


def monitor_throughput(sequence):
    """Wrap a sequence in an object with three additional methods:

    * :code:`read_delay()` the average time it takes to read an item.
    * :code:`throughput()` the invert of the above.
    * :code:`reset()` resets the accumulated statistics.

    """
    return ThroughputMonitor(sequence)
