import os
import sys
import tempfile
import pickle as pkl
import importlib


def test_SerializableFunc():
    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, tmpdir)
        os.mkdir(os.path.join(tmpdir, 'test_package'))
        with open(os.path.join(tmpdir, 'test_package', '__init__.py'), "w") as f:
            f.write("\n")
        with open(os.path.join(tmpdir, 'test_package', 'some_module.py'), "w") as f:
            f.write("from lproc import SerializableFunc\n")
            f.write("@SerializableFunc\n")
            f.write("def a():\n    return 0\n")

        from test_package import some_module
        assert some_module.a() == 0

        b = pkl.loads(pkl.dumps(some_module.a))

        assert some_module.a() == b() == 0

        with open(os.path.join(tmpdir, 'test_package', 'some_module.py'), "w") as f:
            f.write("def a():\n    return 1\n")

        importlib.reload(some_module)

        assert some_module.a() == 1 and b() == 0

        c = pkl.loads(pkl.dumps(some_module.a))

        assert c() == 1

        d = pkl.loads(pkl.dumps(b))

        assert d() == 0

    sys.path.pop(0)
