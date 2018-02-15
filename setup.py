from setuptools import setup


setup(
    name='seqtools',
    author="Nicolas Granger",
    author_email="nicolas.granger.m@gmail.com",
    description="A python library for lazy mapping of functions over "
                "sequences.",
    license="MPL2",
    url="https://github.com/nlgranger/SeqTools",
    packages=['seqtools'],
    version='0.7',
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
