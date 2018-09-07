.. currentmodule:: seqtools

.. testsetup::

   import seqtools


Tutorial
========

Simple mapping
--------------

The most basic (and possibly the most useful) function is :func:`smap`
which maps a function to each element of a sequence:

>>> l = [3, 5, 1, 4]
>>> y = seqtools.smap(lambda x: x * 2, l)
>>> [y[i] for i in range(4)]
[6, 10, 2, 8]

:func:`smap` is equivalent to the standard :func:`map` function. To
understand the effect of lazy evaluation, let's add a notification when the
function is called:

>>> def f(x):
...     print("processing {}".format(x))
...     return x * 2
...
>>> y1 = seqtools.smap(f, l)
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

    There is no caching/memoization mechanism included, so multiple calls to
    the same element will trigger a call to the mapping functions each time:

    >>> y1[0]
    processing 3
    6
    >>> y1[0]
    processing 3
    6

    See :func:`add_cache` for a simple form of caching mechanism.

If the transformation is slow to compute and/or the sequence is large, lazy
evaluation can dramatically reduce the delay to obtain any individual results.
Furthermore, on can chain several transformations in a pipeline. This is
particularly convenient when intermediate transformations are memory heavy
because the intermediate results are stored for only one element at a time:

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
>>> y1 = seqtools.smap(f, l)
>>> y2 = seqtools.smap(g, y1)
>>>
>>> # computing one of the output values only uses sizeof(float) * 10000
>>> # whereas explicitely computing y1 would gather sizeof(float) * 10000 * 2000
>>> y2[2]
2.0


Indexing
--------

Most functions in this library including :func:`smap` try to preserve the
simplicity of python list indexing, that includes negative indexing and slicing
as well:

>>> l = [3, 5, 1, 4]
>>> y = seqtools.smap(lambda x: x * 2, l)
>>> list(y)
[6, 10, 2, 8]
>>> z = y[1:-1]
>>> # following seqtools on-demand logic: z values aren't yet computed
>>> len(z)  # deduced without evaluating z
2
>>> list(z)
[10, 2]

Where it makes sense, transformed sequences also support index and slice based
_assignment_ so as to make the objects truely behave like lists. For example
with the :func:`gather` function:

>>> arr = [0, 1, 2, 3, 4, 5]
>>> y = seqtools.gather(arr, [1, 1, 3, 4])
>>> list(y)
[1, 1, 3, 4]
>>> y[0] = -1
>>> arr
[0, -1, 2, 3, 4, 5]
>>> y[-2:] = [-3, -4]
>>> arr
[0, -1, 2, -3, -4, 5]


Multivariate mapping
--------------------

Similarly to :func:`map`, if more than one sequence is passed, they are zipped
together and fed as distinct arguments to the function:

>>> l1 = [3, 5, 1, 4]
>>> l2 = [4, 5, 7, 2]
>>> y = seqtools.smap(lambda x1, x2: x1 + x2, l1, l2)
>>> list(y)
[7, 10, 8, 6]


Going further
-------------

To finally compute all the values from a sequence, :func:`prefetch` provides
an wrapper backed by multiple workers to compute the values more quickly.

To see the library in practice, you can see how to :ref:`build, debug and run a
transformation pipeline <Building and running a preprocessing pipeline>` over
and image dataset, write a multiprocessing capable :ref:`minibatch iterator
<Fast minibatch sampling>`

The library is quite small for now, how about giving a quick glance at the
:ref:`API Reference`?
