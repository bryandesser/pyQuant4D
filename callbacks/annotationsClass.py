from matplotlib.backend_tools import Cursors
from PyQt5 import QtCore as qtc
import numpy as np

class DraggablePoint(qtc.QObject):
    redrawCircle = qtc.pyqtSignal()
    
    lock = None #only one can be animated at a time
    def __init__(self, point):
        super().__init__()
        self.point = point
        self.press = None
        self.idx = 0
        self.background = None
        self.radius = 1
    
    def remove(self):
        'allow the points to be removed from plots'
        self.point.remove()

    def connect(self):
        'connect to all the events we need'
        self.cidpress = self.point.figure.canvas.mpl_connect('button_press_event', self.on_press)
        self.cidrelease = self.point.figure.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion = self.point.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self, event):
        if event.inaxes != self.point.axes: return
        if DraggablePoint.lock is not None: return
        
        # check that mouse press contains one of the DraggablePoints
        contains, attrd = self.point.contains(event)

        if not contains: return
        # if the point is contained, save point index (i.e. adfInner or adfOuter)
        self.idx = attrd["ind"][0]

        # save info to the self.press 
        self.press = (self.point.get_offsets()[attrd["ind"][0]]), event.xdata, event.ydata

        DraggablePoint.lock = self

        # draw everything but the selected rectangle and store the pixel buffer
        canvas = self.point.figure.canvas
        axes = self.point.axes
        self.point.set_animated(True)
        canvas.draw()
        self.background = canvas.copy_from_bbox(self.point.axes.bbox)

        # update cursor
        canvas.set_cursor(Cursors.HAND)

        # now redraw just the rectangle
        axes.draw_artist(self.point)

        # and blit just the redrawn area
        canvas.blit(axes.bbox)

    def on_motion(self, event):
        # monitor mouse location, if hovering over a Draggable point,
        # change the cursor to HAND, if not, return to standard pointer
        contains, _ = self.point.contains(event)#,radius=self.radius)
        if contains:
            self.point.figure.canvas.set_cursor(Cursors.HAND)
        else:
            self.point.figure.canvas.set_cursor(Cursors.POINTER)

        if DraggablePoint.lock is not self:
            return
        if event.inaxes != self.point.axes: return

        self.point.center, xpress, ypress = self.press
        dx = event.xdata - xpress
        dy = event.ydata - ypress
        centers = self.point.get_offsets()
        centers[self.idx] = np.array([self.point.center[0]+dx, self.point.center[1]+dy])

        self.point.set_offsets(centers)

        canvas = self.point.figure.canvas
        axes = self.point.axes

        # restore the background region
        canvas.restore_region(self.background)

        # redraw just the current rectangle
        axes.draw_artist(self.point)

        # replot the annulus
        self.redrawCircle.emit()

    def on_release(self, event):
        'on release we reset the press data'
        if DraggablePoint.lock is not self:
            return

        self.press = None
        DraggablePoint.lock = None

        # update cursor
        self.point.figure.canvas.set_cursor(Cursors.POINTER)

        # turn off the rect animation property and reset the background
        self.point.set_animated(False)
        self.background = None

        # redraw the full figure
        self.point.figure.canvas.draw()       
    
    def setPointPickerRadius(self,radius):
        self.radius = radius/2
        self.point.set_sizes(2*[self.radius/2])

class InteractiveCircle(qtc.QObject):
    updateCircle = qtc.pyqtSignal()

    lock = None #only one can be animated at a time

    def __init__(self, center, radius, axis, color):
        super().__init__()
        # properties
        self.x = np.cos(2 * np.pi * np.arange(0.0, 1.01, 0.01))
        self.y = np.sin(2 * np.pi * np.arange(0.0, 1.01, 0.01))
        self.center = center
        self.radius = radius
        self.press = None
        self.transform = 'translate'

        # annotations
        self.circ, = axis.plot(radius*self.x+center[0],radius*self.y+center[1],color=color)
        self.point = axis.scatter(self.center[0]+self.radius,self.center[1],c=color)
        
        # shortcuts
        self.circCanvas = self.circ.figure.canvas
        self.circAxes = self.circ.axes
        self.ptCanvas = self.circ.figure.canvas
        self.ptAxes = self.circ.axes
        self.background = self.circ.figure.canvas.copy_from_bbox(axis.bbox)
        self.point.background = self.point.figure.canvas.copy_from_bbox(self.point.axes.bbox)
    
    def remove(self):
        'allow the circle and dot to be removed from plots'
        self.circ.remove()
        self.point.remove()

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
        self.circ.set_animated(True)
        self.point.set_animated(True)
        self.circCanvas.draw()
        self.ptCanvas.draw()
        self.background = self.circCanvas.copy_from_bbox(self.circAxes.bbox)
        self.point.background = self.ptCanvas.copy_from_bbox(self.ptAxes.bbox)

        # update cursor
        self.circCanvas.set_cursor(Cursors.MOVE)

        # now redraw just the circle
        self.circAxes.draw_artist(self.circ)
        self.ptAxes.draw_artist(self.point)

        # and blit just the redrawn area
        self.circCanvas.blit(self.circAxes.bbox)
        self.ptCanvas.blit(self.ptAxes.bbox)

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

        # restore the background region
        self.circCanvas.restore_region(self.background)
        self.ptCanvas.restore_region(self.point.background)

        # redraw just the current rectangle
        self.circAxes.draw_artist(self.circ)
        self.ptAxes.draw_artist(self.point)

        # blit just the redrawn area
        self.circCanvas.blit(self.circAxes.bbox)
        self.ptCanvas.blit(self.ptAxes.bbox)

        self.updateCircle.emit()

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
        #self.background = None
        #self.point.background = None

        # redraw the full figure
        self.circ.figure.canvas.draw()
        self.point.figure.canvas.draw()
    
    def redraw(self):
        #dxy = self.center - np.mean(self.circ._xy,axis=0)
        #self.point.set_offsets(self.point.get_offsets()+dxy)
        vec = self.point.get_offsets()-np.mean(self.circ._xy,axis=0)
        self.point.set_offsets(self.radius*vec/np.linalg.norm(vec)+self.center)
        self.circ.set_xdata(self.radius*self.x+self.center[0])
        self.circ.set_ydata(self.radius*self.y+self.center[1])
        
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