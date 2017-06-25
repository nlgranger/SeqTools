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

Lazy evaluation is a form of of delayed execution of a function where the actual
is performed onlywhen the result is actually needed.

LazyProc provides python 3 helper functions to perform lazy mapping of functions over
sequencial data.


Installation
------------

.. code-block:: bash

   pip install git+https://github.com/nlgranger/LazyProc


Example
-------

>>> def do(x):
...     print("computing now")
...     return x + 2
...
>>> m = rmap(do, a)
>>> # nothing printed because evaluation is delayed
>>> [x for x in m]
computing now
computing now
computing now
computing now
[3, 4, 5, 6]


Documentation
-------------

(WiP) head up to https://lazyproc.readthedocs.io
