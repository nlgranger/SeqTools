from random import random, randint
from seqtools import collate, concatenate, batch, unbatch, split
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


def test_batching():
    arr = list(range(137))

    chunked = list(batch(arr, 5, True))
    expected = [[i + k for k in range(5)] for i in range(0, 135, 5)]
    assert chunked == expected

    unchunked = list(unbatch(chunked, 5, 0))
    assert unchunked == [x for b in expected for x in b]

    chunked = list(batch(arr, 5, False))
    expected = [[i + k for k in range(5)] for i in range(0, 135, 5)] \
        + [[135, 136]]
    assert chunked == expected

    unchunked = [i for i in unbatch(chunked, 5, len(arr) % 5)]
    assert unchunked == [x for b in expected for x in b]

    chunked = list(batch(arr, 5, pad=0, collate_fn=list))
    expected = [[i + k for k in range(5)] for i in range(0, 135, 5)] \
        + [[135, 136, 0, 0, 0]]
    assert chunked == expected

    chunked = batch(arr, 5, pad=0, collate_fn=list)
    chunked[:1] = [[-1, -2, -3, -4, -5]]
    chunked[-1] = [-135, -136]
    assert arr == [-1, -2, -3, -4, -5] + list(range(5, 135)) + [-135, -136]


def test_split():
    arr = list(range(125))

    y = split(arr, 4)
    assert y[-1] == list(range(100, 125))
    assert list(y) == [list(range(i, i + 25)) for i in range(0, 125, 25)]

    y = split(arr, list(range(25, 125, 25)))
    assert y[-1] == list(range(100, 125))
    assert list(y) == [list(range(i, i + 25)) for i in range(0, 125, 25)]

    y = split(arr, [(i, i + 25) for i in range(0, 125, 25)])
    assert y[-1] == list(range(100, 125))
    assert list(y) == [list(range(i, i + 25)) for i in range(0, 125, 25)]

    y[-1] = [0] * 25
    assert arr[100:] == [0] * 25

    y[-1:] = [list(range(0, -25, -1))]
    assert arr[:100] == list(range(100))
    assert arr[100:] == list(range(0, -25, -1))
