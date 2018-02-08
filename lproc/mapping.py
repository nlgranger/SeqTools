import inspect
from typing import Sequence
from .utils import is_int_item
from .indexing import Slice


class MappingException(Exception):
    pass


class RMapping(Sequence):
    def __init__(self, f, sequences, debug_msg=None):
        assert callable(f), "f must be callable"
        assert len(sequences) > 0, "at least one input sample must be provided"
        self.sequences = sequences
        self.f = f
        self.debug_msg = debug_msg

    def __len__(self):
        return len(self.sequences[0])

    def __getitem__(self, item):
        if is_int_item(item):
            try:
                return self.f(*(l[item] for l in self.sequences))

            except Exception as e:
                if self.debug_msg is not None:
                    raise e from MappingException(self.debug_msg)
                else:
                    raise

        elif isinstance(item, slice):
            return Slice(self, item)

        else:
            raise TypeError("RMapping indices must be integer or slices, not "
                            "{}".format(item.__class__.__name__))


def rmap(f, *sequence):
    """Return lazy mapping of a sequence.

    Lazy version of :code:`[f(x) for x in sequence]`.

    If several sequences are passed, they will be zipped together and items
    from eachs will be passed as distinct arguments to f:
    :code:`[f(*x) for x in zip(*sequences)]`

    Only integer indexing is handled directly, other forms of indexing (slices,
    list of integers...) are delegated to wrapped sequence(s). If this is
    undesirable, you may want to use :func:`lproc.subset` instead.

    Example:

    .. testsetup::

        from lproc import rmap

    >>> a = [1, 2, 3, 4]
    >>> [x + 2 for x in a]
    [3, 4, 5, 6]
    >>> m = rmap(lambda x: x + 2, a)
    >>> [x for x in m]
    [3, 4, 5, 6]
    >>> def do(x, y):
    ...     print("computing now")
    ...     return x + y
    ...
    >>> a, b = [1, 2, 3, 4], [4, 3, 2, 1]
    >>> m = rmap(do, a, b)
    >>> [x for x in m]
    computing now
    computing now
    computing now
    computing now
    [5, 5, 5, 5]
    """
    stack = [
        (f, l, m, c[0].strip('\n') if c is not None else '?')
        for _, f, l, m, c, _ in inspect.stack()[1:11][::-1]]
    debug_msg = "in rmap created at:\n" + "\n".join(
        "  File \"{}\", line {}, in {}\n    {}".format(f, l, m, c)
        for f, l, m, c in stack)

    return RMapping(f, sequence, debug_msg)


def imap(f, *iterable):
    """Alias for python's :func:`map`."""
    return map(f, *iterable)


class RIMapping(Sequence):
    def __init__(self, f, *sequences):
        assert callable(f), "f must be callable"
        assert len(sequences) > 0, "at least one input sample must be provided"
        self.f = f
        self.arrays = sequences

    def __len__(self):
        return len(self.arrays[0])

    def __getitem__(self, i):
        kargs = tuple(sample[i] for sample in self.arrays)
        return map(self.f, *kargs)


def rimap(f, *sequence):
    """Return lazy mapping of iterable elements within a sequence.

    Lazy verion of :code:`[map(f, it) for it in sequence]`.

    If several arrays are passed, the iterables at a given index will be zipped
    together and the generated items passed as separate arguments to f:
    :code:`[map(f, zip(*it)) for it in zip(sequences)]`
    """
    return RIMapping(f, *sequence)


def rrmap(f, *sequence):
    """Return lazy mapping of sequencial elements within a sequence.

    Lazy version of :code:`[[f(*e) for e in zip(s)] for s in zip(sequence)]`.

    If several arrays are passed, the sequences at a given index will be zipped
    together and the corresponding items passed as separate arguments to f:
    :code:`[[f(*x) for x in zip(*s)] for s in sequences]`
    """
    stack = [
        (f, l, m, c[0].strip('\n') if c is not None else '?')
        for _, f, l, m, c, _ in inspect.stack()[1:11][::-1]]
    debug_msg = "in rrmap created at:\n" + "\n".join(
        "  File \"{}\", line {}, in {}\n    {}".format(f, l, m, c)
        for f, l, m, c in stack)

    return RMapping(lambda *l: RMapping(f, l, debug_msg), sequence)
