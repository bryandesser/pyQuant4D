from matplotlib.backend_tools import Cursors
from PyQt5 import QtCore as qtc
import numpy as np

class InteractiveCircle(qtc.QObject):
    
    lock = None #only one can be animated at a time

    def __init__(self, circ):
        super().__init__()
        self.circ = circ
        self.press = None
        self.background = None
        self.center = np.mean(self.circ._xy,axis=0)
        self.radius = np.mean(np.linalg.norm(self.circ._xy-self.center,axis=1))
        self.point = self.circ.axes.scatter(self.center[0]+self.radius,self.center[1])
        self.transform = 'translate'
        self.x = np.cos(2 * np.pi * np.arange(0.0, 1.01, 0.01))
        self.y = np.sin(2 * np.pi * np.arange(0.0, 1.01, 0.01))
    
    def remove(self):
        'allow the circle to be removed from plots'
        self.circ.remove()

    def connect(self):
        'connect to all the events we need'
        self.cidpress = self.circ.figure.canvas.mpl_connect('button_press_event', self.on_press)
        self.cidrelease = self.circ.figure.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion = self.circ.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self, event):
        if event.inaxes != self.circ.axes: return
        if InteractiveCircle.lock is not None: return

        # update center and radius
        self.center = np.mean(self.circ._xy,axis=0)
        self.radius = np.mean(np.linalg.norm(self.circ._xy-self.center,axis=1))
        
        # check that mouse press contains the InteractiveCircle
        contains, _ = self.circ.contains(event)

        # check if hand is within InteractiveCircle (i.e. not ON the InteractiveCircle)
        if np.linalg.norm((event.xdata,event.ydata)-self.center)<=self.radius:
            contains = True

        # if the click is not on or in the InteractiveCircle, exit now
        if not contains:
            return
        
        # check if the user has clicked on/near the point
        if np.linalg.norm((event.xdata,event.ydata)-self.point.get_offsets())<=1:
            self.transform = 'resize'
            self.circ.figure.canvas.set_cursor(Cursors.HAND)
        else:
            self.transform = 'translate'
            self.circ.figure.canvas.set_cursor(Cursors.HAND)
        
        # save info to the self.press 
        self.press = (self.circ._x,self.circ._y), self.point.get_offsets(), (event.xdata, event.ydata)

        InteractiveCircle.lock = self

        # draw everything but the selected circle and store the pixel buffer
        circCanvas = self.circ.figure.canvas
        circAxes = self.circ.axes
        ptCanvas = self.point.figure.canvas
        ptAxes = self.point.axes
        self.circ.set_animated(True)
        self.point.set_animated(True)
        circCanvas.draw()
        ptCanvas.draw()
        self.background = circCanvas.copy_from_bbox(circAxes.bbox)
        self.point.background = ptCanvas.copy_from_bbox(ptAxes.bbox)

        # update cursor
        circCanvas.set_cursor(Cursors.MOVE)

        # now redraw just the circle
        circAxes.draw_artist(self.circ)
        ptAxes.draw_artist(self.point)

        # and blit just the redrawn area
        circCanvas.blit(circAxes.bbox)
        ptCanvas.blit(ptAxes.bbox)

    def on_motion(self, event):
        if event.inaxes != self.circ.axes: return

        # monitor mouse location, if hovering over a InteractiveCircle,
        # change the cursor to MOVE, if not, return to standard pointer
        contains, _ = self.circ.contains(event)

        # check if hand is within InteractiveCircle (i.e. not ON the InteractiveCircle)
        if np.linalg.norm((event.xdata,event.ydata)-self.center)<=self.radius:
            contains=True

        if self.press is None:
            (x0,y0) = self.center
            pt0 = self.point.get_offsets()
            (xpress,ypress) = self.center
        else:
            (x0, y0), pt0, (xpress, ypress) = self.press

        dx = event.xdata - xpress
        dy = event.ydata - ypress

        # check if the user has clicked on/near the point or the circle
        if contains and np.linalg.norm((event.xdata,event.ydata)-self.point.get_offsets())<=5:
            self.circ.figure.canvas.set_cursor(Cursors.HAND)
        elif contains:
            self.circ.figure.canvas.set_cursor(Cursors.MOVE)
        else:
            self.circ.figure.canvas.set_cursor(Cursors.POINTER)
        
        # if no press event has happened, quit now
        if InteractiveCircle.lock is not self:    
            return

        if 'translate' in self.transform:
            self.circ.set_xdata(x0+dx)
            self.circ.set_ydata(y0+dy)
            self.point.set_offsets(pt0+(dx,dy))
            self.center = np.mean(self.circ._xy,axis=0)
        else:
            self.radius = np.linalg.norm(pt0 + (dx,dy) - self.center)
            self.circ.set_xdata(self.radius*self.x + self.center[0])
            self.circ.set_ydata(self.radius*self.y + self.center[1])
            self.point.set_offsets(pt0+(dx,dy))

        circCanvas = self.circ.figure.canvas
        circAxes = self.circ.axes
        ptCanvas = self.circ.figure.canvas
        ptAxes = self.circ.axes

        # restore the background region
        circCanvas.restore_region(self.background)
        ptCanvas.restore_region(self.point.background)

        # redraw just the current rectangle
        circAxes.draw_artist(self.circ)
        ptAxes.draw_artist(self.point)

        # blit just the redrawn area
        circCanvas.blit(circAxes.bbox)
        ptCanvas.blit(ptAxes.bbox)

    def on_release(self, event):
        'on release we reset the press data'
        if InteractiveCircle.lock is not self:
            return

        self.press = None
        InteractiveCircle.lock = None

        # update cursor
        self.circ.figure.canvas.set_cursor(Cursors.POINTER)

        # turn off the rect animation property and reset the background
        self.circ.set_animated(False)
        self.point.set_animated(False)
        self.background = None
        self.point.background = None

        # redraw the full figure
        self.circ.figure.canvas.draw()
        self.point.figure.canvas.draw()