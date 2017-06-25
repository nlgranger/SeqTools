from lproc import subset
from lproc.utils import Subset


def test_subset():
    arr = list(range(100))

    # integer list based indexing
    idx = [1, 3, 4, 7]
    s = subset(arr, idx)
    expected = [arr[i] for i in idx]
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))

    # slice based indexing
    idx = slice(25, 87, 3)
    s = subset(arr, idx)
    expected = arr[idx.start:idx.stop:idx.step]
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))

    idx = slice(-34, None, None)
    s = subset(arr, idx)
    expected = arr[idx.start:idx.stop:idx.step]
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))

    idx = slice(None, -1, None)
    s = subset(arr, idx)
    expected = arr[idx.start:idx.stop:idx.step]
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))


def test_subset_nesting():
    arr = list(range(100))

    s = subset(arr, slice(10, 50))
    s = subset(s, [1, 2])
    expected = arr[10:50][1:3]

    assert not isinstance(s.sequence, Subset)
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))


def test_delegated_indexing():
    class TupleIndexable:
        def __init__(self, data):
            self.data = data

        def __getitem__(self, item):
            if isinstance(item, tuple):
                return self.data[item[0]:item[1]]
            else:
                return self.data[item]

    arr = TupleIndexable([10, 3, 5, 2, 8, 0, 4, 9, 6])
    s = subset(arr, TupleIndexable([0, 2, 3, 4]))
    s = s[(0, 3)]
    expected = [10, 5, 2, 8][0:3]
    assert len(s) == len(expected)
    assert all(x == y for x, y in zip(s, expected))
