import os
import sys
import inspect
import tempfile
import shutil
import functools

if sys.version_info >= (3, 4):
    from importlib import import_module, reload
else:
    from importlib import import_module


class SerializableFunc:
    """Make a function independent from its source file.

    This decorator alters the serialization hook so that unpickling the
    pickled function will import a back-up of the original source code.

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

        d = tempfile.mkdtemp()
        try:
            with open(os.path.join(d, "module.py"), 'w') as f:
                f.write(self.source)

            sys.path.insert(0, d)
            m = import_module("module")
            m = reload(m)
            self.func = getattr(m, self.name)
            sys.path.pop(0)

        finally:
            shutil.rmtree(d)
