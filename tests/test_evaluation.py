import logging
import os
import platform
import random
import signal
import string
import tempfile
import threading
from functools import partial
from multiprocessing import Process
from time import sleep, time

import numpy as np
import pytest
from numpy.testing import assert_array_equal

from seqtools import EvaluationError, prefetch, repeat, seterr, smap

logging.basicConfig(level=logging.DEBUG)
seed = int(random.random() * 100000)
# seed = 29130
random.seed(seed)

prefetch_kwargs_set = [
    {"method": "thread"},
    {"method": "process"},
    {"method": "process", "shm_size": 16 * 1024**2},
]


def build_random_object(limit=1.0):
    x = min(random.random(), limit - 1e-6)

    if x < 0.2:
        return random.randint(-100, 100)
    elif x < 0.4:
        return "".join(
            random.choice(string.ascii_letters) for _ in range(random.randint(0, 100))
        )
    elif x < 0.6:
        return random.random()
    elif x < 0.65:
        return {
            build_random_object(0.4): build_random_object(limit - 0.1)
            for _ in range(random.randint(0, 15))
        }
    elif x < 0.70:
        return tuple(
            build_random_object(limit - 0.1) for _ in range(random.randint(0, 15))
        )
    elif x < 0.75:
        return [build_random_object(limit - 0.1) for _ in range(random.randint(0, 15))]
    elif x < 0.80:
        dtype = random.choice(["b", "i1", "i2", "u8", "m8"])
        return np.asarray(
            np.random.rand(
                *[random.randint(0, 10) for _ in range(random.randint(0, 3))]
            )
        ).astype(dtype)
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
    y = prefetch(seq, -1, max_buffered=len(os.sched_getaffinity(0)), **prefetch_kwargs)

    assert len(seq) == len(y)

    for x, y in zip(seq, y):
        compare_random_objects(x, y)


@pytest.mark.parametrize("prefetch_kwargs", prefetch_kwargs_set)
def test_prefetch_infinite(prefetch_kwargs):
    seq = repeat(1)
    y = prefetch(seq, 1, **prefetch_kwargs)

    for i, x in enumerate(y):
        assert x == 1
        if i == 100:
            break


tls = None


def set_seed(*kargs):
    global tls
    tls = threading.local()
    tls.random = random.Random(42)


def randint(*kargs):
    return tls.random.randint(0, 10)


@pytest.mark.parametrize("prefetch_kwargs", prefetch_kwargs_set)
def test_prefetch_start_hook(prefetch_kwargs):
    seq = smap(randint, [None] * 1000)

    y = list(prefetch(seq, 1, **prefetch_kwargs, start_hook=set_seed))

    set_seed()
    z = [randint() for _ in range(1000)]

    compare_random_objects(y, z)


def sleep_and_return(x):
    sleep(0.005 * (1 + random.random()))
    return x


@pytest.mark.parametrize("prefetch_kwargs", prefetch_kwargs_set)
@pytest.mark.timeout(15)
def test_prefetch_timings(prefetch_kwargs):
    start_hook = random.seed

    arr = np.random.rand(100, 10)
    y = smap(sleep_and_return, arr)
    y = prefetch(
        y, nworkers=4, max_buffered=10, start_hook=start_hook, **prefetch_kwargs
    )
    y = [y_.copy() for y_ in y]  # copy needed to release buffers when shm_size>0
    assert_array_equal(np.stack(y), arr)

    # overly large buffer
    arr = np.random.rand(10, 10)
    y = smap(sleep_and_return, arr)
    y = prefetch(y, nworkers=4, max_buffered=50, **prefetch_kwargs)
    y = [y_.copy() for y_ in y]
    assert_array_equal(np.stack(y), arr)

    # multiple restarts
    arr = np.random.rand(100, 10)
    y = smap(sleep_and_return, arr)
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
        sleep(0.02 + 0.01 * (random.random() - 0.5))
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


def raise_if_none(x, picklable_err):
    class CustomError(Exception):
        pass

    if x is None:
        if picklable_err:
            raise ValueError()
        else:
            raise CustomError()

    return x


@pytest.mark.parametrize("error_mode", ["wrap", "passthrough"])
@pytest.mark.parametrize("prefetch_kwargs", prefetch_kwargs_set)
@pytest.mark.parametrize("picklable_err", [False, True])
@pytest.mark.timeout(10)
def test_prefetch_errors(error_mode, prefetch_kwargs, picklable_err):
    seterr(error_mode)

    arr1 = [np.random.rand(10), np.random.rand(10), np.random.rand(10), None]
    arr2 = smap(partial(raise_if_none, picklable_err=picklable_err), arr1)
    y = prefetch(arr2, nworkers=2, max_buffered=4, **prefetch_kwargs)

    if error_mode == "wrap":
        expected_err = "EvaluationError"
    else:  # passthrough
        if prefetch_kwargs["method"] == "process" and not picklable_err:
            expected_err = "EvaluationError"
        elif picklable_err:
            expected_err = "ValueError"
        else:
            expected_err = "CustomError"

    for i in range(3):
        assert_array_equal(y[i], arr1[i])
    try:
        a = y[3]
    except Exception as e:
        assert type(e).__name__ == expected_err
    else:
        assert False, "Should have raised"


def check_pid(pid):
    """Check For the existence of a unix pid."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def write_pid_file(directory, worker_id):
    with open("{}/{}".format(directory, os.getpid()), "w"):
        pass


@pytest.mark.timeout(10)
def test_worker_crash():
    if platform.python_implementation() == "PyPy":
        pytest.skip("broken with pypy")

    # worker dies
    with tempfile.TemporaryDirectory() as d:
        arr = np.random.rand(1000, 10)
        y = smap(sleep_and_return, arr)
        y = prefetch(
            y,
            method="process",
            max_buffered=40,
            nworkers=4,
            start_hook=partial(write_pid_file, d),
        )

        while len(os.listdir(d)) == 0:
            sleep(0.05)

        os.kill(int(os.listdir(d)[0]), signal.SIGKILL)

        with pytest.raises(RuntimeError):
            for i in range(0, 1000):
                a = y[i]


@pytest.mark.timeout(10)
def test_orphan_workers_die():
    if platform.python_implementation() == "PyPy":
        pytest.skip("broken with pypy")

    with tempfile.TemporaryDirectory() as d:

        def target():
            arr = np.random.rand(1000, 10)
            y = smap(sleep_and_return, arr)
            y = prefetch(
                y,
                method="process",
                max_buffered=4,
                nworkers=4,
                start_hook=partial(write_pid_file, d),
            )

            for i in range(0, 1000):
                a = y[i]

        p = Process(target=target)
        # h = signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        p.start()
        # signal.signal(signal.SIGCHLD, h)

        while len(os.listdir(d)) < 4:  # wait for workers to start
            sleep(0.05)

        os.kill(p.pid, signal.SIGKILL)  # parent process crashes

        sleep(3)  # wait for workers to time out

        for pid in map(int, os.listdir(d)):
            assert not check_pid(pid)  # ensure workers have exited
