import pytest
import random
from time import sleep, time

from seqtools import add_cache, smap, eager_iter, EagerAccessException


def test_cached():
    def f(x):
        sleep(.01)
        return x

    cache_size = 3
    arr = [random.random() for _ in range(50)]
    y = smap(f, arr)
    z = add_cache(y, cache_size)

    assert list(iter(y)) == arr
    assert [z[i] for i in range(len(z))] == arr

    t1 = time()
    for i in range(len(arr)):
        for j in range(max(0, i - cache_size + 1), i + 1):
            assert y[j] == arr[j]
            assert y[j] == arr[j]
    t2 = time()

    t3 = time()
    for i in range(len(arr)):
        for j in range(max(0, i - cache_size + 1), i + 1):
            assert z[j] == arr[j]
            assert z[j - len(arr)] == arr[j]
    t4 = time()

    speedup = (t2 - t1) / (t4 - t3)
    assert speedup > 1.9

    arr = list(range(100))
    z = add_cache(arr, cache_size)
    z[-10] = -10
    assert z[-10] == -10
    assert arr[-10] == -10

    z[:10] = list(range(0, -10, -1))
    assert list(z[:10]) == list(range(0, -10, -1))
    assert list(arr[:10]) == list(range(0, -10, -1))


@pytest.mark.timeout(15)
@pytest.mark.parametrize("method", ["thread"])
def test_eager_iter(method):
    def f1(x):
        sleep(.01)
        return x

    arr = list(range(1000))
    y = smap(f1, arr)

    t1 = time()
    list(iter(y))
    t2 = time()

    t3 = time()
    z = list(eager_iter(y, nworkers=4, max_buffered=20, method=method))
    t4 = time()

    assert all(x_ == z_ for x_, z_ in zip(arr, z))
    speedup = (t2 - t1) / (t4 - t3)
    assert speedup > 2.5  # be conservative for travis busy machines...


@pytest.mark.timeout(10)
@pytest.mark.parametrize("method", ["thread", "proc"])
def test_eager_iter_errors(method):
    class CustomError(Exception):
        pass

    def f1(x):
        if x is None:
            raise CustomError()
        else:
            return x

    arr1 = [1, 2, 3, None]
    arr2 = smap(f1, arr1)

    with pytest.raises(EagerAccessException):
        for i, y in enumerate(eager_iter(
                arr2, nworkers=2, max_buffered=2, method=method)):
            assert arr1[i] == y

    def f2(x):
        if x is None:
            raise ValueError("blablabla")
        else:
            return x

    arr3 = smap(f2, arr1)

    try:
        for i, y in enumerate(eager_iter(
                arr3, nworkers=2, max_buffered=2, method=method)):
            assert arr1[i] == y
    except Exception as e:
        assert isinstance(e, EagerAccessException)
        assert isinstance(e.__cause__, ValueError)
