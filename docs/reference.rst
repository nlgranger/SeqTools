.. testsetup:: *

   from seqtools import *

.. py:module:: seqtools


API Reference
=============

.. autosummary::

    add_cache
    batch
    collate
    concatenate
    cycle
    gather
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

.. autofunction:: gather
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

.. autoclass:: EagerAccessException

Tools
-----

.. autofunction:: seqtools.instrument.debug
.. autofunction:: seqtools.instrument.monitor_throughput
