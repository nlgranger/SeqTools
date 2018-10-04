import random
import pytest
from seqtools import smap, starmap, EvaluationError, seterr


def test_smap_basics():
    n = 100
    data = [random.random() for _ in range(n)]

    def do(x):
        do.call_cnt += 1
        return x + 1

    do.call_cnt = 0

    # indexing
    result = smap(do, data)
    assert len(result) == len(data)
    assert do.call_cnt == 0
    assert list(result) == [x + 1 for x in data]
    assert do.call_cnt == n
    assert [result[i] for i in range(len(result))] == [x + 1 for x in data]
    assert list(result[:]) == [x + 1 for x in data]


class CustomException(Exception):
    pass


@pytest.mark.parametrize('evaluation', ['wrap', 'passthrough'])
def test_smap_exceptions(evaluation):
    def do(x):
        del x
        raise CustomException

    data = [random.random() for _ in range(100)]
    m = smap(do, data)

    seterr(evaluation)
    error_t = EvaluationError if evaluation == "wrap" else CustomException

    with pytest.raises(error_t):
        print(m[0])

    with pytest.raises(error_t):
        next(iter(m))

    with pytest.raises(TypeError):
        smap(None, data)

    with pytest.raises(ValueError):
        smap(do)


def test_starmap():
    n = 100
    data = [(random.random(),) for _ in range(n)]

    def do(x):
        do.call_cnt += 1
        return x + 1

    do.call_cnt = 0

    # indexing
    result = starmap(do, data)
    assert len(result) == len(data)
    assert do.call_cnt == 0
    assert list(result) == [x + 1 for (x,) in data]
    assert do.call_cnt == n
    assert [result[i] for i in range(len(result))] == [x + 1 for (x,) in data]
    assert list(result[:]) == [x + 1 for (x,) in data]
