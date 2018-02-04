.. currentmodule:: lproc

Tutorial
========

Simple mapping
--------------

The most basic (and possibly the most useful) function is :func:`rmap`
which maps a function to each elements of a container such as a list or an
array:

.. testsetup::

   from lproc import *


>>> l = [3, 5, 1, 4]
>>> y = rmap(lambda x: x * 2, l)
>>> [y[i] for i in range(4)]
[6, 10, 2, 8]

:func:`rmap` is equivalent to the standard `map` function. To understand the
effect of lazy evaluation, let's add a notification when the function is
called:

>>> def f(x):
...     print("processing {}".format(x))
...     return x * 2
...
>>> y1 = rmap(f, l)
>>> # nothing happened so far
>>>
>>> y1[0]  # f will be called now and specifically on item 0
processing 3
6
>>> y2 = [f(x) for x in l]
processing 3
processing 5
processing 1
processing 4

.. note::

    There is no caching/memoïzation mechanism included, so multiple calls to
    the same element will trigger a call to the mapping functions each time:

    >>> y1[0]
    processing 3
    6
    >>> y1[0]
    processing 3
    6

    See :func:`add_cache` for a simple form of caching mechanism.

If `f` is slow to compute or `l` is large, lazy evaluation can dramatically
reduce the delay to obtain any individual results. Furthermore, on can
chain several transformations in a pipeline. This is particularly convenient
when intermediate transformations are memory heavy because the intermediate
results are stored for only one element at a time:

>>> def f(x):
...     # This intermediate result takes a lot of space...
...     return [x] * 10000
...
>>> def g(x):
...     return sum(x) / len(x)
...
>>> l = list(range(2000))
>>>
>>> # construct pipeline without computing anything
>>> y1 = rmap(f, l)
>>> y2 = rmap(g, y1)
>>>
>>> # compute one of the output values only uses sizeof(float) * 10000
>>> y2[2]
2.0
>>> # whereas explicitely computing the intermediate transformation
>>> # requires sizeof(float) * 10000 * 2000
>>> y3 = [f(x) for x in l]
>>> y4 = [g(x) for x in y3]
>>> y4[2]
2.0


Indexing
--------

:func:`rmap` tries to preserve the simplicity of slice-based indexing:

>>> l = [3, 5, 1, 4]
>>> y = rmap(lambda x: x * 2, l)
>>> [x for x in y[1:-1]]
[10, 2]
>>> len(y)
4
>>> len(y[1:-1])  # known without processing the array
2

When the requested index is neither an integer nor a slice, :func:`rmap`
will delegates indexing to the inner data sequence:

>>> import numpy as np
>>> arr = np.arange(5)
>>> y = rmap(lambda x: x * 2, arr)
>>> list(y[[1, 3, 4]])  #  ~= list(map(lambda x: x * 2, arr[1, 3, 4]))
[2, 6, 8]


Multivariate mapping
--------------------

Similarly to :func:`map`, if more than one sequence is passed, they are zipped
together and fed as distinct arguments to the function:

>>> l1 = [3, 5, 1, 4]
>>> l2 = [4, 5, 7, 2]
>>> y = rmap(lambda x1, x2: x1 + x2, l1, l2)
>>> list(y)
[7, 10, 8, 6]


Going further
-------------

For datasets with a second level of indirection such as an array of arrays
or an array of iterables, one can use :func:`rrmap` and
:func:`rimap` respectively.

:func:`subset` lets one manipulate a subset of a sequence based on a
selection of indexes.

:func:`par_iter` returns an multiprocessing-enabled iterator over a
sequence to quickly process an array.

The library is quite small for now, how about giving a quick glance at the
:ref:`API Reference`?
