from lproc import reindex, cycle
from lproc.indexing import Slice
from random import random, randint


def test_slice():
    arr = [random() for _ in range(100)]
    len(Slice(list(range(20)), slice(0, 20, 1)))
    s = Slice(arr, slice(10, 5, -1))
    assert list(s) == arr[10:5:-1]
    assert list(s[-1:0:-2]) == arr[10:5:-1][-1:0:-2]
    assert [s[-i - 1] for i in range(len(s))] == arr[10:5:-1][::-1]


def test_reindex():
    arr = [random() for _ in range(100)]
    idx = [randint(0, len(arr) - 1) for _ in range(200)]
    reindexed = reindex(arr, idx)
    expected = [arr[i] for i in idx]

    assert [reindexed[i] for i in range(len(reindexed))] == expected
    assert [r for r in iter(reindexed)] == expected

    start, stop, step = 15, -25, -2
    assert list(reindexed[start:stop:step]) == expected[start:stop:step]
    assert reindexed[start:stop:step].indexes == idx[start:stop:step]


def test_cycle():
    arr = [randint(0, 1000) for _ in range(100)]
    looped = cycle(arr, 250)

    assert list(looped) == [arr[i % len(arr)] for i in range(250)]
    assert list(looped[150:105:-2]) == list(looped)[150:105:-2]

    looped = cycle(arr)
    assert [looped[i] for i in range(999)] == [arr[i%100] for i in range(999)]
    it = iter(looped)
    assert [next(it) for _ in range(999)] == [arr[i % 100] for i in range(999)]
    sublooped = looped[3:177:4]
    assert list(sublooped) == [arr[i % 100] for i in range(3, 177, 4)]
