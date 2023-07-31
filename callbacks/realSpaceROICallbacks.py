from callbacks.allFunctions import enableWindows,notifDLG,toUpdateImage,plotAllPatterns
import PyQt5.QtCore as qtc
import PyQt5.QtWidgets as qtw
import PyQt5.QtGui as qtg
import numpy as np

def realSpaceROICallbacks(self, event):

    match self.sender():
        case self.UpdateImages: # Update diffraction image
            if isempty(findobj(self.G.RealAx, 'Tag','Real-space ROI')): # Draw ROI etc if not exists
                self.RealROIShape.currentIndexChanged.emit(self.RealROIShape.currentIndex())
            else:
                moveRealROI(self.A.RealROI.Real, event)
          
        case self.RealROIShape:
            val = self.RealROIShape.currentData()
            if val == "file":
                self.Image.RealROIFile = importMask(self, "Real")
            if self.Image.RealROIFile == "":
                val = "full"
          
            # Update GUI if changed
            self.RealROIShape.blockSignals(True)
            self.RealROIShape.setCurrentIndex(self.RealROIShape.findData(val))
            self.RealROIShape.blockSignals(False)
            
            # Panel enable/disable
            self.FrameX.setEnabled(val=="point")
            self.FrameY.setEnabled(val=="point")
            self.FrameXLabel.setEnabled(val=="point")
            self.FrameYLabel.setEnabled(val=="point")
            self.FrameLabel.setEnabled(val=="point")
            self.RealROIInvert.setEnabled(val != "full")
            
            self.RealROIInvert.blockSignals(True)
            self.RealROIInvert.setChecked(self.RealROIInvert.isChecked() and self.RealROIInvert.isEnabled()) # If disabled, then off
            self.RealROIInvert.blockSignals(False)
            
            # Draw ROIs
            drawRealROI(val)

        case self.FrameX|self.FrameY:
            moveRealROI(self.sender(), event)

        case other:
            # run the listener to update any/all other ROIs and the diffraction pattern
            moveRealROI(self.A.RealROI.Real, event)
      

    ## Sub functions
    # function to draw Real-space ROI of various shapes on real space image(s)
    def drawRealROI(typ):
        self.A.removeGroup("ROIs") # Delete all previous ROIs
        c = qtg.QColor(255,127,127)

        # Special case for drawing polygon ROI
        if typ == "poly":
            # List for available real-space images
            rs = (self.G.Img.space=="Real") & (self.G.Img.type!="Mask") # list of bools
            rs &= self.G.Img.name.isin([self.SettingsWindow.DispImage.itemText(ii) for ii in range(self.SettingsWindow.DispImage.count())])

            message = "Select a Real-space Image to draw a polygon ROI.\n\nPress 'Esc' to cancel during drawing. Please refer to MATLAB's 'drawpolygon' for more tips.\n"
            title = "Draw Polygon ROI"
            sel = notifDLG(self,'list',message,title,self.G.Img.name[rs])

            # Revert to "full" is canceled
            if sel == None:
                self.RealROIShape.currentIndexChanged(self.RealROIShape.findData("full"))
                return
            
            # Bring selected image window to front
            id = self.G.Img[self.G.Img.name.isin([sel])].id.item()
            ax = self.Fig[id].ax
            self.Fig[id].show()
            self.Fig[id].activateWindow()

            enableWindows(self,False) # Disable UIs until drawing finishes
            
            # Draw temporary polygon for positions
            tmpPoly = drawpolygon(ax,"Color",c)
            polyPos = tmpPoly.Position
            delete(tmpPoly)

            enableWindows(self,True) # Re-enable all windows
            # Revert to "full" is canceled
            if polyPos==[]:
                self.RealROIShape.currentIndexChanged(self.RealROIShape.findData("full"))
                return
        
        # Draw ROIs on Real-space images, except the mask image
        rg = np.ptp([self.Fig.Dfrn.ax.get_xlim(),self.Fig.Dfrn.ax.get_ylim()],axis=1)
        p = np.array([self.FrameX.value(),self.FrameY.value()])
        for id in self.G.Img[(self.G.Img.space=="Real")&(self.G.Img.type!="Mask")].id:
            match typ:
                case "full":
                    roi = drawrectangle(self.Fig[id].ax,"Position",[1,1,rg],"Visible",0,"EdgeAlpha",0,"FaceAlpha",0)
                case "point":
                    roi = drawpoint(self.Fig[id].ax,"Position",p)
                case "ellipse":
                    roi = drawellipse(self.Fig[id].ax,'Center',p,"SemiAxes",min(0.1*rg)*[1,1],'FaceAlpha',0)
                case "rectangle":
                    roi = drawrectangle(self.Fig[id].ax,"Position",[p-0.1*rg, 0.2*rg],"Rotatable",True,'FaceAlpha',0)
                case "poly":
                    roi = drawpolygon(self.Fig[id].ax,"Position",polyPos,'FaceAlpha',0)
                case "file":
                    roi = drawrectangle(self.Fig[id].ax,"Position",[1,1,rg],"Visible",0,"EdgeAlpha",0,"FaceAlpha",0)
                    bw = visboundaries(self.Fig[id].ax, bwboundaries(self.Image.RealROIFile), 'Color',c, "EnhanceVisibility",0)
                    bw.Tag = 'Real-space ROI'
          
            set(roi,'Deletable',False,'Color',c,'Tag','Real-space ROI')
            roi.UserData.Move = addlistener(roi,'MovingROI',@moveRealROI)
            addlistener(roi,'ROIMoved',@moveRealROI)
            self.A.RealROI.(id) = roi

        moveRealROI(self.A.RealROI.Real, event)


    def moveRealROI(self.sender(), evt):
        """ live update function for Real-space ROIs """

        # Update panel values for individual probe positions
        roi = self.A.RealROI.Real
        x = self.FrameX.Value
        y = self.FrameY.Value

        match self.sender():
            case self.FrameX:
                x = max(1,self.sender().value()) # Force X >= 1
            case self.FrameY:
                y = max(1,self.sender().value()) # Force Y >= 1
            case other: # E.g. ROIs
                roi = self.sender()
                match self.RealROIShape.currentData():

                    case 'rectangle'|'full'|'file':
                        pos = self.sender().Position[0:2]+0.5*self.sender().Position[3:]
                        x = pos(1)
                        y = pos(2)

                    case 'point':
                        x = self.sender().Position[0]
                        y = self.sender().Position[1]

                    case 'ellipse':
                        x = self.sender().Center[0]
                        y = self.sender().Center[1]

                    case 'poly':
                        [x, y] = centroid(polyshape(self.sender().Position))
        
        # round x,y location as they represent probe positions
        x = round(x)
        y = round(y)

        # Set current ROI position if called from `self.FrameX` or `self.FrameY`, and it's a point ROI
        if (self.sender() in [self.FrameX,self.FrameY]) and (self.RealROIShape.currentData() == "point"):
            roi.Position = [x,y]

        # Update UI
        self.blockAllSignals=True
        self.FrameX.setValue(x)
        self.FrameY.setValue(y)
        self.blockAllSignals=False

        # Only upate ROIs on other visible figures; update all when not in "changing" Event
        rois = structfun(@(i) i, self.A.RealROI)
        rois = rois(arrayfun(@(i) ancestor(i,'figure').Visible, rois) | isStaticEvt(evt))

        # Sync existing properties of positions etc.
        for p in ["Position","Center","SemiAxes","RotationAngle"]:
            if hasattr(roi, p):
                setExself.sender()(evt, rois, p, roi.(p))
        
        # Update images
        if toUpdateImage(self,evt):
            # generate a mask for displaying diffraction pattern
            match self.RealROIShape.currentData():
                case "full":
                    mask_real = True(self.D.NFr)
                case 'point':
                    mask_real = False(self.D.NFr)
                    mask_real[x, y] = True
                case 'file':
                    mask_real = self.Image.RealROIFile
                case other:
                    mask_real = createMask(self.sender(), self.ImgD.Real)
          
        # Convert to single/double
        mask_real = mask_real.astype(self.D.DataType)
        
        # Invert mask?
        if self.RealROIInvert.isChecked():
            mask_real = max(mask_real,[],'all') - mask_real
        
        # Store the mask for plotting/saving
        self.Image.RealMask = mask_real
        
        # Update diffraction pattern for the specified ROI
        self.Image.Dfrn = gather(reshape(self.Data*reshape(mask_real,[],1), self.D.NPx)/sum(mask_real,'all'))

        plotAllPatterns(self)