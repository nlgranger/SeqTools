from functools import singledispatch


@singledispatch
def packed_size(value):
    raise TypeError("unsupported value type: {}".format(type(value)))


@singledispatch
def pack(data, buffer, offset=0):
    raise TypeError("unsupported data type: {}".format(type(data)))


@singledispatch
def unpack(model, buffer, offset=0):
    raise TypeError("unsupported model type: {}".format(type(model)))


# tuple

@packed_size.register(tuple)
def _(value):
    return sum(map(packed_size, value))


@pack.register(tuple)
def _(data, buffer, offset=0):
    for v in data:
        offset = pack(v, buffer, offset)

    return offset


@unpack.register(tuple)
def _(model, buffer, offset=0):
    out = []
    for m in model:
        v, offset = unpack(m, buffer, offset)
        out.append(v)
    return tuple(out), offset


# list

@packed_size.register(list)
def _(value):
    return sum(map(packed_size, value))


@pack.register(list)
def _(data, buffer, offset=0):
    for v in data:
        offset = pack(v, buffer, offset)

    return offset


@unpack.register(list)
def _(model, buffer, offset=0):
    out = []
    for m in model:
        v, offset = unpack(m, buffer, offset)
        out.append(v)
    return out, offset


# dict

@packed_size.register(dict)
def _(value):
    return sum(map(packed_size, value.values()))


@pack.register(dict)
def _(data, buffer, offset=0):
    for _, v in sorted(data.items()):
        offset = pack(v, buffer, offset)

    return offset


@unpack.register(dict)
def _(model, buffer, offset=0):
    out = {}
    for k, v in sorted(model.items()):
        out[k], offset = unpack(v, buffer, offset)
    return out, offset


try:
    import numpy as np
except ImportError:
    pass
else:
    @packed_size.register(np.ndarray)
    def _(value):
        return value.nbytes


    @unpack.register(np.ndarray)
    def _(model, buffer, offset=0):
        out = np.frombuffer(buffer, dtype=model.dtype, count=model.size, offset=offset)
        out = out.reshape(model.shape)
        return out, offset + out.nbytes


    @pack.register(np.ndarray)
    def _(data, buffer, offset=0):
        out = np.frombuffer(buffer, dtype=data.dtype, count=data.size, offset=offset)
        out[:] = data.ravel()
        return offset + out.nbytes
