Welcome to LazyProc's documentation!
====================================

Lazy evaluation is a form of of delayed execution of a function on a value where you
run the actual computation only when the result is actually needed.

LazyProc provides convenient python 3 helper functions to perform lazy mapping of
functions over sequences of values:


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


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   lproc


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
