#from callbacks import importSelectFile
import sys
import torch
import numpy as np
import psutil
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from callbacks.appClass import appStruct
from callbacks.callbacks import plotColorwheel, slotsSignals
from callbacks.imageUtils import drawAnnDetr
    
def startupFcn(self):
    from callbacks.guiClass import ImageWindow, SaveWindow, SettingsWindow, ImportWindow

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

    # Function to Check usable system memory and make sure the file will fit
    def getMem(self):
        mem = psutil.virtual_memory()
        self.C.MemTot = mem.total
        self.C.MemFree = mem.available

    # Function to get pixels in each monitor
    def checkMonitors(self):
        self.C.ScreenSize = qtw.QDesktopWidget().availableGeometry().getRect()
        for i in range(qtw.QDesktopWidget().screenCount()):
            self.C.MonitorPositions.append(qtw.QDesktopWidget().screenGeometry(i).getRect())
        
        # monitor size
        self.C.monitorWidth = qtw.QApplication.desktop().screenGeometry().width()
        self.C.monitorHeight = qtw.QApplication.desktop().screenGeometry().height()

        # toolbar size + any horizontal or vertical offsets due to toolbar
        self.C.hOffset, self.C.vOffset, self.C.toolbarWidth, self.C.toolbarHeight  = abs(np.array(qtw.QApplication.desktop().screenGeometry().getRect())-np.array(qtw.QApplication.desktop().availableGeometry().getRect()))

        # establish window decoration sizes with temporary image window
        tmp = ImageWindow("","","","","",[0, 0, 400, 400])
        self.C.decorPad,self.C.titleHeight = [tmp.geometry().x()-tmp.pos().x(), tmp.geometry().y()-tmp.pos().y()]
        if [self.C.decorPad,self.C.titleHeight]==[0,0]:
            self.C.decorPad = 5
            self.C.titleHeight = 25
        self.C.mplDecor = tmp.size()-qtc.QSize(400,400)
        tmp.close()

        # available monitor space
        self.C.monitorAvailWidth = self.C.monitorWidth - self.C.toolbarWidth
        self.C.monitorAvailHeight = self.C.monitorHeight - self.C.toolbarHeight

        # window positioning
        self.C.sz = int(np.floor(np.minimum(self.C.monitorAvailWidth-4*self.C.decorPad-2*self.C.mplDecor.width(),self.C.monitorAvailHeight-2*self.C.titleHeight-2*self.C.decorPad-2*self.C.mplDecor.height()))/2)
        self.C.shc = self.C.monitorAvailWidth/2
        self.C.l = self.C.monitorAvailWidth-self.C.sz+self.C.hOffset-self.C.mplDecor.width()
        self.C.wb0 = self.C.monitorAvailHeight-self.C.sz+self.C.vOffset

        # Set limits/values for image window resize options
        self.SettingsWindow.WdwWDfrn.setRange(1,self.C.monitorAvailWidth)
        self.SettingsWindow.WdwHDfrn.setRange(1,self.C.monitorAvailHeight)
        self.SettingsWindow.WdwWReal.setRange(1,self.C.monitorAvailWidth)
        self.SettingsWindow.WdwHReal.setRange(1,self.C.monitorAvailHeight)
        self.SettingsWindow.WdwWDfrn.setValue(self.C.sz)
        self.SettingsWindow.WdwHDfrn.setValue(self.C.sz)
        self.SettingsWindow.WdwWReal.setValue(self.C.sz)
        self.SettingsWindow.WdwHReal.setValue(self.C.sz)
    
    def createImageWindows(self):
        self.Fig.Dfrn = ImageWindow("Dfrn","Diffraction","Dfrn","Primary","gray",[self.C.shc-self.C.sz/2, self.C.decorPad + self.C.titleHeight + self.C.vOffset, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()]) # Top-center
        self.Fig.DfrnMask = ImageWindow("DfrnMask","Diffraction Mask","Dfrn","Mask","gray",[self.C.shc-self.C.sz/2, self.C.sz+2*(self.C.decorPad + self.C.titleHeight) + self.C.mplDecor.height() + self.C.vOffset, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()]) # right of Top-center
        self.Fig.iCoM = ImageWindow("iCoM","iCoM","Real","CoM","gray",[self.C.l, self.C.decorPad + self.C.titleHeight + self.C.vOffset, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()])
        self.Fig.dCoM = ImageWindow("dCoM","dCoM","Real","CoM","gray",[self.C.l, 2*(self.C.decorPad + self.C.titleHeight) + self.C.vOffset, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()])
        self.Fig.CoMY = ImageWindow("CoMY","CoM Y","Real","CoM","gray",[self.C.l, 3*(self.C.decorPad + self.C.titleHeight) + self.C.vOffset, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()])
        self.Fig.CoMX = ImageWindow("CoMX","CoM X","Real","CoM","gray",[self.C.l, 4*(self.C.decorPad + self.C.titleHeight) + self.C.vOffset, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()])
        self.Fig.CoMMag = ImageWindow("CoMMag","CoM Magnitude","Real","CoM","gray",[self.C.l, 5*(self.C.decorPad + self.C.titleHeight) + self.C.vOffset, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()])
        self.Fig.CoMPh = ImageWindow("CoMPh","CoM Phase","Real","CoM","hsv",[self.C.l, 6*(self.C.decorPad + self.C.titleHeight) + self.C.vOffset, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()])
        self.Fig.CoMPhMag = ImageWindow("CoMPhMag","CoM Phase (Magnitude-shaded)","Real","CoM","hsv",[self.C.l, 7*(self.C.decorPad + self.C.titleHeight) + self.C.vOffset, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()])
        self.Fig.RealMask = ImageWindow("RealMask","Real-space Mask","Real","Mask","gray",[self.C.l, 8*(self.C.decorPad + self.C.titleHeight) + self.C.vOffset, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()])
        self.Fig.Real = ImageWindow("Real","Real-space","Real","Primary","gray",[self.C.l, 9*(self.C.decorPad + self.C.titleHeight) + self.C.vOffset, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()])
        self.Fig.ColorWheel = ImageWindow(id = "ColorWheel", name = "Color Wheel for Phase Direction", sp = "ColorWheel", typ = "CoM", cmap = "hsv", pos = [self.C.shc-self.C.sz-self.C.mplDecor.width(), self.C.sz+2*(self.C.decorPad+self.C.titleHeight)+self.C.mplDecor.height() + self.C.vOffset, self.C.sz/2 + self.C.mplDecor.width(), self.C.sz/2 + self.C.mplDecor.height()])
        plotColorwheel(self) 

    def populateDropdowns(self):
        """ populates GUI dropdowns with itemText and itemData where necessary """

        # import window, byte order
        self.ImportWindow.ImpByteOrder.clear()
        self.ImportWindow.ImpByteOrder.addItem("Little Endian",'l')
        self.ImportWindow.ImpByteOrder.addItem("Big Endian",'b')

        # export window, byte order
        self.SaveWindow.ExpByteOrder.clear()
        self.SaveWindow.ExpByteOrder.addItem("Little Endian",'l')
        self.SaveWindow.ExpByteOrder.addItem("Big Endian",'b')

        # export window, file format
        self.SaveWindow.ExpFormat.Items = {'HDF5 (*.h5)', 'Raw binary (*.raw)'}
        self.SaveWindow.ExpFormat.ItemsData = {'h5', 'raw'}


        # main UI window, diffraction modes
        diffType = ['PrvwMod', 'AlignMod', 'AnnMod', 'DPCMod', 'CoMMod', 'VrApMod', 'CustMod']
        diffTypeText = ['Import Preview', 'Alignment', 'Annular/Round', 'Segmented (DPC)', 'Center of Mass', 'Virtual Aperture', 'Custom Detectors']
        self.DetrMode.clear()
        for dtt,dt in zip(diffTypeText,diffType):
            self.DetrMode.addItem(dtt,dt)

        # main UI window, real-space ROI shapes
        ROIType = ['full', 'point', 'ellipse', 'rectangle', 'poly', 'file']
        ROITypeText = ['Full Image', 'Point', 'Ellipse', 'Rectangle', 'Draw Polygon', 'From File']
        self.RealROIShape.clear()
        for rtt,rt in zip(ROITypeText,ROIType):
            self.RealROIShape.addItem(rtt,rt)


        # main UI window, vecotr overlay sampling options
        vectType = [0,1,2,4,8,16]
        vectTypeText = ['None', '1:1', '1:2', '1:4', '1:8', '1:16']
        self.DispVecField.clear()
        for vtt,vt in zip(vectTypeText,vectType):
            self.DispVecField.addItem(vtt,vt)

        # import window, GPU selection
        self.ImportWindow.ImpGPU.clear()
        self.ImportWindow.ImpGPU.addItem('GPU off')

        # import window, memory loading selection
        self.ImportWindow.ImpMemType.clear()
        self.ImportWindow.ImpMemType.addItems(['Physical Memory','Virtual Mapping'])

        # settings window, colormap options
        self.SettingsWindow.DispCMap.clear()
        self.SettingsWindow.DispCMap.addItems(['gray', 'inferno', 'hsv', 'jet', 'viridis', 'hot', 'cool', 'spring', 'summer', 'autumn', 'winter', 'bone', 'copper', 'pink'])

        # settings window, diffraction space coordinates system
        self.SettingsWindow.DCSys.clear()
        self.SettingsWindow.DCSys.addItems(['Polar', 'Cartesian'])

        # settings window, diffraction space position reference
        self.SettingsWindow.DCPos.clear()
        self.SettingsWindow.DCPos.addItems(['Relative', 'Absolute'])

        # settings window, diffraction space units
        self.SettingsWindow.DCUnit.clear()
        self.SettingsWindow.DCUnit.addItem('mrad','mrad')
        self.SettingsWindow.DCUnit.addItem('Pixel','px')

        # settings window, real space rotation options
        self.SettingsWindow.RotReal.clear()
        self.SettingsWindow.RotReal.Items = {'0°', '90°', '180°', '-90°'}
        self.SettingsWindow.RotReal.ItemsData = [0,90,180,-90]

        # settings window, calculation policy
        self.SettingsWindow.CalcPolicy.clear()
        self.SettingsWindow.CalcPolicy.addItem('Active',2)
        self.SettingsWindow.CalcPolicy.addItem('Reduced',1)
        self.SettingsWindow.CalcPolicy.addItem('Passive',0)

        # main UI window, virtual aperture rotation options
        rotType = [90,60,45,30,22.5,10,5,2,1,0.5,0.25]
        rotTypeText = ['90°', '60°', '45°', '30°', '22.5°', '10°', '5°', '2°', '1°', '0.5°', '0.25°']
        self.VrApRotStep.clear()
        for rtt,rt in zip(rotTypeText,rotType):
            self.VrApRotStep.addItem(rtt,rt)

        # main UI window, custom aperture rotation options
        rotType = [90,60,45,30,22.5,10,5,2,1,0.5,0.25]
        rotTypeText = ['90°', '60°', '45°', '30°', '22.5°', '10°', '5°', '2°', '1°', '0.5°', '0.25°']
        self.CDRotStep.clear()
        for rtt,rt in zip(rotTypeText,rotType):
            self.CDRotStep.addItem(rtt,rt)

        # main UI window, virtual aperture symmetry options
        symmType = [1,2,3,4,6]
        symmTypeText = ['1', '2', '3', '4', '6']
        self.VrApSymm.clear()
        for stt,st in zip(symmTypeText,symmType):
            self.VrApSymm.addItem(stt,st)

        # main UI window, custom intramask interactions
        self.CDIntraMask.clear()
        self.CDIntraMask.addItems(['Union', 'Intersection', 'Additive'])

        # main UI window, custom intermask interactions
        self.CDInterMask.clear()
        self.CDInterMask.addItems(['Union', 'Intersection', 'Additive', 'Current-only'])

    # add class attributes to match those from original Matlab version app.*
    appStruct(self)

    # Generate additional UI windows
    self.ImportWindow = ImportWindow()
    self.SettingsWindow = SettingsWindow()
    self.SaveWindow = SaveWindow()

    # get current screen size information
    checkMonitors(self)

    # check system endianess
    if sys.byteorder == 'little':
        self.C.SysEndian = 'l'
    else:
        self.C.SysEndian = 'b'

    # get CPU memory information
    getMem(self)

    # get GPU memory information (if available)
    getGPU(self)

    # populate all of the dropdowns
    populateDropdowns(self)

    # create other UI windows and Image figures
    createImageWindows(self)

    # enable custom slot/signal interfaces
    slotsSignals(self)

    # generate adf annotations
    drawAnnDetr(self)

    # start with a mostly blank UI
    self.RealSpacePanel.setVisible(False)
    self.progressBarPanel.setVisible(False)
    self.DfrnDetrTabGroup.setVisible(False)
    self.DetectorModeGroup.setVisible(False)

    # Import Data is the only option to start
    # turn off ALL actions
    for action in self.findChildren(qtw.QAction):
        if not action.isSeparator():
            action.setEnabled(False)
    # make sure top level menu (File, Settings, Window, Help) is enabled
    for menu in self.menubar.actions():
        menu.setEnabled(True)
    # only allow user to import data
    self.ShowImportWdw.setEnabled(True)