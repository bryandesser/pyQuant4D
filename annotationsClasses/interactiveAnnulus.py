from matplotlib.backend_tools import Cursors
from PyQt5 import QtCore as qtc
import numpy as np
import matplotlib.pyplot as plt

class InteractiveAnnulus(qtc.QObject):
    """
    Generate a circle with which the user can interact

    center:         (x,y) point pair defining the center of the annulus
    radius:         (2,) float/int defining the length of the inner and outer radii in axis units
    axis:           matplotlib.axes._subplots.AxesSubplot (i.e. self.Fig.Dfrn.ax)
    color:          matplotlib color specs (https://matplotlib.org/stable/tutorials/colors/colors.html)
    interactions:   'resize'        only radius can be changed, center is locked (default)
                    'translate'     only center can be changed, radius is locked
                    'all'           radius and center can be changed
                    'none'          no modifications allowed
    """
    updateAnnulus = qtc.pyqtSignal()

    lock = None #only one can be animated at a time

    def __init__(self, center, radius, axis, color, interactions='resize'):
        super().__init__()
        # properties
        self.x = np.cos(2 * np.pi * np.arange(0.0, 1.01, 0.01))
        self.y = np.sin(2 * np.pi * np.arange(0.0, 1.01, 0.01))
        self.center = np.array(center) # force conversion in case center is a tuple or list
        self.radius = np.array(radius)
        self.press = None
        self.transform = 'resize' # defines the current change, initialize as a resize action
        self.interactions = interactions
        self.color = color
        self.selectedPoint = None # reference to the selected point (innerPoint or outerPoint)

        # annotations
        self.innerCirc, = axis.plot(radius[0]*self.x+center[0],radius[0]*self.y+center[1],color=color)
        self.outerCirc, = axis.plot(radius[1]*self.x+center[0],radius[1]*self.y+center[1],color=color)
        self.innerPoint = axis.scatter(center[0]+radius[0],center[1],c=color)
        self.outerPoint = axis.scatter(center[0]+radius[1],center[1],c=color)
        if interactions in ["none","translate"]: # points are only needed for resizing
            self.innerPoint.set_visible(False)
            self.outerPoint.set_visible(False)
        
        # shortcuts
        self.canvas = self.innerCirc.figure.canvas
        self.axis = self.innerCirc.axes
        self.innerCirc.set_animated(True)
        self.outerCirc.set_animated(True)
        self.innerPoint.set_animated(True)
        self.outerPoint.set_animated(True)
        #self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(axis.bbox)
    
    def remove(self):
        '''allow the circle and dot to be removed from plots'''
        self.innerCirc.remove()
        self.outerCirc.remove()
        self.innerPoint.remove()
        self.outerPoint.remove()

    def connect(self):
        '''connect to all the events we need'''
        self.cidpress = self.canvas.mpl_connect('button_press_event', self.on_press)
        self.cidrelease = self.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion = self.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self, event):
        # in case self.interactions is changed programmatically, monitor point visibility
        if (self.interactions in ["all","resize"]) and ((self.innerPoint.get_visible()==False) or (self.outerPoint.get_visible()==False)):
            self.innerPoint.set_visible(True)
            self.outerPoint.set_visible(True)
        elif (self.interactions in ["none","translate"]) and ((self.innerPoint.get_visible()==True) or (self.outerPoint.get_visible()==True)):
            self.innerPoint.set_visible(False)
            self.outerPoint.set_visible(False)
            self.restoreBackground()
            
        if self.interactions == "none": return
        if event.inaxes != self.innerCirc.axes: return
        if InteractiveAnnulus.lock is not None: return

        # update center and radii
        self.center = np.mean(self.innerCirc._xy,axis=0)
        self.radius[0] = np.mean(np.linalg.norm(self.innerCirc._xy-self.center,axis=1))
        self.radius[1] = np.mean(np.linalg.norm(self.outerCirc._xy-self.center,axis=1))
        
        # check that mouse press contains the outer circle
        containsInnerCirc, _ = self.innerCirc.contains(event)
        containsInnerPoint, _ = self.innerPoint.contains(event)
        containsOuterCirc, _ = self.outerCirc.contains(event)
        containsOuterPoint, _ = self.outerPoint.contains(event)

        contains = (containsInnerCirc or containsInnerPoint or containsOuterCirc or containsOuterPoint)

        # check if press is within the radius of the outer circle (i.e. not ON the circle)
        if (np.linalg.norm((event.xdata,event.ydata)-self.center)<=self.radius[1]) and (self.interactions in ["all","translate"]):
            contains = True

        # if the click is not on or in the InteractiveAnnulus, exit now
        if not contains:
            self.updateBackground()
            return
        
        # reset selected point to None
        self.selectedPoint = None

        # check if the user has clicked on/near the point
        if (self.interactions in ["all","resize"]) and (containsInnerPoint or containsOuterPoint): # only change to the HAND pointer if resizing is allowed
            self.transform = 'resize'
            self.canvas.set_cursor(Cursors.HAND)
            if containsInnerPoint:
                self.selectedPoint = self.innerPoint
            elif containsOuterPoint:
                self.selectedPoint = self.outerPoint
        elif self.interactions in ["all","translate"]: # only translation allowed
            self.transform = 'translate'
            self.canvas.set_cursor(Cursors.HAND)
        else: #no interactions allowed
            self.canvas.set_cursor(Cursors.POINTER)
        
        # save info to the self.press 
        self.press = (self.innerCirc._x,self.innerCirc._y,self.outerCirc._x,self.outerCirc._y), (self.innerPoint.get_offsets(),self.outerPoint.get_offsets()), (event.xdata, event.ydata)

        InteractiveAnnulus.lock = self

        # draw everything but the selected circle and store the pixel buffer
        self.innerCirc.set_animated(True)
        self.outerCirc.set_animated(True)
        if self.innerPoint.get_visible() or self.outerPoint.get_visible():
            self.innerPoint.set_animated(True)
            self.outerPoint.set_animated(True)
        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.axis.bbox)

        # now redraw just the circle
        self.axis.draw_artist(self.innerCirc)
        self.axis.draw_artist(self.outerCirc)

        # and blit just the redrawn area
        self.canvas.blit(self.axis.bbox)

    def on_motion(self, event):
        # in case self.interactions is changed programmatically, monitor point visibility
        if (self.interactions in ["all","resize"]) and ((self.innerPoint.get_visible()==False) or (self.outerPoint.get_visible()==False)):
            self.innerPoint.set_visible(True)
            self.outerPoint.set_visible(True)
        elif (self.interactions in ["none","translate"]) and ((self.innerPoint.get_visible()==True) or (self.outerPoint.get_visible()==True)):
            self.innerPoint.set_visible(False)
            self.outerPoint.set_visible(False)
            self.restoreBackground()
        
        if self.interactions == "none": return
        if event.inaxes != self.innerCirc.axes: return

        # monitor mouse location, if hovering over InteractiveAnnulus,
        # change the cursor to MOVE, if not, return to standard pointer
        containsInnerCirc, _ = self.innerCirc.contains(event)
        containsInnerPoint, _ = self.innerPoint.contains(event)
        containsOuterCirc, _ = self.outerCirc.contains(event)
        containsOuterPoint, _ = self.outerPoint.contains(event)

        contains = (containsInnerCirc or containsInnerPoint or containsOuterCirc or containsOuterPoint)

        # check if cursor is within the radius of the outer circle (i.e. not ON the circle)
        if (np.linalg.norm((event.xdata,event.ydata)-self.center)<=self.radius[1]) and (self.interactions in ["all","translate"]):
            contains = True

        if self.press is None:
            (x0_inner, y0_inner), (x0_outer, y0_outer) = self.center, self.center
            pt0 = self.innerPoint.get_offsets()
            pt1 = self.outerPoint.get_offsets()
            (xpress,ypress) = self.center
        else:
            (x0_inner, y0_inner, x0_outer, y0_outer), (pt0,pt1), (xpress, ypress) = self.press

        dx = event.xdata - xpress
        dy = event.ydata - ypress

        # check if the user has clicked on/near the point or the circle
        if (contains) and (self.interactions in ["all","resize"]) and (containsInnerPoint or containsOuterPoint):
            self.canvas.set_cursor(Cursors.HAND)
        elif contains and (self.interactions in ["all","translate"]):
            self.canvas.set_cursor(Cursors.MOVE)
        else:
            self.canvas.set_cursor(Cursors.POINTER)
        
        # if no press event has happened, quit now
        if InteractiveAnnulus.lock is not self:    
            return

        if ('translate' in self.transform) and (self.interactions in ["all","translate"]):
            self.innerCirc.set_xdata(x0_inner+dx)
            self.innerCirc.set_ydata(y0_inner+dy)
            self.innerPoint.set_offsets(pt0+(dx,dy))
            self.outerCirc.set_xdata(x0_outer+dx)
            self.outerCirc.set_ydata(y0_outer+dy)
            self.outerPoint.set_offsets(pt1+(dx,dy))
            self.center = np.mean(self.innerCirc._xy,axis=0)
        elif (self.interactions in ["all","resize"]) and (self.selectedPoint != None):
            if self.selectedPoint == self.innerPoint:
                self.radius[0] = np.linalg.norm(pt0+(dx,dy)-self.center)
                self.innerPoint.set_offsets(pt0+(dx,dy))
                self.innerCirc.set_xdata(self.radius[0]*self.x + self.center[0])
                self.innerCirc.set_ydata(self.radius[0]*self.y + self.center[1])
            elif self.selectedPoint == self.outerPoint:
                self.radius[1] = np.linalg.norm(pt1+(dx,dy)-self.center)
                self.outerPoint.set_offsets(pt1+(dx,dy))
                self.outerCirc.set_xdata(self.radius[1]*self.x + self.center[0])
                self.outerCirc.set_ydata(self.radius[1]*self.y + self.center[1])

        self.restoreBackground()

        self.updateAnnulus.emit()

    def on_release(self, event):
        if self.interactions == "none": return

        'on release we reset the press data'
        if InteractiveAnnulus.lock is not self: return

        self.press = None
        self.selectedPoint = None
        InteractiveAnnulus.lock = None

        # update cursor
        self.canvas.set_cursor(Cursors.POINTER)

        # turn off the rect animation property and reset the background
        self.innerCirc.set_animated(False)
        self.outerCirc.set_animated(False)
        self.innerPoint.set_animated(False)
        self.outerPoint.set_animated(False)

        # redraw the full figure
        self.canvas.draw()

        # swap circles if user drags inner beyond outer, or vice versa
        if self.radius[0]>self.radius[1]:
            self.innerCirc, self.outerCirc = self.outerCirc, self.innerCirc
            self.innerPoint, self.outerPoint = self.outerPoint, self.innerPoint
            self.radius.sort()
    
    def redraw(self):
        """ update point and circle locations based on center/radius set externally """

        # both are currently in the wrong position, but using their locations BEFORE updating
        # gives the correct vector from the center of the circle to the dot, which allows it to
        # travel purely radially when being controlled externally
        
        vec = self.innerPoint.get_offsets()-np.mean(self.innerCirc._xy[:-1],axis=0)
        self.innerPoint.set_offsets(self.radius[0]*vec/np.linalg.norm(vec)+self.center)
        self.innerCirc.set_xdata(self.radius[0]*self.x+self.center[0])
        self.innerCirc.set_ydata(self.radius[0]*self.y+self.center[1])

        vec = self.outerPoint.get_offsets()-np.mean(self.outerCirc._xy[:,-1],axis=0)
        self.outerPoint.set_offsets(self.radius[1]*vec/np.linalg.norm(vec)+self.center)
        self.outerCirc.set_xdata(self.radius[1]*self.x+self.center[0])
        self.outerCirc.set_ydata(self.radius[1]*self.y+self.center[1])
        
        self.restoreBackground()

    def restoreBackground(self):
        # in case self.interactions is changed programmatically, monitor point visibility
        if (self.interactions in ["all","resize"]) and ((self.innerPoint.get_visible()==False) or (self.outerPoint.get_visible()==False)):
            self.innerPoint.set_visible(True)
            self.outerPoint.set_visible(True)
        elif (self.interactions in ["none","translate"]) and ((self.innerPoint.get_visible()==True) or (self.outerPoint.get_visible()==True)):
            self.innerPoint.set_visible(False)
            self.outerPoint.set_visible(False)
            self.restoreBackground()

        # restore the background region
        self.canvas.restore_region(self.background)

        # redraw just the current rectangle
        self.axis.draw_artist(self.innerCirc)
        self.axis.draw_artist(self.outerCirc)
        if self.innerPoint.get_visible() or self.outerPoint.get_visible():
            self.axis.draw_artist(self.innerPoint)
            self.axis.draw_artist(self.outerPoint)

        # blit just the redrawn area
        self.canvas.blit(self.axis.bbox)

    def updateBackground(self):
        # draw everything but the selected circle and store the pixel buffer
        self.innerCirc.set_animated(True)
        self.outerCirc.set_animated(True)
        self.innerPoint.set_animated(True)
        self.outerPoint.set_animated(True)
        self.canvas.draw()
        self.background = self.canvas.copy_from_bbox(self.axis.bbox)

        # now redraw just the circle
        self.axis.draw_artist(self.innerCirc)
        self.axis.draw_artist(self.outerCirc)
        if self.innerPoint.get_visible() or self.outerPoint.get_visible():
            self.axis.draw_artist(self.innerPoint)
            self.axis.draw_artist(self.outerPoint)

        # and blit just the redrawn area
        self.canvas.blit(self.axis.bbox)

    def setVisible(self,state):
        self.innerCirc.set_visible(state)
        self.innerPoint.set_visible(state)
        self.outerCirc.set_visible(state)
        self.outerPoint.set_visible(state)
        self.canvas.draw()