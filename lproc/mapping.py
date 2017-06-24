import inspect
from typing import Sequence, Iterable, Callable, Union


__all__ = ['rmap', 'rimap', 'rrmap']


class MappingException(Exception):
    pass


class RMapping(Sequence):
    def __init__(self, f: Callable, *sequence: Sequence):
        assert callable(f), "f must be callable"
        assert len(sequence) > 0, "at least one input sample must be provided"
        self.arrays = sequence
        self.f = f
        self.creation_stack = [(f, l, m, c[0].strip('\n') if c is not None else '?')
                               for _, f, l, m, c, _ in inspect.stack()[1:11][::-1]]

    def __len__(self):
        return len(self.arrays[0])

    def __getitem__(self, item: Union[int, Sequence[int], slice]):
        haslen = False
        try:
            len(item)
            haslen = True
        except TypeError:
            pass

        isint = False
        try:
            int(item)
            isint = True
        except TypeError:
            pass

        if haslen or not isint:  # delegate indexing to subtype
            return RMapping(self.f, *list(l[item] for l in self.arrays))

        else:
            try:
                return self.f(*(l[item] for l in self.arrays))

            except Exception as e:  # gracefully report exceptions from execution
                info_e = MappingException(
                    "An exception occured when using the node created at: \n"
                    + "\n".join(
                        "  File \"{}\", line {}, in {}\n    {}".format(f, l, m, c)
                        for f, l, m, c in self.creation_stack))

                raise e from info_e

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]


def rmap(f: Callable, *sequence: Sequence) -> Sequence:
    """Return lazy mapping of a sequence. 

    Lazy version of `[f(x) for x in sequence]`.

    If several sequences are passed, they will be zipped together and items from eachs 
    will be passed as distinct arguments to f: `[f(*x) for x in zip(*sequences)]`
    
    Example: 

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
    return RMapping(f, *sequence)


class RIMapping(Sequence):
    def __init__(self, f: Callable, *sequences: Sequence[Iterable]):
        assert callable(f), "f must be callable"
        assert len(sequences) > 0, "at least one input sample must be provided"
        self.f = f
        self.arrays = sequences

    def __len__(self):
        return len(self.arrays[0])

    def __getitem__(self, i):
        kargs = tuple(sample[i] for sample in self.arrays)
        return map(self.f, *kargs)


def rimap(f: Callable, *sequence: Sequence[Iterable]) -> Sequence[Iterable]:
    """Return lazy mapping of iterable elements within a sequence.

    Lazy verion of `[map(f, it) for it in sequence]`.

    If several arrays are passed, the iterables at a given index will be zipped together 
    and the generated items passed as separate arguments to f: 
    `[map(f, zip(*it)) for it in zip(sequences)]`
    """
    return RIMapping(f, *sequence)


def rrmap(f: Callable, *sequence: Sequence) -> Sequence:
    """Return lazy mapping of sequencial elements within a sequence.

    Lazy version of `[[f(*e) for e in zip(s)] for s in zip(sequence)]`.s

    If several arrays are passed, the sequences at a given index will be zipped together 
    and the corresponding items passed as separate arguments to f:
    `[[f(*x) for x in zip(*s)] for s in sequences]`
    """
    return RMapping(lambda *l: RMapping(f, *l), *sequence)
