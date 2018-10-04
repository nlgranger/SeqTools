import random
import logging
from time import sleep, time
import pytest

from seqtools import smap, prefetch, EvaluationError, seterr


logging.basicConfig(level=logging.DEBUG)
seed = int(random.random() * 100000)
# seed = 29130
random.seed(seed)


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

    arr = list(range(420))
    y = smap(f1, arr)
    y = prefetch(y, nworkers=2, max_buffered=20, method=method, timeout=1)

    for i in range(20):
        y[i]  # consume first items to eliminate worker startup time
    t1 = time()
    for i in range(20, 420):
        y[i]
    t2 = time()

    duration = t2 - t1
    print("test_prefetch_timing({}) {:.2f}s".format(method, duration))

    assert duration < 4.5


@pytest.mark.timeout(10)
@pytest.mark.parametrize("method", ["thread", "process"])
@pytest.mark.parametrize("evaluation", ["wrap", "passthrough"])
@pytest.mark.parametrize("picklable_err", [False, True])
def test_prefetch_errors(method, evaluation, picklable_err):
    class CustomError(Exception):
        pass

    def f1(x):
        if x is None:
            raise ValueError("blablabla") if picklable_err else CustomError()
        else:
            return x

    arr1 = [1, 2, 3, None]
    arr2 = smap(f1, arr1)
    y = prefetch(arr2, nworkers=2, max_buffered=2, method=method)

    seterr(evaluation)
    if (method == "process" and not picklable_err) or evaluation == "wrap":
        error_t = EvaluationError
    else:
        error_t = ValueError if picklable_err else CustomError

    for i in range(3):
        assert y[i] == arr1[i]
    with pytest.raises(error_t):
        a = y[3]
        del a
