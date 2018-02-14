from lproc import reindex, cycle
from random import random, randint


def test_reindex():
    arr = [random() for _ in range(100)]
    idx = [randint(0, len(arr) - 1) for _ in range(200)]
    reindexed = reindex(arr, idx)
    expected = [arr[i] for i in idx]

    assert [reindexed[i] for i in range(len(reindexed))] == expected
    assert [r for r in iter(reindexed)] == expected

    start, stop, step = -15, -25, -2
    assert list(reindexed[start:stop:step]) == expected[start:stop:step]
    assert reindexed[start:stop:step].indexes == idx[start:stop:step]

    arr1 = [random() for _ in range(100)]
    arr2 = list(arr1)
    reindexed = reindex(arr1, idx)
    reindexed[start:stop:step] = list(range(start, stop, step))
    for i, v in zip(idx[start:stop:step], range(start, stop, step)):
        arr2[i] = v
    assert arr1 == arr2

    arr1 = [random() for _ in range(100)]
    arr2 = list(arr1)
    idx2 = [1, 2, 3]
    new_values = [-1, -2, -3]
    reindexed = reindex(reindex(arr1, idx), idx2)
    for i in range(3):
        reindexed[i] = new_values[i]
        arr2[idx[idx2[i]]] = new_values[i]
    assert arr1 == arr2

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

    arr = [randint(0, 1000) for _ in range(100)]
    looped = cycle(arr, 250)
    looped[50:150] = list(range(0, -100, -1))
    assert arr[50:] == list(range(0, -50, -1))
    assert arr[:50] == list(range(-50, -100, -1))
