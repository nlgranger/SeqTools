.. image:: https://api.travis-ci.org/pixelou/LazyProc.svg
   :target: https://travis-ci.org/pixelou/LazyProc
.. image:: https://readthedocs.org/projects/lazyproc/badge
   :target: https://lazyproc.readthedocs.io


LazyProc
========

Lazy evaluation is a form of of delayed execution of a function where the actual
is performed onlywhen the result is actually needed.

LazyProc provides python 3 helper functions to perform lazy mapping of functions over
sequencial data.


Installation
------------

.. code-block:: bash

   pip install git+https://github.com/pixelou/LazyProc


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
