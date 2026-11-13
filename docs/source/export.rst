.. _export:

Saving and Exporting
====================

Open the **Save / Export** panel from the toolbar.

Launching the application
-------------------------

After installation, launch pyQuant4D from the command line::

    quant4d

or run directly from the repository root::

    python Quant4D_app.py

Save images
-----------

Select one or more images from the list, choose a directory and filename
prefix, then save as:

- **TIFF** — 32-bit float, lossless
- **PNG** — 8-bit, with optional annotations (scale bar, colourbar)

Export dataset
--------------

Export the raw 4-D dataset (all frames, or a sub-range) as:

- **HDF5** — gzip-compressed, with metadata stored in a ``/metadata`` group
- **Raw binary** — specify byte order; metadata written to a sidecar ``.txt``
  file

A progress bar is shown during export.  Partial frame or pixel ranges can be
exported to reduce file size.
