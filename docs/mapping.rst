Mapping
=======

The most basic (and possibly the most useful) function is :func:`lproc.rmap` which maps a
function to each elements of a container such as a list or an array:

.. testsetup:: *

   from lproc import rmap


>>> l = [3, 5, 1, 4]
>>> y = rmap(lambda x: x * 2, l)
>>> [y[i] for i in range(4)]
[6, 10, 2, 8]

To understand the effect of lazy evaluation, let's add a notification when the function
is called:

>>> def f(x):
...     print("processing {}".format(x))
...     return x * 2
...
>>> y1 = rmap(f, l)
>>> # nothing happened so far
>>> y1[0]  # f will be called now and specifically on item 0
processing 3
6
>>> y2 = [f(x) for x in l]
processing 3
processing 5
processing 1
processing 4
>>> y2[0]
6
>>> y1[0]  # note that there is no caching mechanism.
processing 3
6

If `f` is slow to compute or `l` is large, lazy evaluation can dramatically reduce the
delay to obtain the first individual results. Furthermore, on can chain several
transformations and obtain the final result for a single element. This is espcially
convenient when intermediate transformations are memory heavy and the intermediate
transformation cannot be stored:

>>> def f(x):
...     return [x] * 10000
...
>>> def g(x):
...     return sum(x) / len(x)
...
>>> l = list(range(1000))
>>> y1 = rmap(f, l)
>>> y2 = ramp(g, y1)
>>> # check intermediate result
>>> y1[0][:10]
[0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
>>> # compute final result, only requires sizeof(float) * 10000 memory
>>> y2[2]
2
>>> y3 = [f(x) for x in l]  # requires sizeof(float) * 10000 * 1000
>>> y3[0][:10]
[0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
>>> y4 = [g(x) for x in y3]
>>> y4[2]
2

Also for a processing pipeline with many stages, one can quickly preview the result
for a single item which is convenient.

This approach preserves some of the convenient aspects of sequences such as
iteration and slicing:

>>> [x for x in y]
[6, 10, 2, 8]
>>> list(y)
[6, 10, 2, 8]
>>> [x for x in y[1:-1]]
[10, 2]
>>> len(y)
4
>>> len(y[1:-1])  # known before calling f
2

When the requested index is not an integer or a slice, :func:`rmap` transparently
delegates indexing to the underlying data sequence:

>>> import numpy as np
>>> arr = np.arange(5)
>>> y = rmap(lambda x: x * 2, arr)
>>> list(y[[1, 3, 4]])
[2, 8, 10]

Similarly to :func:`map`, if more than one sequence is passed, they are zipped together
and fed as distinct arguments to the function:

>>> l1 = [3, 5, 1, 4]
>>> l2 = [4, 5, 7, 2]
>>> y = rmap(lambda x1, x2: x1 + x2, l1, l2)
>>> list(y)
[7, 10, 8, 6]

For datasets with a second level of indirection such as an array of arrays or an array of
iterables, one can use :func:`rrmap` and :func:`rimap` respectively.
