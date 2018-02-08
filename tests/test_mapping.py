import random
import pytest
from lproc import rmap, rimap, rrmap


def test_rmap_basics():
    n = 100
    data = [random.random() for _ in range(n)]

    def do(x):
        do.call_cnt += 1
        return x + 1

    do.call_cnt = 0

    # indexing
    result = rmap(do, data)
    assert len(result) == len(data)
    assert do.call_cnt == 0
    assert all(result[i] == data[i] + 1 for i in range(n))
    assert do.call_cnt == n

    # iteration
    assert all(r == d + 1 for r, d in zip(result, data))


# def test_rmap_special_indexing():
#     n = 100
#     data = [random.random() for _ in range(n)]
#     result = rmap(lambda x: x * 2, data)
#     expected = [x * 2 for x in data]
#
#     # slicing
#     assert all(x == y
#                for x, y in zip(result[2:25:3], expected[2:25:3]))
#
#     # delegated indexing
#     class Container:
#         def __init__(self, data):
#             self.data = data
#
#         def __len__(self):
#             return n
#
#         def __getitem__(self, item):
#             try:
#                 len(item)
#                 return [self.data[i] for i in item]
#             except TypeError:
#                 return self.data[item]
#
#     c = Container(data)
#     m = rmap(lambda x: x * 2, c)
#     idx = [random.randint(0, n) for _ in range(25)]
#     assert all(v == data[i] * 2 for v, i in zip(m[idx], idx))

class CustomException(Exception):
    pass


def test_rmap_exceptions():
    def do(x):
        del x
        raise CustomException

    data = [random.random() for _ in range(100)]
    m = rmap(do, data)
    with pytest.raises(CustomException):
        print(m[0])


def test_rimap_basics():
    n = 100

    class Iterable:  # expose data only through iteration
        def __init__(self, data):
            self.data = data

        def __iter__(self):
            for x in self.data:
                yield x

    data = [Iterable([random.random() for _ in range(random.randint(1, 100))])
            for _ in range(n - 1)]
    data.append(Iterable([]))  # one extreme case with empty sequence

    m = rimap(lambda x: x + 1, data)
    assert(len(m) == n)
    for i in range(n):
        itdata = iter(data[i])
        itm = iter(m[i])
        for _ in range(len(data[i].data)):
            x = next(itdata)
            y = next(itm)
            assert y == x + 1

        try:
            next(itm)
            assert False
        except StopIteration:
            pass


def test_rrmap_basics():
    n = 100

    data = [[random.random() for _ in range(random.randint(1, 100))]
            for _ in range(n - 1)]
    data.append([])  # one extreme case with empty sequence

    m = rrmap(lambda x: x + 1, data)
    for i in range(n):
        mi = m[i]
        di = data[i]
        assert len(data[i]) == len(mi)
        assert all(y == x + 1 for y, x, in zip(mi, di))
