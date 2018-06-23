SeqTools
========

.. toctree::
   :hidden:
   :includehidden:

   installation
   tutorial
   reference
   examples
   internal


.. testsetup::

   from __future__ import print_function
   import seqtools
   import time


TLDR; Like python's itertools but for sequences.

This library is designed to facilitate the manipulation and transformation of
sequences (anything that supports indexing such as lists, arrays, etc.). It was
concieved with **delayed evaluation** in mind to help setup and test chained
transformation pipelines very quickly like views in numpy but more flexible.

It supports **slice based indexing** and **assignment** when possible so that
you can forget that you are not working with lists directly! Finally it features
**prefetching** with either threads or processes to maximize computation speed.

Delayed (aka lazy or ondemand) evaluation is easily understood by looking at
this example:

>>> def do(x):
...     print("-> computing now")
...     return x + 2
...
>>> a = [1, 2, 3, 4]
>>> m = seqtools.smap(do, a)
>>> # nothing printed because evaluation is delayed
>>> m[0]
-> computing now
3

Because of delayed execution, intermediate values for chained transformations
need not be computed and stored unless explicitly required. As a result:

- a full transformation pipeline is setup without delay
- end-results can be computed without running unnecessary computations for
  other items and without storing intermediate results.
- yet intermediate transformation values remain easily accessible for testing

>>> def f1(x):
...     return x + 1
...
>>> def f2(x):
...     # This is slow and memory heavy
...     time.sleep(.01)
...     return [x + i for i in range(500)]
...
>>> def f3(x):
...     return sum(x) / len(x)
...
>>> arr = list(range(1000))

Without delayed evaluation, defining the pipeline and reading values look
like so:

>>> tmp1 = [f1(x) for x in arr]
>>> tmp2 = [f2(x) for x in tmp1]  # takes 10 seconds and a lot of memory
>>> res = [f3(x) for x in tmp2]
>>> print(res[2])
252.5
>>> print(max(tmp2[2]))  # requires to store 499 500 useless values along
502

With seqtools:

>>> tmp1 = seqtools.smap(f1, arr)
>>> tmp2 = seqtools.smap(f2, tmp1)
>>> res = seqtools.smap(f3, tmp2)
>>> print(res[2])  # takes 0.01 seconds
252.5
>>> print(max(tmp2[2]))  # it's still possible to probe intermediate values
502


Batteries included!
-------------------

The library comes with a set of helper functions to help manipulate sequences:

.. |concatenate| image:: _static/concatenate.png

.. _concatenation: reference.html#seqtools.concatenate

.. |batch| image:: _static/batch.png

.. _batching: reference.html#seqtools.batch

.. |gather| image:: _static/gather.png

.. _reindexing: reference.html#seqtools.gather

.. |prefetch| image:: _static/prefetch.png

.. _prefetching: reference.html#seqtools.prefetch

.. |interleaving| image:: _static/interleaving.png

.. _interleaving: reference.html#seqtools.interleave

==================== ================= ===============
| |concatenate|      | |batch|         | |gather|
| `concatenation`_   | `batching`_     | `reindexing`_
| |prefetch|         | |interleaving|
| `prefetching`_     | `interleaving`_
==================== ================= ===============

... and others (suggestions are also welcome).


Similar libraries
-----------------

These libaries provide comparable functionalities, but mostly for iterable containers:

- `torchvision.transforms <http://pytorch.org/docs/master/torchvision/transforms.html>`_
  and `torch.utils.data <http://pytorch.org/docs/master/data.html>`_.
- `TensorPack <https://github.com/tensorpack/tensorpack>`_
