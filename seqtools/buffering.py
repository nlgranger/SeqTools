from collections import OrderedDict
import threading

from .utils import basic_getitem, basic_setitem


class CachedSequence:
    def __init__(self, sequence, cache_size=1, cache=None):
        self.sequence = sequence
        self.cache = OrderedDict() if cache is None else cache
        self.cache_size = cache_size
        self.lock = threading.Lock()

    def __len__(self):
        return len(self.sequence)

    def __iter__(self):
        # bypass cache as it will be useless
        return iter(self.sequence)

    @basic_getitem
    def __getitem__(self, key):
        with self.lock:
            if key in self.cache.keys():
                return self.cache[key]
            else:
                value = self.sequence[key]
                if len(self.cache) >= self.cache_size:
                    self.cache.popitem(False)
                self.cache[key] = value
                return value

    @basic_setitem
    def __setitem__(self, key, value):
        with self.lock:
            self.sequence[key] = value
            if key in self.cache.keys():
                self.cache[key] = value


def add_cache(arr, cache_size=1, cache=None):
    """
    Add a caching mechanism over a sequence.

    A *reference* of the most recently accessed items will be kept and
    reused when possible.

    Args:
        arr (Sequence): Sequence to provide a cache for.
        cache_size (int): Maximum number of cached values (default 1).
        cache (Optional[Dict[int, Any]]): Dictionary-like container to use as
            cache. Defaults to a standard :class:`python:dict`.

    Return:
        (Sequence): The sequence wrapped with a cache.

    Notes:
        The default cache is thread safe but won't help when multiple processes
        try to use it.

    Example:

        >>> def process(x):
        ...     print("working")
        ...     return x * 2
        >>>
        >>> data = [0, 1, 2, 3, 4, 5, 6]
        >>> result = seqtools.smap(process, data)
        >>> cached = seqtools.add_cache(result)
        >>> result[3]
        working
        6
        >>> result[3]  # smap uses systematic on-demand computations
        working
        6
        >>> cached[3]
        working
        6
        >>> cached[3]  # skips computation
        6
    """
    return CachedSequence(arr, cache_size, cache)
