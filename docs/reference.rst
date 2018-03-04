.. testsetup:: *

   from seqtools import *

.. currentmodule:: seqtools


API Reference
=============

.. autosummary::

   add_cache
   prefetch
   take
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
.. autofunction:: take
.. autofunction:: cycle
.. autofunction:: repeat
.. autofunction:: batches
.. autofunction:: split


Evaluation
----------

.. autofunction:: add_cache
.. autofunction:: prefetch
.. autoclass:: SerializableFunc

Errors
------

.. autoclass:: EagerAccessException
