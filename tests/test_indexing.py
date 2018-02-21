from random import random, randint
import pytest
from seqtools import take, cycle, repeat


def test_reindex():
    arr = [random() for _ in range(100)]
    idx = [randint(-len(arr), len(arr) - 1) for _ in range(200)]
    reindexed = take(arr, idx)
    expected = [arr[i] for i in idx]

    assert [reindexed[i] for i in range(len(reindexed))] == expected
    assert [reindexed[i - 200] for i in range(len(reindexed))] == expected
    assert [r for r in iter(reindexed)] == expected

    start, stop, step = -15, -25, -2
    assert list(reindexed[start:stop:step]) == expected[start:stop:step]
    assert reindexed[start:stop:step].indexes == idx[start:stop:step]

    with pytest.raises(TypeError):
        a = reindexed[float(1)]
        del a

    with pytest.raises(IndexError):
        a = reindexed[200]
        del a

    arr1 = [random() for _ in range(100)]
    arr2 = list(arr1)
    reindexed = take(arr1, idx)
    reindexed[start:stop:step] = list(range(start, stop, step))
    for i, v in zip(idx[start:stop:step], range(start, stop, step)):
        arr2[i] = v
    assert arr1 == arr2

    with pytest.raises(ValueError):
        reindexed[start:stop:step] = list(range(start, stop, step))[:-1]

    with pytest.raises(IndexError):
        reindexed[200] = 1

    with pytest.raises(TypeError):
        reindexed[float(1)] = 1

    arr1 = [random() for _ in range(100)]
    arr2 = list(arr1)
    idx2 = [1, 2, -3]
    new_values = [-1, -2, -3]
    reindexed = take(take(arr1, idx), idx2)
    for i in range(-1, 2):
        reindexed[i] = new_values[i]
        arr2[idx[idx2[i]]] = new_values[i]
    assert arr1 == arr2


def test_cycle():
    arr = [randint(0, 1000) for _ in range(100)]
    looped = cycle(arr, 250)

    assert list(looped) == [arr[i % len(arr)] for i in range(250)]
    assert list(looped[150:105:-2]) == list(looped)[150:105:-2]

    looped = cycle(arr)
    assert [looped[i] for i in range(999)] \
        == [arr[i % 100] for i in range(999)]
    it = iter(looped)
    assert [next(it) for _ in range(999)] \
        == [arr[i % 100] for i in range(999)]
    sublooped = looped[:177:4]
    assert list(sublooped) == [arr[i % 100] for i in range(0, 177, 4)]

    with pytest.raises(IndexError):
        list(looped[-20])

    with pytest.raises(IndexError):
        list(looped[-20::4])

    with pytest.raises(TypeError):
        list(looped[1.0])

    arr = [randint(0, 1000) for _ in range(100)]
    looped = cycle(arr, 250)
    looped[50:150] = list(range(0, -100, -1))
    assert arr[50:] == list(range(0, -50, -1))
    assert arr[:50] == list(range(-50, -100, -1))


def test_repeat():
    a = 3
    r = repeat(a, 100)
    assert len(r) == 100
    it = iter(r)
    assert list(next(it) for _ in range(100)) == [3] * 100
    assert list(iter(r)) == [3] * 100
    r[-3] = 2
    assert r[10] == 2
    r[80:-10] = list(range(10))
    assert list(iter(r)) == [9] * 100

    a = 3
    r = repeat(a)
    it = iter(r)
    assert list(next(it) for _ in range(100)) == [3] * 100
    assert [r[i] for i in range(100)] == [3] * 100
    assert list(r[:100]) == [3] * 100
    with pytest.raises(IndexError):
        r[-3] = 2
    r[3] = 2
    assert r[10] == 2
    with pytest.raises(IndexError):
        r[80:-10] = list(range(10))
    r[80:91] = list(range(10))
    assert r[0] == 9
