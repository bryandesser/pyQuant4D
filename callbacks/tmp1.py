from callbacks.annotationsClass import DraggablePoint
from callbacks.imageUtils import moveAnnR, integrateAnnular
import numpy as np

def annularDetectorCallbacks(self):
    b0 = self.B0  # Absolute pixel coordinates of central beam; only changes in `transBeamCallbacks()`
    dmod = self.DetrMode.currentData() # Detector mode; when changed this callback will be called

    ii=1
    images = {}
    event2 = {}

    match self.sender():
        case self.SettingsWindow.DCSys: # Change coordinate options
            limitAnnUI(self) # UI limits
        case self.DetrMode: # Entering current mode
            limitAnnUI(self) # UI limits
            self.ScanDirUnlock.Value = 0; # Lock scan directions first upon entering annular modes
            enableAnnUI(self) # UI enable/disable
            integrateAnnular(self) # Update annular integral mask
            drawAnnDetr(self) # Draw detectors
            if dmod == "DPCMod":
                drawSegDetr(self) # Whether to draw segmented detectors
            moveAnnDetr(self) # Update UI/ROIs
            enableWindows(self,True) # Enable windows
        case self.AnnRi|self.AnnRi_NF|self.AnnRo|self.AnnRo_NF|self.AnnRLink|self.DetRot|self.DetRot_NF|self.NSeg|self.NRung|self.ScanDir|self.ScanDir_NF|self.ScanDirYFlip|self.UpdateImages:
            moveAnnDetr(self) # Update UI/ROIs
        case self.ScanDirUnlock:
            self.P.ScanDirInit = 1; # Flag scan directions as aligned
            enableAnnUI(self) # Enable/Disable GUI elements
            # Try to remove existing scan direction ROIs
            for scanAnnot in dir(self.A):
                if "ScanDir" in scanAnnot:
                    try:
                        getattr(self.A,scanAnnot).remove()
                    except:
                        pass
                    finally:
                        setattr(self.A,scanAnnot,None)
            if self.ScanDirUnlock.value():
                drawScanDir(self) # Draw annotations
            #mockUICallbacks(self,self.ShowDfrnAxes) # Update diffraction axes annotations #TODO

# Function to enable/disable UI
def enableAnnUI(self):
    dmod = self.DetrMode.currentData() # Detector mode; when changed this callback will be called
    # Change Enable state of scan direction UIs, except `self.ScanDirUnlock`
    self.ScanDirUnlock.setEnable(dmod in ["CoMMod","DPCMod"])
    # Highlight to align Scanning Direction
    if (dmod in ["CoMMod","DPCMod"]) and not self.P.ScanDirInit:
        bc = self.C.WarnC
    else:
        bc = self.C.BgC
    #self.comControls.setStyleSheet = bc; # Set scan direction panel color #TODO

# Function to update Annular detector UI limits/labels when coordinate options change
def limitAnnUI(self):
    self.AnnRi_NFLabel.self.AnnRi_NF.setSuffix(" "+self.SettingsWindow.DCUnit.currentText())
    self.AnnRo_NFLabel.self.AnnRi_NF.setSuffix(" "+self.SettingsWindow.DCUnit.currentText())
    
    self.AnnRi_NF.setRange(0,self.P.RMax*self.DfPxR)
    self.AnnRo_NF.setRange(0,self.P.RMax*self.DfPxR)
    self.AnnRi_NF.setSingleStep(0.25*self.DfPxR)
    self.AnnRo_NF.setSingleStep(0.25*self.DfPxR)

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