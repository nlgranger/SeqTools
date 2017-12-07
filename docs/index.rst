.. toctree::
   :hidden:
   :maxdepth: 3

   installation
   tutorial
   reference

.. testsetup::

   import lproc


LazyProc
========

Lazy evaluation is a form of of delayed execution of a function where the
actual is performed onlywhen the result is actually needed.

LazyProc focuses on lazy-processing of sequential data such as lists or arrays
or any indexable object. It is designed to ease testing and execution of
multi-stage transformation pipelines over datasets.

>>> def do(x):
...     print("computing now")
...     return x + 2
...
>>> a = [1, 2, 3, 4]
>>> # Without lazy mapping:
>>> [do(x) for x in a]
computing now
computing now
computing now
computing now
[3, 4, 5, 6]
>>> # Using mazy mapping:
>>> m = lproc.rmap(do, a)
>>> # nothing printed because evaluation is delayed
>>> m[0]
computing now
3

Compared to sequential execution of functions over a sequence, lproc let's one
look at single elements without computing all the prior transformation steps
for the other elements, and without storing the intermediate processing values.

>>> nops = 0
>>>
>>> def f1(x):
...     global nops
...     nops += 1
...     return x + 1
...
>>> def f2(x):  # simulate slow and memory heavy function
...     global nops
...     nops += 1000
...     return [x + i for i in range(500)]
...
>>> def f3(x):
...     global nops
...     nops += 1
...     return sum(x) / len(x)
...
>>> nops = 0
>>> arr = list(range(500))
>>> res = [f1(x) for x in arr]
>>> res = [f2(x) for x in res]  # this takes a lot of place
>>> res = [f3(x) for x in res]
>>> print(res[2])
252.5
>>> print(nops)
501000
>>>
>>> nops = 0
>>> arr = list(range(500))
>>> res = lproc.rmap(f1, arr)
>>> res = lproc.rmap(f2, res)
>>> res = lproc.rmap(f3, res)
>>> print(res[2])
252.5
>>> print(nops)
1002


Similar libraries
-----------------

- `Fuel <http://fuel.readthedocs.io/en/latest>`_ is a higher level library
  targeted toward Machine Learning and dataset manipulation.
- `torchvision.transforms <http://pytorch.org/docs/master/torchvision/transforms.html>`_
  and `torch.utils.data <http://pytorch.org/docs/master/data.html>`_.
