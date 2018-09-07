.. image:: https://badge.fury.io/py/seqtools.svg
   :target: https://badge.fury.io/py/seqtools
.. image:: https://travis-ci.org/nlgranger/SeqTools.svg?branch=master
   :target: https://travis-ci.org/nlgranger/SeqTools
.. image:: https://readthedocs.org/projects/seqtools-doc/badge
   :target: http://seqtools-doc.readthedocs.io
.. image:: https://api.codacy.com/project/badge/Grade/f5324dc1e36d46f7ae1cabaaf6bce263
   :target: https://www.codacy.com/app/nlgranger/SeqTools?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=nlgranger/SeqTools&amp;utm_campaign=Badge_Grade
.. image:: https://codecov.io/gh/nlgranger/SeqTools/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/nlgranger/SeqTools


SeqTools
========

SeqTools is designed to facilitate the manipulation and transformation of
datasets in the form of indexable sequences, that is to say python lists,
arrays, numpy arrays, or anything that supports :code:`dataset[i]`.
It supports many operations such as element-wise transformations, combinations,
reordering, etc. all of which are commonly found in the preprocessing
steps of data science projects.

During the design and debugging stage of a transformation pipeline, it is
convenient to have fast access to individual outputs and intermediate results.
However, it is also convenient to manipulate the whole datasets as
self-contained objects that can be moved around and passed to other module (for
example to a Machine Learning training routine). This library bridges the gap
between these two aspects by providing sequence-wide transformations with
on-demand element-wise evaluation, it removes the transitions between
prototyping, executing and debugging which are cumbersome and error-prone.

The functions of this library are transparent to the user: they take list-like
objects and return list-like objects with the desired transformation applied,
but the computations actually only run for requested items when needed.
Transformations can therefore be defined easily and tested quickly for
individual elements. Most operations return containers that even support
supports *slice based indexing* and assignment* so that you can forget you are
not working with lists directly!

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
>>> for v in m[:-2]:
...     print(v)
-> computing now
3
-> computing now
4

Because of delayed execution, intermediate values for chained transformations
need not be computed and stored unless explicitly required, as a result:

- a full transformation pipeline is setup without delay
- individual outputs can be computed without running unnecessary computations
  for other items, and without storing intermediate results.
- intermediate transformation values remain easily accessible for testing


Example
-------

>>> def f1(x):
...     return x + 1
...
>>> def f2(x):  # slow and memory heavy transformation
...     time.sleep(.01)
...     return [x for _ in range(500)]
...
>>> def f3(x):
...     return sum(x) / len(x)
...
>>> arr = list(range(1000))

Without delayed evaluation, defining the pipeline and reading values looks like
so:

>>> tmp1 = [f1(x) for x in arr]
>>> tmp2 = [f2(x) for x in tmp1]  # takes 10 seconds and a lot of memory
>>> res = [f3(x) for x in tmp2]
>>> print(res[2])
3.0
>>> print(max(tmp2[2]))  # requires to store 499 500 useless values along
3

With seqtools:

>>> tmp1 = seqtools.smap(f1, arr)
>>> tmp2 = seqtools.smap(f2, tmp1)
>>> res = seqtools.smap(f3, tmp2)  # no computations so far
>>> print(res[2])  # takes 0.01 seconds
3.0
>>> print(max(tmp2[2]))  # easy access to intermediate results
3

The code in SeqTool is designed to keep a low overhead and can scale to high
throughput using multi-processing or multi-threading with background worker
for concurrent execution.


Batteries included!
-------------------

The library comes with a set of functions to manipulate sequences:

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
| `concatenation`_   | `batching`_     | `reindexing`_
| |concatenate|      | |batch|         | |gather|
| `prefetching`_     | `interleaving`_
| |prefetch|         | |interleaving|
==================== ================= ===============

... and others (suggestions are also welcome).


Installation
------------

.. code-block:: bash

   pip install seqtools


Documentation
-------------

The documentation is hosted at https://seqtools-doc.readthedocs.io


Related libraries
-----------------

These libaries provide comparable functionalities, but for iterable containers
only:

- `torchvision.transforms
  <http://pytorch.org/docs/master/torchvision/transforms.html>`_
  and `torch.utils.data <http://pytorch.org/docs/master/data.html>`_.
- `TensorPack <https://github.com/tensorpack/tensorpack>`_
