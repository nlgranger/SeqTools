Welcome to LazyProc
===================

Lazy evaluation is a form of delayed execution of a function where the actual computation
is performed only when the result is actually needed.

LazyProc is a library for lazy mapping of functions over sequencial data.

Example:

.. testsetup:: *

   from lproc import rmap

.. doctest::

   >>> def do(x):
   ...     print("computing now")
   ...     return x + 2
   ...
   >>> m = rmap(do, a)
   >>> # nothing printed because evaluation is delayed
   >>> m[0]
   computing now
   3
   >>> [x for x in m]
   computing now
   computing now
   computing now
   computing now
   [3, 4, 5, 6]


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
