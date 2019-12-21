import logging
import os
import platform
import random
import signal
import sys
import tempfile
import cProfile
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


@pytest.mark.parametrize("method", ["thread", "process", "sharedmem"])
@pytest.mark.timeout(15)
def test_prefetch(method):
    def f1(x):
        sleep(0.005 * (1 + random.random()))
        return x

    if method == "process":
        start_hook = random.seed
    else:
        start_hook = None

    arr = np.random.rand(100, 10)
    y = smap(f1, arr)
    y = prefetch(y, nworkers=4, max_buffered=10, method=method, start_hook=start_hook)
    y = [y_.copy() for y_ in y]  # copy needed to release buffers when method=sharedmem
    assert_array_equal(np.stack(y), arr)

    # overly large buffer
    arr = np.random.rand(10, 10)
    y = smap(f1, arr)
    y = prefetch(y, nworkers=4, max_buffered=50, method=method)
    y = [y_.copy() for y_ in y]
    assert_array_equal(np.stack(y), arr)

    # multiple restarts
    arr = np.random.rand(100, 10)
    y = smap(f1, arr)
    y = prefetch(y, nworkers=-1, max_buffered=10, method=method)
    for _ in range(10):
        n = np.random.randint(0, 99)
        for i in range(n):
            assert_array_equal(y[i], arr[i])

    # starvation
    arr = np.random.rand(100, 10)
    y = prefetch(arr, nworkers=2, max_buffered=10, method=method)
    y[0]
    sleep(2)
    for i in range(1, 100):
        assert_array_equal(y[i], arr[i])


@pytest.mark.no_cover
@pytest.mark.parametrize("method", ["thread", "process", "sharedmem"])
@pytest.mark.timeout(15)
def test_prefetch_timing(method):
    def f1(x):
        sleep(.02 + 0.01 * (random.random() - .5))
        return x

    arr = np.random.rand(420, 10)
    y = smap(f1, arr)
    y = prefetch(y, nworkers=2, max_buffered=40, method=method)

    for i in range(20):
        y[i]  # consume first items to eliminate worker startup time

    pr = cProfile.Profile()

    pr.enable()
    t1 = time()
    for i in range(20, 420):
        y[i]
    t2 = time()
    pr.disable()
    pr.dump_stats("/tmp/prefetch.prof")

    duration = t2 - t1
    print("test_prefetch_timing({}) {:.2f}s".format(method, duration))

    assert duration < 4.5


@pytest.mark.parametrize("method", ["thread", "process", "sharedmem"])
@pytest.mark.parametrize("error_mode", ["wrap", "passthrough"])
@pytest.mark.parametrize("picklable_err", [False, True])
@pytest.mark.timeout(10)
def test_prefetch_errors(method, error_mode, picklable_err):
    class CustomError(Exception):
        pass

    def f1(x):
        if x is None:
            raise ValueError("blablabla") if picklable_err else CustomError()
        else:
            return x

    arr1 = [np.random.rand(10), np.random.rand(10), np.random.rand(10), None]
    arr2 = smap(f1, arr1)
    y = prefetch(arr2, nworkers=2, max_buffered=4, method=method)

    seterr(error_mode)
    if (method != "thread" and not picklable_err) or error_mode == "wrap":
        error_t = EvaluationError
    else:
        error_t = ValueError if picklable_err else CustomError

    for i in range(3):
        assert_array_equal(y[i], arr1[i])
    try:
        a = y[3]
    except Exception as e:
        assert type(e) == error_t

    if (method == "process" or method == "sharedmem") and error_mode == "passthrough":
        class CustomObject:  # unpicklable object
            pass

        arr1 = [np.random.rand(10), CustomObject(), np.random.rand(10)]
        y = prefetch(arr1, nworkers=2, max_buffered=4, method=method)
        with pytest.raises(ValueError):
            y[1]

    if method == "sharedmem":
        arr = np.random.randn(1000, 100)
        y = prefetch(arr, nworkers=2, max_buffered=50, method=method)
        with pytest.raises(MemoryError):
            list(y)


def check_pid(pid):
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


@pytest.mark.parametrize("method", ["process", "sharedmem"])
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
