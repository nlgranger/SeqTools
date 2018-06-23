Minibatch Iterator
------------------

In this example, we want to create a function that takes a dataset as a
sequence and returns block of `k` elements aka minibatches. These minibatches
will be fead to some processing function such as a statistical model fitting
routine.

Often, heavy duty computations like this will be run in a separate thread
leaving some computation time available for other threads. We want to use this
moment to _prepare the next minibatches so that the process function never waits
for its data.

To simulate this free computation time, our central processing function will
call :func:`time.sleep` which also takes some time to run while allowing other
threads to run.

.. literalinclude:: minibatch_iter.py
   :lines: 6-8

It is unlikely that the raw data from the dataset is an appropriate input
for the processing function, it might require some read operations from the
hard drive and some small transformations which we simulate by:

.. literalinclude:: minibatch_iter.py
   :lines: 11-13

To reduce spurious memory allocation and memory release, we will put
the last and the next few minibatches in a small memory buffer preallocated
for the whole process duration.

The signature would therefore look like so:

.. literalinclude:: minibatch_iter.py
   :lines: 16

where `drop_last` indicates wether the final batch should be ignored if it has
less than `batch_size` elements, `f` is the preprocessing function, and
`nworkers` is the number of workers preprocessing the data.

The first step is to map the preprofessing function onto the raw data:

.. literalinclude:: minibatch_iter.py
   :lines: 35

then take a view of the dataset as blocks, which is exactly what
:func:`seqtools.batches` does:

.. literalinclude:: minibatch_iter.py
   :lines: 36

Since we have fewer buffers than batches, we will reuse them in a loop:

.. literalinclude:: minibatch_iter.py
   :lines: 37

We now need to transfer the data to the buffer and return the buffers, it can
be done by mapping a copy-and-return function over the two sequences of blocks:

.. literalinclude:: minibatch_iter.py
   :lines: 39-44

Notice the way :func:`seqtools.smap` handles functions with multiple arguments:
it is the same as the standard :func:`map` function.

The final step is to return a multithreaded view with :func:`seqtools.prefetch`
to quickly retrieve precomputed values. To make sure that the worker are not
too greedy and erase a buffer before it has been read, the `max_buffered`
argument must be set appropriately.

.. literalinclude:: minibatch_iter.py
   :lines: 46

Done! Now is testing time:

.. testcode::

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

.. testoutput::
   :options: +SKIP

   sequential iterator took 30"
   multithreaded iterator took 12"

The full code for this example is available
:download:`here <minibatch_iter.py>`.
