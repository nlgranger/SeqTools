import sys
from setuptools import setup
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to pytest")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ''

    def run_tests(self):
        import shlex
        import pytest
        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)


setup(
    name='seqtools',
    author="Nicolas Granger",
    author_email="nicolas.granger.m@gmail.com",
    description="A python library for lazy mapping of functions over "
                "sequences.",
    license="MPL2",
    url="https://github.com/nlgranger/SeqTools",
    packages=['seqtools'],
    version='0.8.1',
    install_requires=[
        'typing;python_version<"3.6"',
        'backports.weakref;python_version<"3"',
        'monotonic;python_version<"3"',
        'enum34;python_version<"3"',
        'future',
    ],
    extras_require={
        'error_info': ['tblib'],
    },
    tests_require=[
        'pytest', 'pytest-cov', 'tblib'
    ],
    cmdclass={'test': PyTest},
    python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*',
    keywords='mapping lazy delayed pipeline processing',
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Development Status :: 3 - Alpha",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research"
    ]
)
