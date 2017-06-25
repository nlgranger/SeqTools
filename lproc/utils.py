import array
from typing import Sequence, Union
from .common import is_int_item


class Subset(Sequence):
    def __init__(self, sequence: Union[Sequence, 'Subset'],
                 indexes: Union[Sequence[int], slice]):
        if isinstance(sequence, Subset):  # optimize nested subsets
            try:  # let the index type handle subindexing if possible
                indexes = sequence.indexes[indexes]
            except Exception:
                indexes = [sequence.indexes[i] for i in indexes]
            sequence = sequence.sequence

        if isinstance(indexes, slice):
            start = indexes.start or 0
            stop = indexes.stop or len(sequence)
            step = indexes.step or 1
            if start < 0:
                start = len(sequence) + start
            if stop < 0:
                stop = len(sequence) + stop
            indexes = array.array('L', range(start, stop, step))

        self.sequence = sequence
        self.indexes = indexes

    def __len__(self):
        return len(self.indexes)

    def __getitem__(self, item):
        if is_int_item(item):
            return self.sequence[self.indexes[item]]
        else:
            # note: no magic here, we delegate indexing to data containers.
            return Subset(self.sequence[item], self.indexes[item])


def subset(sequence, indexes):
    """Return a view on a reindexed sequence.
    
    The indexes are either a sequence of integers or a slice.
    
    .. note::
        
        The returned object does not support reindexing itself, and will 
        delegate special indexing to the underlying data. To get a subset 
        of a subset, use nested calls to this function (composed views 
        are flattened out automatically for optimization).
    """
    return Subset(sequence, indexes)
