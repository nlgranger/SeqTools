API Reference
=============

.. testsetup:: *

   from seqtools import *

.. py:module:: seqtools


.. autosummary::
   :nosignatures:

   add_cache
   batch
   collate
   concatenate
   cycle
   arange
   gather
   take
   interleave
   prefetch
   repeat
   smap
   split
   starmap
   unbatch


Mapping
-------

.. autofunction:: smap
.. autofunction:: starmap


Indexing and reshaping
----------------------

.. autofunction:: arange
.. autofunction:: gather
.. autofunction:: take
.. autofunction:: concatenate
.. autofunction:: collate
.. autofunction:: interleave
.. autofunction:: cycle
.. autofunction:: repeat
.. autofunction:: batch
.. autofunction:: unbatch
.. autofunction:: split


Evaluation
----------

.. autofunction:: add_cache
.. autofunction:: prefetch
.. autoclass:: SerializableFunc


Errors
------

.. autoclass:: PrefetchException


Tools
-----

.. autofunction:: seqtools.instrument.debug
.. autofunction:: seqtools.instrument.monitor_throughput
