import os
import pickle as pkl
import shutil
import sys
import tempfile
import time
import types
from importlib import reload

from seqtools import SerializableFunc


def test_SerializableFunc():
    tmpdir = tempfile.mkdtemp()
    try:
        sys.path.insert(0, tmpdir)
        pkgdir = os.path.join(tmpdir, 'test_package')
        os.mkdir(pkgdir)
        with open(os.path.join(pkgdir, '__init__.py'), "w") as f:
            f.write("\n")
        with open(os.path.join(pkgdir, 'some_module.py'), "w") as f:
            f.write("from seqtools import SerializableFunc\n")
            f.write("@SerializableFunc\n")
            f.write("def a():\n    return 0\n")

        from test_package import some_module
        assert some_module.a() == 0

        b = pkl.loads(pkl.dumps(some_module.a))

        assert b() == 0, "serialized function malfunctionning"

        time.sleep(1)  # otherwise new timestamp will not invalidate cache
        with open(os.path.join(pkgdir, 'some_module.py'), "w") as f:
            f.write("def a():\n    return 1\n")

        some_module = reload(some_module)

        assert some_module.a() == 1, "reload failed"
        assert b() == 0, "serialized function not standalone"

        d = pkl.loads(pkl.dumps(b))

        assert d() == 0, "doubly serialized function not standalone"

        sys.path.pop(0)
        loaded_package_modules = dict([
            (key, value) for key, value in sys.modules.items()
            if (key.startswith("test_package")
                and isinstance(value, types.ModuleType))])

        for key in loaded_package_modules:
            del sys.modules[key]

    finally:
        shutil.rmtree(tmpdir)


def test_nestprotection():
    tmpdir = tempfile.mkdtemp()
    try:
        sys.path.insert(0, tmpdir)
        pkgdir = os.path.join(tmpdir, 'test_package')
        os.mkdir(pkgdir)
        with open(os.path.join(pkgdir, '__init__.py'), "w") as f:
            f.write("\n")
        with open(os.path.join(pkgdir, 'some_module.py'), "w") as f:
            f.write("from seqtools import SerializableFunc\n")
            f.write("@SerializableFunc\n")
            f.write("def a():\n    return 0\n")

        from test_package import some_module
        assert some_module.a() == 0

        # Accidentally wrap again the function
        b = SerializableFunc(some_module.a)
        c = pkl.loads(pkl.dumps(b))

        assert some_module.a() == 0 and b() == 0 and c() == 0

        time.sleep(1)  # otherwise new timestamp will not invalidate cache
        with open(os.path.join(pkgdir, 'some_module.py'), "w") as f:
            f.write("def a():\n    return 1\n")

        some_module = reload(some_module)

        assert some_module.a() == 1, "reloading test module failed"
        assert c() == 0, "serialized function not standalone"

        sys.path.pop(0)

    finally:
        shutil.rmtree(tmpdir)
