import pytest
import random
from time import sleep, time

from seqtools import add_cache, smap, eager_iter, EagerAccessException


def test_cached():
    def f(x):
        sleep(.01)
        return x

    cache_size = 3
    arr = [random.random() for _ in range(25)]
    y = smap(f, arr)
    z = add_cache(y, cache_size)

    t1 = time()
    for i in range(len(arr)):
        assert z[i] == arr[i]
        for j in range(max(0, i - cache_size + 1), i + 1):
            assert z[j] == arr[j]
    t2 = time()

    assert t2 - t1 < .28
    arr = list(range(100))
    z = add_cache(arr, cache_size)
    z[-10] = -10
    assert z[-10] == -10
    assert arr[-10] == -10

    z[:10] = list(range(0, -10, -1))
    assert list(z[:10]) == list(range(0, -10, -1))
    assert list(arr[:10]) == list(range(0, -10, -1))


@pytest.mark.timeout(15)
@pytest.mark.parametrize("method", ["proc"])
def test_eager_iter(method):
    def f1(x):
        sleep(.05)
        return x

    arr = list(range(121))
    y = smap(f1, arr)

    t1 = time()
    z = list(eager_iter(y, nworkers=3, max_buffered=20, method=method))
    t2 = time()

    assert z == arr
    print(t2 - t1)
    assert t2 - t1 < 2.05 * 1.3  # hopefully more in practice...


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
    else:
        assert False
