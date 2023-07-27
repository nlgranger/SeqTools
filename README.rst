.. image:: https://badge.fury.io/py/SeqTools.svg
   :target: https://pypi.org/project/SeqTools
   :alt: PyPi package
.. image:: https://readthedocs.org/projects/seqtools-doc/badge
   :target: http://seqtools-doc.readthedocs.io
   :alt: Documentation

SeqTools
========

SeqTools extends the functionalities of itertools to indexable (list-like)
objects. Some of the provided functionalities include: element-wise function
mapping, reordering, reindexing, concatenation, joining, slicing, minibatching,
`etc <https://seqtools-doc.readthedocs.io/en/stable/reference.html>`_.

SeqTools functions implement **on-demand evaluation** under the hood:
operations and transformations are only applied to individual items when they
are actually accessed. A simple but powerful prefetch function is also provided
to eagerly evaluate elements in background threads or processes.

SeqTools originally targets data science, more precisely the data preprocessing
stages. Being aware of the experimental nature of this usage,
on-demand execution is made as transparent as possible by providing
**fault-tolerant functions and insightful error message**.

Example
-------

>>> def count_lines(filename):
...     with open(filename) as f:
...         return len(f.readlines())
>>>
>>> def count_words(filename):
...     with open(filename) as f:
...         return len(f.read().split())
>>>
>>> filenames = ["a.txt", "b.txt", "c.txt", "d.txt"]
>>> lc = seqtools.smap(count_lines, filenames)
>>> wc = seqtools.smap(count_words, filenames)
>>> counts = seqtools.collate([lc, wc])
>>> # no computations so far!
>>> lc[2]  # only evaluates on index 2
3
>>> counts[1]  # same for index 1
(1, 2)

Batteries included!
-------------------

The library comes with a set of functions to manipulate sequences:

.. |concatenate| image:: docs/_static/concatenate.svg

.. _concatenate: https://seqtools-doc.readthedocs.io/en/stable/reference.html#seqtools.concatenate

.. |batch| image:: docs/_static/batch.svg

.. _batch: https://seqtools-doc.readthedocs.io/en/stable/reference.html#seqtools.batch

.. |gather| image:: docs/_static/gather.svg

.. _gather: https://seqtools-doc.readthedocs.io/en/stable/reference.html#seqtools.gather

.. |prefetch| image:: docs/_static/prefetch.svg

.. _prefetch: https://seqtools-doc.readthedocs.io/en/stable/reference.html#seqtools.prefetch

.. |interleave| image:: docs/_static/interleave.svg

.. _interleave: https://seqtools-doc.readthedocs.io/en/stable/reference.html#seqtools.interleave

.. |uniter| image:: docs/_static/uniter.svg

.. _uniter: https://seqtools-doc.readthedocs.io/en/stable/reference.html#seqtools.uniter

+-------------------+---------------+
| `concatenate`_    | |concatenate| |
+-------------------+---------------+
| `batch`_          | |batch|       |
+-------------------+---------------+
| `gather`_         | |gather|      |
+-------------------+---------------+
| `prefetch`_       | |prefetch|    |
+-------------------+---------------+
| `interleave`_     | |interleave|  |
+-------------------+---------------+
| `uniter`_         | |uniter|      |
+-------------------+---------------+

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
its default behaviour and applies at all layers of a transformation pipeline.
Eager evaluation of elements in SeqTools does not break the list-like interface
and can be used in the middle of a transformation pipeline.

SeqTools is conceived to connect nicely to the data loading pipeline of Machine
Learning libraries such as PyTorch's `torch.utils.data
<http://pytorch.org/docs/master/data.html>`_ and `torchvision.transforms
<http://pytorch.org/docs/master/torchvision/transforms.html>`_ or Tensorflow's
`tf.data <https://www.tensorflow.org/guide/datasets>`_. The interface of these
libraries focuses on `iterators
<https://docs.python.org/3/library/stdtypes.html#iterator-types>`_ to access
transformed elements, contrary to SeqTools which also provides arbitrary reads
via indexing.
