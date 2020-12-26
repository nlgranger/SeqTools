"""An implementation of PyTorch's DataLoader to showcase seqtools."""

import copyreg
import numbers

import numpy as np
import torch

import seqtools


# overload torch.Tensor pickling to benefit from zero copy on buffer
def pickle_tensor(t: torch.Tensor):
    return torch.from_numpy, (t.numpy(),)


copyreg.pickle(torch.Tensor, pickle_tensor)


def into_tensors(value):
    """Convert arrays inside an object into tensors."""
    if isinstance(value, torch.Tensor):
        return value
    elif isinstance(value, np.ndarray):
        return torch.from_numpy(value)
    elif isinstance(value, (tuple, list)):
        return value.__class__(into_tensors(v) for v in value)
    elif isinstance(value, dict):
        return value.__class__((k, into_tensors(v)) for k, v in value.items())
    else:
        return torch.tensor(value)


def pin_tensors_memory(value):
    """Pin memory of tensors inside an object."""
    if isinstance(value, (tuple, list)):
        return value.__class__(pin_tensors_memory(v) for v in value)
    elif isinstance(value, dict):
        return value.__class__((k, pin_tensors_memory(v)) for k, v in value.items())
    elif isinstance(value, torch.Tensor):
        return value.pin_memory()


def default_collate_fn(values):
    """Stack samples together into a minibatch."""
    if not isinstance(values, list):  # force evaluation if not done already
        values = list(values)

    sample = values[0]

    if isinstance(sample, torch.Tensor):
        return torch.stack(values)
    elif isinstance(sample, np.ndarray):
        return np.stack(values)
    elif isinstance(sample, numbers.Integral):
        return torch.tensor(values)
    elif isinstance(sample, (tuple, list)):
        return sample.__class__(default_collate_fn(row) for row in zip(*values))
    elif isinstance(sample, dict):
        return sample.__class__(
            (k, default_collate_fn([v[k] for v in values]))
            for k in sample.keys())


class DataLoader:
    def __init__(
            self,
            dataset,
            batch_size=1,
            shuffle=False,
            sampler=None,
            batch_sampler=None,
            num_workers=0,
            collate_fn=None,
            pin_memory=False,
            drop_last=False,
            worker_init_fn=None,
            prefetch_factor=2,
            shm_size=None):
        """Re-implementation of pytorch Dataloader using seqtools.

        Notable differences:

        - only datasets and samplers with a len() are supported, and shuffling
          indices will be pre-computed before iterating.
        - shm_size specifies how much shared memory to allocate for zero-copy
          transfers between workers and the main process. That shared
          memory is divided into num_worker * prefetch_factor slots.
        - timeout is not implemented
        - a pool of shared memory with a fixed size (shm_size) is used for
          zero-copy buffer transfers from workers.
        """
        # sampling/batching
        self.dataset = dataset
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.sampler = sampler
        self.batch_sampler = batch_sampler
        self.num_workers = num_workers
        self.collate_fn = collate_fn or default_collate_fn
        self.pin_memory = pin_memory
        self.drop_last = drop_last
        self.worker_init_fn = worker_init_fn
        self.prefetch_factor = prefetch_factor
        self.shm_size = shm_size

    def __len__(self):
        if self.batch_sampler:
            return len(self.batch_sampler)
        dataset_size = len(self.sampler) if self.sampler else len(self.dataset)
        if self.batch_size and self.drop_last and dataset_size % self.batch_size > 0:
            return dataset_size // self.batch_size
        else:
            return dataset_size // self.batch_size + 1

    def make_sequence(self):
        """Build a sequence that looks like a dataloader when iterated over."""
        # shuffling
        if self.batch_sampler:
            batch_indices = list(self.batch_sampler)
            out = seqtools.smap(lambda bi: [self.dataset[i] for i in bi], batch_indices)
        elif self.sampler:
            shuffle_indices = list(self.sampler)
            out = seqtools.gather(self.dataset, shuffle_indices)
        elif self.shuffle:
            shuffle_indices = np.random.permutation(len(self.dataset))
            out = seqtools.gather(self.dataset, shuffle_indices)
        else:
            out = self.dataset

        # batch
        if not self.batch_sampler and self.batch_size is not None:
            out = seqtools.batch(
                out,
                k=self.batch_size, drop_last=self.drop_last,
                collate_fn=self.collate_fn)
        elif self.batch_sampler:
            out = seqtools.smap(self.collate_fn, out)

        # prefetch
        if self.num_workers > 0:
            out = seqtools.prefetch(
                out,
                max_buffered=self.num_workers * self.prefetch_factor,
                nworkers=self.num_workers,
                method='process',
                start_hook=self.worker_init_fn,
                shm_size=self.shm_size)

        # convert into tensors
        out = seqtools.smap(into_tensors, out)

        # pin memory
        if self.pin_memory:
            out = seqtools.smap(pin_tensors_memory, out)
            out = seqtools.prefetch(
                out, nworkers=1, method='thread', max_buffered=1)

        return out

    def __iter__(self):
        """Instantiate a new data pipeline and return an iterator over it."""
        return iter(self.make_sequence())
