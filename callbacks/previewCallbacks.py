from callbacks.allFunctions import enableWindows,plotImage
from callbacks.importCallbacks import importCallbacks
from callbacks.notifDLG import notifDLG
from callbacks.datasetOptCallbacks import datasetOptCallbacks
import numpy as np
import os, h5py

def previewCallbacks(self, event):
    match self.sender():
        case self.DetrMode: # Entering mode
            self.Fig.Preview.ax.cla()
            self.Image.Preview = None; # Clear previous preview
            enableWindows(self,True) # Enable windows
          
        case self.UpdateImages: # Update image
            self.PreviewButton.trigger() # Preview
          
        case self.PvFrX|self.PvFrY: # Preview Frame X/Y
            event.Source.Value = max(self.sender().value(), 1) # Force Frame X/Y minimum as 1
            self.PreviewButton.trigger() # Preview
          
        case self.PvBC|self.PvBL|self.PvBR|self.PvCC|self.PvCL|self.PvCR|self.PvTC|self.PvTL|self.PvTR: # Location buttons
            #set fractional probe position; naming convetion is horrible #TODO
            match self.sender(): 
                # PvB* = Bottom; PvC* = Vertical Center; PvT* = Top
                case self.PvBC|self.PvBL|self.PvBR:
                    frY = self.PvFrY.maximum()
                case self.PvCC|self.PvCL|self.PvCR:
                    frY = np.ceil(self.PvFrY.maximum()/2)
                case self.PvTC|self.PvTL|self.PvTR:
                    frY = 1
                
            match self.sender(): 
                # Pv*L = Left; Pv*C = Horizontal Center; Pv*R = Right
                case self.PvBR|self.PvCR|self.PvTR:
                    frX = self.PvFrX.maximum()
                case self.PvBC|self.PvCC|self.PvTC:
                    frX = np.ceil(self.PvFrX.maximum()/2)
                case self.PvBL|self.PvCL|self.PvTL:
                    frX = 1

            self.PvFrX.setValue(frX)
            self.PvFrY.setValue(frY)
            self.PreviewButton.trigger() # Preview
          
        case self.PreviewButton:
            self.Fig.Preview.ax.cla()
            # Get parameters
            importCallbacks(self)
            d = self.D
            ifx = self.PvFrX.value()-1 # indices displayed in GUI start at 1; python indices start at 0 --> subtract 1
            ify = self.PvFrY.value()-1 # this gets you to the beginning of the frame of interest

            if d != []:
                dnpx = d.DNPxX
                dnpy = d.DNPxY
                dnfx = d.DNFrX
                dnfy = d.DNFrY
                self.P.PreviewAxLim = [0, dnpx -1 , 0, dnpy - 1]
                self.Fig.Preview.ax.set_xlim(0,dnpx-1)
                self.Fig.Preview.ax.set_ylim(0,dnpy-1)
                try:
                    if not d.h5ds == []: # Preview HDF5
                        f = h5py.File(d.filePath)
                        if d.h5ds in f:
                            frame = f["datacube"][ify,ifx,:,:]
                        else:
                            return
                    else: # Preview others
                        skipBytes = d.Offset + (d.FrHead + dnpx*dnpy*d.ByteSize + d.FrFoot)*(dnfx*ify + ifx) + d.FrHead
                        frame = np.fromfile(file=d.filePath,offset=skipBytes,count=1,dtype=str(dnpx*dnpy)+d.DataType).reshape(dnpx,dnpy)

                    self.Image.Preview = self.Fig.Preview.ax.imshow(frame)
                    plotImage(self,"Preview") # Plot image
                    datasetOptCallbacks(self) # Check NaN
                except:
                    notifDLG(self,'error',"Errors occurred during preview! Maybe reached end-of-file.", 'Error during Preview!')