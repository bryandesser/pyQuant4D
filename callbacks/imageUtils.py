import numpy as np
import matplotlib.patches as patches
from callbacks.annotationsClass import DraggablePoint
from PyQt5 import QtCore as qtc


def integrateAnnular(self):
    # generate meshgrid, divide by annulus width and round so distance increments away
    # from transmitted beam as integers to allow for direct use with QRangeSlider[int]
    # and array indexing; self.D.annWidth = 0.5 by default
    xgrid,ygrid = np.ogrid[-self.B0[0]:self.D.NPxX-self.B0[0],-self.B0[1]:self.D.NPxY-self.B0[1]]
    k = np.int32(np.sqrt(xgrid**2+ygrid**2)/self.D.annWidth).flatten()

    # generate a vector of pixel distances from transmitted beam center (divided by annWidth)
    distance = np.arange(0,k.max()+1)

    # create adf annular masks of annWidth pixel width
    adfMask = np.where((k.reshape(1,len(k))>=distance.reshape(len(distance),1)) & (k.reshape(1,len(k))<(distance.reshape(len(distance),1)+0.5)), True, False).T

    # generate all adf images from 0.0.5 pixel annuli; reshape to 3D for faster plotting
    self.adfImages = self.Data@adfMask
    self.adfImages=np.reshape(self.adfImages,(self.D.NFrX,self.D.NFrY,-1))

    # set adfInner and adfOuter slider limits based on k.max()
    self.AnnRi.setMaximum(k.max())

    # set adfInner and adfOuter numerical field limits based on k.max()/2
    self.AnnRi_NF.setMaximum(k.max()*self.D.annWidth)
    self.AnnRo_NF.setMaximum(k.max()*self.D.annWidth)
    
    # set maximum scattering angle
    self.P.RMax = k.max()

def drawAnnDetr(self):
    c = self.B0
    r1 = self.AnnRi.value()[0]
    r2 = self.AnnRi.value()[0]

    # generate two points that a user can drag
    if self.A.adfInnerPt is None:
        self.A.adfInnerPt = DraggablePoint(self.Fig.Dfrn.ax.add_patch(patches.Circle((c[0]+r1,c[1]-r1),radius=1,color='r')))
        self.A.adfInnerPt.connect()
        self.A.adfInnerPt.redrawCircle.connect(lambda: moveAnnR(self))
        self.pointPickerRadius.connect(lambda: self.A.adfInnerPt.setPointPickerRadius(self.screen().physicalDotsPerInch()))

    if self.A.adfOuterPt is None:    
        self.A.adfOuterPt = DraggablePoint(self.Fig.Dfrn.ax.add_patch(patches.Circle((c[0]+r2,c[1]-r2),radius=1,color='r')))
        self.A.adfOuterPt.connect()
        self.A.adfOuterPt.redrawCircle.connect(lambda: moveAnnR(self))
        self.pointPickerRadius.connect(lambda: self.A.adfOuterPt.setPointPickerRadius(self.screen().physicalDotsPerInch()))

    # add circles and points to pacbed plot
    if self.A.adfInnerCirc is None:
        self.A.adfInnerCirc = self.Fig.Dfrn.ax.plot(self.A.circX*r1*np.sqrt(2)+c[0],self.A.circY*r1*np.sqrt(2)+c[1],color='r')
    if self.A.adfOuterCirc is None:
        self.A.adfOuterCirc = self.Fig.Dfrn.ax.plot(self.A.circX*r2*np.sqrt(2)+c[0],self.A.circY*r2*np.sqrt(2)+c[1],color='r')

    
def replotCirc(self):
    r1 = self.AnnRi.value()[0]/2
    self.A.adfInnerCirc[0].set_data(self.A.circX*r1+self.B0[0],self.A.circY*r1+self.B0[1])
    r2 = self.AnnRi.value()[1]/2
    self.A.adfOuterCirc[0].set_data(self.A.circX*r2+self.B0[0],self.A.circY*r2+self.B0[1])
    self.Fig.Dfrn.canvas.draw()

def moveAnnR(self):
    innerRadius,outerRadius = self.AnnRi.value()

    scale = self.DfPxR
    match self.sender():
        case self.A.adfInnerPt: #TODO
            innerRadius = round(np.linalg.norm(np.subtract(self.B0,self.A.adfInnerPt.point.center))/self.D.annWidth)
        case self.A.adfOuterPt:
            outerRadius = round(np.linalg.norm(np.subtract(self.B0,self.A.adfOuterPt.point.center))/self.D.annWidth)
        case self.AnnRi:
            innerRadius,outerRadius = self.AnnRi.value()
        case self.AnnRi_NF:
            innerRadius = round(self.AnnRi_NF.value()/self.D.annWidth/scale)
        case self.AnnRo_NF:
            outerRadius = round(self.AnnRo_NF.value()/self.D.annWidth/scale)

    # allow user to drag inner/outer annulus over the other, swapping their relationships
    if innerRadius>outerRadius:
        innerRadius,outerRadius = outerRadius,innerRadius
        self.A.adfInnerPt,self.A.adfOuterPt = self.A.adfOuterPt,self.A.adfInnerPt
        self.A.adfInnerCirc,self.A.adfOuterCirc = self.A.adfOuterCirc,self.A.adfInnerCirc

    # inner radius cannot be less than 0
    if innerRadius<0:
        innerRadius = 0

    # outer radius cannot be greater than max scattering angle
    if outerRadius>self.P.RMax:
        outerRadius = self.P.RMax
    
    # avoid triggering a valueChanged loop by blocking signals
    self.AnnRi.blockSignals(True)
    self.AnnRi_NF.blockSignals(True)
    self.AnnRo_NF.blockSignals(True)

    # set slider and numerical field values
    self.AnnRi.setValue((innerRadius,outerRadius))
    self.AnnRi_NF.setValue(innerRadius*self.D.annWidth*scale)
    self.AnnRo_NF.setValue(outerRadius*self.D.annWidth*scale)

    # unblock trigger signals
    self.AnnRi.blockSignals(False)
    self.AnnRi_NF.blockSignals(False)
    self.AnnRo_NF.blockSignals(False)

    # update point centers
    self.A.adfInnerPt.point.center = self.B0 + np.array([1,-1])*self.AnnRi.value()[0]*self.D.annWidth/np.sqrt(2)
    self.A.adfOuterPt.point.center = self.B0 + np.array([1,-1])*self.AnnRi.value()[1]*self.D.annWidth/np.sqrt(2)
    replotCirc(self)

    #if isStaticEvt(evt): #TODO
    #    mockUICallbacks(app,self.SaveImgPrefix) # Update saving prefix

    # Whether to update segments as well #TODO
    #if dmod == "DPCMod":
    #    self.moveSeg()

    # add one to outer limit because python doesn't include the last term
    self.Image.Real.set_data(self.adfImages[:,:,innerRadius:outerRadius+1].sum(axis=2))
    self.Image.Real.autoscale()
    self.Fig.Real.canvas.draw()

def detrCoordCallbacks(self):
    drawAnnDetr(self)