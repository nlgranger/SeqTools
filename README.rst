.. image:: https://api.travis-ci.org/nlgranger/LazyProc.svg
   :target: https://travis-ci.org/nlgranger/LazyProc
.. image:: https://readthedocs.org/projects/lazyproc/badge
   :target: https://lazyproc.readthedocs.io
.. image:: https://api.codacy.com/project/badge/Coverage/e76ddab290bb4d1689a6e27f47452bdb
   :target: https://www.codacy.com/app/nlgranger/LazyProc?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=nlgranger/LazyProc&amp;utm_campaign=Badge_Coverage
.. image:: https://api.codacy.com/project/badge/Grade/e76ddab290bb4d1689a6e27f47452bdb
   :target: https://www.codacy.com/app/nlgranger/LazyProc?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=nlgranger/LazyProc&amp;utm_campaign=Badge_Grade


LazyProc
========

TLDR; Like python's itertools but with lazy evaluation on indexable sequences.

This library provides simple helper functions for lazy evaluation of sequences
such as lists. It can be used to quickly design and evaluate chained
transformations pipelines.

Lazy evaluation is easily understood by looking an example:

>>> def do(x):
...     print("-> computing now")
...     return x + 2
...
>>> a = [1, 2, 3, 4]
>>> m = lproc.rmap(do, a)
>>> # nothing printed because evaluation is delayed
>>> m[0]
-> computing now
3

Because of delayed execution, intermediate values for chained transformations
need not be computed and stored unless explicitly required. As a result you
can evaluate a whole pipeline of transformations for each item without storing
intermediate results, but you can also probe intermediate values to test
your pipeline.

>>> def f1(x):
...     return x + 1
...
>>> def f2(x):
...     # This is slow and memory heavy
...     return [x + i for i in range(500)]
...
>>> def f3(x):
...     return sum(x) / len(x)
...
>>> arr = list(range(5000))

Defining and using the pipeline:

>>> tmp1 = lproc.rmap(f1, arr)
>>> tmp2 = lproc.rmap(f2, tmp1)
>>> res = lproc.rmap(f3, tmp2)
>>> print(res[2])  # request output for a single value
252.5
>>> print(tmp1[2])  # probe a single value
3

Compare to:

>>> tmp1 = [f1(x) for x in arr]
>>> tmp2 = [f2(x) for x in tmp1]  # this will take a lot of memory and time
>>> res = [f3(x) for x in tmp2]
>>> print(res[2])  # requires to have all other values computed
252.5
>>> print(tmp1[2])  # requires to keep all other values in memory
3


Installation
------------

.. code-block:: bash

   pip install lproc


Documentation
-------------

The documentation is hosted at https://lazyproc.readthedocs.io


Similar libraries
-----------------

- `Fuel <http://fuel.readthedocs.io/en/latest>`_ is a higher level library
  targeted toward Machine Learning and dataset manipulation.
- `torchvision.transforms <http://pytorch.org/docs/master/torchvision/transforms.html>`_
  and `torch.utils.data <http://pytorch.org/docs/master/data.html>`_.
