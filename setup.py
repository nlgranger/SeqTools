from setuptools import setup, find_packages, Extension
from version import version


with open("README.rst") as f:
    long_description = f.read()

setup(
    name="SeqTools",
    version=version,
    description="A library for transparent transformation of indexable containers (lists, etc.)",
    url="https://github.com/nlgranger/SeqTools",
    long_description=long_description,
    author="Nicolas Granger",
    author_email="nicolas.granger.m@gmail.com",
    keywords=['mapping', 'lazy', 'delayed', 'pipeline', 'processing'],
    license="Mozilla Public License 2.0 (MPL 2.0)",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: Implementation :: CPython",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Development Status :: 3 - Alpha",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research"],
    packages=find_packages(),
    ext_modules=[
        Extension("seqtools.C.refcountedbuffer", ["seqtools/C/refcountedbuffer.c"])],
    install_requires=[
        'tblib'],
    extras_require={
        'numpy support': [
            'numpy'],
        'pytorch support': [
            'pytorch'],
        'documentation': [
            'sphinx', 'ipython', 'ipykernel', 'nbconvert', 'nbsphinx', 'Pillow', 'numpy',
            'scikit-learn'],
        'tests': [
            'pytest', 'pytest-timeout', 'numpy', 'coverage', 'nose']
    }
)
