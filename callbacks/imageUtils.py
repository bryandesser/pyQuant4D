import numpy as np
from callbacks.annotationsClass import DraggablePoint
from PyQt5 import QtCore as qtc
import traceback, sys

class WorkerSignals(qtc.QObject):
    finished = qtc.pyqtSignal()
    error = qtc.pyqtSignal(tuple)
    result = qtc.pyqtSignal(np.ndarray)
    progress = qtc.pyqtSignal(int)


class Worker(qtc.QRunnable):
    def __init__(self, fn, *args):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args[0]
        self.signals = WorkerSignals()

    def run(self):
        # run the function, return results, and signal finished
        try:
            adfImages = self.fn(self.args)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(adfImages)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


def integrateAnnular(self):
    # generate meshgrid, divide by annulus width and round so distance increments away
    # from transmitted beam as integers to allow for direct use with QRangeSlider[int]
    # and array indexing; self.D.annWidth = 0.5 by default
    xgrid,ygrid = np.ogrid[-self.B0[0]:self.D.NPxX-self.B0[0],-self.B0[1]:self.D.NPxY-self.B0[1]]
    self.A.k = np.int32(np.sqrt(xgrid**2+ygrid**2)/self.D.annWidth)
    k = self.A.k.flatten()

    # generate a vector of pixel distances from transmitted beam center (divided by annWidth)
    distance = np.arange(0,k.max()+1)

    # create adf annular masks of annWidth pixel width
    adfMask = np.where((k.reshape(1,len(k))>=distance.reshape(len(distance),1)) & (k.reshape(1,len(k))<(distance.reshape(len(distance),1)+0.5)), True, False).T

    # generate all adf images from 0.0.5 pixel annuli; reshape to 3D for faster plotting
    self.adfImages = self.Data@adfMask
    self.adfImages = np.reshape(self.adfImages,(self.D.NFrY,self.D.NFrX,-1))

    # set adfInner and adfOuter slider limits based on k.max()
    self.AnnRi.setMaximum(k.max())

    # set adfInner and adfOuter numerical field limits based on k.max()/2
    self.AnnRi_NF.setMaximum(k.max()*self.D.annWidth)
    self.AnnRo_NF.setMaximum(k.max()*self.D.annWidth)
    
    # set maximum scattering angle
    self.P.RMax = k.max()

    return self.adfImages

def drawAnnDetr(self):
    """ initiallize the annular detector annotations """
    # define center location and starting radii for annular detector
    c = self.B0
    r1 = self.AnnRi.value()[0]/2
    r2 = self.AnnRi.value()[1]/2

    # # generate two points that a user can drag to control the annular detector
    if self.A.adfPt is None:
        self.A.adfPt = DraggablePoint(self.Fig.Dfrn.ax.scatter(c[0]+np.array([r1,r2]),c[1]-np.array([r1,r2]),s=25,c='r'))
        self.A.adfPt.connect()
        self.A.adfPt.redrawCircle.connect(lambda: moveAnnR(self))
        self.pointPickerRadius.connect(lambda: self.A.adfPt.setPointPickerRadius(self.screen().physicalDotsPerInch()))

    # add circles to pacbed plot, these are not draggable
    if self.A.adfInnerCirc is None:
        self.A.adfInnerCirc = self.Fig.Dfrn.ax.plot(self.A.circX*r1*np.sqrt(2)+c[0],self.A.circY*r1*np.sqrt(2)+c[1],color='r')[0]
    if self.A.adfOuterCirc is None:
        self.A.adfOuterCirc = self.Fig.Dfrn.ax.plot(self.A.circX*r2*np.sqrt(2)+c[0],self.A.circY*r2*np.sqrt(2)+c[1],color='r')[0]

def annDetrVisibility(self,state):
    # show/hide adf annotations
    self.A.adfInnerCirc._visible = state
    self.A.adfOuterCirc._visible = state
    self.A.adfPt.point.set_visible(state)
    self.Fig.Dfrn.canvas.draw()
    
def replotCirc(self):
    """ update the ciruclar annotations on the diffraction pattern """
    
    r1 = self.AnnRi.value()[0]/2
    self.A.adfInnerCirc.set_data(self.A.circX*r1+self.B0[0],self.A.circY*r1+self.B0[1])
    
    r2 = self.AnnRi.value()[1]/2
    self.A.adfOuterCirc.set_data(self.A.circX*r2+self.B0[0],self.A.circY*r2+self.B0[1])
    
    # update diffraction pattern figure
    self.Fig.Dfrn.canvas.draw()

def moveAnnR(self):
    # get QRangeSlider values
    innerRadius,outerRadius = self.AnnRi.value()
    
    # get diffraction scale set by user during alignment
    scale = self.DfPxR

    # get inner/outer adf radii from the calling widget
    match self.sender():
        # draggable points on annular detector annothation
        case self.A.adfPt:
            innerRadius, outerRadius = np.rint(np.linalg.norm(self.B0-self.A.adfPt.point.get_offsets(),axis=1)/self.D.annWidth).astype(int)
        # Inner Radius QDoubleSpinBox
        case self.AnnRi_NF:
            innerRadius = round(self.AnnRi_NF.value()/self.D.annWidth/scale)
        # Outer Radius QDoubleSpinBox 
        case self.AnnRo_NF:
            outerRadius = round(self.AnnRo_NF.value()/self.D.annWidth/scale)
            

    # allow user to drag inner/outer annulus over the other, swapping their relationships
    if innerRadius>outerRadius:
        innerRadius,outerRadius = outerRadius,innerRadius
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

    # update point centers when updated via QRangeSlider or QDoubleSpinBoxes
    if self.sender() is not self.A.adfPt:
        centers = self.A.adfPt.point.get_offsets()-self.B0
        angles = np.arctan2(centers[:,0],centers[:,1])
        centers = np.array([np.sin(angles),np.cos(angles)]).T*np.array([[innerRadius],[outerRadius]])*self.D.annWidth+self.B0
        self.A.adfPt.point.set_offsets(centers)

    # update circles on adf detector and refresh diffraction figure (self.Fig.Dfrn)
    replotCirc(self)

    #if isStaticEvt(evt): #TODO
    #    mockUICallbacks(app,self.SaveImgPrefix) # Update saving prefix

    # Whether to update segments as well #TODO
    #if dmod == "DPCMod":
    #    self.moveSeg()

    # refresh real-space image given new inner/outer radii
    # (add one to outer limit because python doesn't include the last term of the range)
    self.Image.Real.set_data(self.adfImages[:,:,innerRadius:outerRadius+1].sum(axis=2))
    self.Image.Real.autoscale()
    self.Fig.Real.canvas.draw()
    maskOpacity(self)

def detrCoordCallbacks(self):
    drawAnnDetr(self)

def maskOpacity(self):
    alpha = self.SettingsWindow.DispMaskOpa.value()/100 # mask opacity slider
    k = self.A.k.T # distance from optic axis
    mask = ((k>=self.AnnRi.value()[0])&(k<=self.AnnRi.value()[1]))*(alpha)+1-alpha
    self.Image.Dfrn.set_alpha(mask)
    self.Fig.Dfrn.canvas.draw()