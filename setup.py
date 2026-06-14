"""
编译 Cython 搜索模块:
    python setup.py build_ext --inplace
"""
from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np

setup(
    name="cl_search",
    ext_modules=cythonize([
        Extension("cl_search", ["cl_search.pyx"],
                  include_dirs=[np.get_include()],
                  extra_compile_args=["-O3"])
    ], compiler_directives={"language_level":"3",
                            "boundscheck":False,
                            "wraparound":False,
                            "cdivision":True}),
)
