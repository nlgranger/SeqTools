from random import random, randint
from lproc import collate, concatenate
import pytest


def test_collate():
    arrs = [[random() for _ in range(100)] for _ in range(3)]
    collated = collate(arrs)
    assert list(iter(collated)) == list(zip(*arrs))
    assert [collated[i] for i in range(len(collated))] == list(zip(*arrs))
    assert list(collated[:-5]) == list(zip(*arrs))[:-5]

    arrs.append([])
    with pytest.raises(ValueError):
        collate(arrs)


def test_concatenate():
    arrs = [[random() for _ in range(randint(100, 200))] for _ in range(5)]
    concatenated = concatenate(arrs)
    assert list(concatenated) == [x for a in arrs for x in a]

    arrs.append([1, 2, 3, 4, 5])
    extra_concatenated = concatenate([concatenated, [1, 2, 3, 4, 5]])
    assert list(extra_concatenated) == [x for a in arrs for x in a]
    assert len(extra_concatenated.sequences) == 6

    assert list(extra_concatenated[250:]) == [x for a in arrs for x in a][250:]
