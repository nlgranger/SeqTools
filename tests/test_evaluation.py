import pytest
import random
import logging
from time import sleep, time

from seqtools import add_cache, smap, prefetch, PrefetchException


logging.basicConfig(level=logging.INFO)
seed = int(random.random() * 100000)
logging.info("seed: {}".format(seed))
random.seed(seed)


def test_cached():
    def f(x):
        sleep(.01)
        return x

    cache_size = 3
    arr = [random.random() for _ in range(25)]
    z = add_cache(arr, cache_size)

    assert list(z) == arr
    assert list(z[10:]) == arr[10:]
    assert [z[i] for i in range(10)] == arr[:10]

    z[:10] = list(range(0, -10, -1))
    assert list(z[10:]) == arr[10:]
    assert list(z[:10]) == list(range(0, -10, -1))

    y = smap(f, arr)
    z = add_cache(y, cache_size)

    t1 = time()
    for i in range(len(arr)):
        assert z[i] == arr[i]
        for j in range(max(0, i - cache_size + 1), i + 1):
            assert z[j] == arr[j]
    t2 = time()

    assert t2 - t1 < .28


@pytest.mark.timeout(15)
@pytest.mark.parametrize("method", ["thread", "process"])
def test_prefetch(method):
    def f1(x):
        sleep(0.005 * (1 + random.random()))
        return x

    if method == "process":
        start_hook = None
    else:
        start_hook = None

    arr = list(range(300))
    y = smap(f1, arr)
    y = prefetch(y, nworkers=4, max_cached=10, method=method, timeout=1,
                 start_hook=start_hook)
    # arr = arr[3:-1:2]
    # y = y[3:-1:2]

    i = 0
    n_wakeups = 3
    for _ in range(500):
        if n_wakeups > 0 and random.random() < 0.005:
            sleep(1.1)  # will let worker go to sleep
            n_wakeups -= 1
        assert y[i] == arr[i]
        if random.random() < 0.05:
            i = random.randrange(0, len(arr))
        else:
            i = (i + 1) % len(arr)

    # helps with coverage
    y._finalize(y)


@pytest.mark.timeout(15)
@pytest.mark.timing
@pytest.mark.parametrize("method", ["thread", "process"])
def test_prefetch_timing(method):
    def f1(x):
        sleep(.02 + 0.01 * (random.random() - .5))
        return x

    arr = list(range(100))
    y = smap(f1, arr)
    y = prefetch(y, nworkers=2, max_cached=20, method=method, timeout=1)

    t1 = time()
    z = list(y)
    t2 = time()

    assert z == arr
    duration = t2 - t1
    print("test_prefetch_timing({}):1 {}".format(method, duration))
    assert duration < 1.3

    arr = list(range(200))
    y = smap(f1, arr)
    y = prefetch(y, nworkers=2, max_cached=20, method=method,
                 timeout=1, anticipate=lambda i: i + 2)

    t1 = time()
    z = [y[i] for i in range(0, len(y), 2)]
    t2 = time()

    assert z == arr[::2]
    duration = t2 - t1
    print("test_prefetch_timing({}):2 {}".format(method, duration))
    assert duration < 1.3


@pytest.mark.timeout(10)
@pytest.mark.parametrize("method", ["thread", "process"])
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
    y = prefetch(arr2, nworkers=2, max_cached=2, method=method)

    for i in range(3):
        assert y[i] == arr1[i]
    with pytest.raises(PrefetchException):
        a = y[3]
        del a

    def f2(x):
        if x is None:
            raise ValueError("blablabla")
        else:
            return x

    # helps with coverage
    y._finalize(y)

    arr2 = smap(f2, arr1)
    y = prefetch(arr2, nworkers=2, max_cached=2, method=method)

    for i in range(3):
        assert y[i] == arr1[i]
    try:
        a = y[3]
        del a
    except Exception as e:
        assert isinstance(e, PrefetchException)
        assert isinstance(e.__cause__, ValueError)
    else:
        assert False

    assert y[0] == 1
    assert y[1] == 2

    # helps with coverage
    y._finalize(y)
