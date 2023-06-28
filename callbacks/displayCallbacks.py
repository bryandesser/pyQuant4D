import numpy as np
from PyQt5 import QtWidgets as qtw

def displayCallbacks(self):

    id = self.SettingsWindow.DispImage.currentData()
    fig = self.Fig[id]
    ax = self.Axes[id]

    # Initial contrast will be set as the total range of min:max
    # A change in contrast will expand or contract the width of the range
    # Initial brightness will be also set as the total range of min:max
    # A change in brightness will result in shift of the range up or down
    # Initial gamma is set to 1
    # A change in gamma will result in a powerlaw change in contrast I' = I^gamma
    match self.sender():
        case self.SettingsWindow.HistLog: # Log-scale option of histogram
            if self.SettingsWindow.HistLog.isChecked():
                self.SettingsWindow.HistAxes.axes.set_yscale('log')
            else:
                self.SettingsWindow.HistAxes.axes.set_yscale('linear')

        case self.SettingsWindow.DispLock: # Lock "current" image
            # Change dropdown color if locked
            if self.SettingsWindow.DispLock.isChecked():
                backgroundStyle = "background:rgb(255,204,127.5);" # orange
            else:
                backgroundStyle = "" # default
            self.SettingsWindow.DispImage.setStyleSheet(backgroundStyle)
       
        case self.DispVecField:
            fig.vecField = self.DispVecField.currentData() # Vector field

        case self.DispVecColor: # Vector field color
            # Vector field color
            c = qtw.QColorDialog.getColor()
            if c.isValid():
                fig.vecColor = c
            else:
                return # return if canceled

        case self.SettingsWindow.DispCMap:
            fig.colormap = self.SettingsWindow.DispCMap.currentText() # chosen colormap
            ax.set_cmap(fig.colormap+["","_r"][fig.invert]) # append "_r" if inverted

        case self.SettingsWindow.DispCMapInvert:
            fig.invert = self.SettingsWindow.DispCMapInvert.isChecked() # Invert colormap

        case self.SettingsWindow.DispBrightnessReset:
            fig.brightness = 50 # Reset brightness

        case self.SettingsWindow.DispContrastReset:
            fig.contrast = 50 # Reset contrast

        case self.SettingsWindow.DispGammaReset:
            fig.gamma = 1 # Reset gamma

        case self.SettingsWindow.DispBrightness_NF|self.SettingsWindow.DispBrightness:
            fig.brightness = self.sender().value() # Brightness

        case self.SettingsWindow.DispContrast_NF|self.SettingsWindow.DispContrast:
            fig.contrast = self.sender().value() # Contrast

        case self.SettingsWindow.DispGamma|self.SettingsWindow.DispGamma_NF:
            fig.gamma = self.sender().value() # Gamma

        case self.SettingsWindow.DispMaskOpa|self.SettingsWindow.DispMaskOpa_NF:
            fig.maskOpa = self.sender().value() # Mask opacity
            
        case other: # e.g. self.SettingsWindow.DispImage
            # Update GUIs by values stored in `self.Axes.(id).UserData` for the current selected image
            self.Fig[id].activateWindow() # Bring selected image to front
            self.DispVecField.setCurrentIndex(self.DispVecField.findData(fig.vecField))
            self.SettingsWindow.DispCMap.setCurrentIndex(self.SettingsWindow.DispCMap.findText(fig.cmap))
            self.SettingsWindow.DispCMapInvert.setChecked(fig.invert)
            self.DispVecColor.setStyleSheet("background-color:"+fig.vecColor.name())
            
            # Enable vector field UIs if: 1) in CoM/DPC mode AND 2) real-space image selected
            state = (self.DetrMode.currentData() in ["CoMMod","DPCMod"]) and (fig.space == "Real")
            self.DispVecField.setEnabled(state)
            self.DispVecFieldLabel.setEnabled(state)
            self.DispVecColor.setEnabled(state)
            
            # Disable brightness/contrast/colormap UIs if: (CoM/DPC) "Phase" and "ColorWheel for Phase" images
            enabledState = "Phase" not in fig.name # enable components if NOT a Phase image
            self.SettingsWindow.DispBrightness.setEnabled(enabledState)
            self.SettingsWindow.DispBrightness_NF.setEnabled(enabledState)
            self.SettingsWindow.DispContrast.setEnabled(enabledState)
            self.SettingsWindow.DispContrast_NF.setEnabled(enabledState)
            self.SettingsWindow.DispGamma.setEnabled(enabledState)
            self.SettingsWindow.DispGamma_NF.setEnabled(enabledState)
            self.SettingsWindow.DispCMap.setEnabled(enabledState)
            self.SettingsWindow.DispCMapInvert.setEnabled(enabledState)

            # Disable mask opacity UIs if: ColorWheel/Mask/Preview images selected
            enabledState = (fig.space != "ColorWheel") and (fig.type not in ["Mask","Preview"])
            self.SettingsWindow.ShowMaskWdw.setEnabled(enabledState)
            self.SettingsWindow.DispMaskOpa_NF.setEnabled(enabledState)
            self.SettingsWindow.DispMaskOpa.setEnabled(enabledState)

    # Update image
    plotImage(self, id); # Re-plot image

import numpy as np

def plotImage(self,id):
    """Generic function for plotting an image on a given axis with brightness/contrast/gamma values"""
    
    # get image figure and axes
    fig = self.Fig[id] # ImageWindow
    ax = fig.ax # AxesSubplot

    # clear old image(s)
    [ii.remove() for ii in self.Fig.Dfrn.ax.get_images()]

    # abort if image not yet ready
    if self.Axes[id] is None:
        if id == self.SettingsWindow.DispImage.currentData():
            self.SettingsWindow.ImStatsNotes.setPlainText(fig.name)
        return

    im = self.Axes[id].get_array()  # numpy array

    # get image min and max values and resultant range, ignore NaN and +/- Inf 
    minVal = np.ma.masked_invalid(im).min() 
    maxVal = np.ma.masked_invalid(im).max()
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
        
    # Plot the row-major array as row-major `image`
    self.Axes[id] = ax.imshow(im**fig.gamma)  # Apply gamma
        
    # Plot mask opacity on non-mask/non-preview image; maskOpa is in percent (i.e. 50 => 50%)
    if fig.type not in ["Mask","Preview"]:
        mask = self.Axes[fig.space+"Mask"].get_array() # should be a logical mask
        self.Axes[id].set_alpha((1-fig.maskOpa/100)*(1-mask.astype(bool))+mask.astype(bool))

    # Shade CoM/DPC Phase with Magnitude
    if id == "CoMPhMag":
        CoMMagNorm = self.Axes.CoMMag.get_array()
        CoMMagNorm -= np.nanmin(CoMMagNorm)
        CoMMagNorm /= np.nanmax(CoMMagNorm)
        self.Axes[id].set_alpha(self.Axes[id].get_alpha()*CoMMagNorm)

    plotVectorField(self,id) # Plot vector field, if selected #TODO
        
    # Only update statistics if not in changing Event AND it is the "selected" image 
    if (id == self.SettingsWindow.DispImage.currentData()): # and isStaticEvt(evt): #TODO
        #don't update stats while things are changing, only when finished to increase responsiveness
        updateDispImgStats(self,id,im,minVal,maxVal,limitLow,limitHigh,limitRange)

    fig.canvas.draw() # update plot


def updateDispImgStats(self,id,im,minVal,maxVal,limitLow,limitHigh,limitRange):
    """Function to update image's statistics"""
    fig = self.Fig[id]
    ax = fig.ax
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
        binCounts,_,self.A.hist = self.SettingsWindow.HistAxes.axes.hist(im.ravel(),bins=128,ec='k',linewidth=0.5)

        # Set histogram y limits
        self.SettingsWindow.HistAxes.axes.set_ylim(0.5,(1.1*binCounts).max().clip(1)) # Make sure upper limit is at least 1

    # Update histogram annotations skip if values unchanged
    if isDiffToPrev(self,'hist',(ax,minVal,maxVal,limitLow,limitHigh,limitRange,fig.gamma,self.SettingsWindow.HistLog.isChecked())):
        # Update ROIs
        try:
            self.A.histBox.remove()
            self.A.histBox = None
        except:
            pass

        # Draw ROI of range if not yet #TODO
        if self.A.histBox is None:
            pass#self.A.hist.Box = drawrectangle(self.SettingsWindow.HistAxes,'Position',[1 1 1 1],'LineWidth',1,'MarkerSize',eps(),'FaceAlpha',.1,'InteractionsAllowed','translate')
            #self.A.hist.Hi = drawpoint(self.SettingsWindow.HistAxes,'Position',[1 1])
            #self.A.hist.Lo = drawpoint(self.SettingsWindow.HistAxes,'Position',[1 1])
            #addlistener([self.A.hist.Box self.A.hist.Lo self.A.hist.Hi],'MovingROI',@moveHistHiLo)
            #ud.Move = addlistener([self.A.hist.Box self.A.hist.Lo self.A.hist.Hi],'ROIMoved',@moveHistHiLo)
            #set([self.A.hist.Box self.A.hist.Lo self.A.hist.Hi],'Deletable',0,'UserData',ud,'Tag','HistROI')

        # Save current display limits to ROIs
        self.A.histBox.ax = ax
        self.A.histBox.minVal = minVal
        self.A.histBox.maxVal = maxVal
        self.A.histBox.limitLow = limitLow
        self.A.histBox.limitHigh = limitHigh
        self.A.histBox.limitRange = limitRange
          
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
        x = np.linspace(0,1,128) # histogram is on x_lim = [0,1]
        self.A.histGamma, = self.SettingsWindow.HistAxes.axes.plot(x,((x-limitLow)/(limitHigh-limitLow))**fig.gamma*np.ptp(self.SettingsWindow.HistAxes.axes.get_ylim())+self.SettingsWindow.HistAxes.axes.get_ylim()[0], color='k')
        
        # Print display limits on the histogram
        textstr = "High:{:< 9.2e}\nLow:{:< 9.2e}".format(limitHigh,limitLow)

        # these are matplotlib.patch.Patch properties
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)

        # place a text box in upper left in axes coords
        self.A.histNote = self.SettingsWindow.HistAxes.axes.text(0.05, 0.95, textstr, transform=ax.transAxes,fontsize=10,verticalalignment='top', bbox=props)#, font="Courier")

        # update histogram canvas
        self.SettingsWindow.HistAxes.figure.canvas.draw()

def plotVectorField(self,id):
    """ Function to plot a vector field image over top of the DPC or CoM images (either magnitude, angle, or combination) """
    fig = self.Fig[id]
    try:
        self.A.vecField.remove()
        self.A.vecField = None
    except:
        pass

    # vector field sampling (0,1:1,1:2,1:4,1:8,1:16)
    vec = fig.vecField

    # if vector field sampling == 0, or not currently in CoM or DPC modes, return
    if (not vec) or (self.DetrMode.currentData() in ["CoMMod", "DPCMod"]):
        return
    
    # Plot vector arrows over the selected image
    x,y = np.meshgrid(np.arange(0,self.D.NFrX,vec),np.arange(0,self.D.NFrY,vec))
    u = self.Axes.CoMX.get_array()[0::vec, 0::vec]
    v = self.Axes.CoMY.get_array()[0::vec, 0::vec] 
    self.A.vecField[id] = fig.ax.quiver(x, y, u, v, color=fig.vecColor,units='xy')
    fig.canvas.draw()



def isDiffToPrev(self,name,val):
    """Function to check whether the named given value is changed compared to the previous value, and store the new value"""
    c = (not hasattr(self.Prev, name)) or (not getattr(self.Prev,name)==val)
    if c:
        setattr(self.Prev,name,val)
    return c