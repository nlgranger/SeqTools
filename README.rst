.. image:: https://badge.fury.io/py/seqtools.svg
   :target: https://badge.fury.io/py/seqtools
   :alt: PyPi package
.. image:: https://travis-ci.org/nlgranger/SeqTools.svg?branch=master
   :target: https://travis-ci.org/nlgranger/SeqTools
   :alt: Continuous integration
.. image:: https://readthedocs.org/projects/seqtools-doc/badge
   :target: http://seqtools-doc.readthedocs.io
   :alt: Documentation
.. image:: https://api.codacy.com/project/badge/Grade/f5324dc1e36d46f7ae1cabaaf6bce263
   :target: https://www.codacy.com/app/nlgranger/SeqTools?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=nlgranger/SeqTools&amp;utm_campaign=Badge_Grade
   :alt: Code quality analysis
.. image:: https://codecov.io/gh/nlgranger/SeqTools/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/nlgranger/SeqTools
   :alt: Tests coverage
.. image:: http://joss.theoj.org/papers/527a3c6e78ef0b31f93bbd29235d5a0b/status.svg
   :target: http://joss.theoj.org/papers/527a3c6e78ef0b31f93bbd29235d5a0b
   :alt: Citable paper

SeqTools
========

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
under the hood, so that computations are only run when needed, and only for
actually required elements while ignoring the rest of the dataset. This helps to
keep memory resources down to a bare minimum and accelerate the time it take to
access any arbitrary result. This on-demand strategy helps to quickly define
dataset-wide transformations and probe a few results for debugging or
prototyping purposes, yet it is transparent for the users who still benefit from
a simple and convenient list-like interface.

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
helpers to dispatch work between multiple background workers (threads or
processes), and therefore to maximize execution speed and resource usage.

SeqTools originally targets data science, more precisely the preprocessing
stages of a dataset. Being aware of the experimental nature of this usage,
on-demand execution is made as transparent as possible to users by providing
fault-tolerant functions and insightful error reporting. Moreover, internal code
is kept concise and clear with comments to facilitate error tracing through a
failing transformation pipeline.

Nevertheless, this project purposedly keeps a generic interface and only
requires minimal dependencies in order to facilitate reusability beyond this
scope of application.


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

.. |concatenate| image:: docs/_static/concatenate.png

.. _concatenation: reference.html#seqtools.concatenate

.. |batch| image:: docs/_static/batch.png

.. _batching: reference.html#seqtools.batch

.. |gather| image:: docs/_static/gather.png

.. _reindexing: reference.html#seqtools.gather

.. |prefetch| image:: docs/_static/prefetch.png

.. _prefetching: reference.html#seqtools.prefetch

.. |interleaving| image:: docs/_static/interleaving.png

.. _interleaving: reference.html#seqtools.interleave

==================== ================= ===============
| `concatenation`_   | `batching`_     | `reindexing`_
| |concatenate|      | |batch|         | |gather|
| `prefetching`_     | `interleaving`_
| |prefetch|         | |interleaving|
==================== ================= ===============

and others (suggestions are also welcome).


Installation
------------

.. code-block:: bash

   pip install seqtools


Documentation
-------------

The documentation is hosted at `https://seqtools-doc.readthedocs.io
<https://seqtools-doc.readthedocs.io>`_.


Contributing and Support
------------------------

Use the `issue tracker <https://github.com/nlgranger/SeqTools/issues>`_
to request features, propose improvements or report issues. For questions
regarding usage, please send an `email
<mailto:3764009+nlgranger@users.noreply.github.com>`_.


Related libraries
-----------------

`Joblib <https://joblib.readthedocs.io>`_, proposes low-level functions with
many optimization settings to optimize pipelined transformations. This library
notably provides advanced caching mechanisms which are not the primary concern
of SeqTool. SeqTool uses a simpler container-oriented interface with multiple
utility functions in order to assist fast prototyping. On-demand evaluation is
its default behaviour and applies at all layers of a transformation pipeline. In
particular, parallel evaluation can be inserted in the middle of the
transformation pipeline and won't block the execution to wait for the
computation of all elements from the dataset.

SeqTools is conceived to connect nicely to the data loading pipeline of Machine
Learning libraries such as PyTorch's `torch.utils.data
<http://pytorch.org/docs/master/data.html>`_ and `torchvision.transforms
<http://pytorch.org/docs/master/torchvision/transforms.html>`_ or Tensorflow's
`tf.data <https://www.tensorflow.org/guide/datasets>`_. The interface of these
libraries focuses on `iterators
<https://docs.python.org/3/library/stdtypes.html#iterator-types>`_ to access
transformed elements, contary to SeqTools which also provides arbitrary reads
via indexing.
