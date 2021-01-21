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
   uniter
   switch
   case
   batch
   unbatch
   split
   add_cache
   prefetch
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
.. autofunction:: uniter
.. autofunction:: batch
.. autofunction:: unbatch
.. autofunction:: split
.. autofunction:: switch
.. autofunction:: case


Evaluation and buffering
------------------------

.. autofunction:: add_cache
.. autofunction:: prefetch
.. autoclass:: SerializableFunc


Errors
------

Please, consult the `tutorial on error management
<examples/errors_and_debugging.ipynb>`_ for detailed explanations.

.. autoclass:: EvaluationError

.. autofunction:: seterr


Tools
-----

.. autofunction:: seqtools.instrument.debug
.. autofunction:: seqtools.instrument.monitor_throughput
