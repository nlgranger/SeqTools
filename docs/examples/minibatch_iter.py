from __future__ import print_function
import time
import seqtools


files = ['file1', 'file2', 'file3', 'file4', 'file5',
         'file6', 'file7', 'file8', 'file9', 'file10']


def load(some_file):
    time.sleep(.1)
    return list(range(10) if some_file == 'file10' else range(200))


loaded_files = seqtools.smap(load, files)
loaded_files = seqtools.add_cache(loaded_files, 2)
all_samples = seqtools.unbatch(loaded_files, 200, 10)


def preprocess(x):
    t = time.clock()
    while time.clock() - t < 0.005:
        pass  # busy waiting
    return x


preprocessed_samples = seqtools.smap(preprocess, all_samples)
minibatches = seqtools.batch(preprocessed_samples, 64, collate_fn=list)

t1 = time.time()
for batch in minibatches:
    pass
t2 = time.time()
print("sequential read took {:.1f}\"".format(t2 - t1))


t1 = time.time()
for batch in seqtools.prefetch(minibatches, max_buffered=100, method="thread", nworkers=2):
    pass
t2 = time.time()
print("threaded read took {:.1f}\"".format(t2 - t1))


t1 = time.time()
for batch in seqtools.prefetch(minibatches, max_buffered=100, method="process", nworkers=2):
    pass
t2 = time.time()
print("multiprocessing read took {:.1f}\"".format(t2 - t1))
