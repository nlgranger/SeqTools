import inspect
from .indexable import Indexable


class MappingException(Exception):
    pass


class rmap(Indexable):
    """Apply lazy mapping on an indexable.
    
    Similar to `[f(x) for x in sample]`
    
    If several arrays are passed, they will be zipped together and passed as multiple 
    arguments to f.
    """
    def __init__(self, f, *arrays):
        assert callable(f), "f must be callable"
        assert len(arrays) > 0, "at least one input sample must be provided"
        self.arrays = arrays
        self.f = f
        self.creation_stack = [(f, l, m, c[0].strip('\n') if c is not None else '?')
                               for _, f, l, m, c, _ in inspect.stack()[1:11][::-1]]

    def __len__(self):
        return len(self.arrays[0])

    def __getitem__(self, item):
        haslen = False
        try:
            len(item)
            haslen = True
        except TypeError:  # has not length
            pass

        isint = False
        try:
            int(item)
            isint = True
        except TypeError:
            pass

        if haslen or not isint:  # delegate indexing to subtype
            return rmap(self.f, *list(l[item] for l in self.arrays))

        else:
            try:
                return self.f(*(l[item] for l in self.arrays))
            except Exception as e:
                info_e = MappingException(
                    "An exception occured when using the node created at: \n"
                    + "\n".join(
                        "  File \"{}\", line {}, in {}\n    {}".format(f, l, m, c)
                        for f, l, m, c in self.creation_stack))

                raise e from info_e

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]


class rimap(Indexable):
    """Apply lazy mapping on iterable elements from a list.

    Similar to `[map(f, it) for it in sample]`

    If several arrays are passed, the iterables at a given index will zipped together 
    and the generated items passed as separate arguments to f.
    """
    def __init__(self, f, *arrays):
        assert callable(f), "f must be callable"
        assert len(arrays) > 0, "at least one input sample must be provided"
        self.f = f
        self.arrays = arrays

    def __len__(self):
        return len(self.arrays[0])

    def __getitem__(self, i):
        kargs = tuple(sample[i] for sample in self.arrays)
        return map(self.f, *kargs)


def rrmap(f, *samples):
    """Apply lazy mapping on indexable elements from a list.

    Equivalent to `[[f(e) for e in s] for s in sample]`.

    If several arrays are passed, the indexables at a given index will zipped together 
    and the corresponding items passed as separate arguments to f.
    """
    return rmap(lambda *l: rmap(f, *l), *samples)
