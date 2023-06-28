from callbacks.allFunctions import enableWindows, drawAnnDetr, integrateAnnular

def annularDetectorCallbacks(self):
    b0 = self.B0  # Absolute pixel coordinates of central beam; only changes in `transBeamCallbacks()`
    dmod = self.DetrMode.currentData() # Detector mode; when changed this callback will be called

    match self.sender():
        case self.DCSys: # Change coordinate options
            limitAnnUI() # UI limits
        case self.DetrMode: # Entering current mode
            limitAnnUI() # UI limits
            self.ScanDirUnlock.setValue(0) # Lock scan directions first upon entering annular modes
            enableAnnUI() # UI enable/disable
            integrateAnnular() # Update annular integral mask
            drawAnnDetr() # Draw detectors
            if dmod == "DPCMod":
                drawSegDetr() # Whether to draw segmented detectors
            moveAnnDetr(event.Source, event) # Update UI/ROIs
            enableWindows(self,True) # Enable windows
        case self.AnnRi|self.AnnRi_NF|self.AnnRo|self.AnnRo_NF|self.AnnRLink|self.DetRot|self.DetRot_NF|self.NSeg|self.NRung|self.ScanDir|self.ScanDir_NF|self.ScanDirYFlip|self.UpdateImages:
            pass #moveAnnDetr(event.Source, event) # Update UI/ROIs
        case self.ScanDirUnlock:
            self.P.ScanDirInit = 1; # Flag scan directions as aligned
            enableAnnUI() # Enable/Disable GUI elements
            delete(findobj(self.Axes.Dfrn,'Tag','ScanDirAnnot')); # Try to remove existing scan direction ROIs
            if self.ScanDirUnlock.Value:
                drawScanDir() # Draw annotations
            mockUICallbacks(self,self.ShowDfrnAxes) # Update diffraction axes annotations

# Function to enable/disable UI
def enableAnnUI(self):
    # current detector mode
    dmod = self.DetrMode.currentData()

    # Disable/enable segmented panel
    self.dpcControls.setEnabled(dmod == "DPCMod")

    # Change Enable state of scan direction UIs, except `self.ScanDirUnlock`
    self.comControls.setEnabled(self.ScanDirUnlock.isChecked())
    self.ScanDirUnlock.setEnabled(dmod in ["CoMMod","DPCMod"])

    # Highlight to align Scanning Direction
    if (dmod in ["CoMMod" "DPCMod"]) and (not self.P.ScanDirInit):
        bc = self.C.WarnC.name()
    else:
        bc = self.C.BgC.name()
    self.ScanDirGrid.BackgroundColor = bc # Set scan direction panel color
    self.comControls.setStyleSheet("background-color:"+bc)