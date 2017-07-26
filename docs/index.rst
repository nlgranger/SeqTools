Welcome to LazyProc
===================

Lazy evaluation is a form of delayed function execution where the actual
computation is only performed when the result is explicitely used.

LazyProc provides simple tools to facilitate lazy mapping of functions over
sequential data such as lists, arrays, iterators ...

Example:

.. testsetup:: *

   from lproc import rmap

>>> def do(x):
...     print("computing now")
...     return x + 2
...
>>> a = [1, 2, 3, 4]
>>> # Without lazy mapping:
>>> [x for x in m]
computing now
computing now
computing now
computing now
[3, 4, 5, 6]
>>> # Using mazy mapping:
>>> m = rmap(do, a)
>>> # nothing printed because evaluation is delayed
>>> m[0]
computing now
3


.. toctree::
   :hidden:
   :maxdepth: 2

   installation
   mapping
   reference

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
