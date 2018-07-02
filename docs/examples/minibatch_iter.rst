Minibatch Iterator
------------------

This example shows how to create a minibatch loader with some preprocessing
steps. To make sure that the final batch consumer is never starved, we will
use workers to prepare multiple batches simultaneously.

Let's imagine that our data is stored in a list of files, each of which
contains 1000 items except for the last one which only has 10:

.. testcode::

   files = ['file1', 'file2', 'file3', 'file4', 'file5',
            'file6', 'file7', 'file8', 'file9', 'file10']

To simulate loading IO activity (which doesn't consume CPU time), we use the
following function:

.. testcode::

   import time
   import seqtools

   def load(some_file):
       time.sleep(.5)
       return list(range(10) if some_file == 'file10' else range(200))


then we want to load those files when needed:

.. testcode::

   loaded_files = seqtools.smap(load, files)

and concatenate their content:

.. testcode::

   all_samples = seqtools.unbatch(loaded_files, 200, 10)

We draw your attention to the fact that no computation has happened at this
point, this is solely the definition of the pipeline. However, you can check
how it works by reading a few samples:

.. testcode::

   print(len(all_samples))
   print(all_samples[-2])
   print(all_samples[-1])

.. testoutput::

   1810
   8
   9

Although setting up the pipeline is cheap, the above instruction
has cost two file loading operations, indeed `seqtools` is only a thin layer
above your data and does not cache values to avoid saturating memory. To
visualize it, let's add a debug hook:

.. testcode::

   loaded_files = seqtools.instrument.debug(
      loaded_files,
      lambda i, _: print("loading file {} ...".format(i)))
   all_samples = seqtools.unbatch(loaded_files, 200, 10)

   print(all_samples[-2])
   print(all_samples[-1])

.. testoutput::

   loading file 9 ...
   8
   loading file 9 ...
   9

To avoid reloading the same file multiple time during sequential reads, one can
cache the last read elements for later calls:

.. testcode::

   loaded_files = seqtools.smap(load, files)
   loaded_files = seqtools.add_cache(loaded_files, 2)
   all_samples = seqtools.unbatch(loaded_files, 200, 10)

Next comes the element-wise preprocessing step:

.. testcode::

   def preprocess(x):
       t1 = time.clock()
       while time.clock() - t1 < 0.005:
           pass  # busy waiting
       return x

   preprocessed_samples = seqtools.smap(preprocess, all_samples)

Now we want to break this sequence into smaller batches so that it can be
fed into the final data consumer or exported again:

.. testcode::

   minibatches = seqtools.batch(preprocessed_samples, 64, collate_fn=list)

Generating all the batches will take quite some time:

.. testcode::

   t1 = time.time()
   for batch in minibatches:
       pass
   t2 = time.time()
   print("sequential read took {:.0f}\"".format(t2 - t1))

.. testoutput::
   :options: +SKIP

   sequential read took 10.2"

We can exploit the idle downtime waiting for IO by using multiple threads:

.. testcode::

   t1 = time.time()
   for batch in seqtools.prefetch(minibatches, max_cached=100, method="thread", nworkers=2):
      pass
   t2 = time.time()
   print("threaded read took {:.1f}\"".format(t2 - t1))

.. testoutput::
   :options: +SKIP

   threaded read took 7.7"

Or use multiple cores by spreading work over processes:

.. testcode::

   t1 = time.time()
   for batch in seqtools.prefetch(minibatches, max_cached=100, method="process", nworkers=2):
      pass
   t2 = time.time()
   print("multiprocessing read took {:.1f}\"".format(t2 - t1))

.. testoutput::
   :options: +SKIP

   multiprocessing read took 5.6"


The whole example can be downloaded :download:`here <minibatch_iter.py>`.
