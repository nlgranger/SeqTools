from setuptools import setup

setup(
    name='lproc',
    author="Nicolas Granger",
    author_email="nicolas.granger.m@gmail.com",
    description="A python library for lazy mapping of functions over sequences.",
    license="MPL2",
    url="https://github.com/pixelou/LazyProc",
    packages=['lproc'],
    version='0.0.1',
    install_requires=[
        'typing;python_version<"3.6"'
    ]
)
