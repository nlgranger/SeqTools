Dataloader
==========

This example shows how to re-implement Pytorch `Dataloader <https://pytorch.org/docs/stable/data.html#torch.utils.data.DataLoader>`_
using Seqtools. The dataloader is an iterable objects that wraps an indexable dataset
adding shuffling, batching, prefetching and a few other operations relevant for
a Neural Network training pipeline.

For the sake of clarity, this version does not support iterable datasets or infinite
samplers because it would require to generate shuffling indices on the go which is not
easily done with prefetch.
This limitation may be circumvented by writing a different pre-fetching logic that
handles a custom iterator-based index order.
This would actually be fairly easy since the whole multi-process computation lies in a
separate class and can be reused.

.. literalinclude:: dataloader.py