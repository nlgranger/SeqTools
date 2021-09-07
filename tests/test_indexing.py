from random import random, randint
import pytest
from seqtools import arange, case, switch, gather, cycle, interleave, repeat, uniter


def test_arange():
    tests = [(10,),
             (0,),
             (0, -10, 1),
             (10, -10, -3)]
    slices = [slice(None, None, None),
              slice(1, -1, 3),
              slice(None, None, -3)]

    for t in tests:
        arr = list(range(*t))
        assert arr == list(arange(*t))
        assert arr == [x for x in arange(*t)]
        for s in slices:
            assert arr[s] == list(arange(*t)[s])


def test_reindex():
    arr = [random() for _ in range(100)]
    idx = [randint(-len(arr), len(arr) - 1) for _ in range(200)]
    reindexed = gather(arr, idx)
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
    reindexed = gather(arr1, idx)
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
    reindexed = gather(gather(arr1, idx), idx2)
    for i in range(-1, 2):
        reindexed[i] = new_values[i]
        arr2[idx[idx2[i]]] = new_values[i]
    assert arr1 == arr2


def test_case():
    values = [[randint(0, 1000) for _ in range(100)] for _ in range(10)]
    selector = [randint(0, 9) for _ in range(100)]

    res = case(selector, *values)
    tgt = [values[s][i] for i, s in enumerate(selector)]

    assert list(res) == tgt

    original_values = [list(l) for l in values]
    subset = list(range(25, 75, 3))
    res[25:75:3] = [-1] * len(subset)
    for i in range(len(selector)):
        row = [v[i] for v in values]
        tgt = [v[i] for v in original_values]
        if i in subset:
            tgt[selector[i]] = -1
        assert row == tgt


def test_switch():
    values_true = [randint(0, 1000) for _ in range(100)]
    values_false = [randint(0, 1000) for _ in range(100)]
    condition = [randint(0, 1) > 0 for _ in range(100)]

    res = switch(condition, values_true, values_false)
    tgt = [t if c else f
           for c, t, f in zip(condition, values_true, values_false)]

    assert list(res) == tgt


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


def test_interleave():
    arr1 = [1, 2, 3, 4, 5]
    arr2 = ['a', 'b', 'c']
    arr3 = [.1, .2, .3, .4]
    y = interleave(arr1, arr2, arr3)
    expected = [1, 'a', .1, 2, 'b', .2, 3, 'c', .3, 4, .4, 5]
    assert list(y) == expected
    assert [y[i] for i in range(len(y))] == expected

    y[1] = -1
    y[3] = -2
    y[-1] = -3
    assert arr1 == [1, -2, 3, 4, -3]
    assert arr2 == [-1, 'b', 'c']
    assert arr3 == [.1, .2, .3, .4]


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


def test_uniter():
    iterable = range(100)
    uniterator = uniter(iterable, 10)
    for i in range(100):
        assert uniterator[i] == i

    assert uniterator[90] == 90

    for _ in range(50):
        i = randint(0, 99)
        assert uniterator[i] == i

    uniterator = uniter(iterable, 10, n_parallel=5, size=100)

    for _ in range(100):
        i = randint(-99, 99)
        assert uniterator[i] == (i % 100)
