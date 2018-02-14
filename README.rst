.. image:: https://badge.fury.io/py/lproc.svg
   :target: https://badge.fury.io/py/lproc
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

TLDR; Like python's itertools but for index based access with lazy evaluation.

This library is designed to facilitate the manipulation and transformation of
sequences (anything that supports `__getitem__` such as lists). It was
concieved with **lazy evaluation** in mind to help setup and test chained
transformations pipelines very quickly. It also supports **slice based
indexing** and **item assignment** when possible so that you can forget that
you are not working with lists!

Lazy evaluation is easily understood by looking at this example:

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
need not be computed and stored unless explicitly required. As a result:

- a full transformation pipeline is declared without delay
- end-results can be computed without running computation for other items and
  storing unneeded data.
- intermediate transformation results are easily accessible for testing

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

Without delayed evaluation:

>>> tmp1 = [f1(x) for x in arr]
>>> tmp2 = [f2(x) for x in tmp1]  # takes 10 seconds and a lot of memory
>>> res = [f3(x) for x in tmp2]
>>> print(res[2])
252.5
>>> print(max(tmp2[2]))  # requires to store 499 500 useless values along
502

Defining and using the pipeline:

>>> tmp1 = lproc.rmap(f1, arr)
>>> tmp2 = lproc.rmap(f2, tmp1)
>>> res = lproc.rmap(f3, tmp2)
>>> print(res[2])  # takes 0.01 seconds
252.5
>>> print(max(tmp2[2]))  # probe a single value on demand
502


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
