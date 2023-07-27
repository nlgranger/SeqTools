from setuptools import setup, Extension

setup(
    ext_modules=[
        Extension("seqtools.C.refcountedbuffer", ["seqtools/C/refcountedbuffer.c"])
    ],
)
