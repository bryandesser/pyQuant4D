from matplotlib.backend_tools import Cursors
from PyQt5 import QtCore as qtc
import numpy as np
import matplotlib.pyplot as plt

class InteractiveCircle(qtc.QObject):
    """
    Generate a circle with which the user can interact

    center:         (x,y) point pair defining the center of the circle
    radius:         float/int defining the length of the radius in axis units
    axis:           matplotlib.axes._subplots.AxesSubplot (i.e. self.Fig.Dfrn.ax)
    color:          matplotlib color specs (https://matplotlib.org/stable/tutorials/colors/colors.html)
    interactions:   'resize'        only radius can be changed, center is locked
                    'translate'     only center can be changed, radius is locked
                    'all'           radius and center can be changed (default)
                    'none'          no modifications allowed
    """
    updateCircle = qtc.pyqtSignal()

    lock = None #only one can be animated at a time

    def __init__(self, center, radius, axis, color, interactions='all'):
        super().__init__()
        # properties
        self.x = np.cos(2 * np.pi * np.arange(0.0, 1.01, 0.01))
        self.y = np.sin(2 * np.pi * np.arange(0.0, 1.01, 0.01))
        self.center = np.array(center) # force conversion in case center is a tuple or list
        self.radius = radius
        self.press = None
        self.transform = 'translate'
        self.interactions = interactions
        self.color = color

        # annotations
        self.circ, = axis.plot(radius*self.x+center[0],radius*self.y+center[1],color=color)
        self.point = axis.scatter(center[0]+radius,center[1],c=color)
        if interactions in ["none","translate"]:
            self.point.set_visible(False)
        
        # shortcuts
        self.canvas = self.circ.figure.canvas
        self.axis = self.circ.axes
        self.circ.set_animated(True)
        self.point.set_animated(True)
        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(axis.bbox)
    
    def remove(self):
        'allow the circle and dot to be removed from plots'
        self.circ.remove()
        self.point.remove()

    def connect(self):
        'connect to all the events we need'
        self.cidpress = self.canvas.mpl_connect('button_press_event', self.on_press)
        self.cidrelease = self.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion = self.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self, event):
        # in case self.interactions is changed programmatically, monitor point visibility
        if (self.interactions in ["all","resize"]) and (self.point.get_visible()==False):
            self.point.set_visible(True)
        elif (self.interactions in ["none","translate"]) and (self.point.get_visible()==True):
            self.point.set_visible(False)
            self.restoreBackground()
            
        if self.interactions == "none": return
        if event.inaxes != self.circ.axes: return
        if InteractiveCircle.lock is not None: return

        # update center and radius
        self.center = np.mean(self.circ._xy,axis=0)
        self.radius = np.mean(np.linalg.norm(self.circ._xy-self.center,axis=1))
        
        # check that mouse press contains the InteractiveCircle
        contains, _ = self.circ.contains(event)

        # check if hand is within InteractiveCircle (i.e. not ON the InteractiveCircle)
        if (np.linalg.norm((event.xdata,event.ydata)-self.center)<=self.radius) and (self.interactions in ["all","translate"]):
            contains = True

        # if the click is not on or in the InteractiveCircle, exit now
        if not contains:
            return
        
        # check if the user has clicked on/near the point
        if (self.interactions in ["all","resize"]) and (np.linalg.norm((event.xdata,event.ydata)-self.point.get_offsets())<=5): # only change to the HAND pointer if resizing is allowed
            self.transform = 'resize'
            self.canvas.set_cursor(Cursors.HAND)
        elif self.interactions in ["all","translate"]: # only translation allowed
            self.transform = 'translate'
            self.canvas.set_cursor(Cursors.HAND)
        else: #no interactions allowed
            self.canvas.set_cursor(Cursors.POINTER)
        
        # save info to the self.press 
        self.press = (self.circ._x,self.circ._y), self.point.get_offsets(), (event.xdata, event.ydata)

        InteractiveCircle.lock = self

        # draw everything but the selected circle and store the pixel buffer
        self.circ.set_animated(True)
        if self.point.get_visible():
            self.point.set_animated(True)
        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.axis.bbox)


        # now redraw just the circle
        self.axis.draw_artist(self.circ)

        # and blit just the redrawn area
        self.canvas.blit(self.axis.bbox)

    def on_motion(self, event):
        # in case self.interactions is changed programmatically, monitor point visibility
        if (self.interactions in ["all","resize"]) and (self.point.get_visible()==False):
            self.point.set_visible(True)
        elif (self.interactions in ["none","translate"]) and (self.point.get_visible()==True):
            self.point.set_visible(False)
            self.restoreBackground()
        
        if self.interactions == "none": return
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
        if (contains) and (self.interactions in ["all","resize"]) and (np.linalg.norm((event.xdata,event.ydata)-self.point.get_offsets())<=5):
            self.canvas.set_cursor(Cursors.HAND)
        elif contains and (self.interactions in ["all","translate"]):
            self.canvas.set_cursor(Cursors.MOVE)
        else:
            self.canvas.set_cursor(Cursors.POINTER)
        
        # if no press event has happened, quit now
        if InteractiveCircle.lock is not self:    
            return

        if ('translate' in self.transform) and (self.interactions in ["all","translate"]):
            self.circ.set_xdata(x0+dx)
            self.circ.set_ydata(y0+dy)
            self.point.set_offsets(pt0+(dx,dy))
            self.center = np.mean(self.circ._xy,axis=0)
        elif (self.interactions in ["all","resize"]):
            self.radius = np.linalg.norm(pt0 + (dx,dy) - self.center)
            self.circ.set_xdata(self.radius*self.x + self.center[0])
            self.circ.set_ydata(self.radius*self.y + self.center[1])
            self.point.set_offsets(pt0+(dx,dy))

        self.restoreBackground()

        self.updateCircle.emit()

    def on_release(self, event):
        if self.interactions == "none": return

        'on release we reset the press data'
        if InteractiveCircle.lock is not self: return

        self.press = None
        InteractiveCircle.lock = None

        # update cursor
        self.canvas.set_cursor(Cursors.POINTER)

        # turn off the rect animation property and reset the background
        self.circ.set_animated(False)
        self.point.set_animated(False)

        # redraw the full figure
        self.canvas.draw()
    
    def redraw(self):
        # update point and circle locations based on center/radius set externally
        vec = self.point.get_offsets()-np.mean(self.circ._xy,axis=0)-self.center
        self.point.set_offsets(self.radius*vec/np.linalg.norm(vec)+self.center)
        self.circ.set_xdata(self.radius*self.x+self.center[0])
        self.circ.set_ydata(self.radius*self.y+self.center[1])
        
        self.restoreBackground()

    def restoreBackground(self):
        # in case self.interactions is changed programmatically, monitor point visibility
        if (self.interactions in ["all","resize"]) and (self.point.get_visible()==False):
            self.point.set_visible(True)
        elif (self.interactions in ["none","translate"]) and (self.point.get_visible()==True):
            self.point.set_visible(False)
            self.restoreBackground()

        # restore the background region
        self.canvas.restore_region(self.background)

        # redraw just the current rectangle
        self.axis.draw_artist(self.circ)
        if self.point.get_visible():
            self.axis.draw_artist(self.point)

        # blit just the redrawn area
        self.canvas.blit(self.axis.bbox)

    def updateBackground(self):
        # draw everything but the selected circle and store the pixel buffer
        self.circ.set_animated(True)
        self.point.set_animated(True)
        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.axis.bbox)

        # now redraw just the circle
        self.axis.draw_artist(self.circ)
        if self.point.get_visible():
            self.axis.draw_artist(self.point)

        # and blit just the redrawn area
        self.canvas.blit(self.axis.bbox)
    
    def setVisible(self,state):
        self.circ.set_visible(state)
        self.point.set_visible(state)
        self.canvas.draw()