# Configuration file for the Sphinx documentation builder.
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Make the package importable from the repo root (for autodoc).
sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------
project   = "pyQuant4D"
copyright = "Monash Imaging Physics, Monash University"
author    = "Bryan Esser"
release   = "0.1.0"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",    # Google / NumPy docstring style
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "myst_parser",            # Markdown support (for README inclusion)
]

templates_path   = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Allow both .rst and .md source files
source_suffix = {
    ".rst": "restructuredtext",
    ".md":  "markdown",
}

# -- Options for HTML output -------------------------------------------------
html_theme       = "furo"
html_static_path = ["_static"]

html_theme_options = {
    "source_repository": "https://github.com/bryandesser/pyQuant4D/",
    "source_branch":     "main",
    "source_directory":  "docs/",
}

# -- Intersphinx mapping -----------------------------------------------------
intersphinx_mapping = {
    "python":     ("https://docs.python.org/3", None),
    "numpy":      ("https://numpy.org/doc/stable", None),
    "matplotlib": ("https://matplotlib.org/stable", None),
    "scipy":      ("https://docs.scipy.org/doc/scipy", None),
}

# -- Autodoc settings --------------------------------------------------------
autodoc_member_order      = "bysource"
autodoc_typehints         = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring  = True
