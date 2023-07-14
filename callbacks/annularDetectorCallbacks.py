from callbacks.allFunctions import enableWindows,plotImage,isDiffToPrev,plotImage
from annotationsClasses.interactiveAnnulus import InteractiveAnnulus
import numpy as np

def annularDetectorCallbacks(self):

    def limitAnnUI(self):
        """ Function to update Annular detector UI limits/labels when coordinate options change """
        self.AnnRi_NF.blockSignals(True)
        self.AnnRo_NF.blockSignals(True)
        self.AnnRi_NF.setSuffix(" "+self.SettingsWindow.DCUnit.currentData())
        self.AnnRo_NF.setSuffix(" "+self.SettingsWindow.DCUnit.currentData())
        self.AnnRi_NF.setRange(0,self.P.RMax*self.DfPxR)
        self.AnnRo_NF.setRange(0,self.P.RMax*self.DfPxR)
        self.AnnRi_NF.setSingleStep(0.25*self.DfPxR)
        self.AnnRo_NF.setSingleStep(0.25*self.DfPxR)
        self.AnnRi_NF.blockSignals(False)
        self.AnnRo_NF.blockSignals(False)

    def enableAnnUI(self):
        """ Function to enable/disable UI """
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

    def moveAnnDetr():
        """ Function to live update annular/round/segmented detectors """

        def moveAnnR(self):
            """ Sub sub function for annular radii """

            # get QRangeSlider values
            innerRadius,outerRadius = self.AnnRi.value()
            
            # get diffraction scale set by user during alignment
            scale = self.DfPxR

            # get inner/outer adf radii from the calling widget
            match self.sender():
                # InteractiveAnnulus
                case self.A.adf:
                    innerRadius, outerRadius = (self.A.adf.radius/self.D.annWidth).astype(int)
                # Inner Radius QDoubleSpinBox
                case self.AnnRi_NF:
                    innerRadius = round(self.AnnRi_NF.value()/self.D.annWidth/scale)
                # Outer Radius QDoubleSpinBox 
                case self.AnnRo_NF:
                    outerRadius = round(self.AnnRo_NF.value()/self.D.annWidth/scale)

            # allow user to drag inner/outer annulus over the other, swapping their relationships
            if innerRadius>outerRadius:
                innerRadius,outerRadius = outerRadius,innerRadius
                #self.A.adfInnerCirc,self.A.adfOuterCirc = self.A.adfOuterCirc,self.A.adfInnerCirc #TODO delete?

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
            if self.sender() is not self.A.adf:
                self.A.adf.radius = np.array([innerRadius,outerRadius]).clip(np.finfo(np.single).eps,self.P.RMax)*self.D.annWidth
                self.A.adf.redraw()

            #if isStaticEvt(evt): #TODO
            #    mockUICallbacks(app,self.SaveImgPrefix) # Update saving prefix

            # Whether to update segments as well #TODO
            #if dmod == "DPCMod":
            #    self.moveSeg()

            # refresh real-space image given new inner/outer radii
            # (add one to outer limit because python doesn't include the last term of the range)
            if len(self.Fig.Real.ax.images)==0:
                self.Image.Real = self.Data.sum(axis=1).reshape(self.D.NFrY,self.D.NFrX)
                self.ImageAx.Real = self.Fig.Real.ax.imshow(self.Image.Real)
            else:
                self.Image.Real = self.adfImages[:,:,innerRadius:outerRadius+1].sum(axis=2)
                self.ImageAx.Real.set_data(self.Image.Real)
            
            self.ImageAx.Real.autoscale()
            self.Fig.Real.canvas.draw()
        def moveSeg():
            pass
        def moveScan():
            pass

        # current detector mode
        dmod = self.DetrMode.currentData()

        ri,ro = self.AnnRi.value()
        dr = self.DetRot.value()
        sd = self.ScanDir.value()
        syf = 1-2*self.ScanDirYFlip.isChecked()

        # Cases for different detectors #TODO - no .Tag attributes
        match self.sender():
            case self.A.adf:
                moveAnnR(self)
            case self.A.SegDetrCir|self.A.SegDetrL|self.A.SegDetrL0|self.A.SegDetrP0:
                moveSeg(self)
            case self.A.ScanDirXline|self.A.ScanDirYline|self.A.ScanDirXcirc|self.A.ScanDirYcirc:
                moveScan(self)
            case self.DetrMode|self.UpdateImages:
                moveAnnR(self)
                if self.ScanDirUnlock.isChecked():
                    moveScan(self)  # Update scan directions as well
        
        # Whether to update images
        if toUpdateImage(self):
            # Skip calculations of new BF/DF `self.Image.Real` if annular radii are not changed
            if isDiffToPrev(self,'AnnR',[ri,ro]): #or isStaticEvt(evt)
                # 2D matrix of distances from central beam, X/Y on the 1st/2nd dimensions
                mask_ann = np.sqrt((np.arange(0,self.D.NPxX)-self.B0[0])**2 + (np.arange(0,self.D.NPxY)-self.B0[1])**2)
                mask_ann = (mask_ann >= ri) and (mask_ann <= ro)
                self.Image.DfrnMask = mask_ann
                # (add one to outer limit because python doesn't include the last term of the range)
                self.Image.Real = self.adfImages[:,:,ri:ro+1].sum(axis=2)
          
            # CoM/DPC calculations; skip if parameters unchanged
            if dmod in ["CoMMod", "DPCMod"]:
                if isDiffToPrev(self,'CoM_P',[ri,ro,sd,syf,dr]): # or isStaticEvt(evt):
                    calcCoM(ri, ro, sd, syf, dr)
            
            # Update images
            plotAllPatterns(self)
    
    def drawAnnDetr(self):
        """ initiallize the annular detector annotations """
        # define center location and starting radii for annular detector
        c = self.B0
        r1 = self.AnnRi.value()[0]*self.D.annWidth
        r2 = self.AnnRi.value()[1]*self.D.annWidth
    
        # generate adf detector
        if self.A.adf is None:
            self.A.adf = InteractiveAnnulus(center=c, radius=(r1,r2), axis=self.Fig.Dfrn.ax, color='r', interactions='resize')
            self.A.adf.connect()
            self.A.adf.updateAnnulus.connect(lambda: moveAnnDetr(self))
    
    def drawSegDetr():
        pass
    
    def drawScanDir():
        pass
    
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

    def plotAllPatterns(self):
        # always update primary and mask images
        ids = [iID for iType,iID in zip(self.G.ImgType,self.G.ImgID) if iType in ["Primary","Mask"]]
        # update CoM/DPC images if in the correct mode
        if self.DetrMode.currentData() in ["CoMMod","DPCMod"]:
            ids += [iID for iType,iID in zip(self.G.ImgType,self.G.ImgID) if (iID != "ColorWheel") and (iType=='CoM')]
        
        # Update images if visible OR not in changing event; include CoMs if in the modes
        for id in ids:
            if self.Fig[id].isVisible(): # or isStaticEvt(evt): #TODO?
                plotImage(self, id)
    
    def calcCoM():
        def integrateCoM():
            pass
        pass


    b0 = self.B0  # Absolute pixel coordinates of central beam; only changes in `transBeamCallbacks()`
    dmod = self.DetrMode.currentData() # Detector mode; when changed this callback will be called

    match self.sender():
        case self.DCSys: # Change coordinate options
            limitAnnUI(self) # UI limits
        case self.DetrMode: # Entering current mode
            limitAnnUI(self) # UI limits
            self.ScanDirUnlock.setChecked(False) # Lock scan directions first upon entering annular modes
            enableAnnUI(self) # UI enable/disable
            integrateAnnular(self) # Update annular integral mask
            drawAnnDetr(self) # Draw detectors
            if dmod == "DPCMod":
                drawSegDetr() # Whether to draw segmented detectors
            moveAnnDetr(self) # Update UI/ROIs
            enableWindows(self,True) # Enable windows
        case self.AnnRi|self.AnnRi_NF|self.AnnRo|self.AnnRo_NF|self.AnnRLink|self.DetRot|self.DetRot_NF|self.NSeg|self.NRung|self.ScanDir|self.ScanDir_NF|self.ScanDirYFlip|self.UpdateImages:
            moveAnnDetr(self) # Update UI/ROIs
        case self.ScanDirUnlock:
            self.P.ScanDirInit = 1; # Flag scan directions as aligned
            enableAnnUI(self) # Enable/Disable GUI elements
            self.A.removeGroup('ScanDir') # Try to remove existing scan direction ROIs
            if self.ScanDirUnlock.isChecked(self):
                drawScanDir(self) # Draw annotations
            self.SettingsWindow.ShowDfrnAxes.click() # Update diffraction axes annotations


""" external functions """

def toUpdateImage(self):
    """
    Function to determine whether to update images
    Return true if any: 1) `self.SettingsWindow.CalcPolicy.currentData()` is 2 (active update)
                    OR 2) `self.SettingsWindow.CalcPolicy.currentData()` is 1 (reduced) and not when changing
                    OR 3) is a manual update (from update buttons or detector mode change)
    #TODO - currently does not support reduced update functionality
    """
    calc = self.SettingsWindow.CalcPolicy.currentData()
    #upd = (calc == 2) or (calc and isStaticEvt(evt)) or (evt.Source == self.UpdateImages) or (self.sender() == self.DetrMode)
    update = (calc == 2) or (self.sender() in [self.UpdateImages,self.DetrMode])
    return update