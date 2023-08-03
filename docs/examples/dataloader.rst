DataLoader
==========

This example shows how to re-implement Pytorch `DataLoader <https://pytorch.org/docs/stable/data.html#torch.utils.data.DataLoader>`_
using Seqtools. The DataLoader is an iterable objects that wraps an indexable dataset
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

Sample usage:

.. testsetup::
   :skipif: torch is None

   import sys
   sys.path.append("docs/examples")
   from dataloader import DataLoader

.. testcode::
   :skipif: torch is None

   import torch
   from torchvision.datasets import FakeData
   from torchvision import transforms as T

   transform = T.Compose([
       T.Resize((256, 256)),
       T.ColorJitter(),
       T.RandomHorizontalFlip(),
       T.ToTensor(),
       T.ConvertImageDtype(torch.float),
   ])
   dataset = FakeData(100, (320, 320), 10, transform=transform)

   DataLoader = DataLoader(
       dataset,
       num_workers=2,
       batch_size=8,
       shm_size=16777216,  # 16MB
   )
   for images, labels in DataLoader:
       pass
