.. _rois:

Real-Space ROIs
===============

Real-space Region-of-Interest (ROI) selection allows you to restrict the
diffraction pattern to frames from a chosen sub-region of the scan.  Only
frames within the ROI contribute to the displayed diffraction pattern.

ROI types
---------

- **Full** — all frames (default)
- **Point** — single frame at (FrameX, FrameY)
- **Rectangle** — axis-aligned rectangular region; drag corner handles to resize
- **Ellipse** — circular or elliptical region
- **Polygon** — arbitrary closed polygon drawn interactively
- **File** — load a boolean mask from a file

The mask can be **inverted** using the Invert ROI button, selecting all frames
*outside* the drawn region instead.

Usage
-----

1. Select the desired ROI type from the Real-space ROI dropdown in the main
   window.
2. If drawing a shape, an interactive annotation appears on the real-space image
   window.  Drag to position and resize.
3. The diffraction pattern updates live as the ROI is moved.

.. note::
   Full walkthrough with screenshots will be added in a future documentation
   update.
