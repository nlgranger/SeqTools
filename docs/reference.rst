API Reference
=============

.. testsetup:: *

   from seqtools import *

.. py:module:: seqtools


.. autosummary::
   :nosignatures:

   smap
   starmap
   arange
   gather
   take
   concatenate
   collate
   interleave
   cycle
   repeat
   batch
   unbatch
   split
   add_cache
   prefetch
   load_buffers
   SerializableFunc
   EvaluationError
   seterr


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


Evaluation and buffering
------------------------

.. autofunction:: add_cache
.. autofunction:: prefetch
.. autofunction:: load_buffers
.. autoclass:: SerializableFunc


Errors
------

.. autoclass:: EvaluationError

.. autofunction:: seterr


Tools
-----

.. autofunction:: seqtools.instrument.debug
.. autofunction:: seqtools.instrument.monitor_throughput
