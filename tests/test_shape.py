from random import random, randint
from lproc import collate, concatenate, batches
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

    arrs1 = [list(range(i, i + 25)) for i in range(0, 101, 25)]
    arrs2 = [list(range(i, i + 25)) for i in range(0, 101, 25)]
    concatenated = concatenate(arrs1)
    for j, i in enumerate(range(0, 101, 25)):
        concatenated[i:i+10] = range(-i, -i - 10, -1)
        arrs2[j][:10] = range(-i, -i - 10, -1)
    assert arrs1 == arrs2



def test_blockview():
    arr = list(range(137))

    chunked = list(batches(arr, 5, True))
    expected = [[i + k for k in range(5)] for i in range(0, 135, 5)]
    assert chunked == expected

    chunked = list(batches(arr, 5, False))
    expected = [[i + k for k in range(5)] for i in range(0, 135, 5)] \
               + [[135, 136]]
    assert chunked == expected

    chunked = list(batches(arr, 5, pad=0, collate_fn=list))
    expected = [[i + k for k in range(5)] for i in range(0, 135, 5)] \
        + [[135, 136, 0, 0, 0]]
    assert chunked == expected

    chunked = batches(arr, 5, pad=0, collate_fn=list)
    chunked[:1] = [[-1, -2, -3, -4, -5]]
    assert arr == [-1, -2, -3, -4, -5] + list(range(5, 137))
