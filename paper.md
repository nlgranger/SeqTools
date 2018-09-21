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
date: 17 September 2018
---


# Summary

``SeqTools`` facilitates the manipulation of datasets and the evaluation of a
transformation pipeline. Some of the provided functionnalities include: mapping
element-wise operations, reordering, reindexing, concatenation, joining,
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
under the hood, so that computations and memory resources are always kept to a
bare minimum: accessing one element only takes the memory resources needed for
that element (ignoring the rest of the dataset), and computations are only run
when that element is requested. This helps to quickly define dataset-wide
transformations and probe a few results for debugging or prototyping purposes.

When comes the transition from prototyping to execution, the list-like container
interface facilitates serial evaluation. Besides, ``SeqTools`` also provides
simple helpers to dispatch work between multiple workers, and therefore to
maximize execution speed and resource usage.

``SeqTools`` originally targets data science, more precisely the preprocessing
stages of a dataset. In particular, it is meant to connect nicely to the input
pipeline of Machine Learning libraries. However, this project purposedly keeps a
generic interface and only requires minimal dependencies to facilitate
reusability. Moreover, a particular attention was given to prototyping and
debugging usages: the code is kept concise and clear with internal documentation
to facilitate error investigation of faulty transformation pipelines. On-demand
execution is made as transparent as possible to users by providing
fault-tolerant functions and insightful error reporting.

# References
