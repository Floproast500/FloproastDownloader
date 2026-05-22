"""Build the Cython fractal extension: python setup_fractal.py build_ext --inplace"""
from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy as np
import sys

if sys.platform == "win32":
    # MSVC — /O2 = full optimisation, /openmp = OpenMP parallel loops
    cc_args  = ["/O2", "/openmp"]
    lnk_args = []          # MSVC links OpenMP automatically with /openmp
else:
    # GCC / Clang
    cc_args  = ["-O3", "-march=native", "-fopenmp"]
    lnk_args = ["-fopenmp"]

ext = Extension(
    "fractal",
    sources       = ["fractal.pyx"],
    include_dirs  = [np.get_include()],
    extra_compile_args = cc_args,
    extra_link_args    = lnk_args,
)

setup(
    name       = "fractal",
    ext_modules = cythonize(
        ext,
        compiler_directives={
            "boundscheck":    False,
            "wraparound":     False,
            "cdivision":      True,
            "nonecheck":      False,
            "language_level": "3",
        },
        annotate = False,
    ),
)
