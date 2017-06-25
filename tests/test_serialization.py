import os
import sys
import tempfile
import pickle as pkl
import importlib
import types

from lproc import SerializableFunc


def test_SerializableFunc():
    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, tmpdir)
        pkgdir = os.path.join(tmpdir, 'test_package')
        os.mkdir(pkgdir)
        with open(os.path.join(pkgdir, '__init__.py'), "w") as f:
            f.write("\n")
        with open(os.path.join(pkgdir, 'some_module.py'), "w") as f:
            f.write("from lproc import SerializableFunc\n")
            f.write("@SerializableFunc\n")
            f.write("def a():\n    return 0\n")

        from test_package import some_module
        assert some_module.a() == 0

        b = pkl.loads(pkl.dumps(some_module.a))

        assert b() == 0, "serialized function malfunctionning"

        with open(os.path.join(pkgdir, 'some_module.py'), "w") as f:
            f.write("def a():\n    return 1\n")

        importlib.reload(some_module)

        assert some_module.a() == 1, "reload failed"
        assert b() == 0, "serialized function not standalone"

        d = pkl.loads(pkl.dumps(b))

        assert d() == 0, "doubly serialized function not standalone"

        sys.path.pop(0)
        loaded_package_modules = dict([
            (key, value) for key, value in sys.modules.items()
            if key.startswith("test_package")
               and isinstance(value, types.ModuleType)])

        for key in loaded_package_modules:
            del sys.modules[key]


def test_nestprotection():
    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, tmpdir)
        pkgdir = os.path.join(tmpdir, 'test_package')
        os.mkdir(pkgdir)
        with open(os.path.join(pkgdir, '__init__.py'), "w") as f:
            f.write("\n")
        with open(os.path.join(pkgdir, 'some_module.py'), "w") as f:
            f.write("from lproc import SerializableFunc\n")
            f.write("@SerializableFunc\n")
            f.write("def a():\n    return 0\n")

        from test_package import some_module
        assert some_module.a() == 0

        # Accidentally wrap again the function
        b = SerializableFunc(some_module.a)
        c = pkl.loads(pkl.dumps(b))

        assert some_module.a() == b() == c() == 0

        with open(os.path.join(pkgdir, 'some_module.py'), "w") as f:
            f.write("def a():\n    return 1\n")

        importlib.reload(some_module)

        assert some_module.a() == 1, "reloading test module failed"
        assert c() == 0, "serialized function not standalone"

        sys.path.pop(0)
