.. testsetup:: *

   from lproc import *

.. currentmodule:: lproc


API Reference
=============

.. autosummary::
    rmap
    rimap
    rrmap
    collate
    concatenate
    cycle
    reindex
    add_cache
    eager_iter
    EagerAccessException


Mapping
-------

.. autofunction:: rmap
.. autofunction:: rimap
.. autofunction:: rrmap


Indexing and reshaping
----------------------

.. autofunction:: concatenate
.. autofunction:: collate
.. autofunction:: cycle
.. autofunction:: reindex


Evaluation
----------

.. autofunction:: add_cache
.. autofunction:: eager_iter
.. autoclass:: SerializableFunc

Errors
------

.. autoclass:: EagerAccessException
