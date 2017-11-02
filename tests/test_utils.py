from itertools import repeat
from time import sleep, time
import random
from array import array
from nose.tools import assert_raises, timed
from lproc import rmap, subset, add_cache, par_iter, chunk_load, AccessException
from lproc.utils import Subset


def test_subset():
    arr = list(range(100))

    # integer list based indexing
    idx = [1, 3, 4, 7]
    s = subset(arr, idx)
    expected = [arr[i] for i in idx]
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))

    # slice based indexing
    idx = slice(25, 87, 3)
    s = subset(arr, idx)
    expected = arr[idx.start:idx.stop:idx.step]
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))

    idx = slice(-34, None, None)
    s = subset(arr, idx)
    expected = arr[idx.start:idx.stop:idx.step]
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))

    idx = slice(None, -1, None)
    s = subset(arr, idx)
    expected = arr[idx.start:idx.stop:idx.step]
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))


def test_subset_nesting():
    arr = list(range(100))

    s = subset(arr, slice(10, 50))
    s = subset(s, [1, 2])
    expected = arr[10:50][1:3]

    assert not isinstance(s.sequence, Subset)
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))


def test_delegated_indexing():
    class TupleIndexable:
        def __init__(self, data):
            self.data = data

        def __getitem__(self, item):
            if isinstance(item, tuple):
                return self.data[item[0]:item[1]]
            else:
                return self.data[item]

    arr = TupleIndexable([10, 3, 5, 2, 8, 0, 4, 9, 6])
    s = subset(arr, TupleIndexable([0, 2, 3, 4]))
    s = s[(0, 3)]
    expected = [10, 5, 2, 8][0:3]
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))


def test_cached():
    def f(x):
        sleep(.02)
        return x

    x = [random.random() for _ in range(50)]
    y = rmap(f, x)
    z = add_cache(y)

    t1 = time()
    for i in range(len(x)):
        assert y[i] == x[i]
        assert y[i] == x[i]
    t2 = time()

    t3 = time()
    for i in range(len(x)):
        assert z[i] == x[i]
        assert z[i] == x[i]
    t4 = time()

    speedup = (t2 - t1) / (t4 - t3)
    assert speedup > 1.9


@timed(15)
def test_par_iter():
    def f1(x):
        sleep(.1)
        return array('d', repeat(x, 1000))

    def f2(x):
        return sum(x) / len(x)

    x = list(range(70))
    y = rmap(f1, x)
    y = rmap(f2, y)

    t1 = time()
    z1 = list(y)
    t2 = time()

    t3 = time()
    z2 = list(par_iter(y, nprocs=4))
    t4 = time()

    assert all(x == y for x, y in zip(z1, z2))
    speedup = (t2 - t1) / (t4 - t3)
    assert speedup > 3


@timed(5)
def test_par_iter_errors():
    class CustomError(Exception):
        pass

    def f(x):
        if x is None:
            raise CustomError()
        else:
            return x

    arr = [1, 2, 3, None]

    with assert_raises(AccessException):
        for x, y in zip(arr, par_iter(rmap(f, arr), nprocs=4)):
            assert x == y


@timed(5)
def test_buffer_loader():
    class SlowDataSource:
        def __init__(self, data):
            self.data = data

        def __getitem__(self, item):
            return self.data[item]

        def __iter__(self):
            for x in self.data:
                sleep(0.01)
                yield x

    arr = SlowDataSource(range(100))
    buffer = [0] * 10

    t1 = time()
    for i, x in enumerate(arr):
        buffer[i % 5] = x
        if (i + 1) % 5 == 0:
            for k in range(5):
                assert(buffer[k] == arr[i - 4 + k])
            sleep(0.05)
    t2 = time()

    t3 = time()
    for i, (b,) in enumerate(chunk_load([arr], [buffer], 5)):
        for k in range(5):
            assert(b[k] == arr[i * 5 + k])
        sleep(0.05)
    t4 = time()

    assert abs((t2 - t1) - 2) < 0.2
    assert abs((t4 - t3) - 1.05) < 0.2


@timed(5)
def test_buffer_loader_errors():
    arr = [0, 1, 2, 3, 4, 5, 6, None, 7, 8, 9]
    arr = rmap(int, arr)
    buffer = [0, 0, 0, 0]

    with assert_raises(AccessException):
        for i, (b,) in enumerate(chunk_load([arr], [buffer], chunk_size=2)):
            assert (b[0] == arr[i * 2]) and (b[1] == arr[i * 2 + 1])

    it = chunk_load([arr], [buffer], chunk_size=2)
    next(it)
    del it
