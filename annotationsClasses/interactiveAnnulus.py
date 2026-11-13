from annotationsClasses.InteractiveCircle import InteractiveCircle


class InteractiveAnnulus(InteractiveCircle):
    """
    An interactive annular (donut-shaped) detector annotation.

    Subclass of InteractiveCircle that is always initialised with exactly two
    radii: an inner radius and an outer radius.  All interaction logic (drag,
    resize, blitting, signals) is inherited unchanged from InteractiveCircle.

    Parameters
    ----------
    axis : matplotlib.axes.Axes
        The axes on which the annulus is drawn.
    center : array-like, shape (2,)
        (x, y) centre of the annulus in data coordinates.
    inner_radius : float
        Radius of the inner boundary circle.
    outer_radius : float
        Radius of the outer boundary circle.
    color : str or matplotlib colour spec, optional
        Annotation colour.  Default ``'r'``.
    interactions : str, optional
        One of ``'all'``, ``'resize'``, ``'translate'``, or ``'none'``.
        Default ``'all'``.
    """

    def __init__(self, axis, center=None, inner_radius=0.0, outer_radius=1.0,
                 color='r', interactions='all'):
        # Ensure the radii are sorted so inner < outer, then delegate to parent.
        r_inner = min(inner_radius, outer_radius)
        r_outer = max(inner_radius, outer_radius)
        super().__init__(axis, center=center, radius=[r_inner, r_outer],
                         color=color, interactions=interactions)

    # ------------------------------------------------------------------
    # Convenience properties so callers can use semantic names.
    # ------------------------------------------------------------------

    @property
    def inner_radius(self):
        """The smaller of the two radii (innermost boundary)."""
        return float(self.radius[0])

    @inner_radius.setter
    def inner_radius(self, value):
        self.radius[0] = float(value)

    @property
    def outer_radius(self):
        """The larger of the two radii (outermost boundary)."""
        return float(self.radius[-1])

    @outer_radius.setter
    def outer_radius(self, value):
        self.radius[-1] = float(value)
