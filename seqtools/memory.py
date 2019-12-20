import sys
import collections
from functools import singledispatch


def packed_size(value):
    if isinstance(value, dict):
        return sum(map(packed_size, value.values()))
    elif isinstance(value, tuple):
        return sum(map(packed_size, value))
    try:
        return memoryview(value).nbytes
    except TypeError:
        pass

    raise ValueError("unsupported value type")


@singledispatch
def pack(data, buffer, offset=0):
    raise TypeError("unsupported data type: {}".format(type(data)))


@pack.register(dict)
def _(data, buffer, offset=0):
    for _, v in sorted(data.items()):
        offset = pack(v, buffer, offset)

    return offset


@pack.register(tuple)
def _(data, buffer, offset=0):
    for v in data:
        offset = pack(v, buffer, offset)

    return offset


@singledispatch
def unpack(model, buffer, offset=0):
    raise TypeError("unsupported model type: {}".format(type(model)))


@unpack.register(dict)
def _(model, buffer, offset=0):
    out = {}
    for k, v in sorted(model.items()):
        out[k], offset = unpack(v, buffer, offset)
    return out, offset


@unpack.register(tuple)
def _(model, buffer, offset=0):
    out = []
    for m in model:
        v, offset = unpack(m, buffer, offset)
        out.append(v)
    return tuple(out), offset


try:
    import numpy as np
except ImportError:
    pass
else:
    @unpack.register(np.ndarray)
    def _(model, buffer, offset=0):
        out = np.frombuffer(buffer, dtype=model.dtype, count=model.size, offset=offset)
        out = out.reshape(model.shape)
        return out, offset + out.nbytes

    @pack.register(np.ndarray)
    def _(data, buffer, offset=0):
        out = np.frombuffer(buffer, dtype=data.dtype, count=data.size, offset=offset)
        out = out.reshape(data.shape)
        out[:] = data
        return offset + out.nbytes
