"""A reimplementeation of PyTorch's DataLoader to showcase seqtools."""

import functools
import mmap
import numbers
import struct

import numpy as np
import torch
import seqtools


def into_tensors(value):
    """Convert arrays inside an object into tensors."""
    if isinstance(value, np.ndarray):
        return torch.from_numpy(value)
    elif isinstance(value, tuple):
        return tuple(into_tensors(v) for v in value)
    elif isinstance(value, list):
        return [into_tensors(v) for v in value]
    elif isinstance(value, dict):
        return {k: into_tensors(v) for k, v in value.items()}
    else:
        return torch.tensor(value)


def pin_tensors_memory(value):
    """Pin memory of tensors inside an object."""
    if isinstance(value, tuple):
        return tuple(pin_tensors_memory(v) for v in value)
    elif isinstance(value, list):
        return [pin_tensors_memory(v) for v in value]
    elif isinstance(value, dict):
        return {k: pin_tensors_memory(v) for k, v in value.items()}
    elif isinstance(value, torch.Tensor):
        return value.pin_memory()


class NDStack:
    """A list of arrays that should be stacked.

    Allows to skip a useless stack operation prior to packing. Instead,
    NDStack items will be packed consecutively and unpacked as a single
    array.
    """
    def __init__(self, *kargs, **kwargs):
        self.values = list(*kargs, **kwargs)

        if len(self.values) == 0:
            raise ValueError("NDStack requires at least one item")
        if any(v.shape != self.values[0].shape for v in self.values):
            raise ValueError("All items must have the same shape")
        if any(v.dtype != self.values[0].dtype for v in self.dtype):
            raise ValueError("All items must have the same type")

        self.dtype = self.values[0].dtype
        self.nbytes = len(self.values) * self.values[0].nbytes
        self.shape = (len(self.values),) + self.values[0].shape
        self.ndim = len(self.values[0].shape) + 1

    def __len__(self):
        return len(self.values)

    def __getitem__(self, item):
        return self.values[item]

    def __iter__(self):
        return iter(self.values)


# Monkey patch seqtools.memory to support NDStack

@seqtools.memory.pack_model.register(NDStack)
def _(value):
    model = NDStack([seqtools.memory.MockNDArray(value[0])] * len(value))
    ndim = value[0].ndim + 1
    nbytes = struct.calcsize("{}L".format(ndim)) + model.nbytes
    return model, nbytes


@seqtools.memory.pack.register(NDStack)
def _(model, data, buffer, offset=0):
    if not isinstance(data, NDStack):
        raise TypeError("expected NDStack but got " + str(data.__class__))
    if model.dtype != data.dtype or model.ndim != data.ndim:
        raise ValueError("value and model[0] type mismatch")
    if model.shape < data.shape or model.ndim < data.ndim:
        raise ValueError("incompatible value and model[0] shape: "
                         "expected {} but got {}".format(model.shape, data.shape))

    ndim = data[0].ndim + 1
    struct.pack_into("{}L".format(ndim), buffer, offset, len(data), *data[0].shape)
    offset = offset + struct.calcsize("{}L".format(ndim))

    for d in data:
        b = np.frombuffer(buffer[offset:offset + d.nbytes], d.dtype).reshape(d.shape)
        b[:] = d
        offset += d.nbytes

    return offset


seqtools.memory.unpack.register(NDStack)(seqtools.memory.unpack.dispatch(np.ndarray))


def default_collate_fn(values, fake_stack=False):
    """Stack samples together into a minibatch while preserving data structure.

    This function also handles NDStack values to optimize out stacking
    operations.
    """
    if not isinstance(values, list):  # force evaluation if not done already
        values = list(values)

    sample = values[0]

    if isinstance(sample, torch.Tensor):
        return torch.stack(values)

    elif isinstance(sample, np.ndarray):
        if fake_stack and len(set(v.shape for v in values)) == 1:
            return NDStack(values)
        else:
            np.stack(values)

    elif isinstance(sample, numbers.Integral):
        return np.array(values)

    elif isinstance(sample, tuple):
        return tuple(default_collate_fn(row, fake_stack) for row in zip(*values))

    elif isinstance(sample, list):
        return [default_collate_fn(row, fake_stack) for row in zip(*values)]

    elif isinstance(sample, dict):
        return {k: default_collate_fn([v[k] for v in values], fake_stack)
                for k in values[0].keys()}


class DataLoader:
    def __init__(self, dataset, batch_size=1, shuffle=False, num_workers=0,
                 collate_fn=None, pin_memory=False, drop_last=False,
                 worker_init_fn=None, max_buffered=None):
        """Re-implementation of pytorch Dataloader using seqtools.

        Notable differences:

        - all dataset elements must have the same structure
        - custom samplers are not implemented
        - timeout is irrelevant
        - a single shared buffer is used by all workers to write
          their output, max_buffered specifies how many items this buffer
          can hold.
        """
        if num_workers > 0 and collate_fn is None:
            collate_fn = functools.partial(default_collate_fn, fake_stack=True)
        elif collate_fn is None:
            collate_fn = default_collate_fn
        if max_buffered is None:
            max_buffered = num_workers + 5

        # shuffle
        if shuffle:
            self.shuffling_indexes = np.frombuffer(
                mmap.mmap(-1, np.dtype('uint32').itemsize * len(dataset)),
                dtype=np.uint32)
            self.shuffling_indexes[:] = np.arange(len(dataset))
            dataset = seqtools.gather(dataset, self.shuffling_indexes)
        else:
            self.shuffling_indexes = None

        # batch
        if batch_size is not None:
            dataset = seqtools.batch(
                dataset,
                k=batch_size, drop_last=drop_last,
                collate_fn=collate_fn)

        # prefetch
        if num_workers > 0:
            dataset = seqtools.prefetch(
                dataset,
                max_buffered=max_buffered, nworkers=num_workers,
                method='sharedmem',
                start_hook=worker_init_fn)

        # convert into tensors
        dataset = seqtools.smap(into_tensors, dataset)

        # pin memory
        if pin_memory:
            dataset = seqtools.smap(pin_tensors_memory, dataset)
            dataset = seqtools.prefetch(
                dataset, nworkers=1, method='thread', max_buffered=1)

        self.dataset = dataset

    def __len__(self):
        return len(self.dataset)

    def __iter__(self):
        if self.shuffling_indexes is not None:
            np.random.shuffle(self.shuffling_indexes)

        return iter(self.dataset)
