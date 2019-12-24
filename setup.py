from setuptools import setup, find_packages, Extension


setup(
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
