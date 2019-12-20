import logging
import random
from time import time, sleep

import numpy as np
import pytest

from seqtools import add_cache, smap
from seqtools.memory import packed_size, pack, unpack


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


@pytest.mark.no_cover
@pytest.mark.timeout(5)
def test_cached_timing():
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


def test_packing():
    sample_items = [
        np.random.rand(10, 20),
        (np.random.rand(22, 33, 44), (np.arange(10), np.arange(10))),
        {"a": np.random.rand(25), "b": np.random.rand(25)}
    ]

    # test packed_size
    assert tuple([packed_size(i) for i in sample_items]) == (1600, 255712, 400)

    def check_equal(a, b):
        if isinstance(b, np.ndarray):
            np.testing.assert_allclose(a, b)
        elif isinstance(b, dict):
            assert set(a.keys()) == set(b.keys())
            # insertion order matters
            for (_, va), (_, vb) in zip(sorted(a.items()), sorted(b.items())):
                check_equal(va, vb)
        elif isinstance(b, tuple):
            assert len(a) == len(b)
            for va, vb in zip(a, b):
                check_equal(va, vb)

    # test (un)packing
    sample_items[-1] = dict(sorted(sample_items[-1].items())[::-1])
    for sample in sample_items:
        size = packed_size(sample)
        buffer = np.empty(size, dtype='b')
        pack(sample, buffer)
        rebuild, _ = unpack(sample, buffer)

        check_equal(rebuild, sample)
