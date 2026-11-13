Changelog
=========

0.1.0 (2026)
------------

Initial Python release.

- Ported all GUI and analysis functions from the original MATLAB Quant4D
  application.
- PyQt5 GUI with matplotlib-embedded image windows.
- Annular integration, CoM/DPC, iCoM, dCoM, and segmented-DPC modes.
- Real-space ROI selection and masking.
- Save images as 32-bit float TIFF or annotated PNG.
- Export datasets as HDF5 (gzip-compressed) or raw binary.
- Optional GPU acceleration via PyTorch.
- pip-installable package (``pip install pyquant4d``).
- GitHub Actions CI for lint and import tests on Linux and Windows.
- ReadTheDocs documentation.
