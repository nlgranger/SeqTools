SeqTools
========

.. toctree::
   :hidden:
   :includehidden:

   installation
   tutorial
   reference
   examples


.. testsetup::

   import seqtools
   import time


SeqTools facilitates the manipulation of datasets and the evaluation of a
transformation pipeline. Some of the provided functionnalities include: mapping
element-wise operations, reordering, reindexing, concatenation, joining,
slicing, minibatching, etc...

To improve ease of use, SeqTools assumes that dataset are objects that implement
a list-like `sequence <https://docs.python.org/3/glossary.html#term-sequence>`_
interface: a container object with a length and its *elements accessible via
indexing or slicing*. All SeqTools functions take and return objects compatible
with this simple and convenient interface.

Sometimes manipulating a whole dataset with transformations or combinations can
be slow and resource intensive; a transformed dataset might not even fit into
memory! To circumvent this issue, SeqTools implements *on-demand* execution
under the hood, so that computations and memory resources are always kept to a
bare minimum: accessing one element only takes the memory resources needed for
that element (ignoring the rest of the dataset), and computations are only run
when that element is requested. This helps to quickly define dataset-wide
transformations and probe a few results for debugging or prototyping purposes.

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

When comes the transition from prototyping to execution, the list-like container
interface facilitates serial evaluation. Besides, SeqTools also provides simple
helpers to dispatch work between multiple workers, and therefore to maximize
execution speed and resource usage.

SeqTools originally targets data science, more precisely the preprocessing
stages of a dataset. In particular, it is meant to connect nicely to the input
pipeline of Machine Learning libraries. However, this project purposedly keeps a
generic interface and only requires minimal dependencies to facilitate
reusability. Moreover, a particular attention was given to prototyping and
debugging usages: the code is kept concise and clear with internal documentation
to facilitate error investigation of faulty transformation pipelines. On-demand
execution is made as transparent as possible to users by providing
fault-tolerant functions and insightful error reporting.


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
>>> data = list(range(1000))

Without delayed evaluation, defining the pipeline and reading values looks like
so:

>>> tmp1 = [f1(x) for x in data]
>>> tmp2 = [f2(x) for x in tmp1]  # takes 10 seconds and a lot of memory
>>> res = [f3(x) for x in tmp2]
>>> print(res[2])
3.0
>>> print(max(tmp2[2]))  # requires to store 499 500 useless values along
3

With seqtools:

>>> tmp1 = seqtools.smap(f1, data)
>>> tmp2 = seqtools.smap(f2, tmp1)
>>> res = seqtools.smap(f3, tmp2)  # no computations so far
>>> print(res[2])  # takes 0.01 seconds
3.0
>>> print(max(tmp2[2]))  # easy access to intermediate results
3


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


Related libraries
-----------------

These libaries provide comparable functionalities, but for iterable containers
only, they should plug easily above a SeqTool based preprocessing pipeline:

- `torchvision.transforms
  <http://pytorch.org/docs/master/torchvision/transforms.html>`_
  and `torch.utils.data <http://pytorch.org/docs/master/data.html>`_.
- `TensorPack <https://github.com/tensorpack/tensorpack>`_
