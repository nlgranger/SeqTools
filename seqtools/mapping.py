from .errors import EvaluationError, format_stack, seterr
from .utils import basic_getitem


class Mapping(object):
    def __init__(self, f, *sequences):
        if not callable(f):
            raise TypeError("f must be callable")
        if len(sequences) <= 0:
            raise ValueError("at least one input sample must be provided")

        self.sequences = sequences
        self.f = f
        self.stack = format_stack(2)

    def __len__(self):
        return len(self.sequences[0])

    def __iter__(self):
        i = 0
        try:
            for args in zip(*self.sequences):
                yield self.f(*args)
                i += 1

        except Exception as error:
            if seterr() == 'passthrough' or isinstance(error, EvaluationError):
                raise
            else:
                msg = "Failed to evaluate item {} in {} created at:\n{}".format(
                    i, self.__class__.__name__, self.stack)
                raise EvaluationError(msg) from error

    @basic_getitem
    def __getitem__(self, item):
        try:
            return self.f(*(l[item] for l in self.sequences))

        except Exception as cause:
            if seterr() == 'passthrough' or isinstance(cause, EvaluationError):
                raise
            else:
                msg = "Failed to evaluate item {} in {} created at:\n{}".format(
                    item, self.__class__.__name__, self.stack)
                raise EvaluationError(msg) from cause


def smap(f, *sequences):
    """Return a mapping of `f` over the sequence(s).

    Equivalent to :code:`[f(x) for x in sequence]` with on-demand evaluation.

    If several sequences are passed, they will be zipped together and their
    items will be passed as distinct arguments to f:
    :code:`[f(*x) for x in zip(*sequences)]`

    .. image:: _static/smap.png
       :alt: smap
       :width: 20%
       :align: center

    Example:

        >>> a = [1, 2, 3, 4]
        >>> print([v + 2 for v in a])
        [3, 4, 5, 6]
        >>> m = seqtools.smap(lambda x: x + 2, a)
        >>> print([v for v in m])
        [3, 4, 5, 6]
        >>> def do(y, z):
        ...     print("computing now")
        ...     return y + z
        ...
        >>> a, b = [1, 2, 3, 4], [4, 3, 2, 1]
        >>> m = seqtools.smap(do, a, b)
        >>> print([v for v in m])
        computing now
        computing now
        computing now
        computing now
        [5, 5, 5, 5]
    """
    return Mapping(f, *sequences)


def starmap(f, sequence):
    """Map a function over a sequence of argument tuples.

    A sequential equivalent of :func:`python:itertools.starmap`.
    """
    return smap(lambda x: f(*x), sequence)
