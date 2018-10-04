"""
A python library to manipulate and transform sequences.

The seqtools package contains functions to manipulate sequences
(anything that supports indexing such as lists or arrays).
Its objective is to simplify the execution of pipelines transformations.

Unless otherwise specified, all functions feature on-demand evaluation
which means operations on an item or sequence are only executed when
needed which is convenient for rapid prototyping.
Most function apply 'transparently' over sequence and return objects
that support integer indexing, iteration, slicing, item assignment,
slice based assignment...

The library also feature a robust multihreading/multiprocessing
prefetch routine which hides away the difficulties of concurrent
processing into a simple sequence wrapper.
"""

from .evaluation import prefetch, eager_iter
from .errors import EvaluationError, seterr
from .buffering import add_cache, load_buffers
from .indexing import arange, gather, take, reindex, cycle, interleave, repeat
from .mapping import smap, starmap
from .serialization import SerializableFunc
from .shape import collate, concatenate, batch, unbatch, split
from . import instrument

__all__ = [
    'prefetch', 'eager_iter',
    'EvaluationError', 'seterr',
    'add_cache', 'load_buffers',
    'arange', 'gather', 'take', 'reindex', 'cycle', 'interleave', 'repeat',
    'smap', 'starmap',
    'collate', 'concatenate', 'batch', 'unbatch', 'split']
