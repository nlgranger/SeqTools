import sys
import random
import array
import logging
from time import sleep, time
import multiprocessing
import pytest

from seqtools import add_cache, smap, prefetch, PrefetchException

if sys.version_info[:2] >= (3, 5):
    from seqtools import load_buffers


logging.basicConfig(level=logging.DEBUG)
seed = int(random.random() * 100000)
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


@pytest.mark.timeout(15)
@pytest.mark.parametrize("method", ["thread", "process"])
def test_prefetch(method):
    def f1(x):
        sleep(0.005 * (1 + random.random()))
        return x

    if method == "process":
        start_hook = random.seed
    else:
        start_hook = None

    arr = list(range(300))
    y = smap(f1, arr)
    y = prefetch(y, nworkers=4, max_buffered=10, method=method, timeout=1,
                 start_hook=start_hook)

    # check if workers are properly restarted when asleep
    i = 0
    n_wakeups = 3
    for _ in range(500):
        if n_wakeups > 0 and random.random() < 0.005:
            sleep(1.1)  # will let worker go to sleep
            n_wakeups -= 1
        value = y[i]
        assert value == arr[i]
        if random.random() < 0.05:
            i = random.randrange(0, len(arr))
        else:
            i = (i + 1) % len(arr)

    # helps with coverage
    y.async_seq._finalize(y.async_seq)

    # overly large buffer
    arr = list(range(10))
    y = smap(f1, arr)
    y = prefetch(y, nworkers=4, max_buffered=50, method=method, timeout=1)
    assert list(y) == arr

    # anticipate method
    arr = list(range(200))
    y = smap(f1, arr)
    y = prefetch(y, nworkers=2, max_buffered=20, method=method,
                 timeout=1, anticipate=lambda i: i + 2)

    z = [y[i] for i in range(0, len(y), 2)]

    assert z == arr[::2]


@pytest.mark.no_cover
@pytest.mark.timeout(15)
@pytest.mark.parametrize("method", ["thread", "process"])
def test_prefetch_timing(method):
    def f1(x):
        sleep(.02 + 0.01 * (random.random() - .5))
        return x

    arr = list(range(421))
    y = smap(f1, arr)
    y = prefetch(y, nworkers=2, max_buffered=20, method=method, timeout=1)

    for i in range(20):
        y[i]  # consume first items to eliminate worker startup time
    t1 = time()
    for i in range(20, 421):
        y[i]
    t2 = time()

    duration = t2 - t1
    print("test_prefetch_timing({}) {:.2f}s".format(method, duration))

    assert duration < 4.3


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
    y = prefetch(arr2, nworkers=2, max_buffered=2, method=method)

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

    arr2 = smap(f2, arr1)
    y = prefetch(arr2, nworkers=2, max_buffered=2, method=method)

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


@pytest.mark.skipif(sys.version_info[:2] < (3, 5),
                    reason="requires python3.5 or higher")
def test_load_buffer():
    class MinibatchSampler:
        def __init__(self):
            self.state = multiprocessing.Value('l', 0)

        def __call__(self):
            with self.state.get_lock():
                v = self.state.value
                self.state.value += 1
            out = (array.array('l', range(v, v + 5)),
                   array.array('f', range(v, v + 5)))
            return out

    def wrap_slot(x):
        return tuple([array.array(f.format, f.tolist()) for f in x])

    samples_1 = []
    sampler = MinibatchSampler()
    sampler()  # consume sample
    for i in range(100):
        samples_1.append(sampler())
    samples_1 = sorted(samples_1)

    samples_2 = []
    sample_iter = load_buffers(
        MinibatchSampler(), max_cached=10, nworkers=2, timeout=.1)
    pause_n_times = 3
    for i in range(100):
        if pause_n_times > 0 and random.random() < 1 / (99 - i - pause_n_times):
            print("{} pause".format(i))
            sleep(1)
            pause_n_times -= 1
        samples_2.append(wrap_slot(next(sample_iter)))
    samples_2 = sorted(samples_2)

    assert samples_1[:-10] == samples_2[:-10]

    sample_iter._finalize(sample_iter)  # for coverage

    class MinibatchSampler:
        def __init__(self):
            self.state = multiprocessing.Value('l', 0)

        def __call__(self):
            with self.state.get_lock():
                v = self.state.value
                self.state.value += 1
            if v == 1:
                raise ValueError("aarrgh")
            out = (array.array('l', range(v, v + 5)),
                   array.array('f', range(v, v + 5)))
            return out

    with pytest.raises(PrefetchException):
        next(load_buffers(MinibatchSampler(), nworkers=1))
