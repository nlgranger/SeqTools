from setuptools import setup

setup(
    name='lproc',
    author="Nicolas Granger",
    author_email="nicolas.granger.m@gmail.com",
    description="A python library for lazy mapping of functions over "
                "sequences.",
    license="MPL2",
    url="https://github.com/nlgranger/LazyProc",
    packages=['lproc'],
    version='0.6',
    install_requires=[
        'tblib',
        'typing;python_version<"3.6"'
    ],
    python_requires='>=3',
    keywords='mapping lazy delayed pipeline processing',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Topic :: Software Development :: Libraries",
    ]
)
