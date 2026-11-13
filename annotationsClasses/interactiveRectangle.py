from matplotlib.backend_tools import Cursors
from matplotlib.backend_bases import MouseButton
from matplotlib.backend_bases import MouseEvent
from matplotlib.patches import Polygon
from PyQt5 import QtCore as qtc
import numpy as np


class InteractiveRectangle(qtc.QObject):
    """
    A draggable, resizable rectangle drawn on a matplotlib axes, following
    the same blitting-based design as InteractiveCircle.

    Parameters
    ----------
    axis : matplotlib Axes
    center : (x, y) pair — defaults to axes mid-point
    size   : (w, h) pair — defaults to 20 % of axes range
    rotation : float, degrees — CCW rotation (default 0)
    color  : matplotlib color spec
    interactions : 'all' | 'translate' | 'resize' | 'none'
    """

    updateRect = qtc.pyqtSignal()
    rightClick  = qtc.pyqtSignal(MouseEvent)

    lock = None   # only one InteractiveRectangle active at a time

    def __init__(self, axis, center=None, size=None,
                 rotation=0.0, color='r', interactions='all'):
        super().__init__()

        xl, xr = sorted(axis.get_xlim())
        yl, yr = sorted(axis.get_ylim())
        ax_w, ax_h = xr - xl, yr - yl

        if center is None:
            center = [(xl + xr) / 2.0, (yl + yr) / 2.0]
        if size is None:
            size = [0.2 * ax_w, 0.2 * ax_h]

        self.center     = np.asarray(center, dtype=float)
        self.size       = np.asarray(size,   dtype=float)
        self.rotation   = float(rotation)
        self.color      = color
        self.interactions = interactions

        self.transform      = None   # 'translate' | 'resize'
        self.press          = None   # (center0, size0, (xp, yp))
        self._active_corner = None   # index 0-3

        # Rectangle drawn as an animated Polygon patch
        self.patch = Polygon(
            self._corners(), closed=True, fill=False,
            edgecolor=color, linewidth=1.5, animated=True
        )
        axis.add_patch(self.patch)

        # Corner handles as a scatter collection
        corners = self._corners()
        self.handles = axis.scatter(
            corners[:, 0], corners[:, 1],
            color=color, s=36, zorder=5, animated=True
        )
        if interactions in ('none', 'translate'):
            self.handles.set_visible(False)

        self.canvas = axis.figure.canvas
        self.axis   = axis

        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.axis.bbox)

    # ------------------------------------------------------------------ helpers

    def _corners(self, center=None, size=None, rotation=None):
        """Return the 4 corners of the rectangle as a (4, 2) array."""
        cx, cy = self.center   if center   is None else center
        w,  h  = (self.size    if size     is None else size) / 2.0
        rot    =  self.rotation if rotation is None else rotation
        theta  = np.radians(rot)
        c, s   = np.cos(theta), np.sin(theta)
        R      = np.array([[c, -s], [s, c]])
        local  = np.array([[-w, -h], [w, -h], [w, h], [-w, h]])
        return local @ R.T + np.array([cx, cy])

    def _update_artists(self):
        corners = self._corners()
        self.patch.set_xy(corners)
        self.handles.set_offsets(corners)

    def _hit_test(self, event):
        """
        Return (on_corner, inside, corner_idx).
        on_corner: True if cursor is on a resize handle.
        inside:    True if cursor is inside the rectangle.
        corner_idx: 0-3, or None.
        """
        if event.xdata is None or event.ydata is None:
            return False, False, None

        # Check corner handles
        on_corner, attrd = self.handles.contains(event)
        corner_idx = attrd['ind'][-1] if on_corner else None

        # Check containment in local (un-rotated) frame
        pt = np.array([event.xdata, event.ydata])
        theta = np.radians(self.rotation)
        c, s  = np.cos(theta), np.sin(theta)
        R_inv = np.array([[c, s], [-s, c]])     # transpose = inverse rotation
        local = R_inv @ (pt - self.center)
        inside = bool(np.all(np.abs(local) <= self.size / 2.0))

        return on_corner, (inside or on_corner), corner_idx

    # ------------------------------------------------------------------ public

    def connect(self):
        self.cidpress   = self.canvas.mpl_connect('button_press_event',   self.on_press)
        self.cidrelease = self.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion  = self.canvas.mpl_connect('motion_notify_event',  self.on_motion)

    def remove(self):
        self.patch.remove()
        self.handles.remove()

    def redraw(self):
        """Update artists when center / size / rotation change externally."""
        self._update_artists()
        self.restoreBackground()

    # ------------------------------------------------------------------ events

    def on_press(self, event):
        if event.button == MouseButton.RIGHT:
            self.rightClick.emit(event)
            return
        if self.interactions == 'none':             return
        if event.inaxes != self.axis:               return
        if InteractiveRectangle.lock is not None:   return

        on_corner, inside, corner_idx = self._hit_test(event)
        if not inside:
            return

        if on_corner and self.interactions in ('all', 'resize'):
            self.transform      = 'resize'
            self._active_corner = corner_idx
            self.canvas.set_cursor(Cursors.HAND)
        elif self.interactions in ('all', 'translate'):
            self.transform = 'translate'
            self.canvas.set_cursor(Cursors.MOVE)
        else:
            return

        self.press = (self.center.copy(), self.size.copy(),
                      np.array([event.xdata, event.ydata]))
        InteractiveRectangle.lock = self

        self.patch.set_animated(True)
        self.handles.set_animated(self.handles.get_visible())
        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.axis.bbox)
        self.axis.draw_artist(self.patch)
        if self.handles.get_visible():
            self.axis.draw_artist(self.handles)
        self.canvas.blit(self.axis.bbox)

    def on_motion(self, event):
        if self.interactions == 'none':              return
        if event.inaxes != self.axis:                return
        if InteractiveRectangle.lock is not self:    return
        if self.press is None or event.xdata is None: return

        center0, size0, (xp, yp) = self.press
        dx = event.xdata - xp
        dy = event.ydata - yp

        if self.transform == 'translate':
            self.center = center0 + np.array([dx, dy])

        elif self.transform == 'resize' and self._active_corner is not None:
            # Keep the corner diagonally opposite fixed
            opp_idx = (self._active_corner + 2) % 4
            corners0 = self._corners(center0, size0, self.rotation)
            fixed   = corners0[opp_idx]
            moved   = corners0[self._active_corner] + np.array([dx, dy])
            new_center = (fixed + moved) / 2.0

            # Project (moved - fixed) onto local axes to get new half-widths
            theta = np.radians(self.rotation)
            c, s  = np.cos(theta), np.sin(theta)
            R_inv = np.array([[c, s], [-s, c]])
            diff  = R_inv @ (moved - fixed)
            new_size = np.abs(diff)
            if np.any(new_size < 1e-6):
                return
            self.center = new_center
            self.size   = new_size

        self._update_artists()
        self.restoreBackground()
        self.updateRect.emit()

    def on_release(self, event):
        if InteractiveRectangle.lock is not self:
            return
        self.press          = None
        self.transform      = None
        self._active_corner = None
        InteractiveRectangle.lock = None

        self.patch.set_animated(False)
        self.handles.set_animated(False)
        self.canvas.draw()

    # ------------------------------------------------------------------ blit

    def restoreBackground(self):
        self.canvas.restore_region(self.background)
        self.axis.draw_artist(self.patch)
        if self.handles.get_visible():
            self.axis.draw_artist(self.handles)
        self.canvas.blit(self.axis.bbox)

    def updateBackground(self):
        self.patch.set_animated(True)
        self.handles.set_animated(True)
        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.axis.bbox)
        self.axis.draw_artist(self.patch)
        if self.handles.get_visible():
            self.axis.draw_artist(self.handles)
        self.canvas.blit(self.axis.bbox)
