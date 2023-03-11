import numpy as np
import matplotlib.patches as patches
from callbacks.annotationsClass import DraggablePoint


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
    r1 = 7.3614/np.sqrt(2) #TODO
    r2 = 2*r1

    # generate two points that a user can drag
    innerPt = self.Fig.Dfrn.ax.add_patch(patches.Circle((c[0]+r1,c[1]-r1),radius=1,color='r'))
    outerPt = self.Fig.Dfrn.ax.add_patch(patches.Circle((c[0]+r2,c[1]-r2),radius=1,color='r'))

    self.A.adfInnerPt = DraggablePoint(innerPt)
    self.A.adfOuterPt = DraggablePoint(outerPt)
    self.A.adfInnerPt.connect()
    self.A.adfOuterPt.connect()
    self.A.adfInnerPt.redrawCircle.connect(lambda: replotCirc(self))
    self.A.adfOuterPt.redrawCircle.connect(lambda: replotCirc(self))

    # add circles and points to pacbed plot
    self.A.adfInnerCirc = self.Fig.Dfrn.ax.plot(self.A.circX*r1*np.sqrt(2)+c[0],self.A.circY*r1*np.sqrt(2)+c[1],color='r')
    self.A.adfOuterCirc = self.Fig.Dfrn.ax.plot(self.A.circX*r2*np.sqrt(2)+c[0],self.A.circY*r2*np.sqrt(2)+c[1],color='r')

    
def replotCirc(self):
    r1 = np.linalg.norm(np.subtract(self.B0,self.A.adfInnerPt.point.center))
    self.A.adfInnerCirc[0].set_data(self.A.circX*r1+self.B0[0],self.A.circY*r1+self.B0[1])
    r2 = np.linalg.norm(np.subtract(self.B0,self.A.adfOuterPt.point.center))
    self.A.adfOuterCirc[0].set_data(self.A.circX*r2+self.B0[0],self.A.circY*r2+self.B0[1])
    #moveAnnR(self)

def moveAnnR(self):
    innerRadius,outerRadius = self.AnnRi.value()
    detRot = self.DetRot.value()
    scanDir = self.ScanDir.value()
    scanFlip = 1-2*self.ScanDirYFlip.isChecked()


    scale = self.DfPxR
    match self.sender():
        # case self.A.AnnInner: #TODO
        #     innerRadius = evt.CurrentRadius
        # case self.A.AnnOuter:
        #     outerRadius = evt.CurrentRadius
        case self.AnnRi:
            innerRadius,outerRadius = self.AnnRi.value()
        case self.AnnRi_NF:
            innerRadius = round(self.AnnRi_NF.value()/self.D.annWidth/scale)
        case self.AnnRo_NF:
            outerRadius = round(self.AnnRo_NF.value()/self.D.annWidth/scale)

    # Restrict Inner/Outer radii
    if self.sender() is self.AnnRi_NF: #TODO add annotations
        innerRadius = max(0, min(innerRadius, outerRadius))
    elif self.sender() is self.AnnRo_NF: #TODO add annotations
        outerRadius = min(max(outerRadius, innerRadius), self.P.RMax)

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
    self.A.adfInnerPt.point.center = self.B0 + np.array([1,-1])*self.AnnRi.value()[0]/np.sqrt(2)
    self.A.adfOuterPt.point.center = self.B0 + np.array([1,-1])*self.AnnRi.value()[1]/np.sqrt(2)
    replotCirc(self)

    # Update ROI #TODO
    #self.A.AnnInner.setRadius(innerRadius)
    #self.A.AnnOuter.setRadius(outerRadius)

    # Update UI with Limits check
    #setExself.sender()(evt, [self.AnnRi; self.AnnRo; self.AnnRi_NF; self.AnnRo_NF],{'Value'},{innerRadius; outerRadius; min(innerRadius*scale, self.P.RMax*scale); min(outerRadius*scale, self.P.RMax*scale)}); #TODO

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