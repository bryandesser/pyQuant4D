import numpy as np
from callbacks.annotationsClass import DraggablePoint

self = []

def transBeamCallbacks(self):
    ## Sub functions
    # Function to sync UIs/ROIs depending on the central beam location
    def moveTransBeam(src,evt):
        b0 = np.array([self.TBX.value(),self.TBY.value()])
        r = self.TBR.value()
        a = self.Alpha.value()
        mrad_per_px = a/r
        nPix = self.D.NPx

        if isempty(findobj(self.Axes.Dfrn,'Tag','TransBeamAnnot')):
            self.A.tbCirc = None # If ROI is not plotted
        else:
            match self.sender():
                case self.TBX|self.TBX_NF:
                    b0[0] = max(1, evt.Value); # Force X >= 1
                case self.TBY|self.TBY_NF:
                    b0[1] = max(1, evt.Value); # Force Y >= 1
                case self.TBR|self.TBR_NF:
                    r = evt.Value; # Radius
                case self.Alpha:
                    a = evt.Value
                    mrad_per_px = a/r # Calculate the diffraction scale
                case self.mradPx:
                    mrad_per_px = evt.Value
                    a = mrad_per_px*r # Manually set the diffraction scale
                case self.A.tbCirc:
                    b0 = src.Center
                    r = src.Radius # ROI

        # Restrict transmitted beam location/size
        b0[b0 > nPix] = nPix[b0 > nPix]
        b0[b0 < 1] = 1
        self.B0 = b0
        self.P.RMax = np.ceil(np.sqrt(sum((abs(self.P.DfCtr-b0)+self.P.DfCtr)**2))) # Find the max allowed radius
        r = min(r, self.P.RMax)

        # Update UI limits
        self.TBR.setRange(0,self.P.RMax)
        self.TBR_NF.setRange(0,self.P.RMax)
        self.AnnRi.setRange(0,self.P.RMax)
        self.VrApR.setRange(0,self.P.RMax)

        # Update UI values
        self.TBR.setValue(r)
        self.TBX.setValue(b0[0])
        self.TBY.setValue(b0[1])
        self.TBR_NF.setValue(r)
        self.TBX_NF.setValue(b0[0])
        self.TBY_NF.setValue(b0[1])
        self.Alpha.setValue(a)
        self.mradPx.setValue(mrad_per_px)
        
        # Update ROI
        set(self.A.tbCirc,'Center',b0,'Radius',r)
        # Update global coordnate properties
        detrCoordCallbacks(app, event)

    # Auto-align transmitted beam
    def autoAlign(self):
        self.T.progDLG = progDLG(app, 'Finding transmitted beam ...', "Auto Alignment");
        # Reset any zoom on the transmitted beam
        axis(self.Axes.Dfrn, self.P.DfrnAxLim)

        # Align transmitted beam by trying to find the transmitted disk in the diffraction pattern (self.Image.Dfrn),
        # apply slight gaussaian blur of 5 pixels to help the fit if necessary
        try:
            [center, radius, ~] = imfindcircles(self.Image.Dfrn, [1 round(max(self.D.NPx)/2)]);
            if center==[]:
                [center, radius, ~] = imfindcircles(imgaussfilt(self.Image.Dfrn,5), [1 round(max(self.D.NPx)/2)]);
        except:
            center = [];  radius = []
        
        transBeam_old = [self.B0,self.TBR.value()]; # Store old transmitted beam values

        # Find circle closest to the center of the diffraction pattern, plot for user confirmation
        if center==[]:
            notifDLG(self,'warn',"No transmitted beam detected. Please align the transmitted beam manually.",'Auto-align Failed')
            sel = "No. Revert"
        else:
            # Assign radius and center value(s) found above using imfindcircles based on whichever is found to be
            # closest to the diffraction pattern center `self.P.DfCtr`
            [~,im] = min(sqrt(sum((center-self.P.DfCtr).^2,2)));
            self.TBX.Value = center(im,1);  self.TBY.Value = center(im,2);  self.TBR.Value = radius(im);
            # To update annotation/panel values
            transBeamCallbacks(app,struct("Source","","EventName",""));

            sel = notifDLG(app,'quest',"Is the auto-alignment correct?",'Auto-align',["Yes","No. Revert"])

        # Revert alignment if not correctly detected
        if sel == "No. Revert":
            self.TBX.Value = transBeam_old[0]
            self.TBY.Value = transBeam_old[1]
            self.TBR.Value = transBeam_old[2]


    # align transmitted beam at the crossing of two lines
    def crossAlign(): #TODO
        self.A.line1 = drawline("Position",self.D.NPx.*[1 1;3 3]/4,"Color","r","Deletable",false)
        self.A.line2 = drawline("Position",self.D.NPx.*[1 3;3 1]/4,"Color","r","Deletable",false)

        addlistener(self.A.line1,'ROIMoved',@moveTB)
        addlistener(self.A.line1,'MovingROI',@moveTB)
        addlistener(self.A.line2,'ROIMoved',@moveTB)
        addlistener(self.A.line2,'MovingROI',@moveTB)

        h = helpdlg('Push OK when finished')
        uiwait(h)

        delete(self.A.line1)
        delete(self.A.line2)



        def moveTB():
            x1 = self.A.line1.Position(1,1)
            x2 = self.A.line1.Position(2,1)
            x3 = self.A.line2.Position(1,1)
            x4 = self.A.line2.Position(2,1)

            y1 = self.A.line1.Position(1,2)
            y2 = self.A.line1.Position(2,2)
            y3 = self.A.line2.Position(1,2)
            y4 = self.A.line2.Position(2,2)

            self.B0 = [x1*y2-x2*y1,x3*y4-x4*y3]/[y2-y1,y4-y3;-(x2-x1),-(x4-x3)]

            self.TBX.Value = self.B0(1)
            self.TBX_NF.Value = self.B0(1)
            self.TBY.Value = self.B0(2)
            self.TBY_NF.Value = self.B0(2)

            self.A.tbCirc.Center = self.B0

    def replotTb(self):
        """ update the ciruclar annotations on the diffraction pattern """
    
        r= self.TBR.value()
        
        
        # update diffraction pattern figure
        

    def moveTbR(self):
        # get diffraction scale set by user during alignment
        scale = self.DfPxR

        # get transmitted beam radius from the calling widget
        match self.sender():
            # draggable points on transmitted beam annothation
            case self.A.tbPt:
                r = np.linalg.norm(self.B0-self.A.tbPt.point.get_offsets(),axis=1)
            # transmitted beam radius QDoubleSpinBox
            case self.TBR_NF:
                r = self.TBR_NF.value()/scale
                
        # radius cannot be less than 0
        if r<0:
            r = 0

        # radius cannot be greater than max scattering angle
        if r>self.P.RMax:
            r = self.P.RMax

        # avoid triggering a valueChanged loop by blocking signals
        self.TBR.blockSignals(True)
        self.TBR_NF.blockSignals(True)

        # set slider and numerical field values
        self.TBR.setValue(r)
        self.TBR_NF.setValue(r*scale)

        # unblock trigger signals
        self.TBR.blockSignals(False)
        self.TBR_NF.blockSignals(False)

        # update transmitted beam point center when updated via QRangeSlider or QDoubleSpinBoxes
        if self.sender() is not self.A.tbPt:
            center = self.A.tbPt.point.get_offsets()-self.B0
            angles = np.arctan2(center[0],center[1])
            center = np.array([np.sin(angles),np.cos(angles)])*r+self.B0
            self.A.tbPt.point.set_offsets(center)

        # update transmitted beam circle and refresh diffraction figure (self.Fig.Dfrn)
        self.A.tbCirc[0].set_data(self.A.circX*r+self.B0[0],self.A.circY*r+self.B0[1])
        self.Fig.Dfrn.canvas.draw()

    def drawTb(self):
        """ initiallize the transmitted beam annotations """
        # define center location and starting radii for transmitted beam
        c = self.B0
        r = self.TBR.value()

        # # generate one point that a user can drag to control the transmitted beam
        if self.A.tbPt is None:
            self.A.tbPt = DraggablePoint(self.Fig.Dfrn.ax.scatter(c[0]+r,c[1]-r,s=25,c='b'))
            self.A.tbPt.connect()
            self.A.tbPt.redrawCircle.connect(lambda: moveTbR(self))
            self.pointPickerRadius.connect(lambda: self.A.tbPt.setPointPickerRadius(self.screen().physicalDotsPerInch()))
        else:
            self.A.tbPt.point._visible=True

        # add circles to pacbed plot, these are not draggable
        if self.A.tbCirc is None:
            self.A.tbCirc = self.Fig.Dfrn.ax.plot(self.A.circX*r*np.sqrt(2)+c[0],self.A.circY*r*np.sqrt(2)+c[1],color='b')


    match self.sender():
        case self.DetrMode: # Entering mode
            # Create transmitted beam annotation, allow for disk as large as the entire diffraction pattern
            self.A.tbCirc = drawTb(self)
            self.Fig.Dfrn.activateWindow() # Select `Dfrn` image
            # If this is the initializing alignment, then do swap byte check and auto-align
            if not self.P.TransBeamInit:
                #datasetOptCallbacks(app, event) #TODO
                autoAlign() #TODO
            #enableWindows(app,true) # Enable windows #TODO
        case self.UpdateImages: # Update images
            # Create a summed image of all diffraction patterns simply for alignment and calibration
            self.Image.DfrnMask = np.ones(self.D.NPx,self.D.DataType)
            self.Image.Real.set_data(np.reshape(self.Data.sum(axis=1), self.D.NFr))
            self.Image.Real.autoscale(True)
            self.Fig.Real.canvas.draw()
        case self.TBAutoAlign: # Auto-align
            autoAlign()
        case self.TBCrossAlign: # Align transmitted beam via two crossed lines
            crossAlign()
        
    # Update dependent variables
    moveTransBeam(event.Source,event)