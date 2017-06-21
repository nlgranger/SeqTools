class Indexable:
    """Interface for indexable containers.

    An indexable is typically either the training, the validation or the test
    set of a dataset. It behaves like a simplified read-only python list
    meaning that it has a length, its elements are accessible through indexing. Python 
    lists and numpy arrays implicitely implement this interface.

    All the lazy transformation implemented in this library return an Indexable. The 
    computation on the elements is done on the fly when the elements are accessed.
    
    :note:
        slice based indexing may not always be implemented.
    """

    def __len__(self):
        raise NotImplementedError

    def __getitem__(self, i):
        raise NotImplementedError

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]
