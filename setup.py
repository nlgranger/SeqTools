from setuptools import setup, find_packages, Extension


setup(
    packages=find_packages(),
    ext_modules=[
        Extension("seqtools.C.memory", ["seqtools/C/memory.c"])],
    install_requires=[
        'tblib'],
    extras_require={
        'numpy support': 'numpy',
        'pytorch support': 'pytorch'
    },
    tests_require=[
        'pytest',
        'pytest-timeout',
        'numpy']
)
