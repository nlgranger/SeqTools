---
title: 'SeqTools: A python package for easy transformation, combination and evaluation of large datasets.'
tags:
  - python
  - pre-processing
  - pipeline
  - dataset
  - machine learning
  - lazy evaluation
authors:
 - name: Nicolas Granger
   orcid: 0000-0003-2943-9888
   affiliation: "1"
 - name: Mounîm A. El Yacoubi
   orcid: 0000-0000-0000-0000
   affiliation: "1"
affiliations:
 - name: Télécom SudParis
   index: 1
date: 5 October 2018
---


# Summary

``SeqTools`` facilitates the manipulation of large datasets and the evaluation
of a transformation pipeline. Some of the provided functionnalities include:
mapping element-wise operations, reordering, reindexing, concatenation, joining,
slicing, minibatching, etc...

To improve ease of use, ``SeqTools`` assumes that dataset are objects that
implement a list-like
[sequence](https://docs.python.org/3/glossary.html#term-sequence) interface: a
container object with a length and its _elements accessible via indexing or
slicing_. All ``SeqTools`` functions take and return objects compatible with
this simple and convenient interface.

Sometimes manipulating a whole dataset with transformations or combinations can
be slow and resource intensive; a transformed dataset might not even fit into
memory! To circumvent this issue, ``SeqTools`` implements _on-demand_ execution
under the hood, so that computations are only run when needed, and only for
actually required elements while ignoring the rest of the dataset. This helps to
keep memory resources down to a bare minimum and accelerate the time it take to
access any arbitrary result. This on-demand strategy helps to quickly define
dataset-wide transformations and probe a few results for debugging or
prototyping purposes, yet it is transparent for the users who still benefit from
a simple and convenient list-like interface.
 
When comes the transition from prototyping to execution, the list-like container
interface facilitates serial evaluation. Besides, ``SeqTools`` also provides
simple helpers to dispatch work between multiple background workers (threads or
processes), and therefore to maximize execution speed and resource usage.

``SeqTools`` originally targets data science, more precisely the preprocessing
stages of a dataset. Being aware of the experimental nature of this usage,
on-demand execution is made as transparent as possible to users by providing
fault-tolerant functions and insightful error reporting. Moreover, internal code
is kept concise and clear with comments to facilitate error tracing through a
failing transformation pipeline.

The library should connect nicely to the input pipeline of Machine Learning
libraries. Nevertheless, this project purposedly keeps a generic interface and
only requires minimal dependencies in order to facilitate reusability.

# References
