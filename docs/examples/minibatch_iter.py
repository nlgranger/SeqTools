import array
import time
import seqtools


def process_fn(x):
    time.sleep(1)
    return x


def preprocess_fn(x):
    time.sleep(0.2)
    return x


def make_batches(data, f, buffers, batch_size, drop_last=False, nworkers=0):
    """Transfer data to buffers and iterate over minibatches.

    :param data:
        The input sequence
    :param f:
        Preprocessing function
    :param buffers:
        A preallocated memory space that recieves the elements from data.
        **if smaller than data, memory slots will be reused**. Must be
        at least `batch_size` long, the recommended size is `batch_size` \*
        `nworkers`.
    :batch_size:
        The size of the minibatches
    :drop_last:
        Wether to drop a final minibatch smaller than `batch_size`
    :nworkers:
        number of workers, see :func:`seqtools.eager_iter`
    """
    preprocessed = seqtools.smap(f, data)
    data_batches = seqtools.batches(preprocessed, batch_size, drop_last)
    ring_buffers = seqtools.cycle(buffers, len(data_batches))

    def batch_copy(source, destination):
        for i, v in enumerate(source):
            destination[i] = v
        return destination

    minibatches = seqtools.smap(batch_copy, data_batches, ring_buffers)

    return seqtools.prefetch(minibatches, nworkers, max_buffered=len(buffers))


raw_data = list(range(100))
batch_size = 10

# Reference
t1 = time.time()
for i in range(0, len(raw_data), batch_size):
    preprocessed = [preprocess_fn(x) for x in raw_data[i:i + batch_size]]
    process_fn(preprocessed)
t2 = time.time()
print("sequential iterator took {:.0f}\"".format(t2 - t1))

# Multithreaded version
buffers = [array.array('l', [0] * batch_size) for _ in range(5)]
t1 = time.time()
for b in make_batches(
        raw_data, preprocess_fn, buffers, batch_size, nworkers=2):
    process_fn(b)
t2 = time.time()
print("multithreaded iterator took: {:.0f}\"".format(t2 - t1))
