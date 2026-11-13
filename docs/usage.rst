Usage
=====

Launching the application
--------------------------

After installation, launch pyQuant4D from the command line::

    quant4d

or run directly from the repository root::

    python Quant4D_app.py

Loading a dataset
-----------------

1. Click the **Import Data** button (or use the menu) to open the import
   dialog.
2. Navigate to your data file.  Supported formats:

   - **DM4 / DM3** — Gatan DigitalMicrograph files
   - **Raw binary** — specify byte order, header offsets, and frame/pixel
     dimensions manually
   - **HDF5** — HDF5 files with a dataset path

3. Set the real-space frame size (NFrX × NFrY) and diffraction-pattern size
   (NPxX × NPxY).
4. Optionally swap X/Y axes if the data dimensions are transposed.
5. Click **Import** to load the dataset.

A progress bar is shown for large files.  On machines with a compatible GPU,
data are loaded directly to GPU memory when possible.

Detector modes
--------------

Switch between analysis modes using the **Detector Mode** selector:

Alignment mode
    Displays the summed diffraction pattern to allow beam-centre alignment and
    annular-radii setup.

Annular integration
    Integrates intensity within the annular detector (inner radius *Ri*, outer
    radius *Ro*) at each probe position to produce a real-space image (ADF, BF,
    ABF, etc.).

CoM / DPC mode
    Computes the intensity-weighted centre-of-mass of each diffraction pattern
    within the annular mask.  Produces **CoM X**, **CoM Y**, **CoM Magnitude**,
    and **CoM Phase** images, plus the Fourier-reconstructed **iCoM** (integrated
    CoM) and **dCoM** (differential CoM / divergence) images.

Segmented DPC mode
    Divides the detector into angular segments and computes directional
    differential phase contrast signals.

Image display controls
----------------------

Each image window has brightness, contrast, and gamma sliders that adjust the
display without modifying the underlying data.  Right-click an image for
additional options (save, copy, etc.).

A vector-field overlay showing CoM deflection arrows can be enabled per image
in CoM/DPC mode.

Saving and exporting
--------------------

Open the **Save / Export** panel from the toolbar.

**Save images** tab
    Select one or more images from the list, choose a directory and filename
    prefix, then save as:

    - **TIFF** — 32-bit float, lossless
    - **PNG** — 8-bit, with optional annotations (scale bar, colourbar)

**Export dataset** tab
    Export the raw 4-D dataset (all frames, or a sub-range) as:

    - **HDF5** — gzip-compressed, with metadata stored in a ``/metadata``
      group
    - **Raw binary** — specify byte order; metadata written to a sidecar
      ``.txt`` file
