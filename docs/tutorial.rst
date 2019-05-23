.. currentmodule:: seqtools

.. testsetup::

   import seqtools


Tutorial
========

Simple mapping
--------------

The most basic (and possibly the most useful) function is :func:`smap` which
maps a function to each element of a sequence, similarly to what :func:`map`
does for iterables:

>>> data = [3, 5, 1, 4]
>>> y = seqtools.smap(lambda x: x * 2, data)
>>> [y[i] for i in range(4)]
[6, 10, 2, 8]

To understand the effect of lazy evaluation, let's add a notification when the
function is called:

>>> def f(x):
...     print("processing {}".format(x))
...     return x * 2
...
>>> y1 = seqtools.smap(f, data)
>>> # nothing happened so far
>>>
>>> y1[0]  # f will be called now and specifically on item 0
processing 3
6

.. note::

    There is no caching/memoization mechanism included, so repeated calls to
    the same element will trigger a call to the mapping functions each time:

    >>> y1[0]
    processing 3
    6
    >>> y1[0]
    processing 3
    6

    See :func:`add_cache` for a simple form of caching mechanism.

If the transformation is slow to compute and/or the sequence is large, lazy
evaluation can dramatically reduce the delay to obtain any particular item.
Furthermore, on can chain several transformations in a pipeline. This is
particularly convenient when intermediate transformations are memory heavy
because SeqTools only stores intermediate results for one element at a time:

>>> def f(x):
...     # This intermediate result takes a lot of space...
...     return [x] * 10000
...
>>> def g(x):
...     return sum(x) / len(x)
...
>>> data = list(range(2000))
>>>
>>> # construct pipeline without computing anything
>>> y1 = seqtools.smap(f, data)
>>> y2 = seqtools.smap(g, y1)
>>>
>>> # computing one of the output values only uses sizeof(float) * 10000
>>> # whereas explicitely computing y1 would use sizeof(float) * 10000 * 2000
>>> y2[2]
2.0


Indexing
--------

Most functions in this library including :func:`smap` try to preserve the
simplicity of python list indexing, that includes negative indexing and slicing
as well:

>>> data = [3, 5, 1, 4]
>>> y = seqtools.smap(lambda x: x * 2, data)
>>> list(y)
[6, 10, 2, 8]
>>> z = y[1:-1]  # on-demand slicing ⇒ z values aren't computed yet
>>> len(z)  # deduced without evaluating z
2
>>> list(z)
[10, 2]

Where it makes sense, transformed sequences also support index and slice based
_assignment_ so as to make the objects truely behave like lists. For example
with the :func:`gather` function:

>>> data = [0, 1, 2, 3, 4, 5]
>>> y = seqtools.gather(data, [1, 1, 3, 4])
>>> list(y)
[1, 1, 3, 4]
>>> y[0] = -1
>>> data
[0, -1, 2, 3, 4, 5]
>>> y[-2:] = [-3, -4]
>>> data
[0, -1, 2, -3, -4, 5]


Multivariate mapping
--------------------

Similarly to :func:`map`, if more than one sequence is passed, they are zipped
together and fed as distinct arguments to the function:

>>> data1 = [3, 5, 1, 4]
>>> data2 = [4, 5, 7, 2]
>>> y = seqtools.smap(lambda x1, x2: x1 + x2, data1, data2)
>>> list(y)
[7, 10, 8, 6]


Going further
-------------

To finally compute all the values from a sequence, :func:`prefetch` provides
a wrapper backed by multiple workers to compute the values more quickly.

To see the library in practice, you can see how to :ref:`build, debug and run a
transformation pipeline <Building and running a preprocessing pipeline>` over
and image dataset, write a multiprocessing capable :ref:`minibatch iterator
<Fast minibatch sampling>`

The library is quite small for now, how about giving a quick glance at the
:ref:`API Reference`?
