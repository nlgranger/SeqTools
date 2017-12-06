.. testsetup:: *

   from lproc import *

.. currentmodule:: lproc


API Reference
=============

.. autosummary::

    rmap
    rimap
    rrmap
    concatenate
    collate
    subset
    par_iter
    chunk_load


Mapping
-------

.. autofunction:: rmap
.. autofunction:: rimap
.. autofunction:: rrmap


Index manipulation
------------------

.. autofunction:: concatenate
.. autofunction:: collate
.. autofunction:: subset


Serialization
-------------

At some point, you will want to evaluation the values in your lists, those
function can help you process large sequences.

.. autofunction:: par_iter
.. autofunction:: chunk_load
.. autoclass:: SerializableFunc