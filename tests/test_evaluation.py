import pytest
import random
from time import sleep, time

from seqtools import add_cache, smap, prefetch, EagerAccessException


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
@pytest.mark.parametrize("method", ["thread", "proc"])
def test_prefetch(method):
    def f1(x):
        sleep(random.random() / 500)
        return x

    arr = list(range(300))
    y = smap(f1, arr)
    y = prefetch(y, nworkers=3, max_buffered=20, method=method, idle_timout=.1)

    i = 0
    for _ in range(1000):
        assert y[i] == arr[i]
        if random.random() < 0.05:
            i = random.randrange(0, len(y))
        if random.random() < 0.01:
            sleep(.2)


@pytest.mark.timeout(15)
@pytest.mark.parametrize("method", ["thread", "proc"])
def test_prefetch_timing(method):
    def f1(x):
        sleep(.05)
        return x

    arr = list(range(121))
    y = smap(f1, arr)
    y = prefetch(y, nworkers=3, max_buffered=20, method=method)

    t1 = time()
    z = list(y)
    t2 = time()

    assert z == arr
    print(t2 - t1)
    assert t2 - t1 < 2.05 * 1.3  # hopefully better in practice...

    t1 = time()
    z = [y[i] for i in range(len(y))]
    t2 = time()

    assert z == arr
    print(t2 - t1)
    assert t2 - t1 < 2.05 * 1.3


@pytest.mark.timeout(10)
@pytest.mark.parametrize("method", ["thread", "proc"])
def test_prefetch_errors(method):
    class CustomError(Exception):
        pass

    def f1(x):
        if x is None:
            raise CustomError()
        else:
            return x

    arr1 = [1, 2, 3, None]
    arr2 = smap(f1, arr1)
    y = prefetch(arr2, nworkers=2, max_buffered=2, method=method)

    for i in range(3):
        assert y[i] == arr1[i]
    with pytest.raises(EagerAccessException):
        print(y[3])

    def f2(x):
        if x is None:
            raise ValueError("blablabla")
        else:
            return x

    arr2 = smap(f2, arr1)
    y = prefetch(arr2, nworkers=2, max_buffered=2, method=method)

    for i in range(3):
        assert y[i] == arr1[i]
    try:
        print(y[3])
    except Exception as e:
        assert isinstance(e, EagerAccessException)
        assert isinstance(e.__cause__, ValueError)
    else:
        assert False
