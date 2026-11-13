.. _dpc_com:

DPC and Centre-of-Mass
======================

Centre-of-Mass (CoM) and Differential Phase Contrast (DPC) modes compute the
intensity-weighted centroid of each diffraction pattern within the annular mask,
yielding direct access to the projected electric field and charge density.

Output images
-------------

CoM mode produces the following real-space images:

- **CoM X** — horizontal component of the centre-of-mass deflection
- **CoM Y** — vertical component of the centre-of-mass deflection
- **CoM Magnitude** — magnitude of the deflection vector
- **CoM Phase** — angle of the deflection vector
- **iCoM** — integrated CoM (Fourier reconstruction), proportional to the
  projected electrostatic potential
- **dCoM** — divergence of CoM, proportional to the projected charge density

Segmented DPC
-------------

The segmented DPC mode divides the detector into *N* angular wedge segments.
Each segment produces a separate real-space DPC image.  The number of segments
and detector rotation angle are controlled from the main window.

.. note::
   Full mathematical background and usage walkthrough will be added in a future
   documentation update.
