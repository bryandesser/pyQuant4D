import os, sys, traceback, re, gc, psutil, importlib, h5py, matplotlib
import numpy as np
import torch
from multiprocessing.pool import ThreadPool
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from PyQt5 import QtGui as qtg
import callbacks.appClass as appClass
from callbacks.appClass import *
from annotationsClasses.interactiveCircle import InteractiveCircle
from annotationsClasses.interactivePoint import DraggablePoint

def flashBackground(target):
    pass

def getGPU(self):
    self.ImportWindow.ImpGPU.clear()
    self.C.nGPU = 0
    self.C.GPUmem = []
    self.C.GPUname = []
    
    # Check if CUDA capable GPU is available for acceleration
    self.C.nGPU = torch.cuda.device_count()
        
    # Find GPU devices and turn on/off GPU support; `self.ImgGPU.Value` of `0` is always "GPU off"
    if self.C.nGPU==0: # no GPU devices
        self.ImportWindow.ImpGPU.addItem('No GPU found.',0)
    else: # 1 or more devices found
        maxmem = 0
        for i in np.arange(0,self.C.nGPU):
            self.C.GPUmem.append(torch.cuda.get_device_properties(i).total_memory)
            self.C.GPUname.append(torch.cuda.get_device_name(i))
            self.ImportWindow.ImpGPU.addItem(self.C.GPUname[i],i)
            # Select GPU with max memory
            if self.C.GPUmem[i] > maxmem:
                maxmem = self.C.GPUmem[i]
                self.ImportWindow.ImpGPU.setCurrentIndex(i)
        self.ImportWindow.ImpGPU.addItem('GPU off',0)

def getMem(self):
    mem = psutil.virtual_memory()
    self.C.MemTot = mem.total
    self.C.MemFree = mem.available

def rangeImportExport(self, src):
    # spinner upper/lower limits must be different, so now set lower limit `0` but force minimum to `1`
    if hasattr(src,'value'):
        val = np.maximum(src.value(), 0)
    
    # Round positions from ROIs
    #if hasattr(evt,'CurrentPosition'):
    #    pos = round(evt.CurrentPosition)
    
    # `sp`/`U`: space/unit, "Dfrn"/"Px" for diffraction/pixel OR "Real"/"Fr" for real-space/frame
    if "Dfrn" in src.accessibleDescription():
        sp = "Dfrn"
        U = "Px"
    else:
        sp = "Real"
        U = "Fr"
    
    # `O`: "I" or "E" for Import/Export
    if "Import" in src.accessibleDescription():
        O = "I"
        dnp = np.asarray([self.ImportWindow.findChild(qtw.QSpinBox,"DN"+U+"X").value(), self.ImportWindow.findChild(qtw.QSpinBox,"DN"+U+"Y").value()]).astype(int) # Raw dataset dimensions, e.g. self.ImportWindow.DNPxX.value()
    else: # Export
        O = "E"
        dnp = np.asarray(getattr(self.D,"N"+U)).astype(int) # Loaded dataset dimensions
    
    # Get values from UI
    binDist = np.asarray(self.ImportWindow.findChild(qtw.QSpinBox,O+U+"D").value()) # Binning/Sampling (self.ImportWindow.IPxD, self.ImportWindow.EPxD, self.ImportWindow.IFrD or self.ImportWindow.EFrD)

    if src.accessibleDescription() == "Export Dfrn ROI": # From Export Diffraction ROIs
            initPoint = pos[0:1]
            numPoints = np.max(np.floor((pos[2:3]+1)/binDist), 1)
    elif src.accessibleDescription() == "Export Real ROI": # From Export Real-space ROIs
            initPoint = pos[0:1]
            numPoints = np.floor(pos[2:3]/binDist)+1
    else: # From other sources
            initPoint = np.asarray([self.ImportWindow.findChild(qtw.QSpinBox,O+U+"X1").value(), self.ImportWindow.findChild(qtw.QSpinBox,O+U+"Y1").value()])  # self.IPxX1, self.EFrX1 etc, Point-1 X & Y UIs
            numPoints = np.asarray([self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"X").value(), self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"Y").value()])  # self.INPxX, self.ENFrX etc, N-Points X & Y UIs

    # Replace value with current event value
    if src == getattr(self.ImportWindow,O+U+"D"):
        binDist = val # Binning/Sampling UI
    elif src == getattr(self.ImportWindow,O+U+"X1"):
        initPoint[0] = val # Point-1 X UI
    elif src == getattr(self.ImportWindow,O+U+"Y1"):
        initPoint[1] = val # Point-1 Y UI
    elif src == getattr(self.ImportWindow,O+"N"+U+"X"):
        numPoints[0] = val # N-Points X UI
    elif src == getattr(self.ImportWindow,O+"N"+U+"Y"):
        numPoints[1] = val # N-Points Y UI
    elif src in [getattr(self.ImportWindow,"DN"+U+"X"), getattr(self.ImportWindow,"DN"+U+"Y"), getattr(self.ImportWindow,"Imp"+U+"Part"), getattr(self.SaveWindow,"Exp"+U+"Part")]:
        # Reset range options if dataset raw dimension changes OR partial selection enables/disables
        getattr(self.ImportWindow,O+U+"D").setMaximum(min(dnp)) # Update binning/sampling UI limits
        if O == "I" and U == "Fr": # Update preview frame limits
            self.blockAllSignals = True
            self.PvFrX.setRange(1,dnp[0])
            self.PvFrX.setValue(dnp[0])
            self.PvFrY.setRange(1,dnp[1])
            self.PvFrY.setValue(dnp[1])
            self.blockAllSignals = False
        binDist = 1
        initPoint = np.asarray([1,1])
        numPoints = dnp

    # In general, N-Points are determined by Point-1 and Binning/Sampling, unless N-Points are the source
    #s = [self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"X"), self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"Y")] != src # Whether N-Points X or Y are not the source
    #s = np.asarray([x in src for x in [self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"X"), self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"Y")]])
    if src==getattr(self.ImportWindow,O+"N"+U+"X"):
        s = np.asarray([1])
    elif src==getattr(self.ImportWindow,O+"N"+U+"Y"):
        s = np.asarray([0])
    else:
        s = np.asarray([0,1])

    if U == "Px":
        numPoints[s] = np.maximum(1, np.minimum(numPoints[s], np.floor((dnp[s]-initPoint[s]+1)/binDist)))  # Determine N-Points X/Y if not source
        #numPoints[s] = np.maximum(np.asarray([1,1]), np.minimum(numPoints[s], np.floor((dnp[s]-initPoint[s]+1)/binDist)))  # Determine N-Points X/Y if not source
        initPoint = np.minimum(initPoint, dnp-numPoints*binDist+1)
        endPoint = initPoint+numPoints*binDist-1 # Endpoints of Pixel ranges
        l1 = dnp-binDist+1
        ln = np.floor(dnp/binDist).astype(int) # Upper limits of Pixel Point-1 X & Y and N-Points X & Y
        pos = [initPoint, numPoints*binDist-1] # Positions for Export ROI
        txt = "Diffraction Range (in pixels [px])"
        u = " px"
        txtb = "binning to "
    else: # "Fr"
        # Frame sampling has slightly different logics to pixel binning
        numPoints[s] = np.minimum(numPoints[s], np.floor((dnp[s]-initPoint[s])/binDist)+1)
        initPoint = np.minimum(initPoint, dnp-(numPoints-1)*binDist)
        endPoint = initPoint+(numPoints-1)*binDist # Endpoints of Frame ranges
        l1 = dnp
        ln = np.floor((dnp-1)/binDist).astype(int)+1 # Upper limits of Frame Point-1 X & Y and N-Points X & Y
        pos = [initPoint,(numPoints-1)*binDist] # Positions for Export ROI
        txt = "Real-space Range (in frames [fr])"
        u = " fr"
        txtb = "sampling "
    
    # Set Point-1 X & Y, N-Points X & Y and Binning/Sampling UIs
    getattr(self.ImportWindow,O+U+"X1").setRange(0,l1[0])
    getattr(self.ImportWindow,O+U+"Y1").setRange(0,l1[1])
    getattr(self.ImportWindow,O+"N"+U+"X").setRange(0,ln[0])
    getattr(self.ImportWindow,O+"N"+U+"Y").setRange(0,ln[1])
    getattr(self.ImportWindow,O+U+"D").setRange(0,min(dnp))

    getattr(self.ImportWindow,O+U+"X1").setValue(initPoint[0])
    getattr(self.ImportWindow,O+U+"Y1").setValue(initPoint[1])
    getattr(self.ImportWindow,O+"N"+U+"X").setValue(numPoints[0])
    getattr(self.ImportWindow,O+"N"+U+"Y").setValue(numPoints[1])
    getattr(self.ImportWindow,O+U+"D").setValue(binDist)

    # Try to update Export ROIs
    #if O == "E":
    #    set(findobj(self.G.(sp+"Ax"),'Tag',"Export "+sp+" ROI"), 'Position', pos) #TODO
    
    # Range notes
    tp = [x1 + u for x1 in [str(ints) for ints in numPoints]]

    if binDist > 1:
        tp = [x6 + u for x6 in [x4 + x5 for x4,x5 in list(zip([x3 + " from " for x3 in [txtb + x2 for x2 in tp]],[str(ints) for ints in endPoint-initPoint+1]))]]

    # If not from 1st to last
    s = np.maximum(initPoint>1,endPoint<dnp)
    for i in np.arange(len(s)):
        if s[i]:
            tp[i] = str(numPoints[i])+u+", "+str(initPoint[i]-1)+"/"+str(dnp[i]-endPoint[i])+u+" offset from start/end"
    notes = "{}:\n\tX = {}-{} ({})\n\tY = {}-{} ({})\n".format(txt,*[items for sublist in zip(initPoint,endPoint,tp) for items in sublist])

    return notes,binDist,initPoint,numPoints,endPoint

def progImportExport(self, proc, tot_fr, frsize):
    return wb, tmr

def importMask(self, sp):
    return im

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

def plotImage(self, id):
    """Generic function for plotting an image on a given axis with brightness/contrast/gamma values"""

    def updateDispImgStats():
        """Function to update image's statistics"""

        def moveHistHiLo(src, evt):
            pass

        fig = self.Fig[id]
        ax = fig.ax
        im = np.ma.masked_invalid(fig.Image)

        # Update histogram skip if image unchanged
        if isDiffToPrev(self,'im',im):
            if im.mask.any():
                nanwarn = "Contains NaN/Inf"
            else:
                nanwarn = ""
            self.SettingsWindow.ImStatsNotes.setPlainText("min:{:< 14.7g}\tavg:{:< 14.7g}\nmax:{:< 14.7g}\tstd:{:< 14.7g}\nsum:{:< 14.7g}\t{:s}".format(minVal, np.nanmean(im), maxVal, np.nanstd(im), np.nansum(im), nanwarn))

            # try to clear the histogram
            try:
                self.SettingsWindow.HistAxes.axes.cla()
                self.A.hist = None
            except:
                pass

            # Generate an intensity histogram for the selected image
            binCounts,binEdges,self.A.hist = self.SettingsWindow.HistAxes.axes.hist(im.ravel(),bins=128,ec='k',linewidth=0.5)

            # Set histogram limits
            self.SettingsWindow.HistAxes.axes.set_xlim(binEdges.min(),binEdges.max())
            self.SettingsWindow.HistAxes.axes.set_ylim(0.5,(1.1*binCounts).max().clip(1)) # Make sure upper limit is at least 1

            # set vertical scale
            if self.SettingsWindow.HistLog.isChecked():
                self.SettingsWindow.HistAxes.axes.set_yscale('log')
            else:
                self.SettingsWindow.HistAxes.axes.set_yscale('linear')

        # Update histogram annotations skip if values unchanged
        if isDiffToPrev(self,'hist',(ax,minVal,maxVal,limitLow,limitHigh,limitRange,fig.gamma,self.SettingsWindow.HistLog.isChecked())):
            # Update ROIs #TODO
            #try:
            #    self.A.histBox.remove()
            #    self.A.histBox = None
            #except:
            #    pass

            # Draw ROI of range if not yet #TODO
            if self.A.histBox is None:
                pass#self.A.hist.Box = drawrectangle(self.SettingsWindow.HistAxes,'Position',[1 1 1 1],'LineWidth',1,'MarkerSize',eps(),'FaceAlpha',.1,'InteractionsAllowed','translate')
                #self.A.hist.Hi = drawpoint(self.SettingsWindow.HistAxes,'Position',[1 1])
                #self.A.hist.Lo = drawpoint(self.SettingsWindow.HistAxes,'Position',[1 1])
                #addlistener([self.A.hist.Box self.A.hist.Lo self.A.hist.Hi],'MovingROI',@moveHistHiLo)
                #ud.Move = addlistener([self.A.hist.Box self.A.hist.Lo self.A.hist.Hi],'ROIMoved',@moveHistHiLo)
                #set([self.A.hist.Box self.A.hist.Lo self.A.hist.Hi],'Deletable',0,'UserData',ud,'Tag','HistROI')

            # Save current display limits to ROIs #TODO
            #self.A.histBox.ax = ax
            #self.A.histBox.minVal = minVal
            #self.A.histBox.maxVal = maxVal
            #self.A.histBox.limitLow = limitLow
            #self.A.histBox.limitHigh = limitHigh
            #self.A.histBox.limitRange = limitRange
            
            # Update ROI if not the caller
            if self.sender() is not self.A.histBox:
                pass#moveHistHiLo(self.Sender()) #TODO

            # Update other annotations
            # remove gamma curve
            try:
                self.A.histGamma.remove()
                self.A.histGamma = None
            except:
                pass
            # remove any text(s)
            if len(ax.texts):
                for ii in ax.texts:
                    ii.remove()
            self.A.histNote = None

            # Gamma line
            x = np.linspace(limitLow,limitHigh,128) # histogram is on x_lim = [0,1]
            self.A.histGamma, = self.SettingsWindow.HistAxes.axes.plot(x,((x-limitLow)/(limitHigh-limitLow))**fig.gamma*np.diff(self.SettingsWindow.HistAxes.axes.get_ylim())+self.SettingsWindow.HistAxes.axes.get_ylim()[0], color='k')
            
            # Print display limits on the histogram
            textstr = "High:{:< 9.2e}\nLow:{:< 9.2e}".format(limitHigh,limitLow)

            # these are matplotlib.patch.Patch properties
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)

            # place a text box in upper left in axes coords
            self.A.histNote = self.SettingsWindow.HistAxes.axes.text(0.05, 0.95, textstr, transform=ax.transAxes,fontsize=10,verticalalignment='top', bbox=props)#, font="Courier")

            # update histogram canvas
            self.SettingsWindow.HistAxes.figure.canvas.draw_idle()

    def plotVectorField():
        """ Function to plot a vector field image over top of the DPC or CoM images (either magnitude, angle, or combination) """
        fig = self.Fig[id]
        #try: #TODO
        #    self.A.vecField.remove()
        #    self.A.vecField = None
        #except:
        #    pass

        # vector field sampling (0,1:1,1:2,1:4,1:8,1:16)
        vec = fig.vecField

        # if vector field sampling == 0, or not currently in CoM or DPC modes, return
        if (not vec) or (self.DetrMode.currentData() in ["CoMMod", "DPCMod"]):
            return
        
        # Plot vector arrows over the selected image
        x,y = np.meshgrid(np.arange(0,self.D.NFrX,vec),np.arange(0,self.D.NFrY,vec))
        u = self.Fig.Dfrn.CoMX[0::vec, 0::vec]
        v = self.Fig.Dfrn.CoMY[0::vec, 0::vec] 
        self.A.vecField[id] = fig.ax.quiver(x, y, u, v, color=fig.vecColor,units='xy')
        fig.canvas.draw_idle()
        
    def plotColorWheel():
        # Make ColorWheel for DPC/CoM imaging - this color scheme will stay constant for all DPC/CoM images
        # regardless of their individual parameters like scan or detector rotation for consistency
        r = 256
        xgrid,ygrid = np.meshgrid(np.linspace(1-r,r,int(2*r)),np.linspace(1-r,r,int(2*r)))
        
        # Get atan from -pi to pi
        a = np.arctan2(ygrid, xgrid)

        # shift the negative values of atan up by 2*pi
        a[a<0] += 2*np.pi
        
        # make circular mask for colorwheel
        mask = (xgrid**2 + ygrid**2) < r**2

        # save masked colorwheel image    
        self.Fig.ColorWheel.Image = a
        if self.ImageAx.ColorWheel == None:
            self.ImageAx.ColorWheel = self.Fig.ColorWheel.ax.imshow(self.Fig.ColorWheel.Image,alpha=mask.astype(float),cmap='hsv',interpolation="None")
        self.Fig.ColorWheel.maskOpa = 100
        self.Fig.ColorWheel.ax.axis('off')
    
    # Special case for plotting the color wheel - can get unloaded
    if id == "ColorWheel":
        plotColorWheel()
        return

    # get image figure and axes
    fig = self.Fig[id]  # ImageWindow
    ax = fig.ax         # AxesSubplot
    im = np.ma.masked_invalid(self.Fig[id].Image) # numpy masked array

    # clear old image(s)
    #[ii.remove() for ii in self.Fig[id].ax.get_images()]

    # abort if image not yet ready
    if im is None:
        if id == self.SettingsWindow.DispImage.currentData():
            self.SettingsWindow.ImStatsNotes.setPlainText(fig.name)
        return

    # get image min and max values and resultant range, ignore NaN and +/- Inf 
    minVal = im.min() 
    maxVal = im.max()
    intensityRange = maxVal-minVal

    # Brightness between -0.5 and 0.5; Contrast between -Inf and 0.5
    brightness = (fig.brightness-50)/100
    contrast = np.log2(np.max((np.finfo('single').eps,fig.contrast/50)))/2 # Avoid log2(0)

    # Display limits from brightness/contrast; have the same magnitude to the raw image `im` 
    limitLow = minVal-(brightness-contrast)*intensityRange
    limitHigh = maxVal-(brightness+contrast)*intensityRange
    limitRange = limitHigh - limitLow

    # Normalize image, and apply display thresholds; `im` is always between 0 and 1
    if (limitHigh == limitLow) and (limitHigh <= 1 or limitHigh >= 0):
        # If display limits are both 1 or 0, then no rescale (e.g. `im` is all 1 or 0)
        pass

    elif (limitHigh > limitLow) or ((limitHigh == limitLow) and ((limitHigh > 1) or (limitHigh < 0))):
        # Typical case for upper limit > lower limit; apply limits and rescale [0,1]
        im = (im.clip(limitLow,limitHigh)-limitLow)/limitRange

    else:
        # Display limits are too close/identical, im becomes binary
        # If limits are NaN, then make them 0.5
        immi = (limitHigh+limitLow)/2
        if np.isnan(immi):
            immi = 0.5
        limitHigh = limitLow = immi
        im = np.double(im > immi)
        
    # display image with gamma and brightness contrast applied
    if self.ImageAx[id] == None:
        self.ImageAx[id] = ax.imshow(im**fig.gamma)
    else:
        self.ImageAx[id].set_data(im**fig.gamma)
    self.ImageAx[id].set_clim(0,1)
        
    # Plot mask opacity on non-mask/non-preview image; maskOpa is in percent (i.e. 50 => 50%)
    if fig.type not in ["Mask","Preview"]:
        mask = self.Fig[fig.space+"Mask"].Image # should be a logical mask
        self.ImageAx[id].set_alpha((1-fig.maskOpa/100)*(1-mask.astype(bool))+mask.astype(bool))

    # Shade CoM/DPC Phase with Magnitude
    if id == "CoMPhMag":
        CoMMagNorm = self.Fig.Dfrn.CoMMag
        CoMMagNorm -= np.nanmin(CoMMagNorm)
        CoMMagNorm /= np.nanmax(CoMMagNorm)
        self.ImageAx.CoMPhMag.set_alpha(self.ImageAx.CoMPhMag.get_alpha()*CoMMagNorm)

    plotVectorField() # Plot vector field, if selected #TODO
        
    # Only update statistics if not in changing Event AND it is the "selected" image 
    if (id == self.SettingsWindow.DispImage.currentData()): # and isStaticEvt(evt): #TODO
        # don't update stats while things are changing, only when finished to increase responsiveness
        updateDispImgStats()

    # set colormap
    self.ImageAx[id].set_cmap(fig.cmap+["","_r"][fig.invert]) # append "_r" if inverted

    fig.canvas.draw() # update plot

def isDiffToPrev(self,name,val):
    """Function to check whether the named given value is changed compared to the previous value, and store the new value"""
    c = (not hasattr(self.Prev, name)) or (getattr(self.Prev,name)!=val)
    
    # in case an image is being compared to an image, c will be an array of bool, not a single bool
    if isinstance(c,np.ndarray):
        c = c.all()

    if c:
        setattr(self.Prev,name,val)
    return c

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

def notifDLG(self, icon="", msg="", ttl="", opt=[]):
    """ Wrapper for notification dialogs; use `sprintf()` before calling this function to process "\n" in `msg` """
    sel=''

    # predefined Qt icons
    icons = dict()
    icons[""] = qtw.QMessageBox.NoIcon
    icons["help"] = qtw.QMessageBox.Question #TODO ?
    icons["quest"] = qtw.QMessageBox.Question
    icons["none"] = qtw.QMessageBox.Information
    icons["warn"] = qtw.QMessageBox.Warning
    icons["error"] = qtw.QMessageBox.Critical

    enableWindows(self,False) # disable windows

    if icon == 'list':
        sel,ok = qtw.QInputDialog().getItem(self,ttl,msg,opt,0,False) # default option 0, multiselect=False
        if not ok:
            enableWindows(self,True) # enable windows
            return None
    
    else: 
        dlg = qtw.QMessageBox(self) # establish a messagebox
        dlg.setIcon(icons[icon]) # set messagebox icon type
        dlg.setText(msg) # set the message
        dlg.setWindowTitle(ttl) # set the title

        match icon:
            case 'quest':
                for ii in opt:
                    dlg.addButton(ii,qtw.QMessageBox.YesRole)
                            
            case '':
                pass

            case 'help'|'warn'|'error'|'none':
                dlg.setStandardButtons(qtw.QMessageBox.Ok) # only allow for an "Ok" button

        sel = dlg.exec_() # Block background process until `msgbox()` is gone

    enableWindows(self,True) # re-enable windows

    # convert from integer return to text
    match icon:
        case 'list':
            pass # QInputDialog() will return the selected item text
        case 'quest':
            sel = opt[sel]
        case other:
            sel = 'Ok'

    return sel

def progDLG(self, msg, ttl, interruptible):
    return wb

# Function to unload data and clean all images
def unloadData(self, keep_p=False):
    importlib.reload(appClass)
    from callbacks.appClass import A,P,Mask,D,Prev

    """ Function to unload data and clean all images """
    enableWindows(self,False) # Disable windows for the data unload process
    self.setWindowTitle('Quant4D')
    # Whether to swap dataset only, without changing any existing parameters
    if not keep_p:
        # clear all axes
        for id in self.Fig:
            fig = self.Fig[id]
            fig.Image = None
            fig.ax.cla()
            fig.canvas.draw_idle()
            self.ImageAx[id] = None
        self.SettingsWindow.HistAxes.axes.cla()
        self.SettingsWindow.HistAxes.figure.canvas.draw_idle()

        # clear annotations (lines and draggable points)
        for ii in dir(self.A):
            if type(getattr(self.A,ii)) in (DraggablePoint,InteractiveCircle,matplotlib.lines.Line2D):#,InteractiveBox #TODO
                setattr(self.A,ii,None)

        setattr(self,'P',P())
        setattr(self,'A',A())
        setattr(self,'Mask',Mask())
        #self.ImgD = [] #TODO
        self.CDT.clearContents() # custom aperture table
    
    # Remove all data from GPU if in use #TODO
    #try:
    #    if self.D.GPU > 0:
    #        reset(parallel.gpu.GPUDevice.getDevice(self.D.GPU))
    #        gpuDevice([])
    #except:
    #    pass

    # Clear data, parameters and Axes
    self.Data = None
    self.Memfile = None
    setattr(self,'D',D())
    setattr(self,'Prev',Prev())

def enableWindows(self,sw=True):
    """ Function to enable/disable windows/UI; disable is only for notification/progress bar/busy background etc """
    assert isinstance(sw,bool)

    prvw = self.DetrMode.currentData() == "PrvwMod" # Preview mode or not
    # Detector Mode UI, keep disabled in Import Preview Mode unless a dataset is loaded
    self.DetrMode.setEnabled(sw and ~prvw) #(sw and (~prvw or ~isempty(self.D))) #TODO ~isempty(self.D) doesn't make sense when converted to Python

    # Real-space ROI controls, keep disabled in Import Preview Mode
    self.RealSpacePanel.setEnabled(sw and ~prvw)

    # Other UIs can be enabled in Import Preview Mode
    self.toolBar.setEnabled(sw)
    self.DfrnDetrTabGroup.setEnabled(sw)
    self.SettingsWindow.setEnabled(sw)
    self.SaveWindow.setEnabled(sw)
    self.ImportWindow.setEnabled(sw)
       
    # Also reset all windows' mouse pointer when enabling UIs
    if sw:
        [ii.setCursor(qtc.Qt.ArrowCursor) for ii in self.G.AllFig]

def createOtherWindows(self):
    def minSize(src, _, wh):
        pass
    def keyPress(_, evt):
        pass
    def hideWindow(src, _):
        pass
    def moveUI2NewFig(name, ui):
        return fig
    def createAxesFig(id, name, sp, typ, cmap, pos):
        def restoreView(_,evt):
            pass
        def showVal(_,evt):
            return txt
        def clickedWindow(src, _):
            pass
        pass
    pass

def checkNaN(self, image, preview = False):
    """ Function to check nan/inf in data/image """

    if np.ma.masked_invalid(image).mask.any():
        ttl = 'NaN/Inf in Data!'
        msg = "There are NaN/Inf values in the data, which may indicate that the data structure is not correctly set " + \
            "(e.g. wrong Data Type, Byte Order, Data Offset, Frame Header/Footer etc).\n\nIf any data are corrupt, NaNs can be set to 0."

        if preview: # For preview only
            opt = ["Continue","Set NaNs to 0"]

        elif (self.D.PxD > 1) or (self.D.FrFoot + self.D.FrHead > 0):
            msg += "\n\nRe-importing with corrected configuration is suggested."
            opt = ["Continue","Set NaNs to 0"]

        else:
            msg += "\n\nDo you want to swap the byte-order?"
            opt = ["Yes, try to swap the byte-order","No"]
            self.SettingsWindow.activate()
            self.SettingsWindow.SettingsTabGroup.setCurrentWidget(self.SettingsWindow.InfoTab)  # Select the Data Info tab
        
        sel = notifDLG(self, 'quest', msg, ttl, opt)

        # Execute the swap byte order callbacks
        if sel.startswith("Yes"):
            self.SettingsWindow.SwapByteOrder.click()

        return sel #string of button, will be checked outside function for further action
    
    else:
        return None

### Callbacks that handle component events

def startupFcn(self):
    pass

def importCallbacks(self, event):
    def gatherImportOptions(d,preview):
        d.filePath = self.ImportWindow.ImpFilePath.text()
        [d.fileDir, d.fileName] = os.path.split(d.filePath)
        d.fileDir = d.fileDir+os.sep
        d.subImg = self.ImportWindow.ImpSubImg.currentText()

        # BYTES offset of: 1) the dataset from the beginning of file, 2) before and 3) after each frame
        d.Offset = self.ImportWindow.DataOffset.value()
        d.FrHead = self.ImportWindow.FrHead.value()
        d.FrFoot = self.ImportWindow.FrFoot.value()

        # Endianness (big 'b' or little 'l'), Data type of the dataset and Size in bytes of the data type
        d.ByteOrder = self.ImportWindow.ImpByteOrder.currentData()
        d.DataType = self.ImportWindow.ImpDataType.currentData()
        d.ByteSize = getattr(self.ByteSize,d.DataType)

        # Physical or virtual memory loading
        d.mem = self.ImportWindow.ImpMemType.currentText()

        # Select GPU if acceleration is enabled AND not in Import Preview Mode
        d.GPU = self.ImportWindow.ImpGPU.currentText()
        #if not preview and d.GPU: gpuDevice(d.GPU) #TODO

        # Dimensions of pixels/frames in file and import binning/sampling distance
        d.DNPxX = self.ImportWindow.DNPxX.value()
        d.DNPxY = self.ImportWindow.DNPxY.value()
        d.PxD = self.ImportWindow.IPxD.value()
        d.DNFrX = self.ImportWindow.DNFrX.value()
        d.DNFrY = self.ImportWindow.DNFrY.value()
        d.FrD = self.ImportWindow.IFrD.value()

        # Starting points and Number of pixels/frames after binning/sampling to import
        d.PxX1 = self.ImportWindow.IPxX1.value()
        d.PxY1 = self.ImportWindow.IPxY1.value()
        d.NPxX = self.ImportWindow.INPxX.value()
        d.NPxY = self.ImportWindow.INPxY.value()
        d.FrX1 = self.ImportWindow.IFrX1.value()
        d.FrY1 = self.ImportWindow.IFrY1.value()
        d.NFrX = self.ImportWindow.INFrX.value()
        d.NFrY = self.ImportWindow.INFrY.value()

        # Frequently used dimension parameters
        d.NPx = np.array([d.NPxX,d.NPxY])
        d.NPxS = d.NPxX * d.NPxY
        d.NFr = np.array([d.NFrX,d.NFrY])
        d.NFrS = d.NFrX * d.NFrY

        # Estimated memory usage for current dataset
        d.EstMem = self.T.EstMem

        # Swap dataset option+self.ImpNotes.Value
        d.KeepP = self.ImportWindow.ImpKeepP.isChecked()

        # Notes at import
        d.NoteFileMeta = self.ImportWindow.ImpFileMetaNotes.toPlainText()
        d.NoteImp = self.ImportWindow.ImpNotes.toPlainText()

        # H5 dataset path within the H5 file. if not set empty, the H5 library API will be called when importing
        d.h5ds = []
        if self.ImportWindow.HDF5Button.isChecked() and  ("Physical Memory" in d.mem):
            d.h5ds = d.subImg

        return d
    
    def prepareData():
        #self.T.progDLG = progDLG(self, 'Preparing data ...', "Data Preparation"); #TODO
    
        # block slots/signals whilst initializing UI components
        self.blockAllSignals = True

        # Detector controls
        self.P.ScanDirInit = 0 # Reset alignments
        self.NSeg.setValue(4)
        self.NRung.setValue(1)
        self.DetRot.setValue(0)
        self.DetRot_NF.setValue(0)
        self.ScanDir.setValue(0)
        self.ScanDir_NF.setValue(0)

        self.VrApSymm.setCurrentIndex(0)
        self.VrApInvert.setChecked(False)
        self.VrApMirror.setChecked(False)
        self.VrApMirrRot.setValue(0)
        self.VrApMirrRot_NF.setValue(0)

        # Alignments
        self.P.DfCtr = self.D.NPx/2+.5 # Exact center of the Diffraction image
        self.P.RsCtr = self.D.NFr/2+.5 # Exact center of the Real-space image
        self.Alpha.setValue(12)
        self.P.VrApXY = self.P.DfCtr

        # Axes limits, restrict to avoid rounding to pixels outside the image. Origin upper left as in raster scanning
        self.P.DfrnAxLim = np.array([0, self.D.NPxX, self.D.NPxY, 0]) - 0.5
        self.P.RealAxLim = np.array([0, self.D.NFrX, self.D.NFrY, 0]) - 0.5

        # initialize diffraction space axis limits
        self.Fig.Dfrn.ax.set_xbound(self.P.DfrnAxLim[0:2])
        self.Fig.Dfrn.ax.set_ybound(self.P.DfrnAxLim[2:4])
        self.Fig.Dfrn.canvas.draw_idle()

        # initialize real space axis limits
        self.Fig.Real.ax.set_xbound(self.P.RealAxLim[0:2])
        self.Fig.Real.ax.set_ybound(self.P.RealAxLim[2:4])
        self.Fig.Real.canvas.draw_idle()

        # Transmitted Beam controls
        if self.sender() is not self.SettingsWindow.SwapRealXY: # Keep transmitted beam alignment if swapping Real-space X/Y
            self.P.TransBeamInit = 0
            # set transmitted beam slider ranges and values
            self.TBR.setRange(0,max(self.D.NPx))
            self.TBX.setRange(0,self.D.NPxX)
            self.TBY.setRange(0,self.D.NPxY)
            self.TBR.setValue(min(self.D.NPx)/10)
            self.TBX.setValue(self.P.DfCtr[0])
            self.TBY.setValue(self.P.DfCtr[1])
            self.TBX_NF.setRange(0,self.D.NPxX)
            self.TBY_NF.setRange(0,self.D.NPxY)
            self.TBX_NF.setValue(self.P.DfCtr[0])
            self.TBY_NF.setValue(self.P.DfCtr[1])
            transBeamCallbacks(self) # Update Transmitted Beam dependant variables

        # Real-space ROI controls
        self.FrameX.setRange(0,self.D.NFrX)
        self.FrameY.setRange(0,self.D.NFrY)
        self.FrameX.setValue(round(self.P.RsCtr[0]))
        self.FrameY.setValue(round(self.P.RsCtr[1]))
        self.RealROIInvert.setChecked(False)
        self.RealROIShape.setCurrentIndex(0) # "full"

        # Export controls
        self.SaveWindow.ExpPxPart.setChecked(False)
        self.SaveWindow.ExpFrPart.setChecked(False)

        # initiate image display parameters for all ImageWindows
        for id in self.G.ImgID:
            self.Fig[id].brightness = 50
            self.Fig[id].contrast = 50
            self.Fig[id].gamma = 1
            self.Fig[id].maskOpa = 0
            self.Fig[id].vecField = 0

        # unblock slots/signals
        self.blockAllSignals = False

        self.UpdateImages.trigger() # Update all images
        #delete(self.T.progDLG);  # Close progress bar and Enable panel objects #TODO

        #initialize SettingsWindow and move next to main UI window
        self.SettingsWindow.SettingsTabGroup.setCurrentIndex(0) # "Display" tab
        self.SettingsWindow.setVisible(True)
        pos = self.SettingsWindow.geometry()
        pos.moveLeft(self.geometry().getRect()[0]+self.geometry().getRect()[2]+self.C.decorPad*2)
        pos.moveTop(self.geometry().getRect()[1])
        self.SettingsWindow.setGeometry(pos)

        self.DetrMode.setCurrentIndex(self.DetrMode.findData("AlignMod"))
        detectorModeCallbacks(self)

        #flashBackground(self, [self.DfrnCalibGrid self.TransBeamAlignGrid])
        
    def importData(evt):
        def readFile():
            self.ImportWindow.hide()
            self.ShowImportWdw.setChecked(False)

            # initialize progressBar
            self.progressBar.setTextVisible(False)
            self.progressBar.setMaximum(0)

            #while not importDialog.wasCanceled():
            filename = self.D.filePath

            # dataset offset
            dataOffset = self.D.Offset

            # dataset header/foot sizes (in bytes)
            header = self.D.FrHead
            footer = self.D.FrFoot

            # detector shape
            nopix = self.D.NPxX
            nopiy = self.D.NPxY

            # real space scan shape
            framesx = self.D.NFrX
            framesy = self.D.NFrY
            dataType = [("header", "{}uint8".format(header)), ("data", "{}{}".format(nopix*nopiy,self.D.DataType)), ("footer", "{}uint8".format(footer))]
            
            # show progressbar to let user know things are happening
            self.progressBarPanel.setVisible(True)
            self.progressBarPanel.setEnabled(True)

            # Read in the file on a separate thread, if dtype is int, default to memmap and convert to float
            if self.ImportWindow.ImpMemType.currentIndex()==0: # physical memory
                self.workerThread = qtc.QThread()
                self.worker = importThread(filename,dataType,self.D.DataType,nopix*nopiy,framesx*framesy,dataOffset)
                self.worker.moveToThread(self.workerThread)
                self.workerThread.started.connect(self.worker.run)
                self.worker.result.connect(self.receiveThreadData)
                self.worker.finished.connect(lambda: finishImport(self))
                self.workerThread.start()

            else: # lazy loading
                self.Data = np.memmap(filename, dataType,'r')["data"]
        pass
    pass

def importSelectFile(self):
    # bypass execution if signals are actively being blocked (i.e. for programmatically updating UI values)
    if self.blockAllSignals:
        return
    
    # if the user pushes the "Select" button in the Import window, open file dialog, filter for known filetypes
    if self.sender() is self.ImportWindow.ImpFileSelect:
        fDialog  = qtw.QFileDialog(self)
        fDialog.setWindowTitle("Select 4DSTEM Dataset")
        fDialog.setNameFilter("(*.raw *.mib *.mrc *.dm3 *.dm4 *.npy *.h5 *.hdf5);;(*.*)")
        fDialog.setDirectory(qtc.QDir.currentPath())
        fileName = None
        if fDialog.exec_() == qtw.QDialog.Accepted:
            fileName = fDialog.selectedFiles()
        else: # user selected cancel
            self.ImportWindow.activateWindow()
            self.ImportWindow.ImportDataButton.setDefault(False)
            self.ImportWindow.ImportDataButton.setAutoDefault(False)
            self.ImportWindow.ImpFileSelect.setFocus(True)
            self.ImportWindow.ImpFileSelect.setAutoDefault(True)
            self.ImportWindow.ImpFileSelect.setDefault(True)
            return

        # reflect user selection in path field box
        if fileName is not None:
            self.D.fileName = fileName
            self.fname = str(self.D.fileName[0])
            self.ImportWindow.ImpFilePath.setText(self.fname)
            # activate rest of wigets in window
            for widget in self.ImportWindow.children():
                widget.setEnabled(True)
        
        # switch to directory containing dataset for future saving
        os.chdir(qtc.QDir.currentPath())

        # ensure ImportWindow remains on top
        self.ImportWindow.activateWindow()

        # set default button to "Import Data"
        self.ImportWindow.ImportDataButton.setDefault(True)
        self.ImportWindow.ImportDataButton.setAutoDefault(True)
        self.ImportWindow.ImportDataButton.setFocus(True)
        self.ImportWindow.ImpFileSelect.setAutoDefault(False)
        self.ImportWindow.ImpFileSelect.setDefault(False)
    
    # get file directory, name, extension, and size. display in filesize field
    if os.path.isfile(self.ImportWindow.ImpFilePath.text()):
        self.D.fileDir = os.path.dirname(self.ImportWindow.ImpFilePath.text())
        self.D.fileName = os.path.basename(self.ImportWindow.ImpFilePath.text())
        self.D.fileExt = os.path.splitext(self.ImportWindow.ImpFilePath.text())[1]
        os.chdir(self.D.fileDir)
        self.T.FileSize = os.path.getsize(self.D.fileName)
        self.ImportWindow.ImpActualFilesize.setText("{} bytes, {:.2f} GiB".format(self.T.FileSize,self.T.FileSize/1024**3))

        # activate Import Preview
        self.DfrnDetrTabGroup.setVisible(True)
        self.DfrnDetrTabGroup.setCurrentIndex(0)

        # activate preset buttons if file extension matches a known filetype, else custom
        match self.D.fileExt.casefold():
            case ".raw":
                self.ImportWindow.EMPADButton.setChecked(True)
            case ".mib":
                self.ImportWindow.MedipixButton.setChecked(True)
            case ".mrc":
                self.ImportWindow.MRCButton.setChecked(True)
            case ".dm3"|".dm4":
                self.ImportWindow.DM34Button.setChecked(True)
            case ".h5":
                self.ImportWindow.HDF5Button.setChecked(True)
            case other:
                self.ImportWindow.CustomButton.setChecked(True)
    
    # if filename is incorrect/does not exist...
    else:
        self.ImportWindow.ImpActualFilesize.setText("")
        self.DfrnDetrTabGroup.setVisible(False)
        self.PreviewTab.setVisible(False)
        self.PreviewTab.setEnabled(False)
    
    importFileType(self)

def importFileType(self, event):
    def guessFramesFromSize():
        pass
    def guessFramesFromDimZ(dz):
        pass
    def getDimFromName(name):
        pass
    pass

def importBoxInput(self, event):
    def checkMem(nPx,nFr,byte_size):
        # Display estimated size in green if matches actual size, brown if smaller, red if larger
        if self.T.EstSize == self.T.FileSize:
            self.ImportWindow.ImpEstFilesize.setStyleSheet("color: rgb(0, 128, 0);")
        elif self.T.EstSize < self.T.FileSize:
            self.ImportWindow.ImpEstFilesize.setStyleSheet("color: rgb(128, 128, 0);")
        else:
            self.ImportWindow.ImpEstFilesize.setStyleSheet("color: rgb(255, 0, 0);")
        
        # keep the same font after changing color
        self.ImportWindow.ImpEstFilesize.setFont(self.ImportWindow.ImpActualFilesize.font())

        # Estimate the amount of memory needed to hold the largest arrays in memory
        # Estimate of the distance to the far corner of the diffraciton pattern
        # est_mem = np.prod([nPx,nFr]) /                                # self.Data
        # + np.prod(nFr)*(2*np.floor(np.sqrt(np.sum((nPx/2)**2)))+1) /  # self.ImageAx.IntgAnn
        # + np.prod(nFr)*10 + np.prod(nPx)*2  /                         # self.Fig[id].Image
        # + np.prod(nPx)*10                                             # self.Mask
        est_mem = np.prod([nPx,nFr]) \
                + np.prod(nFr)*(2*np.floor(np.sqrt(np.sum((nPx/2)**2)))+1) \
                + np.prod(nFr)*10 + np.prod(nPx)*2 \
                + np.prod(nPx)*10
        self.T.EstMem = est_mem*byte_size

        notes = "Estimated memory usage: {:.3f} GiB.".format(self.T.EstMem/(1024**3))
        if self.T.EstMem > self.C.MemTot:
            warnDiag = qtw.QMessageBox()
            warnDiag.setIcon(qtw.QMessageBox.Warning)
            msg = "WARNING: Size of dataset is larger than the system memory!"
            warnDiag.setText(msg)
            warnDiag.setWindowTitle("Size Exceeds System Memory!")
            notes = notes+"\n"+msg
        
        notes = notes+"\nSystem byte order: "+self.C.EndianTxt[self.C.SysEndian]+"."
        return notes
    
    def checkGPUMEM(np,nf):
        igpu = self.ImportWindow.ImpGPU.currentIndex()
        if ~igpu:
            gpu_note = 'GPU disabled.'
        #elif np.prod([nPx,nFr]) > intmax('int32'):
        #    gpu_note = 'GPU disabled, because dataset has more elements than MATLAB CUDA''s maximum (2^31-1).';
        #    self.ImportWindow.ImpGPU.setCurrentIndex(0)
        else:
            tgpu = "GPU {:.0f}. "+self.C.GPU(igpu).name+" {:.2f} GiB".format(igpu, self.C.GPU(igpu).mem/1024**3)
            try:
                device = torch.device(igpu if torch.cuda.is_available() else "cpu")
                amem = torch.cuda.get_device_properties(igpu).total_memory
                # If GPU is already in use, taking the current data size into account
                if self.D.GPU == self.ImportWindow.ImpGPU.value():
                    try:
                        amem = amem + self.D.EstMem
                    except:
                        pass

                amem_t = '{:.3f} GiB'.format(amem/1024**3)
                wt = []
                if self.T.EstMem > amem - 128*1024**2: # Has 128 MiB extra?
                    gpu_note = tgpu+" has NOT enough free memory ("+amem_t+"). 128 MiB EXTRA free memory is also required."
                    wt = 'GPU Not Enough Free Memory!'
                    self.ImportWindow.ImpGPU.setCurrentIndex(0)
                elif self.T.EstMem > (amem - 512*1024**2): # Has 512 MiB extra?
                    gpu_note = tgpu+" has LIMITED free memory ("+amem_t+") and may cause errors."
                    wt = 'GPU Limited Free Memory!'
                else:
                    gpu_note = tgpu+" has enough free memory ("+amem_t+") for the selected dataset."
                
                # Notify warnings if any
                if wt:
                    warnDiag = qtw.QMessageBox()
                    warnDiag.setIcon(qtw.QMessageBox.Warning)
                    warnDiag.setText(gpu_note)
                    warnDiag.setWindowTitle(wt)
            except:
                gpu_note = "Failed to select "+tgpu+"!"
                warnDiag = qtw.QMessageBox()
                warnDiag.setIcon(qtw.QMessageBox.Warning)
                warnDiag.setText(gpu_note)
                warnDiag.setWindowTitle("Error Selecting GPU")
                self.ImportWindow.ImpGPU.setCurrentIndex(0)
        return gpu_note
    pass

def saveCallbacks(self, event):
    def updatePrefix():
        pass
    def saveImages():
        pass
    pass

def exportCallbacks(self, event):
    def moveExpAnnot(_, evt):
        pass
    def updateExpRange():
        return pd,px1,py1,npx,npy,px2,py2,fd,fx1,fy1,nfx,nfy
    def exportData():
        return err
    pass

def axeDirCallbacks(self, event):
    def drawAxeDir(id,sp):
        def posAxeDir(annot,offset,xy):
            pass
        pass
    pass

def displayCallbacks(self, event):
    pass

def realSpaceROICallbacks(self, event):
    def drawRealROI(typ):
        pass
    def moveRealROI(src, evt):
        pass
    pass

def detectorModeCallbacks(self, event):
    def clearDetectors():
        pass
    pass

def detrCoordCallbacks(self, event):
    pass

def datasetOptCallbacks(self, event):
    def swap(a,b):
        return b,a
    def getImportInfo():
        return notes
    pass

def previewCallbacks(self, event):
    pass

def transBeamCallbacks(self, event):
    def moveTransBeam(src,evt):
        pass
    def autoAlign():
        pass
    def crossAlign():
        def moveTB(source,event):
            pass
        pass
    pass

def annularDetectorCallbacks(self, event):
    def limitAnnUI():
        pass
    def enableAnnUI():
        pass
    def moveAnnDetr(src, evt):
        def moveAnnR():
            pass
        def moveSeg():
            pass
        def moveScan():
            pass
        pass
    def drawAnnDetr():
        pass
    def drawSegDetr():
        pass
    def drawScanDir():
        pass
    def integrateAnnular():
        pass
    def calcCoM(ri, ro, sd, syf, dr):
        def integrateCoM():
            return CoMX,CoMY
        pass
    pass

def virtualApertureCallbacks(self, event):
    def enableVrApUI():
        pass
    def limitVrApUI():
        pass
    def drawVrApAnnot():
        pass
    def moveVrAp(src, evt):
        pass
    pass

def customDetectorCallbacks(self, event):
    def fontColor(c):
        return fc
    def colorCDTLabel(isel,c):
        pass
    def limitCustDetrUI():
        pass
    def updateEnableShowROI():
        pass
    def updateCustDetrUI():
        pass
    def drawCDROI(id, typ):
        return ROI
    def moveCDROI(src, evt):
        pass
    def plotCustomMask(evt, id):
        pass
    pass

def mathCallbacks(self, event):
    pass

def firstMoment(self, event):
    def saveVect():
        pass
    pass

def showWindowCallbacks(self, event):
    pass

def resizeWindowCallbacks(self, event):
    pass

def updateImagesCallbacks(self, event):
    pass

def resetQuant4DCallbacks(self, event):
    pass

def enableAllUICallbacks(self, event):
    pass