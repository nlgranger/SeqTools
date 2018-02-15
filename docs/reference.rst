.. testsetup:: *

   from seqtools import *

.. currentmodule:: seqtools


API Reference
=============

.. autosummary::

   add_cache
   eager_iter
   reindex
   cycle
   repeat
   smap
   starmap
   collate
   concatenate
   batches
   split


Mapping
-------

.. autofunction:: smap
.. autofunction:: starmap


Indexing and reshaping
----------------------

.. autofunction:: concatenate
.. autofunction:: collate
.. autofunction:: reindex
.. autofunction:: cycle
.. autofunction:: repeat


Evaluation
----------

.. autofunction:: add_cache
.. autofunction:: eager_iter
.. autoclass:: SerializableFunc

Errors
------

.. autoclass:: EagerAccessException
