import logging
import random
from time import time, sleep

import pytest

from seqtools import add_cache, smap

logging.basicConfig(level=logging.DEBUG)
seed = int(random.random() * 100000)
logging.info("random seed was %d", seed)
# seed = 29130
random.seed(seed)


def test_cached():
    def f(x):
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

    duration = t2 - t1
    assert duration < .28


@pytest.mark.timeout(5)
def test_cached_timing():  # pragma: no cover
    def f(x):
        sleep(.01)
        return x

    cache_size = 3
    arr = [random.random() for _ in range(100)]

    y = smap(f, arr)
    z = add_cache(y, cache_size)

    t1 = time()
    for i in range(len(arr)):
        assert z[i] == arr[i]
        for j in range(max(0, i - cache_size + 1), i + 1):
            assert z[j] == arr[j]
    t2 = time()

    duration = t2 - t1
    print("test_cached_timing {:.2f}s".format(duration))

    assert duration < 1.2
