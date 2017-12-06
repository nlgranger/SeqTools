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

Lazy evaluation is a form of of delayed execution of a function where the
actual is performed onlywhen the result is actually needed.

LazyProc focuses on lazy-processing of sequential data such as lists or arrays
or any indexable object. It is designed to ease testing and execution of
multi-stage transformation pipelines over datasets.

>>> def do(x):
...     print("computing now")
...     return x + 2
...
>>> a = [1, 2, 3, 4]
>>> # Without lazy mapping:
>>> [do(x) for x in a]
computing now
computing now
computing now
computing now
[3, 4, 5, 6]
>>> # Using mazy mapping:
>>> m = lproc.rmap(do, a)
>>> # nothing printed because evaluation is delayed
>>> m[0]
computing now
3


Installation
------------

.. code-block:: bash

   pip install lproc


Documentation
-------------

The documentationn is hosted at `https://lazyproc.readthedocs.io`_.


Similar libraries
-----------------

- `Fuel <http://fuel.readthedocs.io/en/latest>`_ is a higher level library
  targeted toward Machine Learning and dataset manipulation.
- `torchvision.transforms <http://pytorch.org/docs/master/torchvision/transforms.html>`_
  and `torch.utils.data <http://pytorch.org/docs/master/data.html>`_.
