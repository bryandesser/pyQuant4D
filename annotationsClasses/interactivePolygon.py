from matplotlib.backend_tools import Cursors
from matplotlib.backend_bases import MouseButton
from matplotlib.backend_bases import MouseEvent
from matplotlib.patches import Polygon
from matplotlib.path import Path
from PyQt5 import QtCore as qtc
import numpy as np


class InteractivePolygon(qtc.QObject):
    """
    A draggable, vertex-editable polygon drawn on a matplotlib axes.

    The polygon is supplied as a fixed set of vertices (drawn once a user
    has sketched them with PolygonSelector and confirmed the shape).
    Translate the whole polygon by clicking inside; move individual vertices
    by clicking on a vertex handle.

    Parameters
    ----------
    axis : matplotlib Axes
    vertices : (N, 2) array-like — initial polygon vertices in data coords
    color  : matplotlib color spec
    interactions : 'all' | 'translate' | 'resize' | 'none'
        'all'       — translate body + move individual vertices
        'translate' — drag the whole polygon only
        'resize'    — drag individual vertices only
        'none'      — display only
    """

    updatePoly = qtc.pyqtSignal()
    rightClick  = qtc.pyqtSignal(MouseEvent)

    lock = None   # only one InteractivePolygon active at a time

    def __init__(self, axis, vertices, color='r', interactions='all'):
        super().__init__()

        self.vertices     = np.asarray(vertices, dtype=float)   # (N, 2)
        self.color        = color
        self.interactions = interactions

        self.transform      = None   # 'translate' | 'vertex'
        self.press          = None   # (verts0, (xp, yp))
        self._active_vertex = None   # int index into self.vertices

        # Animated polygon patch
        self.patch = Polygon(
            self.vertices, closed=True, fill=False,
            edgecolor=color, linewidth=1.5, animated=True
        )
        axis.add_patch(self.patch)

        # Vertex handles
        self.handles = axis.scatter(
            self.vertices[:, 0], self.vertices[:, 1],
            color=color, s=36, zorder=5, animated=True
        )
        if interactions in ('none', 'translate'):
            self.handles.set_visible(False)

        self.canvas = axis.figure.canvas
        self.axis   = axis

        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.axis.bbox)

    # ------------------------------------------------------------------ props

    @property
    def centroid(self):
        """Geometric centroid of the vertex set."""
        return np.mean(self.vertices, axis=0)

    # ------------------------------------------------------------------ helpers

    def _update_artists(self):
        self.patch.set_xy(self.vertices)
        self.handles.set_offsets(self.vertices)

    def _hit_test(self, event):
        """
        Return (on_vertex, inside, vertex_idx).
        on_vertex : cursor is on a handle.
        inside    : cursor is inside the polygon or on a handle.
        vertex_idx: int or None.
        """
        if event.xdata is None or event.ydata is None:
            return False, False, None

        # Check vertex handles
        on_vertex, attrd = self.handles.contains(event)
        vertex_idx = attrd['ind'][-1] if on_vertex else None

        # Point-in-polygon via matplotlib Path
        path   = Path(np.vstack([self.vertices, self.vertices[0]]))
        inside = path.contains_point([event.xdata, event.ydata])

        return on_vertex, (inside or on_vertex), vertex_idx

    # ------------------------------------------------------------------ public

    def connect(self):
        self.cidpress   = self.canvas.mpl_connect('button_press_event',   self.on_press)
        self.cidrelease = self.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion  = self.canvas.mpl_connect('motion_notify_event',  self.on_motion)

    def remove(self):
        self.patch.remove()
        self.handles.remove()

    def redraw(self):
        """Refresh artists after external change to self.vertices."""
        self._update_artists()
        self.restoreBackground()

    def mask(self, shape):
        """
        Return a boolean mask of *shape* = (ny, nx) where True means the
        pixel centre falls inside this polygon.
        """
        ny, nx = shape
        yy, xx = np.mgrid[0:ny, 0:nx]
        pts    = np.column_stack([xx.ravel(), yy.ravel()])
        path   = Path(np.vstack([self.vertices, self.vertices[0]]))
        return path.contains_points(pts).reshape(ny, nx)

    # ------------------------------------------------------------------ events

    def on_press(self, event):
        if event.button == MouseButton.RIGHT:
            self.rightClick.emit(event)
            return
        if self.interactions == 'none':           return
        if event.inaxes != self.axis:             return
        if InteractivePolygon.lock is not None:   return

        on_vertex, inside, vertex_idx = self._hit_test(event)
        if not inside:
            return

        if on_vertex and self.interactions in ('all', 'resize'):
            self.transform      = 'vertex'
            self._active_vertex = vertex_idx
            self.canvas.set_cursor(Cursors.HAND)
        elif self.interactions in ('all', 'translate'):
            self.transform      = 'translate'
            self._active_vertex = None
            self.canvas.set_cursor(Cursors.MOVE)
        else:
            return

        self.press = (self.vertices.copy(),
                      np.array([event.xdata, event.ydata]))
        InteractivePolygon.lock = self

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
        if InteractivePolygon.lock is not self:      return
        if self.press is None or event.xdata is None: return

        verts0, (xp, yp) = self.press
        dx = event.xdata - xp
        dy = event.ydata - yp

        if self.transform == 'translate':
            self.vertices = verts0 + np.array([dx, dy])
        elif self.transform == 'vertex' and self._active_vertex is not None:
            self.vertices = verts0.copy()
            self.vertices[self._active_vertex] += np.array([dx, dy])

        self._update_artists()
        self.restoreBackground()
        self.updatePoly.emit()

    def on_release(self, event):
        if InteractivePolygon.lock is not self:
            return
        self.press          = None
        self.transform      = None
        self._active_vertex = None
        InteractivePolygon.lock = None

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
