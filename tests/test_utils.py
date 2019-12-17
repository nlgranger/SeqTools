from seqtools.utils import SeqSlice


def test_slice():
    arr = list(range(100))

    keys = [
        slice(None, None, None),
        slice(None, -10, None),
        slice(0, 0, 1),
        slice(0, 10, -1),
        slice(10, 0, -1),
        slice(250, -125, -1)]

    for k in keys:
        v = SeqSlice(arr, k)
        assert list(v) == arr[k]
        assert list(iter(v)) == arr[k]
        assert [v[i] for i in range(len(v))] == arr[k]

    v = SeqSlice(arr, slice(3, -25, 4))[14:1:-2]
    assert list(v) == arr[3:-25:4][14:1:-2]
    assert id(v.sequence) == id(arr)

    arr2 = list(arr)
    v = SeqSlice(arr2, slice(25, 37, 3))
    v[1] = -1
    assert arr2[:28] == arr[:28]
    assert arr2[28] == -1
    assert arr2[29:] == arr[29:]

    arr2 = list(arr)
    arr3 = list(arr)
    v = SeqSlice(arr2, slice(25, 37, 3))
    v[1:-1] = [-1, -2]
    arr3[28:34:3] = [-1, -2]
    assert arr2 == arr3
