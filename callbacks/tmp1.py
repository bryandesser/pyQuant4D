from callbacks.appClass import *
from PyQt5 import QtCore as qtc

def unloadData(self, keep_p=False):
    """ Function to unload data and clean all images """
    enableWindows(self,False) # Disable windows for the data unload process
    self.setWindowTitle('Quant4D')
    # Whether to swap dataset only, without changing any existing parameters
    if not keep_p:
        for image in dir(self.Image):
            if not image.startswith("_"):
                setattr(self.Image,image,None)
                fig = getattr(self.Fig,image)
                fig.ax.cla()
                fig.canvas.draw()
        
        #self.HistAxes.ax.cla() # Clear all Axes #TODO
        setattr(self,'P',P)
        setattr(self,'A',A)
        setattr(self,'Image',Image)
        setattr(self,'Mask',Mask)
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
    setattr(self,'D',D)
    setattr(self,'Prev',Prev)

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
    
    # Disable all images when not "on"; visible means disable #TODO
    # ImgGyO is a gray box overlay that disables figure interactions? 
    #set(self.G.ImgGyO,'Visible',~sw)
    
    # Also reset all windows' mouse pointer when enabling UIs
    if sw:
        [ii.setCursor(qtc.Qt.ArrowCursor) for ii in self.G.AllFig]