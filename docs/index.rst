SeqTools
========

.. toctree::
   :hidden:
   :includehidden:
   :maxdepth: 2

   self
   installation
   tutorial
   reference
   examples
   PyPi <https://pypi.org/project/SeqTools>
   Repository <https://github.com/nlgranger/SeqTools>


.. testsetup::

   import time

   with open("a.txt", "w") as f:
      pass
   with open("b.txt", "w") as f:
      f.write("abc de")
   with open("c.txt", "w") as f:
      f.write("a\nb\nc")
   with open("d.txt", "w") as f:
      pass

.. testcleanup::

   import os

   os.remove("a.txt")
   os.remove("b.txt")
   os.remove("c.txt")
   os.remove("d.txt")


SeqTools extends the functionalities of itertools to indexable (list-like)
objects. Some of the provided functionalities include: element-wise function
mapping, reordering, reindexing, concatenation, joining, slicing, minibatching,
`etc <API Reference>`_.

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

.. |concatenate| image:: _static/concatenate.svg

.. _concatenate: reference.html#seqtools.concatenate

.. |batch| image:: _static/batch.svg

.. _batch: reference.html#seqtools.batch

.. |gather| image:: _static/gather.svg

.. _gather: reference.html#seqtools.gather

.. |prefetch| image:: _static/prefetch.svg

.. _prefetch: reference.html#seqtools.prefetch

.. |interleave| image:: _static/interleave.svg

.. _interleave: reference.html#seqtools.interleave

.. |uniter| image:: _static/uniter.svg

.. _uniter: reference.html#seqtools.uniter

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
