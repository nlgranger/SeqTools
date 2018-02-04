import inspect
import os
import tempfile

import sys
from importlib import import_module, reload
import functools


class SerializableFunc:
    """Make a function independent from modifications of the source code.

    This decorator alters the serialization hook so that unpickling the
    function will import a backed-up version of the module containing the
    function.

    .. warning::
        This is a hackish solution where only the source file containing the
        function is saved, regenerated and reloaded. Use with care.
    """
    def __init__(self, func):
        if isinstance(func, SerializableFunc):
            self.name = func.name
            self.source = func.source
            self.func = func.func
        else:
            self.name = func.__name__
            with open(inspect.getsourcefile(func)) as f:
                self.source = f.read()
            self.func = func
            functools.update_wrapper(self, func)

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def __getstate__(self):
        return self.source, self.name

    def __setstate__(self, state):
        self.source, self.name = state

        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "module.py"), 'w') as f:
                f.write(self.source)

            sys.path.insert(0, d)
            m = import_module("module")
            reload(m)
            self.func = getattr(m, self.name)
            sys.path.pop(0)
