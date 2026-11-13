"""
histBoxWidget.py – Interactive histogram ROI for display-limit adjustment.

Replaces the MATLAB `drawrectangle` / `drawpoint` ROI combo.
The widget draws:
  • A semi-transparent rectangle spanning [limitLow, limitHigh]
  • A dashed blue vertical line at limitLow  (Lo handle)
  • A dashed red  vertical line at limitHigh (Hi handle)

Mouse interactions (all within the histogram axes):
  • Drag Lo line  → adjusts lower limit only
  • Drag Hi line  → adjusts upper limit only
  • Drag interior of the rect (not a handle) → translates both (brightness shift)
  • On button-release the on_change callback fires with (new_lo, new_hi)

The caller (updateDispImgStats) converts (lo, hi) back to slider values:
    brightness_slider = clamp(50 + (maxVal+minVal - hi - lo) / (2*intensityRange) * 100,  0, 100)
    contrast_slider   = clamp(2**((maxVal-minVal - hi + lo) / (2*intensityRange) * 2) * 50, 0, 100)
"""

import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
class HistBox:
    """Interactive histogram range selector."""

    # Width (in data units) of the hit-test zone around each handle line
    _HANDLE_FRAC = 0.015  # 1.5% of the x-axis span

    def __init__(self, ax, limitLow, limitHigh, on_change):
        """
        Parameters
        ----------
        ax         : matplotlib.axes.Axes  – the histogram axes
        limitLow   : float  – initial lower display limit
        limitHigh  : float  – initial upper display limit
        on_change  : callable(lo, hi)  – fired once on mouse-release
        """
        self.ax = ax
        self._lo = float(limitLow)
        self._hi = float(limitHigh)
        self.on_change = on_change

        # Drag state
        self._drag_mode = None   # 'lo' | 'hi' | 'box'
        self._press_x   = None
        self._press_lo  = None
        self._press_hi  = None

        # Visual elements
        self._span = ax.axvspan(limitLow, limitHigh,
                                alpha=0.15, color='steelblue', zorder=2,
                                label='_histbox_span')
        self._lo_line = ax.axvline(limitLow,
                                   color='dodgerblue', linewidth=1.5,
                                   linestyle='--', zorder=3,
                                   label='_histbox_lo')
        self._hi_line = ax.axvline(limitHigh,
                                   color='tomato', linewidth=1.5,
                                   linestyle='--', zorder=3,
                                   label='_histbox_hi')

        canvas = ax.figure.canvas
        self._cid_press   = canvas.mpl_connect('button_press_event',   self._on_press)
        self._cid_move    = canvas.mpl_connect('motion_notify_event',  self._on_move)
        self._cid_release = canvas.mpl_connect('button_release_event', self._on_release)

    # ── public ────────────────────────────────────────────────────────────────

    def update_position(self, lo, hi):
        """Reposition the visuals (called externally when sliders change)."""
        self._lo = float(lo)
        self._hi = float(hi)
        self._redraw()
        self.ax.figure.canvas.draw_idle()

    def remove(self):
        """Detach events and remove all artists."""
        canvas = self.ax.figure.canvas
        for cid in (self._cid_press, self._cid_move, self._cid_release):
            canvas.mpl_disconnect(cid)
        for artist in (self._span, self._lo_line, self._hi_line):
            try:
                artist.remove()
            except Exception:
                pass

    # ── private ───────────────────────────────────────────────────────────────

    def _redraw(self):
        lo, hi = self._lo, self._hi
        # Update axvspan: its polygon has vertices at x = lo and x = hi
        poly = self._span.get_xy()
        poly[:, 0] = [lo, lo, hi, hi, lo]
        self._span.set_xy(poly)
        # Update the two handle lines
        self._lo_line.set_xdata([lo, lo])
        self._hi_line.set_xdata([hi, hi])

    def _handle_tol(self):
        xl = self.ax.get_xlim()
        return self._HANDLE_FRAC * abs(xl[1] - xl[0])

    def _on_press(self, event):
        if event.inaxes is not self.ax or event.xdata is None:
            return
        x   = event.xdata
        tol = self._handle_tol()

        if abs(x - self._lo) <= tol:
            self._drag_mode = 'lo'
        elif abs(x - self._hi) <= tol:
            self._drag_mode = 'hi'
        elif self._lo < x < self._hi:
            self._drag_mode = 'box'
        else:
            return  # click outside → ignore

        self._press_x  = x
        self._press_lo = self._lo
        self._press_hi = self._hi

    def _on_move(self, event):
        if self._drag_mode is None:
            return
        if event.inaxes is not self.ax or event.xdata is None:
            return

        dx = event.xdata - self._press_x
        xl = self.ax.get_xlim()
        x0, x1 = min(xl), max(xl)

        if self._drag_mode == 'lo':
            new_lo = np.clip(self._press_lo + dx, x0, self._hi)
            self._lo = float(new_lo)
        elif self._drag_mode == 'hi':
            new_hi = np.clip(self._press_hi + dx, self._lo, x1)
            self._hi = float(new_hi)
        elif self._drag_mode == 'box':
            width  = self._press_hi - self._press_lo
            new_lo = np.clip(self._press_lo + dx, x0, x1 - width)
            self._lo = float(new_lo)
            self._hi = float(new_lo + width)

        self._redraw()
        self.ax.figure.canvas.draw_idle()

    def _on_release(self, event):
        if self._drag_mode is None:
            return
        self._drag_mode = None
        # Fire callback so the caller can update sliders
        try:
            self.on_change(self._lo, self._hi)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def histbox_to_sliders(lo, hi, minVal, maxVal):
    """
    Convert histogram ROI edges to (brightness_slider, contrast_slider).

    Inverse of the display-limit formula in plotImage:
        limitLow  = minVal − (brightness − contrast) * intensityRange
        limitHigh = maxVal − (brightness + contrast) * intensityRange

    Returns
    -------
    brightness_slider : float clamped [0, 100]
    contrast_slider   : float clamped [0, 100]
    """
    intensityRange = maxVal - minVal
    if intensityRange == 0 or not np.isfinite(intensityRange):
        return 50.0, 50.0

    brightness_raw = (maxVal + minVal - hi - lo) / (2.0 * intensityRange)
    brightness_slider = _clamp(50.0 + brightness_raw * 100.0, 0.0, 100.0)

    # contrast in log2 space: contrast = log2(fig.contrast/50)/2
    # → fig.contrast = 50 * 2^(2*contrast_raw)
    contrast_raw = (maxVal - minVal - hi + lo) / (2.0 * intensityRange)
    eps = np.finfo(np.single).eps
    contrast_linear = 2.0 ** (2.0 * contrast_raw)   # = fig.contrast / 50
    contrast_slider = _clamp(50.0 * max(contrast_linear, eps), 0.0, 100.0)

    return brightness_slider, contrast_slider
