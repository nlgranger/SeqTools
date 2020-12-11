import logging
import os
import platform
import random
import signal
import sys
import tempfile
import string
from multiprocessing import Process
from time import sleep, time

import numpy as np
import pytest
from numpy.testing import assert_array_equal

from seqtools import smap, prefetch, EvaluationError, seterr


logging.basicConfig(level=logging.DEBUG)
seed = int(random.random() * 100000)
# seed = 29130
random.seed(seed)

prefetch_kwargs_set = [
    {'method': "thread"},
    {'method': "process"}]
if sys.version_info >= (3, 8):
    prefetch_kwargs_set.append(
        {'method': "process", 'shm_size': 16 * 1024 ** 2})


def build_random_object(limit=1.):
    x = min(random.random(), limit - 1e-6)

    if x < 0.2:
        return random.randint(-100, 100)
    elif x < 0.4:
        return ''.join(random.choice(string.ascii_letters)
                       for _ in range(random.randint(0, 100)))
    elif x < 0.6:
        return random.random()
    elif x < 0.65:
        return {build_random_object(0.4): build_random_object(limit - 0.1)
                for _ in range(random.randint(0, 15))}
    elif x < 0.70:
        return tuple(build_random_object(limit - 0.1) for _ in range(random.randint(0, 15)))
    elif x < 0.75:
        return [build_random_object(limit - 0.1) for _ in range(random.randint(0, 15))]
    elif x < 0.80:
        dtype = random.choice(['b', 'i1', 'i2', 'u8', 'm8'])
        return np.asarray(np.random.rand(
            *[random.randint(0, 10) for _ in range(random.randint(0, 3))])).astype(dtype)
    else:
        return None


def compare_random_objects(a, b):
    if isinstance(a, (list, tuple)):
        assert isinstance(b, type(a))
        assert len(a) == len(b)
        for a_, b_ in zip(a, b):
            compare_random_objects(a_, b_)

    elif isinstance(a, dict):
        assert len(a) == len(b)
        for k, v in a.items():
            assert k in b
            compare_random_objects(v, b[k])

    elif isinstance(a, float):
        assert abs(a - b) < 1e-6

    elif isinstance(a, np.ndarray):
        assert a.dtype == b.dtype
        assert a.shape == b.shape
        if a.size > 0:
            assert np.max(np.abs((a - b).astype(np.float32))) < 1e-6

    else:
        assert a == b


@pytest.mark.parametrize("prefetch_kwargs", prefetch_kwargs_set)
def test_prefetch_random_objects(prefetch_kwargs):
    seq = [build_random_object() for _ in range(1000)]
    y = prefetch(seq, 2, **prefetch_kwargs)
    for x, y in zip(seq, y):
        compare_random_objects(x, y)


@pytest.mark.parametrize("prefetch_kwargs", prefetch_kwargs_set)
@pytest.mark.timeout(15)
def test_prefetch_timings(prefetch_kwargs):
    def f1(x):
        sleep(0.005 * (1 + random.random()))
        return x

    start_hook = random.seed

    arr = np.random.rand(100, 10)
    y = smap(f1, arr)
    y = prefetch(
        y, nworkers=4, max_buffered=10, start_hook=start_hook, **prefetch_kwargs)
    y = [y_.copy() for y_ in y]  # copy needed to release buffers when shm_size>0
    assert_array_equal(np.stack(y), arr)

    # overly large buffer
    arr = np.random.rand(10, 10)
    y = smap(f1, arr)
    y = prefetch(y, nworkers=4, max_buffered=50, **prefetch_kwargs)
    y = [y_.copy() for y_ in y]
    assert_array_equal(np.stack(y), arr)

    # multiple restarts
    arr = np.random.rand(100, 10)
    y = smap(f1, arr)
    y = prefetch(y, nworkers=4, max_buffered=10, **prefetch_kwargs)
    for _ in range(10):
        n = np.random.randint(0, 99)
        for i in range(n):
            assert_array_equal(y[i], arr[i])

    # starvation
    arr = np.random.rand(100, 10)
    y = prefetch(arr, nworkers=2, max_buffered=10, **prefetch_kwargs)
    y[0]
    sleep(2)
    for i in range(1, 100):
        assert_array_equal(y[i], arr[i])


@pytest.mark.xfail
@pytest.mark.parametrize("prefetch_kwargs", prefetch_kwargs_set)
@pytest.mark.timeout(15)
def test_prefetch_throughput(prefetch_kwargs):  # pragma: no cover
    def f1(x):
        sleep(.02 + 0.01 * (random.random() - .5))
        return x

    arr = np.random.rand(420, 10)
    y = smap(f1, arr)
    y = prefetch(y, nworkers=2, max_buffered=40, **prefetch_kwargs)

    for i in range(20):
        y[i]  # consume first items to eliminate worker startup time

    t1 = time()
    for i in range(20, 420):
        y[i]
    t2 = time()

    duration = t2 - t1
    print("test_prefetch_timing: {:.2f}s".format(duration))

    assert duration < 4.5


@pytest.mark.parametrize("error_mode", ["wrap", "passthrough"])
@pytest.mark.parametrize("prefetch_kwargs", prefetch_kwargs_set)
@pytest.mark.parametrize("picklable_err", [False, True])
@pytest.mark.timeout(10)
def test_prefetch_errors(error_mode, prefetch_kwargs, picklable_err):
    class CustomError(Exception):
        pass

    def f1(x):
        if x is None:
            raise ValueError("blablabla") if picklable_err else CustomError()
        else:
            return x

    arr1 = [np.random.rand(10), np.random.rand(10), np.random.rand(10), None]
    arr2 = smap(f1, arr1)
    y = prefetch(arr2, nworkers=2, max_buffered=4, **prefetch_kwargs)

    seterr(error_mode)
    if (prefetch_kwargs['method'] != "thread" and not picklable_err) or error_mode == "wrap":
        error_t = EvaluationError
    else:
        error_t = ValueError if picklable_err else CustomError

    for i in range(3):
        assert_array_equal(y[i], arr1[i])
    try:
        a = y[3]
    except Exception as e:
        assert type(e) == error_t

    if (prefetch_kwargs['method'] == "process") and error_mode == "passthrough":
        class CustomObject:  # unpicklable object
            pass

        arr1 = [np.random.rand(10), CustomObject(), np.random.rand(10)]
        y = prefetch(arr1, nworkers=2, max_buffered=4, **prefetch_kwargs)
        with pytest.raises(ValueError):
            y[1]


def check_pid(pid):
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


@pytest.mark.parametrize("method", ["process"])
@pytest.mark.timeout(10)
def test_prefetch_crash(method):
    if platform.python_implementation() == "PyPy":
        pytest.skip("broken with pypy")

    # worker dies
    with tempfile.TemporaryDirectory() as d:
        def init_fn():
            signal.signal(signal.SIGUSR1, lambda *_: sys.exit(-1))
            with open('{}/{}'.format(d, os.getpid()), "w"):
                pass

        def f1(x):
            sleep(.02 + 0.01 * (random.random() - .5))
            return x

        arr = np.random.rand(1000, 10)
        y = smap(f1, arr)
        y = prefetch(y, method=method, max_buffered=40,
                     nworkers=4, start_hook=init_fn)

        sleep(0.1)

        while True:
            if len(os.listdir(d)) > 0:
                os.kill(int(os.listdir(d)[0]), signal.SIGUSR1)
                break

        with pytest.raises(RuntimeError):
            for i in range(0, 1000):
                a = y[i]

    # parent dies
    with tempfile.TemporaryDirectory() as d:
        def init_fn():
            signal.signal(signal.SIGUSR1, lambda *_: sys.exit(-1))
            with open('{}/{}'.format(d, os.getpid()), "w"):
                pass

        def target():
            arr = np.random.rand(1000, 10)
            y = smap(f1, arr)
            y = prefetch(y, method=method, max_buffered=40,
                         nworkers=4, start_hook=init_fn)

            for i in range(0, 1000):
                a = y[i]

        p = Process(target=target)
        p.start()

        while len(os.listdir(d)) < 4:
            sleep(0.05)

        os.kill(p.pid, signal.SIGUSR1)
        sleep(2)  # wait for workers to time out

        for pid in map(int, os.listdir(d)):
            assert not check_pid(pid)
