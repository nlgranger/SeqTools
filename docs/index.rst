.. toctree::
   :hidden:
   :maxdepth: 3

   installation
   tutorial
   reference


.. testsetup::

   import lproc
   import pickle as pkl


LazyProc
========

TLDR; Like python's map but you can also use indexing on the result.

This library provides simple helper functions for lazy evaluation of indexable
objects such as lists. It can be used to design and evaluate chained
transformations pipelines.

Lazy evaluation is easily understood by looking an example:

>>> def do(x):
...     print("-> computing now")
...     return x + 2
...
>>> a = [1, 2, 3, 4]
>>> m = lproc.rmap(do, a)
>>> # nothing printed because evaluation is delayed
>>> m[0]
-> computing now
3

Because of delayed execution, intermediate values for chained transformations
need not be computed and stored unless explicitly required. As a result,
memory usage remains as low as possible but it is still possible to probe
intermediate values.

>>> def f1(x):
...     return x + 1
...
>>> def f2(x):
...     # This is slow and memory heavy
...     return [x + i for i in range(500)]
...
>>> def f3(x):
...     return sum(x) / len(x)
...
>>> arr = list(range(5000))
>>> tmp1 = lproc.rmap(f1, arr)
>>> tmp2 = lproc.rmap(f2, tmp1)
>>> res = lproc.rmap(f3, tmp2)
>>> print(res[2])
252.5

Compare to:

>>> tmp1 = [f1(x) for x in arr]
>>> tmp2 = [f2(x) for x in tmp1]  # this will take a lot of time and memory
>>> res = [f3(x) for x in tmp2]
>>> print(res[2])
252.5


Similar libraries
-----------------

- `Fuel <http://fuel.readthedocs.io/en/latest>`_ is a higher level library
  targeted toward Machine Learning and dataset manipulation.
- `torchvision.transforms <http://pytorch.org/docs/master/torchvision/transforms.html>`_
  and `torch.utils.data <http://pytorch.org/docs/master/data.html>`_.
