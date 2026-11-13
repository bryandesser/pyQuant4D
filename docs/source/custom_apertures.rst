.. _custom_apertures:

Custom Apertures
================

Custom aperture mode allows an arbitrary mask to be drawn on the diffraction
pattern to define the integration region for the real-space image.

Supported aperture types:

- **Rectangle** — axis-aligned draggable rectangle
- **Ellipse / Circle** — circular or elliptical region
- **Polygon** — arbitrary closed polygon drawn interactively with
  ``PolygonSelector``

After drawing an aperture, the real-space image updates to reflect the
integrated intensity within the selected region.  The aperture can be
repositioned by dragging.

.. note::
   This mode is currently under active development.  Full documentation will be
   added when the feature is complete.
