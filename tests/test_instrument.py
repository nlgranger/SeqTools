import pytest
import time
from seqtools import smap
from seqtools.instrument import debug, monitor_throughput


def test_debug():
    arr = list(range(100))

    def do(i, v):
        del i, v
        do.i += 1

    do.i = 0

    debugged_arr = debug(arr, do)

    assert list(debugged_arr) == arr
    assert do.i == 100
    assert [debugged_arr[i] for i in range(len(debugged_arr))] == arr
    assert do.i == 200

    do.i = 0
    debugged_arr = debug(arr, do, max_calls=3)

    assert list(debugged_arr) == arr
    assert do.i == 3

    def proc(x):
        time.sleep(0.01)
        return x

    do.i = 0
    debugged_arr = debug(smap(proc, arr), do, max_rate=10)

    assert list(debugged_arr) == arr
    assert do.i == 10


def test_throughput():
    def proc(x):
        time.sleep(proc.delay)
        return x

    proc.delay = 0.01

    arr = list(range(100))
    monitored_arr = monitor_throughput(smap(proc, arr))
    x = list(monitored_arr)

    assert x == arr
    assert monitored_arr.throughput() - 100 < 1

    monitored_arr.reset()

    with pytest.raises(RuntimeError):
        monitored_arr.read_delay()
    with pytest.raises(RuntimeError):
        monitored_arr.throughput()

    proc.delay = 0.02

    arr = list(range(100))
    monitored_arr = monitor_throughput(smap(proc, arr))
    x = [monitored_arr[i] for i in range(len(monitored_arr))]

    assert x == arr
    assert monitored_arr.read_delay() - 0.02 < 0.002
