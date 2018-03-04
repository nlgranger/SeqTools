import pytest
import queue
import multiprocessing
import time
from seqtools.utils import SeqSlice, SharedCtypeQueue


def test_sliceview():
    arr = list(range(100))

    keys = [
        slice(None, None, None),
        slice(None, -10, None),
        slice(0, 0, 1),
        slice(0, 10, -1),
        slice(10, 0, -1),
        slice(250, -125, -1)]

    for k in keys:
        v = SeqSlice(arr, k)
        assert list(v) == arr[k]
        assert list(iter(v)) == arr[k]
        assert [v[i] for i in range(len(v))] == arr[k]

    v = SeqSlice(arr, slice(3, -25, 4))[14:1:-2]
    assert list(v) == arr[3:-25:4][14:1:-2]
    assert id(v.sequence) == id(arr)

    arr2 = list(arr)
    v = SeqSlice(arr2, slice(25, 37, 3))
    v[1] = -1
    assert arr2[:28] == arr[:28]
    assert arr2[28] == -1
    assert arr2[29:] == arr[29:]

    arr2 = list(arr)
    arr3 = list(arr)
    v = SeqSlice(arr2, slice(25, 37, 3))
    v[1:-1] = [-1, -2]
    arr3[28:34:3] = [-1, -2]
    assert arr2 == arr3


@pytest.mark.timeout(3)
def test_sharedctypesqueue():
    fmt = "iii"

    # basic read/write
    q = SharedCtypeQueue(fmt, 10)
    for i in range(10):
        q.put((i, i, i))
    for i in range(10):
        assert q.get() == (i, i, i)

    # read protection
    t = time.time()
    with pytest.raises(queue.Empty):
        q.get(False)
    with pytest.raises(queue.Empty):
        q.get(True, 0.1)
    assert time.time() - t < 0.11

    # write protection
    for i in range(10):
        q.put((i, i, i))
    with pytest.raises(queue.Full):
        q.put((-1, -1, -1), blocking=False)
    t = time.time()
    with pytest.raises(queue.Full):
        q.put((-1, -1, -1), blocking=True, timeout=0.1)
    assert time.time() - t < 0.11

    # reading empty queue blocks execution
    def f(q):
        for _ in range(10):
            q.get()

        q.get()
    p = multiprocessing.Process(target=f, args=(q,))
    p.start()
    time.sleep(0.3)
    assert q.empty()  # almost guarantied to work
    assert p.is_alive()
    q.put((-1, -1, -1))
    p.join()
