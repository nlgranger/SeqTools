import array
import multiprocessing
import random
import sys
from time import time, sleep
from numbers import Integral, Real
import logging

import pytest
import numpy as np
from seqtools import add_cache, smap, load_buffers, PrefetchException


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


def make_array(v):
    if isinstance(v[0], Integral):
        return array.array('i', v)
    elif isinstance(v[0], Real):
        return array.array('f', v)
    else:
        raise TypeError


array_types = [np.array]
if sys.version_info[:2] >= (3, 5):
    array_types.append(make_array)


@pytest.mark.parametrize("array_t", array_types)
def test_load_buffer(array_t):
    class MinibatchSampler:
        def __init__(self):
            self.state = multiprocessing.Value('l', 0)

        def __call__(self):
            with self.state.get_lock():
                v = self.state.value
                self.state.value += 1
            sleep(random.random() * 0.01)
            return (array_t([v + i for i in range(5)]),
                    array_t([float(v + i) for i in range(5)]))

    samples_1 = []
    sampler = MinibatchSampler()
    sampler()  # consume sample
    for i in range(100):
        samples_1.append(sampler())
    samples_1 = sorted(samples_1, key=lambda a: sum(a[0]))

    samples_2 = []
    sample_iter = load_buffers(
        MinibatchSampler(), max_cached=10, timeout=.1, start_hook=random.seed)
    pause_n_times = 3
    for i in range(100):
        if pause_n_times > 0 and random.random() < 1 / (99 - i - pause_n_times):
            print("{} pause".format(i))
            sleep(1)
            pause_n_times -= 1
        samples_2.append(tuple(array_t(field) for field in next(sample_iter)))
    samples_2 = sorted(samples_2, key=lambda a: sum(a[0]))

    for a, b in zip(samples_1[:-10], samples_2[:-10]):
        assert len(a) == len(b)
        for f1, f2 in zip(a, b):
            assert list(f1) == list(f2)

    sample_iter._finalize(sample_iter)  # for coverage


def test_load_buffer_errors():
    class MinibatchSampler:
        def __init__(self):
            self.state = multiprocessing.Value('l', 0)

        def __call__(self):
            with self.state.get_lock():
                v = self.state.value
                self.state.value += 1
            if v == 5:
                raise ValueError("aarrgh")
            out = (np.array([v + i for i in range(5)]),
                   np.array([float(v + i) for i in range(5)]))
            return out

    it = load_buffers(MinibatchSampler(), nworkers=1)
    for _ in range(4):
        next(it)

    try:
        next(it)
    except PrefetchException as error:
        assert isinstance(error.__cause__, ValueError)
    else:
        raise AssertionError("should have failed")
