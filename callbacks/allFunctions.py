import matplotlib.backend_bases
import os, sys, traceback, re, gc, psutil, importlib, h5py, matplotlib,time
from PIL import Image
import numpy as np
import torch
from multiprocessing.pool import ThreadPool
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from PyQt5 import QtGui as qtg
import callbacks.appClass as appClass
from callbacks.appClass import *
from annotationsClasses.InteractiveCircle import InteractiveCircle
from annotationsClasses.interactiveAnnulus import InteractiveAnnulus
from annotationsClasses.interactivePoint import InteractivePoint
from callbacks.virtualApertureCallbacks import virtualApertureCallbacks as _virtualApertureCallbacks

def importCallbacks(self):
    def gatherImportOptions(preview):
        d = D() # initialize 

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
        d.ByteSize = self.ByteSize[d.DataType]

        # Physical or virtual memory loading
        d.mem = self.ImportWindow.ImpMemType.currentText()

        # Select GPU if acceleration is enabled AND not in Import Preview Mode
        d.GPU = self.ImportWindow.ImpGPU.currentData()
        if not preview and d.GPU!=None:
            torch.device(0 if torch.cuda.is_available() else "cpu")

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
        d.NFr = np.array([d.NFrY,d.NFrX]) 
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

    match self.sender():
        case self.ShowImportWdw:
            if self.ShowImportWdw.isChecked():
                # Enter Import Preview Mode
                if self.DetrMode.currentData != "PrvwMod":
                    self.DetrMode.setCurrentIndex(self.DetrMode.findData("PrvwMod"))
                
                # if the file path exists, keep all fields accessible; else disable all by file selection button
                fileExists = os.path.exists(self.ImportWindow.ImpFilePath.text())
                self.ImportWindow.DatasetInfoFrame.setEnabled(fileExists)
                self.ImportWindow.ImportOptionsFrame.setEnabled(fileExists)
                self.ImportWindow.ImpFilePath.setEnabled(fileExists)
                self.ImportWindow.ImportDataButton.setEnabled(fileExists)
                self.ImportWindow.ImpKeepP.setEnabled(fileExists)
                self.ImportWindow.ImpFileSelect.setEnabled(True)
                self.ImportWindow.ImportCancelButton.setEnabled(True)

                # set default button to "Select" if file does NOT exist; else default to "Import"
                self.ImportWindow.ImportDataButton.setDefault(fileExists)
                self.ImportWindow.ImportDataButton.setAutoDefault(fileExists)
                self.ImportWindow.ImpFileSelect.setDefault(not fileExists)
                self.ImportWindow.ImpFileSelect.setAutoDefault(not fileExists)
                
                # show import UI
                self.ImportWindow.show()
            else:
                self.ImportWindow.ImportCancelButton.click()

        case self.ImportWindow.ImportCancelButton: # Hide window when closing
            self.ImportWindow.hide()
            self.ShowImportWdw.setChecked(False)
            # return to previous detector mode from Import Preview Mode
            if (self.DetrMode.currentData() == "PrvwMod") and (self.P.DetrMode != None):
                self.DetrMode.setCurrentIndex(self.DetrMode.findData(self.P.DetrMode))

        case self.ImportWindow.ImportDataButton|self.PreviewButton: # When the "Import Data" or "Preview" button is pressed
            self.T.Preview = D() # reset the preview parameters

            # warn user if file does not exist at path, or the datatype is not selected; else import data
            if not os.path.exists(self.ImportWindow.ImpFilePath.text()):
                notifDLG(self, self.ImportWindow, 'warn', 'The entered file path is invalid!', 'Invalid File!')
            
            elif self.ImportWindow.ImpDataType.currentData() == "unknown":
                notifDLG(self, self.ImportWindow, 'warn', 'Select the correct data type!', 'Select Data Type!')
            
            else:
                if self.sender() == self.ImportWindow.ImportDataButton: # Import data
                    self.ImportWindow.hide()
                    unloadData(self, self.ImportWindow.ImpKeepP.isChecked())
                    self.D = gatherImportOptions(preview=False)
                    self.T.prev_D = self.D # Backup current `self.D`
                    importData(self)
                else: # Preview
                    self.T.Preview = gatherImportOptions(preview=True)

        case self.SettingsWindow.SwapDfrnXY|self.SettingsWindow.SwapRealXY: # Refresh axes settings etc when dimensions swapped
            prepareData(self)

def previewCallbacks(self):
    # bypass execution if signals are actively being blocked (i.e. for programmatically updating UI values)
    if self.blockAllSignals:
        return

    match self.sender():
        case self.DetrMode: # Entering mode
            self.Fig.Preview.ax.cla()
            self.Fig.Preview.Image = None # Clear previous preview
            self.ImageAx.Preview = None # clear AxesImage
            enableWindows(self,True) # Enable windows
        
        case self.PvFrX|self.PvFrY:
            self.PreviewButton.click() # Preview

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

            self.blockAllSignals = True
            self.PvFrX.setValue(int(frX))
            self.PvFrY.setValue(int(frY))
            self.blockAllSignals = False
            self.PreviewButton.click() # Preview
          
        case self.PreviewButton|self.UpdateImages:
            self.Fig.Preview.ax.cla()
            self.Fig.Preview.Image = None # Clear previous preview
            self.ImageAx.Preview = None # clear AxesImage
            self.Fig.Preview.show()
            # Get parameters
            importCallbacks(self)
            d = self.T.Preview
            ifx = self.PvFrX.value()-1 # indices displayed in GUI start at 1; python indices start at 0 -->
            ify = self.PvFrY.value()-1 # subtract 1 to get to the beginning of the frame of interest

            if d != None:
                dnpx = d.DNPxX
                dnpy = d.DNPxY
                dnfx = d.DNFrX
                dnfy = d.DNFrY
                self.P.PreviewAxLim = np.array([0, dnpx, dnpy, 0]) - 0.5
                self.Fig.Preview.ax.set_xlim(self.P.PreviewAxLim[0:2])
                self.Fig.Preview.ax.set_ylim(self.P.PreviewAxLim[2:])
                try:
                    if not d.h5ds == []: # Preview HDF5
                        f = h5py.File(d.filePath)
                        if d.h5ds in f:
                            frame = f[d.h5ds][ify,ifx,:,:]
                            f.close()
                        else:
                            f.close()
                            return
                    else: # Preview others
                        skipBytes = d.Offset + (d.FrHead + dnpx*dnpy*d.ByteSize + d.FrFoot)*(dnfx*ify + ifx) + d.FrHead
                        frame = np.fromfile(file=d.filePath,offset=skipBytes,count=1,dtype=str(dnpx*dnpy)+d.DataType).reshape(dnpx,dnpy)

                    self.Fig.Preview.Image = frame
                    plotImage(self,"Preview") # Plot image
                    datasetOptCallbacks(self) # Check NaN
                except:
                    notifDLG(self,self.Fig.Preview,'error',"Errors occurred during preview! Maybe reached end-of-file.", 'Error during Preview!')
                    
def notifDLG(self, parent, icon="", msg="", ttl="", opt=[]):
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
        sel,ok = qtw.QInputDialog().getItem(parent,ttl,msg,opt,0,False) # default option 0, multiselect=False
        if not ok:
            enableWindows(self,True) # enable windows
            return None
    
    else: 
        dlg = qtw.QMessageBox(parent) # establish a messagebox
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
        
        sel = notifDLG(self, self.ImportWindow, 'quest', msg, ttl, opt)



        # Execute the swap byte order callbacks
        if sel.startswith("Yes"):
            self.SettingsWindow.SwapByteOrder.click()

        return sel #string of button, will be checked outside function for further action
    
    else:
        return None

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
            fileName, = fDialog.selectedFiles()
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
            self.fname = fileName
            self.ImportWindow.ImpFilePath.setText(self.fname)
            # enable rest of wigets in window
            for widget in self.ImportWindow.children():
                widget.setEnabled(True)
        else:
            # keep wigets disabled
            for widget in self.ImportWindow.children():
                widget.setEnabled(False)
            
        
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
        self.fileDir = os.path.dirname(self.ImportWindow.ImpFilePath.text())
        self.fileName = os.path.basename(self.ImportWindow.ImpFilePath.text())
        _,self.fileExt = os.path.splitext(self.ImportWindow.ImpFilePath.text())
        os.chdir(self.fileDir)
        self.T.FileSize = os.path.getsize(self.fileName)
        self.ImportWindow.ImpActualFilesize.setText("{} bytes, {:.2f} GiB".format(self.T.FileSize,self.T.FileSize/1024**3))

        # activate Import Preview
        self.DfrnDetrTabGroup.setVisible(True)
        self.DfrnDetrTabGroup.setCurrentIndex(0)

        # activate preset buttons if file extension matches a known filetype, else custom
        match self.fileExt.casefold():
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
        self.ImportWindow.ImpActualFilesize.clear()
        self.DfrnDetrTabGroup.setVisible(False)
        self.PreviewTab.setVisible(False)
        self.PreviewTab.setEnabled(False)
    
    importFileType(self)

def importFileType(self):
    def guessFramesFromSize():
        """ Make an initial guess at the file dimensions (assume ~square field of view: NFrX≈NFrY) """
        if self.ImportWindow.DNPxX.value() > 1 and self.ImportWindow.DNPxY.value() > 1:
            bitSize = self.ByteSize[self.ImportWindow.ImpDataType.currentData()]

            # factoring in dataoffset/tail/header/footer lengths, get total number of frames (xy)
            z = (self.T.FileSize-self.ImportWindow.DataOffset.value()-self.T.fileTail) \
                    /(self.ImportWindow.DNPxX.value()*self.ImportWindow.DNPxY.value()*bitSize+self.ImportWindow.FrHead.value()+self.ImportWindow.FrFoot.value())
            
            # assume dataset is as close to square as possible, factorize xy to (x,y)
            guessFramesFromDimZ(int(z))

    def guessFramesFromDimZ(z):
        """ Guess number of frames (x,y) from 3D dataset by finding the two largest integer factors that go into z without remainder """
        x = round(np.sqrt(z))
        while z%x > 0:
            x -= 1

        self.ImportWindow.DNFrX.setValue(x)
        self.ImportWindow.DNFrY.setValue(z//x)

    def getDimFromName(filename):
        """
        Guess dataset size from fileName in the following style (only the first match):
            fileName = 'fooAxBxCxDbar', where A,B,C,D are integers:
                            A = NPxX
                            B = NPxY
                            C = NFrX
                            D = NFrY
        """

        try:
            # standard EMPAD naming scheme
            s = re.search(r'_x(\d+)_y(\d+).raw', filename)
            DNFrX,DNFrY = [int(ii) for ii in s.groups()]
            DNPxX = DNPxY = int(128)

        except:
            try:
                # above described naming scheme
                t = re.search(r'(\d+)x(\d+)x(\d+)x(\d+)', filename)
                DNPxX,DNPxY,DNFrX,DNFrY = [int(ii) for ii in t.groups()]
            except:
                # failure, quit now
                return
            
        finally:
            # if the above passed, set the import window UI values
            self.ImportWindow.DNPxX.setValue(DNPxX)
            self.ImportWindow.DNPxY.setValue(DNPxY)
            self.ImportWindow.DNFrX.setValue(DNFrX)
            self.ImportWindow.DNFrY.setValue(DNFrY)
    
    def returnKeys(obj):
        datasetKeys=[]
        def allkeys(obj):
            keys = (obj.name,)
            if isinstance(obj, h5py.Group):
                for key, value in obj.items():
                    if isinstance(value, h5py.Group):
                        keys = keys + allkeys(value)
                    else:
                        keys = keys + (value.name,)
                        datasetKeys.append(value.name)
            return keys
        allkeys(obj)
        return datasetKeys
    
    # block slots/signals whilst updating UI values
    self.blockAllSignals = True

    # Default values/properties
    notes = None
    err = 0 #TODO
    self.T.dm = []
    self.T.h5 = []
    self.T.fileTail = 0
    self.ImportWindow.DataOffset.setValue(0)
    self.ImportWindow.FrHead.setValue(0)
    self.ImportWindow.FrFoot.setValue(0)
    self.ImportWindow.DNPxX.setValue(1)
    self.ImportWindow.DNPxY.setValue(1)
    self.ImportWindow.DNFrX.setValue(1)
    self.ImportWindow.DNFrY.setValue(1)
    
    # Medipix data are saved as a .mib file of varying bit-depth as unsigned integers of the next highest class
    #   (i.e. 12-bit is saved as a 16-bit unsigned integer) with big-endian ordering.
    # EMPAD data are saved as a .raw file with 32-bit depth with little endian ordering.
    # Fiji/ImageJ tend to save their files with big-endian ordering, though this is also system- and user-dependent.
    # H5 and other binary/raw data types are allowed, but user-dependent.

    # available data types and their plain text names
    dataType = ['unknown','i1','u1','i2','u2','f4','i4','u4','f8','i8','u8']
    dataTypeText = ['Select Data Type...','8-bit Signed','8-bit Unsigned','16-bit Signed','16-bit Unsigned','32-bit Real', \
                    '32-bit Signed','32-bit Unsigned','64-bit Real','64-bit Signed','64-bit Unsigned']

    # add to combobox
    self.ImportWindow.ImpDataType.clear()
    for dtt,dt in zip(dataTypeText,dataType):
        self.ImportWindow.ImpDataType.addItem(dtt,dt)

    # default to "Select Data Type..." prompt
    self.ImportWindow.ImpDataType.setCurrentIndex(0)

    # start with h5 directory combobox cleared and disabled
    if self.sender() == self.ImportWindow.ImpFileSelect:
        self.ImportWindow.ImpSubImg.clear()
        self.ImportWindow.ImpSubImg.setEnabled(False)

    # default to "little endian"
    self.ImportWindow.ImpByteOrder.setCurrentIndex(0)

    # unblock slots/signals
    self.blockAllSignals = False

    if os.path.isfile(self.ImportWindow.ImpFilePath.text()):
        if self.ImportWindow.EMPADButton.isChecked():
            self.ImportWindow.FrFoot.setValue(1024)
            self.ImportWindow.DNPxX.setValue(128)
            self.ImportWindow.DNPxY.setValue(128)
            self.ImportWindow.ImpDataType.setCurrentIndex(self.ImportWindow.ImpDataType.findData('f4'))

            notes = 'Pixels:\t128x128\n32-bit Real\n** EMPAD data have 1024-byte frame footers'
            guessFramesFromSize()
            getDimFromName(self.ImportWindow.ImpFilePath.text())

        elif self.ImportWindow.MedipixButton.isChecked():
            # available data types and their plain text names - Medipix edition
            dataType = ['unknown','u1','u2','u4']
            dataTypeText = ['Select Data Type...','1 or 6-bit Padded Unsigned','12-bit Padded Unsigned','24-bit Padded Unsigned']

            # add to combobox
            self.ImportWindow.ImpDataType.blockSignals(True)
            self.ImportWindow.ImpDataType.clear()
            for dtt,dt in zip(dataTypeText,dataType):
                self.ImportWindow.ImpDataType.addItem(dtt,dt)
            self.ImportWindow.ImpDataType.blockSignals(True)

            # check .mib file header
            fmeta = np.fromfile(self.ImportWindow.ImpFilePath.text(),dtype=np.uint8,count=128)
            fmeta = re.split(",",''.join(chr(i) for i in fmeta))

            if (len(fmeta) >= 7) and (fmeta[6][0].casefold() in ("u","r")):
                # Re-read with known header size
                fmeta = np.fromfile(self.ImportWindow.ImpFilePath.text(),dtype=np.uint8,count=int(fmeta[2]))
                fmeta = re.split(",",''.join(chr(i) for i in fmeta))
                datatype = fmeta[6].casefold()
                bitsize = int(fmeta[-2])
                if datatype.startswith('u'):
                    match bitsize:
                        case 1|6:
                            self.ImportWindow.ImpDataType.setCurrentIndex(1)
                        case 12:
                            self.ImportWindow.ImpDataType.setCurrentIndex(2)
                        case 24:
                            self.ImportWindow.ImpDataType.setCurrentIndex(3)

                self.ImportWindow.FrHead.setValue(int(fmeta[2]))
                self.ImportWindow.ImpByteOrder.setCurrentIndex(1) # 'b'
                self.ImportWindow.DNPxX.setValue(int(fmeta[4]))
                self.ImportWindow.DNPxY.setValue(int(fmeta[5]))
                notes = 'Dim: X = '+str(int(fmeta[4]))+', Y = '+str(int(fmeta[5]))+'\nData type: '+fmeta[6]+'\nPixel depth: '+str(bitsize)+' bit\n' \
                    'Frame header: '+str(int(fmeta[2]))+' bytes\nBig endian'
                guessFramesFromSize()
                getDimFromName(self.ImportWindow.ImpFilePath.text())
            else:
                notes = 'Unrecognizable as a Medipix/.mib file.'
                err = -1

        elif self.ImportWindow.MRCButton.isChecked():
            # Read in MRC header - first 1024 bytes
            map = np.fromfile(self.ImportWindow.ImpFilePath.text(),count=212,dtype=np.uint8)
            map = ''.join(chr(let) for let in map[-4:])

            if map == "MAP ":
                # Bytes for Endianness
                e = np.fromfile(self.ImportWindow.ImpFilePath.text(),count=2,dtype=np.uint8,offset=212)
                if e[0] == 68 and e[1] in [65, 68]:
                    self.ImportWindow.ImpByteOrder.setCurrentIndex(0) # 'l'
                    bo = 'Little Endian'
                elif e[0] == 17 and e[1] == 17:
                    self.ImportWindow.ImpByteOrder.setCurrentIndex(1) # 'b'
                    bo = 'Big Endian'
                else:
                    bo = 'Unknown Endianness'
                
                # X, Y and Z: data is structured as 3D
                dim = np.fromfile(self.ImportWindow.ImpFilePath.text(),count=3,dtype=np.uint32)
                self.ImportWindow.DNPxX.setValue(dim[0])
                self.ImportWindow.DNPxY.setValue(dim[1])
                self.ImportWindow.DNFrX.setValue(dim[2])

                guessFramesFromDimZ(dim[2])
                getDimFromName(self.ImportWindow.ImpFilePath.text())

                dataType = np.fromfile(self.ImportWindow.ImpFilePath.text(),count=1,dtype=np.uint32,offset=12)
                match dataType:
                    case 0:
                        self.ImportWindow.ImpDataType.setCurrentIndex(self.ImportWindow.ImpDataType.findData('i1'))
                        tnote = '8-bit Signed Integer'
                    case 1:
                        self.ImportWindow.ImpDataType.setCurrentIndex(self.ImportWindow.ImpDataType.findData('i2'))
                        tnote = '16-bit Signed Integer'
                    case 2:
                        self.ImportWindow.ImpDataType.setCurrentIndex(self.ImportWindow.ImpDataType.findData('f4'))
                        tnote = '32-bit Real Float'
                    case 3:
                        tnote = '16-bit Complex Signed Integer, unsupported'
                    case 4:
                        tnote = '32-bit Complex Float, unsupported'
                    case 6:
                        self.ImportWindow.ImpDataType.setCurrentIndex(self.ImportWindow.ImpDataType.findData('u2'))
                        tnote = '16-bit Unsigned Integer'
                    case other:
                        tnote = 'Uknown data type'

                self.ImportWindow.DataOffset.setValue(1024)
                notes = 'Dim: X = '+str(dim[0])+', Y = '+str(dim[1])+', Z = '+str(dim[2])+'\n'+tnote+', '+bo+'\n** MRC files have a 1024-byte data offset'
            else:
                notes = 'Unrecognizable as MRC.\n\n"MAP " word missed.'
                err = -1
                return
        elif self.ImportWindow.DM34Button.isChecked():
            prepDM(self)
        elif self.ImportWindow.HDF5Button.isChecked():
            try:
                self.T.h5 = h5py.File(self.ImportWindow.ImpFilePath.text())
                keys = returnKeys(self.T.h5)
            except:
                notes = 'Read HDF5 file error'
                err = -1

            if err != -1:
                # enable subimage dropdown
                self.ImportWindow.ImpSubImg.setEnabled(True)
                
                # Select sub-image with the 1st largest dimension; unless manually selected
                if self.sender() is not self.ImportWindow.ImpSubImg:
                    # List all images' names in `self.ImportWindow.ImpSubImg`
                    self.ImportWindow.ImpSubImg.blockSignals(True)
                    pdim = [self.T.h5[key].size for key in keys]
                    self.ImportWindow.ImpSubImg.clear()
                    self.ImportWindow.ImpSubImg.addItems(keys)
                    self.ImportWindow.ImpSubImg.blockSignals(False)
                    self.ImportWindow.ImpSubImg.setCurrentIndex(np.argmax(pdim))

                # Info of selected sub-image
                h5i = self.T.h5[keys[self.ImportWindow.ImpSubImg.currentIndex()]]

                # Read dimensions, 
                dims = h5i.shape
                if len(dims)<4: np.append(dims,np.ones(4-len(dims),dtype=int))
                self.ImportWindow.DNPxX.setValue(dims[3])
                self.ImportWindow.DNPxY.setValue(dims[2])
                self.ImportWindow.DNFrX.setValue(dims[1])
                self.ImportWindow.DNFrY.setValue(dims[0])
                
                # Find offset, file tail, data type, byte-order of dataset
                offset = int(h5i.id.get_offset())
                if offset == -1:
                    self.ImportWindow.DataOffset.setValue(0)
                    noteoffs = 'This dataset is not "contiguous", thus data offset is unknown.'
                else:
                    self.ImportWindow.DataOffset.setValue(offset)
                    noteoffs = "Selected dataset's offset is {} bytes.".format(offset)
                
                self.T.fileTail = self.T.FileSize - self.ImportWindow.DataOffset.value() - h5i.size

                # set datatype; strip < or > if included as these represent big/little endian
                self.ImportWindow.ImpDataType.setCurrentIndex(self.ImportWindow.ImpDataType.findData(re.sub('<|>',"",h5i.dtype.str)))
                
                if ">" in h5i.dtype.str:
                    self.ImportWindow.ImpByteOrder.setCurrentIndex(1)
                    bo = 'Big Endian'
                else:
                    self.ImportWindow.ImpByteOrder.setCurrentIndex(0)
                    bo = 'Little Endian'

                notes = "Dim: X = {:d}, Y = {:d}, Z = {:d}, W = {:d}\n{:s}, {:s}\n{:s}".format(*dims, bo, str(h5i.dtype), noteoffs)
                if dims[3] == 1:
                    guessFramesFromDimZ(dims[2])
        else:
            getDimFromName(self.ImportWindow.ImpFilePath.text())
            self.ImportWindow.ImpDataType.setCurrentIndex(self.ImportWindow.ImpDataType.findData("f4")) #32-bit float
            notes = "Custom import"
    else:
        notes = "File path is invalid"
        err = -1
    
    self.ImportWindow.ImpFileMetaNotes.setText(notes)
    if self.ImportWindow.ImpDataType.currentIndex() == 0 and  err != -1:
        _ = notifDLG(self,self.ImportWindow,"warn","The data type indicated in the file's metadata is not supported/recognized.","Invalid Data Type!")

    # Reset import range selections
    rangeImportExport(self, self.ImportWindow.DNPxX)
    rangeImportExport(self, self.ImportWindow.DNFrX)

    # generate placeholder images #TODO #DELETE?
    #self.Fig.Preview.Image = np.zeros(self.D.NPx)
    #self.Fig.Dfrn.Image = np.zeros(self.D.NPx)
    #self.Fig.Dfrn.Real = np.zeros(self.D.NFr)

    importBoxInput(self)

def importBoxInput(self):
    
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
        # est_mem = np.prod([nPx,nFr]) \                                        # self.Data
        #         + nFr.prod()*(2*np.floor(np.linalg.norm(nPx/2))+1) \          # self.adfImages
        #         + 10*nFr.prod() + 2*nPx.prod()  \                             # self.Fig[id].Image
        #         + 10*nPx.prod()                                               # self.Mask
        est_mem = np.prod([nPx,nFr]) \
                + nFr.prod()*(2*np.floor(np.linalg.norm(nPx/2))+1) \
                + 10*nFr.prod() + 2*nPx.prod() \
                + 10*nPx.prod()
        self.T.EstMem = est_mem*byte_size

        notes = "Estimated memory usage: {:.3f} GiB.".format(self.T.EstMem/(1024**3))
        
        # warn if the dataset will not fit in memory
        if self.T.EstMem > self.C.MemTot:
            msg = "WARNING: Size of dataset is larger than the system memory!"
            _ = notifDLG(self,self.ImportWindow,"warn",msg,"Size Exceeds System Memory!")
            notes += "\n"+msg
        
        notes += "\nSystem byte order: " + self.C.EndianTxt[self.C.SysEndian] + "."

        return notes

    def checkGPUMEM(nPx,nFr):
        igpu = self.ImportWindow.ImpGPU.currentData()
        if igpu == None:
            gpu_note = 'GPU disabled.'
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
                wt = None
                # TODO - this seems really arbitrary
                if self.T.EstMem > amem - 128*1024**2: # Has 128 MiB extra?
                    gpu_note = tgpu + " has NOT enough free memory ("+amem_t+"). 128 MiB EXTRA free memory is also required."
                    wt = 'GPU Not Enough Free Memory!'
                    self.ImportWindow.ImpGPU.setCurrentIndex(self.ImportWindow.ImpGPU.findData(None))
                
                elif self.T.EstMem > (amem - 512*1024**2): # Has 512 MiB extra?
                    gpu_note = tgpu + " has LIMITED free memory ("+amem_t+") and may cause errors."
                    wt = 'GPU Limited Free Memory!'
                
                else:
                    gpu_note = tgpu + " has enough free memory ("+amem_t+") for the selected dataset."
                
                # Notify warnings if any
                if wt:
                    _ = notifDLG(self,self.ImportWindow,"warn",gpu_note,wt)
            except:
                gpu_note = "Failed to select "+tgpu+"!"
                _ = notifDLG(self,self.ImportWindow,"warn",gpu_note,"Error Selecting GPU")
                self.ImportWindow.ImpGPU.setCurrentIndex(self.ImportWindow.ImpGPU.findData(None))

        return gpu_note

    # bypass execution if signals are actively being blocked (i.e. for programmatically updating UI values)
    if self.blockAllSignals:
        return
            
    self.ImportWindow.ImpEstFilesize.clear()       # clear estimated file size
    notes = None                                   # initialize notes in case file is not on path
    dfrn_src = real_src = self.sender()            # capture UI component that triggered this callback

    if os.path.isfile(self.ImportWindow.ImpFilePath.text()):

        # Update Diffraction and Real-space import ranges; use default source if self.sender() is not a range UI component
        if (not hasattr(self.sender(),'accessibleDescription')) or (not "Dfrn" in self.sender().accessibleDescription()):
            dfrn_src = self.ImportWindow.IPxD
        if (not hasattr(self.sender(),'accessibleDescription')) or (not "Real" in self.sender().accessibleDescription()):
            real_src = self.ImportWindow.IFrD
    
        dnote,_,_,nPx,_ = rangeImportExport(self, dfrn_src)
        rnote,_,_,nFr,_ = rangeImportExport(self, real_src)
        
        notes = dnote+rnote

        # Enable/Disable Range UIs
        self.ImportWindow.ImpPxPart.setEnabled(True)
        self.ImportWindow.ImpFrPart.setEnabled(True)
        
        # Current dataset dimensions
        irng = [nPx,nFr]

        # Allow for virtual memory mapping in some situations
        if self.ImportWindow.FrHead.value() == 0 and self.ImportWindow.FrFoot.value() == 0 \
                and (not self.ImportWindow.HDF5Button.isChecked() or self.ImportWindow.DataOffset.value()>0) \
                and (self.ImportWindow.ImpByteOrder.currentData() == self.C.SysEndian) \
                and (not 'int' in self.ImportWindow.ImpDataType.currentData()) \
                and [self.ImportWindow.DNPxX.value(), self.ImportWindow.DNPxY.value(), self.ImportWindow.DNFrX.value(), self.ImportWindow.DNFrY.value()]==irng:
            self.ImportWindow.ImpMemType.setEnabled(True)
        else:
            self.ImportWindow.ImpMemType.setEnabled(False)
            self.ImportWindow.ImpMemType.setCurrentIndex(0) #Physical Memory
        
        # Calculate dataset size and memory usage
        if self.ImportWindow.ImpDataType.currentData() != "unknown":
            byte_size = self.ByteSize[self.ImportWindow.ImpDataType.currentData()]
            self.T.EstSize = self.ImportWindow.DataOffset.value() + self.T.fileTail \
                            + (self.ImportWindow.FrHead.value()+self.ImportWindow.DNPxX.value()*self.ImportWindow.DNPxY.value()*byte_size+self.ImportWindow.FrFoot.value()) \
                            * self.ImportWindow.DNFrX.value()*self.ImportWindow.DNFrY.value()
            self.ImportWindow.ImpEstFilesize.setText("{} bytes, {:.2f} GiB".format(self.T.EstSize,self.T.EstSize/1024**3))

            if np.issubdtype(self.ImportWindow.ImpDataType.currentData(),np.integer):
                if byte_size > 4:
                    f = 'f8'
                else:
                    f = 'f4'
                byte_size = self.ByteSize[f]
                notes += "\nDataset will be converted into "+str(byte_size*8)+"-bit Real."
            
            notes += "\nImport by "+self.ImportWindow.ImpMemType.currentText()+"\n"+checkMem(nPx,nFr,byte_size)+"\n\n"
            notes += checkGPUMEM(nPx,nFr)
        
        # Allow to swap dataset/keep parameters if the dimensions are identical and self.D is not None
        #self.ImportWindow.ImpKeepP.Enable = ~isempty(self.D) and isequal(irng, [self.D.NPxX self.D.NPxY self.D.NFrX self.D.NFrY])
        self.ImportWindow.ImpKeepP.setEnabled((self.D != None) and (irng == [self.D.NPxX, self.D.NPxY, self.D.NFrX, self.D.NFrY]))
        if self.ImportWindow.ImpKeepP.isEnabled() == False:
            self.ImportWindow.ImpKeepP.setChecked(False)
        if self.ImportWindow.ImpKeepP.isChecked()==True:
            notes += "\n\nSwapping dataset - keeping current setups/alignments etc."
    
    # update notes in the text field
    self.ImportWindow.ImpNotes.setText(notes)

def saveCallbacks(self):
    pass

def exportCallbacks(self):
    pass

def axeDirCallbacks(self):
    pass

def realSpaceROICallbacks(self):
    pass

def clearDetectors(self):

        detectorList = [
            "adf",
            "tb"]

        # Try removing annotations and then setting to None so that they can be replotted later
        for ii in detectorList:
            if getattr(self.A,ii) is not None:
                try:
                    getattr(self.A,ii).remove()
                except:
                    pass
                finally:
                    setattr(self.A,ii,None)

        # Custom detectors
        # Hide Custom ROIs only
        #set(findobj(self.ImageAx.Dfrn.Children,'-regexp','Tag',"Custom "),'Visible',0) #TODO
        # Scan direction alignment
        #delete(findobj(self.ImageAx.Dfrn,'Tag','ScanDirAnnot')) #TODO

def detectorModeCallbacks(self):
    # bypass execution if signals are actively being blocked (i.e. for programmatically updating UI values)
    if self.blockAllSignals:
        return
    
    dmod = self.DetrMode.currentData()

    enableWindows(self,False) # Disable all on change windows
    clearDetectors(self) # Clear ROIs on Diffraction

    # Clear Real-space images if not switching to alignment or preview
    if dmod not in ["AlignMod","PrvwMod"]:
        for ii in self.G.RealID:
            if not "Mask" in ii:
                #self.Fig[ii].ax.cla()
                self.Fig[ii].canvas.draw_idle()

    # Enable/Disable CoM/DPC related buttons/images
    for btn in self.G.CoM_btns:
        btn.setEnabled(dmod in ["CoMMod","DPCMod"]) 

    # block singals whilst updating DispImage QComboBox
    self.SettingsWindow.DispImage.blockSignals(True)

    if dmod in ["CoMMod","DPCMod"]:
        # add all images to dropdown list in the Settings Window and
        # Subsitute "CoM"/"DPC" in image names and window titles
        imageNames = [re.sub('DPC|CoM',dmod[:3],ii) for ii in self.G.ImgName]

        self.SettingsWindow.DispImage.clear()
        for itemText,itemID in zip(imageNames,self.G.ImgID):
            self.SettingsWindow.DispImage.addItem(itemText,itemID) # drop down items
            self.Fig[itemID].setWindowTitle(itemText) # window title
        
        # Subsitute "CoM"/"DPC" in button text
        for btn in self.G.CoM_btns:
            re.sub('DPC|CoM',dmod[:3],btn.text())
        
    else:
        self.SettingsWindow.DispImage.clear()
        for itemText,itemID,itemType in zip(self.G.ImgName,self.G.ImgID,self.G.ImgType):
            if "CoM" not in itemType:
                self.SettingsWindow.DispImage.addItem(itemText,itemID) # drop down items
            else:
                self.Fig[itemID].hide() # Image windows


    # Show primary diffraction/real-space image when mode changes unless in Preview mode
    if dmod != "PrvwMod":
        self.Fig.Dfrn.show()
        self.Fig.Real.show()
    else:
        self.Fig.Dfrn.hide()
        self.Fig.Real.hide()

    # Special case for Import Preview Mode
    if dmod == "PrvwMod":
        # Keep only "Preview" image
        self.SettingsWindow.DispImage.clear()
        self.SettingsWindow.DispImage.addItem("Preview","Preview")

        # Hide other UIs
        self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.MiscTab),False)
        self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.InfoTab),False)
        self.SaveWindow.SaveTabGroup.setTabVisible(self.SaveWindow.SaveTabGroup.indexOf(self.SaveWindow.ExportTab),False)
        
        self.Fig.Preview.show()
        self.ImportWindow.show()
        self.SettingsWindow.show()
    else:
        self.P.DetrMode = self.DetrMode.currentData() # Note current mode
        # Remove "Preview" image from drop down
        self.SettingsWindow.DispImage.removeItem(self.SettingsWindow.DispImage.findData("Preview"))
        self.Fig.Preview.hide()

        # Show all UIs
        self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.MiscTab),True)
        self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.InfoTab),True)
        self.SaveWindow.SaveTabGroup.setTabVisible(self.SaveWindow.SaveTabGroup.indexOf(self.SaveWindow.ExportTab),True)

    # unblock singals after updating DispImage QComboBox
    self.SettingsWindow.DispImage.blockSignals(False)

    # Define images in the saving list
    self.SaveWindow.SaveImgList.blockSignals(True)
    self.SaveWindow.SaveImgList.clear()
    self.SaveWindow.SaveImgList.addItems([self.SettingsWindow.DispImage.itemData(ii) for ii in range(self.SettingsWindow.DispImage.count())])
    self.SaveWindow.SaveImgList.blockSignals(False)
    self.SaveWindow.SaveImgPrefix.textChanged.emit(self.SaveWindow.SaveImgPrefix.text()) # Update Image saving prefix
    self.SettingsWindow.ShowDfrnAxes.clicked.emit() # Update diffraction axis annotations
    

    # Set detector size when transmitted beam is aligned the first time
    if not(self.P.TransBeamInit) and (dmod != "AlignMod"):
        self.AnnRi.blockSignals(True)
        self.AnnRi.setValue((self.TBR.value(),(self.TBR.value() + self.P.RMax)/3))
        self.AnnRi.blockSignals(False)
        self.VrApR.setValue(self.TBR.value())
        self.P.VrApXY = self.B0
        self.P.TransBeamInit = 1

    # hide custom mask maths tab
    self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.MathTab),False)

    match dmod:
        case "PrvwMod":
            self.DfrnDetrTabGroup.setCurrentIndex(0)
            previewCallbacks(self)
        case "AlignMod":
            # display the full dataset pacbed
            self.Fig.Dfrn.Image = self.Data.sum(axis=0).reshape(self.D.NPx)
            self.ImageAx.Dfrn = self.Fig.Dfrn.ax.imshow(self.Fig.Dfrn.Image,cmap=self.Fig.Dfrn.cmap)
            self.ImageAx.Dfrn.figure.set_facecolor('black')
            self.Fig.Dfrn.show()
            self.Fig.Dfrn.ax.axis(self.P.DfrnAxLim)
            self.Fig.Dfrn.canvas.draw_idle()

            # initialize real space image with sum over all diffraction space
            self.Fig.Real.Image = self.Data.sum(axis=1).reshape(self.D.NFrY,self.D.NFrX)
            self.ImageAx.Real = self.Fig.Real.ax.imshow(self.Fig.Real.Image,cmap=self.Fig.Real.cmap)
            self.ImageAx.Real.figure.set_facecolor('black')
            self.Fig.Real.show()
            self.Fig.Real.ax.axis(self.P.RealAxLim)
            self.Fig.Real.canvas.draw_idle()

            # initial masking for diffraction space should be all ones
            self.Fig.DfrnMask.Image = np.ones(self.D.NPx)
            self.ImageAx.DfrnMask = self.Fig.DfrnMask.ax.imshow(self.Fig.DfrnMask.Image,cmap=self.Fig.DfrnMask.cmap)
            self.ImageAx.DfrnMask.figure.set_facecolor('black')
            self.Fig.DfrnMask.ax.axis(self.P.DfrnAxLim)
            self.Fig.DfrnMask.canvas.draw_idle()
            
            # initial masking for real space should be all ones
            self.Fig.RealMask.Image = np.ones(self.D.NFr)
            self.ImageAx.RealMask = self.Fig.RealMask.ax.imshow(self.Fig.RealMask.Image,cmap=self.Fig.RealMask.cmap)
            self.ImageAx.RealMask.figure.set_facecolor('black')
            self.Fig.RealMask.ax.axis(self.P.RealAxLim)
            self.Fig.RealMask.canvas.draw_idle()

            # Create transmitted beam annotation, allow for disk as large as the entire diffraction pattern
            if self.A.tb is None:
                self.A.tb = InteractiveCircle(center = self.B0, radius = self.TBR.value(), axis=self.Fig.Dfrn.ax, color="r", interactions="all")
                self.A.tb.connect()
                self.A.tb.updateCircle.connect(lambda: moveTransBeam(self))
                self.Fig.Dfrn.canvas.flush_events()
            
            self.DfrnDetrTabGroup.setCurrentIndex(1)
            transBeamCallbacks(self)
            
        case "AnnMod":
            self.DfrnDetrTabGroup.setCurrentIndex(2)
            self.dpcControls.setVisible(False)
            self.comControls.setVisible(False)
            annularDetectorCallbacks(self) #TODO
        case "CoMMod"|"DPCMod":
            self.DfrnDetrTabGroup.setCurrentIndex(2)
            self.dpcControls.setVisible("DPC" in dmod)
            self.comControls.setVisible(True)
            annularDetectorCallbacks(self) #TODO
            plotImage(self, 'ColorWheel') # Plot ColorWheel #TODO
            self.Fig.CoMPhMag.activateWindow()
            self.Fig.ColorWheel.activateWindow()
            if not self.P.ScanDirInit:
                pass#flashBackground(self, self.ScanDirGrid) # Flashing to align scan direction #TODO
        case "VrApMod": # 'Virtual Aperture'
            self.DfrnDetrTabGroup.setCurrentIndex(3)
            virtualApertureCallbacks(self)
        case "CustMod":
            self.DfrnDetrTabGroup.setCurrentIndex(4)
            self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.MathTab),True)
            #customDetectorCallbacks(self) #TODO
            self.Fig.DfrnMask.activateWindow()
    
    enableWindows(self,True)

def datasetOptCallbacks(self):
    match self.sender():
        case self.SettingsWindow.SwapByteOrder: # Swap byte-order
            #msg = "Swapping byte order ..." #TODO
            #self.T.progDLG = progDLG(self, sprintf("\n#s\n",msg), "Byte Order Swap") #TODO
            self.progressBar.setMaximum(0)
            try:
                self.Data.byteswap(inplace=True)
            except:
                notifDLG(self,self,'error',"It seems the system does not have enough memory for this process! Maybe try to increase system's virtual memory.", "Out of Memory")
                return

            self.D.ByteOrder = ['b','l'][self.D.ByteOrder=='b'] # swap `l`<->`b` at `self.D.ByteOrder`
            self.SettingsWindow.DataInfo.setPlainText(getImportInfo(self))
            self.UpdateImages.tirgger()
            #delete(self.T.progDLG) #TODO
            self.progressBar.setValue(1)
            self.progressBar.setMaximum(1)
            sel = notifDLG(self,self,'quest',"Does the current byte-order look correct?",'Byte Order Swap',["Yes","No. Revert"])
            
            # Run the process again if selected "No ....."
            if sel.startswith("No"):
               self.SettingsWindow.SwapByteOrder.click()#datasetOptCallbacks(self,struct('Source',self.SwapByteOrder,'EventName',"")) #TODO?

        case self.SettingsWindow.SwapDfrnXY|self.SettingsWindow.SwapRealXY:
            # Diffraction or real-space
            if self.sender() == self.SettingsWindow.SwapDfrnXY:
                # Swap diffraction X/Y dimensions
                self.D.swapDiff()
                #self.D.DNPxX,self.D.DNPxY = self.D.DNPxY,self.D.DNPxX
                #self.D.NPxX,self.D.NPxY = self.D.NPxY,self.D.NPxX
                #self.D.PxX1,self.D.PxY1 = self.D.PxY1,self.D.PxX1
                #self.D.NPx = np.flip(self.D.NPx)

            else:
                # Delete all Real-space ROIs;  
                self.A.removeGroup("ROI")
                self.P.TransBeamInit = 1

                # Swap real X/Y dimensions
                self.D.swapReal()
                #self.D.DNFrX,self.D.DNFrY = self.D.DNFrY,self.D.DNFrX
                #self.D.NFrX,self.D.NFrY = self.D.NFrY,self.D.NFrX
                #self.D.FrX1,self.D.FrY1 = self.D.FrY1,self.D.FrX1
                #self.D.NFr = np.flip(self.D.NFr)
            
            # Re-prepare the imported data
            importCallbacks(self)
        
            self.SettingsWindow.DataInfo.setPlainText(getImportInfo(self))
          
        case self.PreviewButton:
            sel = checkNaN(self, image=self.Fig.Preview.Image, preview=True) # Check data NaN/Inf, without asking to sway byte-order
            if sel == 'Set NaNs to 0':
                self.Data[np.ma.masked_invalid(self.Data).mask]=0

        case other:
            self.SettingsWindow.DataInfo.setPlainText(getImportInfo(self))
            # Check data NaN/Inf, ask whether to sway byte-order
            sel = checkNaN(self, image=self.Fig.Dfrn.Image, preview=False)
            if sel == 'Set NaNs to 0':
                self.Data[np.ma.masked_invalid(self.Data).mask]=0

def getImportInfo(self):
    """ Function to update current data info """
    d = self.D
    d0 = self.T.prev_D
    notes = "File: "+d.filePath
    if d.subImg != '':
        notes += "\nSub-dataset: "+d.subImg

    notes += "\n\n# Current Data Info #" +\
            "\nByte Order: "+self.C.EndianTxt[d.ByteOrder]+"\nData Type: "+np.dtype(d.DataType).name+"\nByte Size: "+str(d.ByteSize)+" bytes" +\
            "\n{:s} (X\u2A2FY): {:d}\u2A2F{:d}".format("Diffraction",*d.NPx) +\
            "\n{:s} (X\u2A2FY): {:d}\u2A2F{:d}".format("Real-space",*d.NFr) +\
            "\n\n# Data Structure in File #" +\
            "\nData Offset: "+str(d0.Offset)+" bytes\nFrame Header: "+str(d0.FrHead)+" bytes\nFrame Footer: "+str(d0.FrFoot)+" bytes" +\
            "\nByte Order: "+self.C.EndianTxt[d0.ByteOrder]+"\nData Type: "+np.dtype(d0.DataType).name+"\nByte Size: "+str(d0.ByteSize)+" bytes" +\
            "\n\n# File Meta Info Notes #\n"+d0.NoteFileMeta+'\n' +\
            "\n\n# Import Option Notes #\n"+d0.NoteImp+'\n'
    
    return notes

def transBeamCallbacks(self):
    match self.sender():
        case self.DetrMode: # Entering mode
            # Create transmitted beam annotation, allow for disk as large as the entire diffraction pattern
            if self.A.tb is None:
                self.A.tb = InteractiveCircle(center = self.B0, radius = self.TBR.value(), axis=self.Fig.Dfrn.ax, color="r", interactions="all")
                self.A.tb.connect()
                self.A.tb.updateCircle.connect(lambda: moveTransBeam(self))
                self.Fig.Dfrn.canvas.draw_idle()
                self.Fig.Dfrn.canvas.flush_events()
            
            # Select `Dfrn` image and bring window to the front
            self.SettingsWindow.DispImage.setCurrentIndex(self.SettingsWindow.DispImage.findData("Dfrn"))
            self.Fig.Dfrn.activateWindow()

            # If this is the initializing alignment, then do swap byte check and auto-align
            if not self.P.TransBeamInit:
                datasetOptCallbacks(self) # checks for nans and asks if user wants to swap byteorder
                autoAlign(self)

            enableWindows(self,True) # Enable windows

        case self.UpdateImages: # Update images
            # Create a summed image of all diffraction patterns simply for alignment and calibration
            self.Fig.DfrnMask.Image = np.ones(self.D.NPx,self.D.DataType)
            self.Fig.Real.Image = np.reshape(self.Data.sum(axis=1), self.D.NFr)

        case self.TBAutoAlign: # Auto-align
            autoAlign(self)

        case self.TBCrossAlign: # Align transmitted beam via two crossed lines
            crossAlign(self)
        
    # Update dependent variables
    moveTransBeam(self)

def moveTransBeam(self):
    """ Function to sync UIs/ROIs depending on the central beam location """

    # bypass execution if signals are actively being blocked (i.e. for programmatically updating UI values)
    if self.blockAllSignals:
        return
    
    b0 = np.array([self.TBX.value(),self.TBY.value()])
    r = np.maximum(self.TBR.value(),np.finfo(np.single).eps)
    a = self.Alpha.value()
    mrad_per_px = a/r
    nPix = self.D.NPx

    match self.sender():
        case self.TBX|self.TBX_NF:
            b0[0] = max(1, self.sender().value()); # Force X >= 1
        case self.TBY|self.TBY_NF:
            b0[1] = max(1, self.sender().value()); # Force Y >= 1
        case self.TBR|self.TBR_NF:
            r = self.sender().value(); # Radius
        case self.Alpha:
            a = self.sender().value()
            mrad_per_px = a/r # Calculate the diffraction scale
        case self.mradPx:
            mrad_per_px = self.sender().value()
            a = mrad_per_px*r # Manually set the diffraction scale
        case self.A.tb:
            b0 = self.A.tb.center
            r = self.A.tb.radius

    # Restrict transmitted beam location/size
    b0 = b0.clip([1,1],nPix)
    self.B0 = b0
    self.P.RMax = np.ceil(np.linalg.norm(abs(self.P.DfCtr-b0)+self.P.DfCtr)) # Find the max allowed radius
    r = np.clip(r,np.finfo(np.single).eps,self.P.RMax) # 0 < r <= RMax

    # avoid triggering a valueChanged loop by blocking signals
    self.blockAllSignals = True

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
    
    # Update transmitted beam annotation
    if (self.sender() is not self.A.tb) and (self.A.tb is not None):
        self.A.tb.center = b0
        self.A.tb.radius = np.array([r])
        self.A.tb.redraw()

    # unblock trigger signals
    self.blockAllSignals = False

    detrCoordCallbacks(self)


def virtualApertureCallbacks(self):
    """Delegate to the full implementation in virtualApertureCallbacks.py."""
    _virtualApertureCallbacks(self)

def autoAlign(self):
    """
    Auto-detect the transmitted beam centre (and radius) using the
    Circular Hough Transform (imfindcircles.py).

    Input pattern
    -------------
    * No real-space ROI active (RealROIShape == 'full'):
        PACBED = sum of ALL probe positions.
    * Real-space ROI active:
        Weighted average over the probe positions selected by the ROI
        (uses self.Fig.RealMask.Image as weights), so e.g. a single
        point ROI gives the pattern of exactly that probe position.

    In either case ``self.Fig.Dfrn.Image`` already holds the correct
    pattern (it is updated whenever the ROI changes), so we read it
    directly rather than re-computing the sum.
    """
    from callbacks.imfindcircles import imfindcircles

    nPx      = self.D.NPx           # (height, width) tuple
    rmax_abs = max(1, self.P.RMax)

    # ── Choose the input pattern ──────────────────────────────────────────
    roi_shape = self.RealROIShape.currentData()   # 'full', 'point', …

    if roi_shape == 'full' or self.Fig.Dfrn.Image is None:
        # Full PACBED: sum every probe position
        pacbed = np.nansum(self.Data, axis=0).reshape(nPx).astype(np.float64)
    else:
        # ROI-weighted average: already computed and stored in Fig.Dfrn.Image
        # (shape = nPx, normalised by the number of included probe positions)
        pacbed = np.asarray(self.Fig.Dfrn.Image, dtype=np.float64).reshape(nPx)

    # ── Radius search range ───────────────────────────────────────────────
    tbr = self.TBR.value()
    if tbr > 1:
        # Use ±50 % of the current beam-disc radius, clamped to sensible values
        rmin = max(1,          int(np.floor(0.5  * tbr)))
        rmax = min(rmax_abs,   int(np.ceil( 1.5  * tbr)))
    else:
        # First-time call: search over the central quarter of the pattern
        rmin = 1
        rmax = max(2, int(np.ceil(min(nPx) / 4)))

    if rmax <= rmin:
        rmax = rmin + 1

    # ── Run circle finder ─────────────────────────────────────────────────
    try:
        centers, radii, metric = imfindcircles(
            pacbed, [rmin, rmax],
            ObjectPolarity='bright',
            Method='PhaseCode',
            Sensitivity=0.85,
        )
    except Exception:
        # PhaseCode requires rmax > rmin; fall back to TwoStage if needed
        try:
            centers, radii, metric = imfindcircles(
                pacbed, [rmin, rmax],
                ObjectPolarity='bright',
                Method='TwoStage',
                Sensitivity=0.85,
            )
        except Exception:
            return   # give up gracefully — leave B0/TBR unchanged

    if len(centers) == 0:
        return  # no circle found — leave B0 unchanged

    # Best match: imfindcircles already sorts by descending metric
    cx, cy = float(centers[0, 0]), float(centers[0, 1])
    r      = float(radii[0])

    # Clamp to valid pixel range
    cx = np.clip(cx, 1, nPx[1])
    cy = np.clip(cy, 1, nPx[0])
    r  = np.clip(r,  np.finfo(np.single).eps, rmax_abs)

    self.blockAllSignals = True
    self.TBX.setValue(cx);    self.TBX_NF.setValue(cx)
    self.TBY.setValue(cy);    self.TBY_NF.setValue(cy)
    self.TBR.setValue(r);     self.TBR_NF.setValue(r)
    self.blockAllSignals = False

    moveTransBeam(self)


def crossAlign(self):
    """
    Manual beam-centre alignment via an interactive cross-hair cursor.

    Draws two draggable lines (H + V) on the diffraction window that
    follow the mouse.  A single left-click fixes the intersection as the
    new B0 (TBX, TBY) and removes the cursor.

    A second call to crossAlign (e.g. user presses the button again)
    while a cursor is already active will remove it without updating B0.
    """
    canvas = self.Fig.Dfrn.canvas
    ax     = self.Fig.Dfrn.ax

    # ── toggle off if already active ────────────────────────────────────
    if hasattr(self, '_crossAlignState') and self._crossAlignState is not None:
        _state = self._crossAlignState
        for cid in _state['cids']:
            canvas.mpl_disconnect(cid)
        for line in _state['lines']:
            try:
                line.remove()
            except Exception:
                pass
        canvas.draw_idle()
        self._crossAlignState = None
        return

    # ── create crosshair lines ───────────────────────────────────────────
    xl = ax.get_xlim()
    yl = ax.get_ylim()
    b0 = self.B0

    h_line = ax.axhline(b0[1], color='yellow', linewidth=1,
                         linestyle='--', alpha=0.8, zorder=10)
    v_line = ax.axvline(b0[0], color='yellow', linewidth=1,
                         linestyle='--', alpha=0.8, zorder=10)
    canvas.draw_idle()

    def _on_move(event):
        if event.inaxes is not ax or event.xdata is None:
            return
        h_line.set_ydata([event.ydata, event.ydata])
        v_line.set_xdata([event.xdata, event.xdata])
        canvas.draw_idle()

    def _on_click(event):
        if event.inaxes is not ax or event.xdata is None:
            return
        if event.button != 1:   # left-click only
            return

        new_x = float(np.clip(event.xdata, 1, self.D.NPx[1]))
        new_y = float(np.clip(event.ydata, 1, self.D.NPx[0]))

        self.blockAllSignals = True
        self.TBX.setValue(new_x)
        self.TBX_NF.setValue(new_x)
        self.TBY.setValue(new_y)
        self.TBY_NF.setValue(new_y)
        self.blockAllSignals = False

        # Tear down the crosshair
        crossAlign(self)   # second call → removes state
        moveTransBeam(self)

    cids = [
        canvas.mpl_connect('motion_notify_event', _on_move),
        canvas.mpl_connect('button_press_event',  _on_click),
    ]

    self._crossAlignState = {
        'cids':  cids,
        'lines': [h_line, v_line],
    }


def customDetectorCallbacks(self):
    pass

def mathCallbacks(self):
    """
    Evaluate the formula in MathFormula (CustMod).

    Supported variables (case-sensitive):
        A   – current Real image (self.Fig.Real.Image)
        B   – current DfrnMask image (self.Fig.DfrnMask.Image)
        C   – diffraction preview (self.Fig.Dfrn.Image if set)
        D   – CoM magnitude (self.Fig.CoMX / CoMY combined, if available)

    Supported Python / numpy operators:
        +  -  *  /  **  @  &  |  ~  .T  np.xxx(...)

    MATLAB shorthands translated before evaluation:
        .^  →  **      element-wise power
        .*  →  *       element-wise multiply (arrays multiply element-wise in numpy anyway)
        .'  →  .T      element-wise transpose
        end →  -1      (simple end-of-array alias)
        ^   →  **      (scalar power fall-through)

    The result is stored in self.Fig.Real.Image and plotted.
    """
    formula = self.SettingsWindow.MathFormula.toPlainText().strip()
    if not formula:
        return

    # ── Translate MATLAB shorthands → Python/numpy ───────────────────────
    formula = formula.replace('.^', '**')   # element-wise power
    formula = formula.replace('.*', '*')    # element-wise multiply
    formula = formula.replace(".'", '.T')   # transpose
    formula = formula.replace('end', '-1')  # end-of-array index
    # bare ^ that wasn't already converted (scalar context)
    formula = re.sub(r'(?<!\*)\^', '**', formula)

    # ── Build evaluation namespace ────────────────────────────────────────
    def _safe_img(img):
        return np.ma.masked_invalid(img).astype(np.float64) if img is not None else None

    ns = {
        'np'  : np,
        'A'   : _safe_img(self.Fig.Real.Image),
        'B'   : _safe_img(self.Fig.DfrnMask.Image),
        'C'   : _safe_img(getattr(self.Fig.Dfrn, 'Image', None)),
        'D'   : _safe_img(getattr(self.Fig, 'CoMMag', None)),
        'abs' : np.abs,
        'sum' : np.nansum,
        'mean': np.nanmean,
        'max' : np.nanmax,
        'min' : np.nanmin,
        'sqrt': np.sqrt,
        'log' : np.log,
        'log2': np.log2,
        'exp' : np.exp,
        'fft' : np.fft.fft2,
        'ifft': np.fft.ifft2,
    }

    # ── Evaluate ─────────────────────────────────────────────────────────
    try:
        result = eval(formula, {"__builtins__": {}}, ns)  # restrict builtins
        result = np.array(result, dtype=np.float64)
    except Exception as exc:
        qtw.QMessageBox.warning(
            self, "Math formula error",
            f"Could not evaluate formula:\n{formula}\n\nError: {exc}"
        )
        return

    # ── Store and display ─────────────────────────────────────────────────
    self.Fig.Real.Image = result
    plotImage(self, 'Real')

def saveVect(self):
    pass

def resizeWindowCallbacks(self):
    # bypass execution if signals are actively being blocked (i.e. for programmatically updating UI values)
    if self.blockAllSignals:
        return
    
    # set the space: `Dfrn` or `Real`; get updated height and width, add mpl decor size
    if self.sender() in [self.SettingsWindow.WdwWDfrn,self.SettingsWindow.WdwHDfrn,self.SettingsWindow.WdwSetDfrn,self.SettingsWindow.WdwSetAllDfrn]:
        space = "Dfrn"
        width = self.SettingsWindow.WdwWDfrn.value() + self.C.mplDecor.width()
        height = self.SettingsWindow.WdwHDfrn.value() + self.C.mplDecor.height()
    else:
        space = "Real"
        width = self.SettingsWindow.WdwWReal.value() + self.C.mplDecor.width()
        height = self.SettingsWindow.WdwHReal.value() + self.C.mplDecor.height()

    match self.sender():
        case self.SettingsWindow.WdwSetDfrn|self.SettingsWindow.WdwSetReal: # Set size for just one image window
            id = self.SettingsWindow.DispImage.currentData() # Default image window to resize

            # If the selected image is not of that space, then resize that space's primary image window instead
            if self.Fig[id].space != space:
                id = space
            
            # temporarily block slots/signals to avoid recursion
            self.Fig[id].blockSignals(True)
            
            # set the height and wdith
            self.Fig[id].resize(width,height)
            
            # unblock slots/signals
            self.Fig[id].blockSignals(False)
        
        case self.SettingsWindow.WdwSetAllDfrn|self.SettingsWindow.WdwSetAllReal: # Set all image windows of the given space to the same size
            for fig in self.G.ImgFig:
                if fig.space == space:
                    fig.blockSignals(True)
                    fig.resize(width,height)
                    fig.blockSignals(False)

def updateImagesCallbacks(self):
    match self.sender():
        case self.SettingsWindow.CalcPolicy:
            # Update once if not passive
            if self.SettingsWindow.CalcPolicy.curentData():
                self.UpdateImages.trigger()

        case self.UpdateImages: # Calculate and update all images
            # Trigger detector callbacks 
            match self.DetrMode.currentData():
                case "PrvwMod":
                    previewCallbacks(self)
                case "AlignMod":
                    transBeamCallbacks(self)
                case 'AnnMod'|'CoMMod'|'DPCMod':
                    annularDetectorCallbacks(self)
                case "VrApMod":
                    virtualApertureCallbacks(self)
                case "CustMod":
                    customDetectorCallbacks(self)
          
            # Trigger real-space ROI callbacks
            if self.DetrMode.currentData() != "PrvwMod":
                realSpaceROICallbacks(self)

def unlockScanDir(self):
    # bypass execution if signals are actively being blocked (i.e. for programmatically updating UI values)
    if self.blockAllSignals:
        return
    
    if self.ScanDirUnlock.isChecked():
        self.ScanDirUnlock.setIcon(self.unlock)
    else:
        self.ScanDirUnlock.setIcon(self.lock)

def debugImport(self):
    self.fname = 'C:/Users/bess0001/Documents/dataStorage/research/code/testData/scan_x128_y128.raw'
    if os.path.exists(self.fname):
        self.ImportWindow.ImpFilePath.setText(self.fname)
        self.ShowImportWdw.trigger()
        for widget in self.ImportWindow.children():
            widget.setEnabled(True)
        importSelectFile(self)
        self.ImportWindow.ImportDataButton.click()

def breakpoint(self):
    print()

def slotsSignals(self):
    # debug
    self.enableAllUIs.triggered.connect(lambda:enableWindows(self,True))
    self.debugImport.triggered.connect(lambda:debugImport(self))
    self.breakpoint.triggered.connect(lambda:breakpoint(self))

    # resize window callabcks
    self.SettingsWindow.WdwSetDfrn.clicked.connect(lambda:resizeWindowCallbacks(self))
    self.SettingsWindow.WdwSetAllDfrn.clicked.connect(lambda:resizeWindowCallbacks(self))
    self.SettingsWindow.WdwSetReal.clicked.connect(lambda:resizeWindowCallbacks(self))
    self.SettingsWindow.WdwSetAllReal.clicked.connect(lambda:resizeWindowCallbacks(self))

    # change lock/unlock icon when clicked
    self.ScanDirUnlock.clicked.connect(lambda: unlockScanDir(self))

    # Import window slots/signals
    self.ShowImportWdw.triggered.connect(lambda:importCallbacks(self))
    self.ImportWindow.ImportCancelButton.clicked.connect(lambda:importCallbacks(self))
    self.ImportWindow.xEvent.connect(lambda: self.ShowImportWdw.setChecked(False)) #ImportWindow.ImportCancelButton.click())
    self.ImportWindow.ImpFileSelect.clicked.connect(lambda:importSelectFile(self))
    self.ImportWindow.ImportDataButton.clicked.connect(lambda:importCallbacks(self))
    self.ImportWindow.ImpKeepP.clicked.connect(lambda: importBoxInput(self))
    self.ImportWindow.ImpGPU.currentIndexChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.ImpFrPart.clicked.connect(lambda: importBoxInput(self))
    self.ImportWindow.ImpPxPart.clicked.connect(lambda: importBoxInput(self))
    self.ImportWindow.IFrD.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.IFrY1.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.INFrX.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.IFrX1.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.INFrY.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.IPxD.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.INPxY.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.IPxY1.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.INPxX.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.IPxX1.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.DNFrY.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.DNFrX.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.DNPxY.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.DNPxX.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.ImpByteOrder.currentIndexChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.ImpDataType.currentIndexChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.DataOffset.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.FrFoot.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.FrHead.valueChanged.connect(lambda: importBoxInput(self))
    self.ImportWindow.ImpSubImg.currentIndexChanged.connect(lambda: importFileType(self))

    # save window slots/signals
    self.SaveWindow.SaveImgSelectAll.clicked.connect(lambda isChecked: self.SaveWindow.SaveImgList.selectAll() if isChecked else self.SaveWindow.SaveImgList.clearSelection())

    # menu action slots/signals
    self.actionShow_Diffraction_Pattern.triggered.connect(lambda: self.Fig.Dfrn.show(self.actionShow_Diffraction_Pattern.isChecked()))
    self.actionShow_Diffraction_Mask.triggered.connect(lambda: self.Fig.DfrnMask.show(self.actionShow_Diffraction_Mask.isChecked()))
    self.actionShow_Real_Space_Image.triggered.connect(lambda: self.Fig.Real.show(self.actionShow_Real_Space_Image.isChecked()))
    self.actionShow_Real_Space_Mask.triggered.connect(lambda: self.Fig.RealMask.show(self.actionShow_Real_Space_Mask.isChecked()))
    self.actionShow_Center_of_Mass_Magnitude_CoM.triggered.connect(lambda: self.Fig.CoMMag.show(self.actionShow_Center_of_Mass_Magnitude_CoM.isChecked()))
    self.actionShow_Center_of_Mass_X.triggered.connect(lambda: self.Fig.CoMX.show(self.actionShow_Center_of_Mass_X.isChecked()))
    self.actionShow_Center_of_Mass_Y.triggered.connect(lambda: self.Fig.CoMY.show(self.actionShow_Center_of_Mass_Y.isChecked()))
    self.actionShow_Colorwheel.triggered.connect(lambda: self.Fig.ColorWheel.show(self.actionShow_Colorwheel.isChecked()))
    self.actionShow_Differential_Center_of_Mass_dCoM.triggered.connect(lambda: self.Fig.dCoM.show(self.actionShow_Differential_Center_of_Mass_dCoM.isChecked()))
    self.actionShow_Integrated_Center_of_Mass_iCoM.triggered.connect(lambda: self.Fig.iCoM.show(self.actionShow_Integrated_Center_of_Mass_iCoM.isChecked()))
    self.actionShow_Phase_Magnitude.triggered.connect(lambda: self.Fig.CoMPhMag.show(self.actionShow_Phase_Magnitude.isChecked()))
    self.actionShow_Phase_Vector_Image.triggered.connect(lambda: self.Fig.CoMPh.show(self.actionShow_Phase_Vector_Image.isChecked()))
    self.actionShow_All_Windows.triggered.connect(lambda: showAllWindows(self))
    self.actionHide_All_Windows.triggered.connect(lambda: hideAllWindows(self))
    self.ShowSettingsWdw.triggered.connect(lambda: self.SettingsWindow.show())
    self.ShowSettingsWdw.triggered.connect(lambda: self.SettingsWindow.activateWindow())
    self.ShowSaveWdw.triggered.connect(lambda: self.SaveWindow.show())
    self.ShowSaveWdw.triggered.connect(lambda: self.SaveWindow.activateWindow())

    self.DetrMode.currentIndexChanged.connect(lambda: detectorModeCallbacks(self))

    # dataset options (i.e. swap Rxy, swap Kxy, and swap endianness)
    self.SettingsWindow.SwapDfrnXY.clicked.connect(lambda: datasetOptCallbacks(self))
    self.SettingsWindow.SwapRealXY.clicked.connect(lambda: datasetOptCallbacks(self))
    self.SettingsWindow.SwapByteOrder.clicked.connect(lambda: datasetOptCallbacks(self))

    # show window buttons
    self.SettingsWindow.ShowDfrnWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowRealMaskWdw_2.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowColorWheelWdw_2.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowDfrnMaskWdw_2.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowCoMMagWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowCoMPhWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowCoMPhMagWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowRealWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowCoMXWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowCoMYWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowdCoMWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowiCoMWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowImageWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.SettingsWindow.ShowMaskWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.ShowRealMaskWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.ShowDfrnMaskWdw.clicked.connect(lambda: showWindowCallbacks(self))
    self.ShowColorWheelWdw.clicked.connect(lambda: showWindowCallbacks(self))
    

    # transmitted beam controls
    self.TBX.valueChanged.connect(lambda: moveTransBeam(self))
    self.TBY.valueChanged.connect(lambda: moveTransBeam(self))
    self.TBR.valueChanged.connect(lambda: moveTransBeam(self))
    self.Alpha.valueChanged.connect(lambda: moveTransBeam(self))
    self.mradPx.valueChanged.connect(lambda: moveTransBeam(self))
    self.TBX_NF.valueChanged.connect(lambda: moveTransBeam(self))
    self.TBY_NF.valueChanged.connect(lambda: moveTransBeam(self))
    self.TBR_NF.valueChanged.connect(lambda: moveTransBeam(self))
    self.TBAutoAlign.clicked.connect(lambda: transBeamCallbacks(self))
    self.TBCrossAlign.clicked.connect(lambda: transBeamCallbacks(self))

    # Math formula (CustMod)
    self.SettingsWindow.MathEval.clicked.connect(lambda: mathCallbacks(self))
    
    # preview tab on main UI
    self.PvBL.clicked.connect(lambda: previewCallbacks(self))
    self.PvBC.clicked.connect(lambda: previewCallbacks(self))
    self.PvBR.clicked.connect(lambda: previewCallbacks(self))
    self.PvCL.clicked.connect(lambda: previewCallbacks(self))
    self.PvCC.clicked.connect(lambda: previewCallbacks(self))
    self.PvCR.clicked.connect(lambda: previewCallbacks(self))
    self.PvTL.clicked.connect(lambda: previewCallbacks(self))
    self.PvTC.clicked.connect(lambda: previewCallbacks(self))
    self.PvTR.clicked.connect(lambda: previewCallbacks(self))
    self.PreviewButton.clicked.connect(lambda: previewCallbacks(self))
    self.PvFrX.valueChanged.connect(lambda: previewCallbacks(self))
    self.PvFrY.valueChanged.connect(lambda: previewCallbacks(self))

    # displayCallbacks
    self.UpdateImages.triggered.connect(lambda: updateImagesCallbacks(self))
    self.DispVecColor.triggered.connect(lambda: displayCallbacks(self))
    self.DispVecField.currentIndexChanged.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.DispCMap.currentIndexChanged.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.DispCMapInvert.clicked.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.DispImage.currentIndexChanged.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.DispLock.clicked.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.DispBrightness.valueChanged.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.DispContrast.valueChanged.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.DispGamma.setSingleStep(0.1/3) # scroll step = 3 single steps
    self.SettingsWindow.DispGamma.setValue(1)
    self.SettingsWindow.DispGamma.valueChanged.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.DispGammaReset.triggered.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.DispContrastReset.triggered.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.DispBrightnessReset.triggered.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.DispMaskOpa.valueChanged.connect(lambda: displayCallbacks(self))
    self.SettingsWindow.HistLog.clicked.connect(lambda: displayCallbacks(self))

    # reset values, should not be necessary once connected to displayCallbacks #TODO
    self.SettingsWindow.DispBrightnessReset.clicked.connect(lambda: self.SettingsWindow.DispBrightness.setValue(50))
    self.SettingsWindow.DispContrastReset.clicked.connect(lambda: self.SettingsWindow.DispContrast.setValue(50))
    self.SettingsWindow.DispGammaReset.clicked.connect(lambda: self.SettingsWindow.DispGamma.setValue(1))

    # detector slider/numerical field connections
    self.AnnRi.valueChanged.connect(lambda: annularDetectorCallbacks(self))
    self.AnnRi_NF.valueChanged.connect(lambda: annularDetectorCallbacks(self))
    self.AnnRo_NF.valueChanged.connect(lambda: annularDetectorCallbacks(self))
    self.NSeg.valueChanged.connect(lambda: annularDetectorCallbacks(self))
    self.DetRot_NF.valueChanged.connect(lambda: annularDetectorCallbacks(self))
    self.DetRot.valueChanged.connect(lambda: annularDetectorCallbacks(self))
    self.ScanDirUnlock.clicked.connect(lambda: annularDetectorCallbacks(self))
    self.ScanDirYFlip.clicked.connect(lambda: annularDetectorCallbacks(self))
    self.ScanDir_NF.valueChanged.connect(lambda: annularDetectorCallbacks(self))
    self.ScanDir.valueChanged.connect(lambda: annularDetectorCallbacks(self))

    # virtual aperture connections
    self.VrApR.valueChanged.connect(lambda: virtualApertureCallbacks(self))
    self.VrApSymm.currentIndexChanged.connect(lambda: virtualApertureCallbacks(self))
    self.VrApInvert.clicked.connect(lambda: virtualApertureCallbacks(self))
    self.VrApMirror.clicked.connect(lambda: virtualApertureCallbacks(self))
    self.VrApMirrRot.valueChanged.connect(lambda: virtualApertureCallbacks(self))
    self.VrApMirrRot_NF.valueChanged.connect(lambda: virtualApertureCallbacks(self))

    # Settings window, units choices
    self.SettingsWindow.DCSys.currentIndexChanged.connect(lambda: detrCoordCallbacks(self))
    self.SettingsWindow.DCPos.currentIndexChanged.connect(lambda: detrCoordCallbacks(self))
    self.SettingsWindow.DCUnit.currentIndexChanged.connect(lambda: detrCoordCallbacks(self))
    self.RealROIShape.currentIndexChanged.connect(lambda: realSpaceROICallbacks(self))

    
def toggleWindows(self):
    print(self.sender())
    match self.sender():
        case self.Fig.Dfrn:
            print(999)

def showAllWindows(self):
    for ii in self.Fig:
        self.Fig[ii].show()
    self.actionShow_All_Windows.setChecked(True)
    self.actionHide_All_Windows.setChecked(False)
    self.activateWindow()

def hideAllWindows(self):
    for ii in self.Fig:
        self.Fig[ii].hide()
    self.actionShow_All_Windows.setChecked(False)
    self.actionHide_All_Windows.setChecked(True)
    self.activateWindow()

def unHideOpenWindows(self):
    # figure out which windows should be re-shown after a hideAll event
    for action in self.menuDiffraction.actions()+self.menuReal_Space.actions()+self.menuCenter_of_Mass.actions():
        if not action.isSeparator() and action.isChecked():
            action.trigger()
            action.trigger()

def on_ShowImportWdw_triggered(self):
    # bypass execution if signals are actively being blocked (i.e. for programmatically updating UI values)
    if self.blockAllSignals:
        return
    
    self.ShowImportWdw.setChecked(not self.ImportWindow.isVisible())
    self.ImportWindow.show(self.ShowImportWdw.isChecked())
    

    if self.ShowImportWdw.isChecked():
        hideAllWindows(self)
        self.ImportWindow.activateWindow()
    else:
        unHideOpenWindows(self)
    


def plotColorWheel(self):
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

class WorkerSignals(qtc.QObject):
    finished = qtc.pyqtSignal()
    error = qtc.pyqtSignal(tuple)
    result = qtc.pyqtSignal(np.ndarray)
    progress = qtc.pyqtSignal(int)


class Worker(qtc.QRunnable):
    def __init__(self, fn, *args):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args[0]
        self.signals = WorkerSignals()

    def run(self):
        # run the function, return results, and signal finished
        try:
            adfImages = self.fn(self.args)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(adfImages)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done

def detrCoordCallbacks(self):
    # "Polar" and "Absolute" are mutually exclusive
    match self.sender():
        case self.SettingsWindow.DCSys:
            if self.SettingsWindow.DCSys.currentText() == "Polar":
                self.SettingsWindow.DCPos.setCurrentIndex(self.SettingsWindow.DCPos.findText("Relative"))
        case self.SettingsWindow.DCPos:
            if self.SettingsWindow.DCPos.currentText() == "Absolute":
                self.SettingsWindow.DCSys.setCurrentIndex(self.SettingsWindow.DCSys.findText("Cartesian"))
        case self.SettingsWindow.DCUnit:
            pass
    
    # Update coordinate conversion related convenient global properties
    self.DfPxR = 1
    self.RB0 = [0,0]

    if self.SettingsWindow.DCUnit.currentText() == "mrad":
        self.DfPxR = self.mradPx.value()
    if self.SettingsWindow.DCPos.currentText() == "Relative":
        self.RB0 = self.B0
    
    # Update UI
    match self.DetrMode.currentData():
        case "AlignMod":
            pass
        case "AnnMod"|"DPCMod"|"CoMMod":
            self.SettingsWindow.DCSys.currentIndexChanged.emit(self.SettingsWindow.DCSys.currentIndex())
        case "VrApMod":
            self.SettingsWindow.DCSys.currentIndexChanged.emit(self.SettingsWindow.DCSys.currentIndex())
        case "CustMod":
            self.SettingsWindow.DCSys.currentIndexChanged.emit(self.SettingsWindow.DCSys.currentIndex())

def annularDetectorCallbacks(self):

    def limitAnnUI():
        """ Function to update Annular detector UI limits/labels when coordinate options change """
        self.blockAllSignals = True
        self.AnnRi_NF.setSuffix(" "+self.SettingsWindow.DCUnit.currentData())
        self.AnnRo_NF.setSuffix(" "+self.SettingsWindow.DCUnit.currentData())
        self.AnnRi_NF.setRange(0,self.P.RMax*self.DfPxR)
        self.AnnRo_NF.setRange(0,self.P.RMax*self.DfPxR)
        self.AnnRi_NF.setSingleStep(0.25*self.DfPxR)
        self.AnnRo_NF.setSingleStep(0.25*self.DfPxR)
        self.blockAllSignals = False

    def enableAnnUI():
        """ Function to enable/disable parts of annular/DPC/CoM UI """
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
        self.comControls.BackgroundColor = bc # Set scan direction panel color
        self.comControls.setStyleSheet("background-color:"+bc)

    def moveAnnDetr():
        """ Function to live update annular/round/segmented detectors """

        def moveAnnR():
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
            self.blockAllSignals = True

            # set slider and numerical field values
            self.AnnRi.setValue((innerRadius,outerRadius))
            self.AnnRi_NF.setValue(innerRadius*self.D.annWidth*scale)
            self.AnnRo_NF.setValue(outerRadius*self.D.annWidth*scale)

            # unblock signals
            self.blockAllSignals = False

            # update point centers when updated via QRangeSlider or QDoubleSpinBoxes
            if self.sender() is not self.A.adf:
                self.A.adf.radius = np.array([innerRadius,outerRadius]).clip(np.finfo(np.single).eps,self.P.RMax)*self.D.annWidth
                self.A.adf.redraw()

            #if isStaticEvt(evt): #TODO
            #    self.SaveWindow.SaveImgPrefix.textChanged.emit(self.SaveWindow.SaveImgPrefix.text()) # Update saving prefix

            # Whether to update segments as well
            if dmod == "DPCMod":
                moveSeg()

            # refresh real-space image given new inner/outer radii
            # (add one to outer limit because python doesn't include the last term of the range)
            #if len(self.Fig.Real.ax.images)==0:
            #    self.Fig.Real.Image = self.Data.sum(axis=1).reshape(self.D.NFrY,self.D.NFrX)
            #    #self.ImageAx.Real = self.Fig.Real.ax.imshow(self.Fig.Real.Image)
            #else:
            #    self.Fig.Real.Image = self.adfImages[:,:,innerRadius:outerRadius+1].sum(axis=2)
            #    #self.ImageAx.Real.set_data(self.Fig.Real.Image)
            
            #self.Fig.Real.canvas.draw_idle()
            
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
            case self.A.adf|self.AnnRi|self.AnnRi_NF|self.AnnRo_NF:
                moveAnnR()
            case self.DetRot|self.DetRot_NF|self.NRung|self.NSeg|self.A.SegDetrCir|self.A.SegDetrL|self.A.SegDetrL0|self.A.SegDetrP0:
                moveSeg()
            case self.ScanDirUnlock|self.ScanDirYFlip|self.ScanDir|self.ScanDir_NF|self.A.ScanDirXline|self.A.ScanDirYline|self.A.ScanDirXcirc|self.A.ScanDirYcirc:
                moveScan()
            case self.DetrMode|self.UpdateImages:
                moveAnnR()
                if self.ScanDirUnlock.isChecked():
                    moveScan()  # Update scan directions as well
        
        # Whether to update images
        if toUpdateImage(self):
            # Skip calculations of new BF/DF `self.Fig.Real.Image` if annular radii are not changed
            if isDiffToPrev(self,'AnnR',[ri,ro]): #or isStaticEvt(evt)
                # self.A.k is a 2D matrix of distances from central beam generated in integrateAnnular
                # k is already modified by self.D.annWidth, so ri and ro can be used directly
                self.Fig.DfrnMask.Image = np.ma.masked_inside(self.A.k,ri,ro).mask.astype(self.D.DataType).T # convert from bool to DataType

                # (add 1 to outer limit because python doesn't include the last term of the range)
                self.Fig.Real.Image = self.adfImages[:,:,ri:ro+1].sum(axis=2)
          
            # CoM/DPC calculations; skip if parameters unchanged
            if dmod in ["CoMMod", "DPCMod"]:
                if isDiffToPrev(self,'CoM_P',[ri,ro,sd,syf,dr]): # or isStaticEvt(evt):
                    calcCoM()
            
            # Update images
            plotAllPatterns(self)
        
        self.Fig.Dfrn.canvas.flush_events()
    
    def drawAnnDetr():
        """ initiallize the annular detector annotations """
        # define center location and starting radii for annular detector
        c = self.B0
        r1 = self.AnnRi.value()[0]*self.D.annWidth
        r2 = self.AnnRi.value()[1]*self.D.annWidth
    
        # generate adf detector
        if self.A.adf is None:
            self.A.adf = InteractiveCircle(center=c, radius=(r1,r2), axis=self.Fig.Dfrn.ax, color='r', interactions='resize')
            self.A.adf.connect()
            self.A.adf.updateCircle.connect(lambda: moveAnnDetr())
            self.Fig.Dfrn.canvas.flush_events()
    
    def drawSegDetr():
        pass
    
    def drawScanDir():
        pass
    
    def integrateAnnular():
        #  only rerun the annular integration if transmitted disk center is changed
        if isDiffToPrev(self,"B0",self.B0):
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

            # block signals whilst UI components are updated
            self.blockAllSignals = True

            # set adfInner and adfOuter slider limits based on k.max()
            self.AnnRi.setMaximum(k.max())

            # set adfInner and adfOuter numerical field limits based on k.max()/2
            self.AnnRi_NF.setMaximum(k.max()*self.D.annWidth)
            self.AnnRo_NF.setMaximum(k.max()*self.D.annWidth)

            # unblock signals
            self.blockAllSignals = False
            
            # set maximum scattering angle
            self.P.RMax = k.max()
   
    def calcCoM():
        def integrateCoM():
            """Tikhonov-regularised Fourier integration of CoM → iCoM phase image."""
            ny, nx = self.Fig.CoMX.Image.shape
            kx = np.fft.fftfreq(nx)
            ky = np.fft.fftfreq(ny)
            KX, KY = np.meshgrid(kx, ky)
            k2 = KX**2 + KY**2
            k2[0, 0] = 1  # prevent division by zero; DC → 0 after IFFT

            FCoMX = np.fft.fft2(self.Fig.CoMX.Image)
            FCoMY = np.fft.fft2(self.Fig.CoMY.Image)

            # Fourier integration: phase = IFFT[(kx·FCoMX + ky·FCoMY) / (2πi·k²)]
            self.Fig.iCoM.Image = np.fft.ifft2(
                (KX * FCoMX + KY * FCoMY) / (2j * np.pi * k2)
            ).real

            # dCoM: divergence of CoM field (∂CoMX/∂x + ∂CoMY/∂y)
            dCoMX = np.gradient(self.Fig.CoMX.Image, axis=1)
            dCoMY = np.gradient(self.Fig.CoMY.Image, axis=0)
            self.Fig.dCoM.Image = dCoMX + dCoMY

        # Annular mask in diffraction space (flattened, matches self.Data column order)
        mask = ((self.A.k >= ri) & (self.A.k <= ro)).flatten()
        if not mask.any():
            return  # nothing inside the selected annulus

        # Pixel coordinate grids relative to transmitted beam, same layout as self.A.k
        # self.A.k was built with ogrid[-B0[0]:NPxX-B0[0], -B0[1]:NPxY-B0[1]]
        xgrid, ygrid = np.mgrid[0:self.D.NPxX, 0:self.D.NPxY]
        xweight = (xgrid.flatten() - self.B0[0]).astype(np.float32)
        yweight = (ygrid.flatten() - self.B0[1]).astype(np.float32)

        # Mask-select data columns and compute intensity-weighted CoM
        data_m = self.Data[:, mask].astype(np.float32)   # (NFrX*NFrY, n_masked)
        norm = data_m.sum(axis=1).clip(np.finfo(np.float32).eps, None)

        CoMX_flat = (data_m @ xweight[mask]) / norm        # (NFrX*NFrY,)
        CoMY_flat = (data_m @ yweight[mask]) / norm * syf  # apply Y-axis flip

        # Apply scan-direction rotation (sd in degrees, in scope from moveAnnDetr)
        c, s = np.cos(np.radians(sd)), np.sin(np.radians(sd))
        CoM = np.array([[c, -s], [s, c]]) @ np.vstack([CoMX_flat, CoMY_flat])

        # Reshape to real-space images (NFrY × NFrX)
        self.Fig.CoMX.Image   = CoM[0].reshape(self.D.NFrY, self.D.NFrX)
        self.Fig.CoMY.Image   = CoM[1].reshape(self.D.NFrY, self.D.NFrX)
        self.Fig.CoMMag.Image = np.hypot(self.Fig.CoMX.Image, self.Fig.CoMY.Image)
        self.Fig.CoMPh.Image  = np.arctan2(self.Fig.CoMY.Image, self.Fig.CoMX.Image)

        integrateCoM()

    # bypass execution if signals are actively being blocked (i.e. for programmatically updating UI values)
    if self.blockAllSignals:
        return

    b0 = self.B0  # Absolute pixel coordinates of central beam; only changes in `transBeamCallbacks()`
    dmod = self.DetrMode.currentData() # Detector mode; when changed this callback will be called

    match self.sender():
        case self.SettingsWindow.DCSys: # Change coordinate options
            limitAnnUI() # UI limits
        case self.DetrMode: # Entering current mode
            limitAnnUI() # UI limits
            self.ScanDirUnlock.setChecked(False) # Lock scan directions first upon entering annular modes
            enableAnnUI() # UI enable/disable
            integrateAnnular() # Update annular integral mask
            drawAnnDetr() # Draw detectors
            if dmod == "DPCMod":
                drawSegDetr() # Whether to draw segmented detectors
            moveAnnDetr() # Update UI/ROIs
            enableWindows(self,True) # Enable windows
        case self.AnnRi|self.AnnRi_NF|self.AnnRo_NF|self.DetRot|self.DetRot_NF|self.NSeg|self.NRung|self.ScanDir|self.ScanDir_NF|self.ScanDirYFlip|self.UpdateImages:
            moveAnnDetr() # Update UI/ROIs
        case self.ScanDirUnlock:
            self.P.ScanDirInit = 1; # Flag scan directions as aligned
            enableAnnUI() # Enable/Disable GUI elements
            self.A.removeGroup('ScanDir') # Try to remove existing scan direction ROIs
            if self.ScanDirUnlock.isChecked():
                drawScanDir() # Draw annotations
            self.SettingsWindow.ShowDfrnAxes.click() # Update diffraction axes annotations

def plotAllPatterns(self):
    # always update primary and mask images
    ids = [iID for iType,iID in zip(self.G.ImgType,self.G.ImgID) if iType in ["Primary","Mask"]]
    # update CoM/DPC images if in the correct mode
    if self.DetrMode.currentData() in ["CoMMod","DPCMod"]:
        ids += [iID for iType,iID in zip(self.G.ImgType,self.G.ImgID) if (iID != "ColorWheel") and (iType=='CoM')]
    
    # Update images if visible OR not in changing event; include CoMs if in the modes
    for id in ids:
        if self.Fig[id].isVisible(): # or isStaticEvt(evt): #TODO?
            print(id,self.Fig[id].fig.stale)
            plotImage(self, id)

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

class importThread(qtc.QObject):
    result = qtc.pyqtSignal(np.ndarray)
    finished = qtc.pyqtSignal()

    def __init__(self,filename,dataType,dtype,pixCount,frameCount,dataOffset):
        super().__init__()
        self.filename = filename
        self.dataType = dataType
        self.dType = dtype
        self.pixCount = pixCount
        self.frameCount = frameCount
        self.dataOffset = dataOffset
        self.isInt = np.issubdtype(self.dType,np.integer)
        if self.isInt:
            if np.dtype(self.dType).itemsize>4:
                self.float = np.float64
            else:
                self.float = np.float32


    def run(self):
        if self.isInt:
            self.DataMemmap = np.memmap(self.filename, dtype=self.dataType, mode = "c", offset=self.dataOffset, shape=(self.frameCount))["data"]
            self.Data = np.zeros(shape=self.DataMemmap.shape,dtype=self.float)
            nThreads = psutil.cpu_count(logical=False)
            with ThreadPool(processes=nThreads) as pool:
                pool.map(self.convertInt2Float,range(self.DataMemmap.shape[0]))
            pool.join()
        else:
            self.Data = np.fromfile(self.filename, dtype=self.dataType, count=self.frameCount, offset=self.dataOffset)["data"]
        self.result.emit(self.Data)
        self.finished.emit()
    
    def convertInt2Float(self,val):
        self.Data[val,:] = self.DataMemmap[val,:].astype(self.float)

def prepEMPAD(self):
    # filename from import dialog
    filename = self.D.fileName

    # standar dataset header/footer sizes (in bytes)
    header = 0
    footer = 1024
    
    # standard detector shape
    nopix = 128
    nopiy = 128

    # default EMPAD datatype is float32
    bitsize = 4
    
    # real space scan shape is saved in the empad footer data
    framesx,framesy = np.fromfile(filename, count=2, dtype="float32", offset=header+(nopix*nopiy+142)*bitsize).astype(int)

    # check to make sure scan shape makes sense
    if self.T.FileSize != ((header + nopix*nopiy*bitsize + footer)*int(framesx*framesy)):
        # check to see if filename has 'fooAxBxCxDbar' structure, where:  A = NPxX, B = NPxY, C = NFrX, D = NFrY, and are numbers
        if re.findall(r"\d+x\d+x\d+x\d+", filename):
            s = re.findall(r"\d+x\d+x\d+x\d+", filename)
            nopix, nopiy, framesx, framesy = [int(i) for i in re.split("x", s[0])]
        elif re.findall(r"_x\d+_y\d+", filename):
            s = re.findall(r"\d+", filename)
            framesx,framesy = [int(i) for i in s]
        else:
            framesx,framesy = 1,1

    self.ImportWindow.DNPxX.setValue(nopix)
    self.ImportWindow.DNPxY.setValue(nopiy)
    self.ImportWindow.DNFrX.setValue(framesx)
    self.ImportWindow.DNFrY.setValue(framesy)
    self.ImportWindow.ImpByteOrder.setCurrentIndex(0)
    self.ImportWindow.FrHead.setValue(header)
    self.ImportWindow.FrFoot.setValue(footer)

def prepDM(self):
    # create a MATLAB-like structure
    class struct(object):
        def __init__(self) -> None:
            pass
    
    # Identify DM scalar type for byte reading
    def dmBin(btype, out_type):
        match btype:
            case 2:
                p, b = "i2", 2
            case 3:
                p, b = "i4", 4
            case 4:
                p, b = "u2", 2 # OR Unicode string
            case 5:
                p, b = "u4", 4
            case 6:
                p, b = "f4", 4
            case 7:
                p, b = "f8", 8
            case 8:
                p, b = "i1", 1 # Boolean
            case 9:
                p, b = "i1", 1
            case 10:
                p, b = "u1", 1
            case 11:
                p, b = "i8", 8
            case 12:
                p, b = "u8", 8
            case 15:
                p, b = "TagGroup", None
            case 18:
                p, b = "String", None
            case 20:
                p, b = "Array", None
            case other:
                p, b = "Unknown type", None
        

        if out_type == 'p':
            prc_bytes = p
        elif out_type == 'b':
            prc_bytes = b
        
        return prc_bytes

    def dbgDMBin(btype):
        if btype == 8:
            dbt = "int8 (boolean)"
        else:
            dbt = dmBin(btype, 'p')
        return dbt
    

    # DM Image Data Type
    def dmImageType(iT, oo):
        match iT:
            case 1:
                px, sc, vt, bit = "scalar", "int", 0, 16
            case 2:
                px, sc, vt, bit = "scalar", "float", 0, 32
            case 3:
                px, sc, vt, bit = "complex", "float", 0, 32
            case 5:
                px, sc, vt, bit = "complex", "float", 0, 32
            case 6:
                px, sc, vt, bit = "scalar", "uint", 0, 8
            case 7:
                px, sc, vt, bit = "scalar", "int", 0, 32
            case 8:
                px, sc, vt, bit = "rgba", "uint", 3, 8
            case 9:
                px, sc, vt, bit = "scalar", "int", 0, 8
            case 10:
                px, sc, vt, bit = "scalar", "uint", 0, 16
            case 11:
                px, sc, vt, bit = "scalar", "uint", 0, 32
            case 12:
                px, sc, vt, bit = "scalar", "float", 0, 64
            case 13:
                px, sc, vt, bit = "complex", "float", 0, 64
            case 14:
                px, sc, vt, bit = "scalar", "binary", 0, 8
            case 15:
                px, sc, vt, bit = "rgb", "uint", 0, 8
            case 16:
                px, sc, vt, bit = "rgb", "uint", 1, 8
            case 17:
                px, sc, vt, bit = "rgb", "uint", 0, 16
            case 18:
                px, sc, vt, bit = "rgb", "float", 0, 32
            case 19:
                px, sc, vt, bit = "rgb", "float", 0, 64
            case 20:
                px, sc, vt, bit = "rgba", "uint", 0, 8
            case 21:
                px, sc, vt, bit = "rgba", "uint", 1, 8
            case 22:
                px, sc, vt, bit = "rgba", "uint", 2, 8
            case 23:
                px, sc, vt, bit = "rgba", "uint", 3, 8
            case 24:
                px, sc, vt, bit = "rgba", "uint", 0, 16
            case 25:
                px, sc, vt, bit = "rgba", "float", 0, 32
            case 26:
                px, sc, vt, bit = "rgba", "float", 0, 64
            case 27:
                px, sc, vt, bit = "complex", "float", 0, 32
            case 28:
                px, sc, vt, bit = "complex", "float", 0, 64
            case 29:
                px, sc, vt, bit = "point2", "int", 0, 16
            case 30:
                px, sc, vt, bit = "point2", "int", 1, 16
            case 31:
                px, sc, vt, bit = "point2", "int", 0, 64
            case 32:
                px, sc, vt, bit = "point2", "float", 0, 32
            case 33:
                px, sc, vt, bit = "point2", "float", 0, 64
            case 34:
                px, sc, vt, bit = "rect", "int", 1, 16
            case 35:
                px, sc, vt, bit = "rect", "int", 1, 64
            case 36:
                px, sc, vt, bit = "rect", "float", 1, 32
            case 37:
                px, sc, vt, bit = "rect", "float", 0, 32
            case 38:
                px, sc, vt, bit = "rect", "float", 0, 64
            case 39:
                px, sc, vt, bit = "scalar", "int", 0, 64
            case 40:
                px, sc, vt, bit = "scalar", "uint", 0, 64
            case other:
                px = sc = vt = bit = None
        
        match oo:
            case 'pixel':
                d = px
            case 'scalar':
                d = sc
            case 'variant':
                d = vt
            case 'bit':
                d = bit
            case other:
                d = px+" "+str(sc)+str(bit)
        
        return d

    # Pack Image Data Type info
    def imgDataType(dt):
        imgInfo = struct()
        imgInfo.full = dmImageType(dt, 'full')
        imgInfo.pixel = dmImageType(dt, 'pixel')
        imgInfo.scalar = dmImageType(dt, 'scalar')
        imgInfo.variant = dmImageType(dt, 'variant')
        imgInfo.bit = dmImageType(dt, 'bit')
        return imgInfo
    
    # Read Tag that is not directory
    def readTag(ff, lv, label):
        Tg = struct()
        
        #tmp = ''.join([chr(let) for let in np.fromfile(ff.file,count=4,offset = int(ff.offset),dtype='u1')]) # "%%%%" for Tag
        ff.offset += 4
        nTagType = np.fromfile(ff.file, count=1, dtype='>'+ff.w,offset = int(ff.offset))[0]
        ff.offset += ff.wSize
        tagType = np.fromfile(ff.file, count=nTagType, dtype='>'+ff.w,offset = int(ff.offset))
        ff.offset += int(nTagType)*ff.wSize

        nA = 1
        nM = 1
        isArray = 0
        isMultiItem = 0

        if tagType[0] == 20:
            isArray = 1
            nA = tagType[-1]

        if tagType[isArray] == 15:
            nM = tagType[2 + isArray]
            isMultiItem = 1
        

        sTypes = np.zeros(nM)
        sTypes_s = [None]*nM
        sTypes_b = np.zeros(nM)
        for iM in range(nM):
            sTypes[iM] = tagType[isArray + 3 * isMultiItem + (iM+1) * (1 + isMultiItem)-1]
            sTypes_s[iM] = dbgDMBin(sTypes[iM])
            sTypes_b[iM] = dmBin(sTypes[iM], 'b')

        if isArray==1 and (not label.endswith("Name")):
            Tg.offset = int(ff.offset)
            if isMultiItem:
                Tg.dim = [nM, nA]
                Tg.tagType = "array of multiItems"
            else:
                Tg.dim = nA
                Tg.tagType = "array of scalars"

            Tg.dataType = sTypes_s[:]
            aSize = sum(sTypes_b) * nA
            Tg.size = aSize
            ff.offset += aSize

        else:
            # Read data in tag
            aTg = []
            for iA in range(nA):
                aTg.append(struct())

                mTg = []
                for iM in range(nM):
                    mTg.append(np.fromfile(ff.file, count = 1, dtype = ff.bo + dmBin(sTypes[iM], 'p'), offset = int(ff.offset))[0])
                    ff.offset += int(dmBin(sTypes[iM], 'b'))

                if isMultiItem:
                    aTg[iA] = mTg
                else:
                    aTg[iA] = mTg[0]

            if isArray:
                Tg = aTg          
            else:
                Tg = aTg[0]

        return Tg
    
    # Read Tag directory
    def readTagGp(ff, lv):
        # Tag Group or Tag List
        notList = np.fromfile(ff.file,dtype='u1',offset = int(ff.offset),count=1)[0] # 0 = Tag List, 1 = Tag Group
        ff.offset += 2
        nChd = np.fromfile(ff.file,dtype='>'+ff.w,offset = int(ff.offset),count=1)[0]
        ff.offset += ff.wSize

        if notList:
            Gp = struct()
        else:
            Gp = []

        for iC in range(nChd):
            tagType = np.fromfile(ff.file, dtype = 'u1', count = 1, offset = int(ff.offset))[0]
            ff.offset +=1
            labelSize = np.fromfile(ff.file, dtype = '>u2', count = 1, offset = int(ff.offset))[0]
            ff.offset +=2
            label = ""

            if notList:
                label0 = np.fromfile(ff.file, dtype = 'u1', count=labelSize, offset = int(ff.offset))
                label0 = ''.join([chr(let) for let in label0])
                ff.offset += labelSize

                label = re.sub('[^a-zA-Z_0-9]+','',label0.replace(' ','_'))
                if label=="":
                    label = 'LABEL_FORMATTED_'

                # increment labels with the same name
                if hasattr(Gp,label):
                    iL = 1
                    while hasattr(Gp,label+str(iL)):
                        iL+=1
                    label = label+str(iL)



            if ff.v == 4:
                tagSize = np.fromfile(ff.file, count = 1, dtype = '>'+ff.w, offset = int(ff.offset))[0]
                ff.offset += ff.wSize
                # Skip other Tags
                if lv == 0 and label not in ["ImageList", "ImageSourceList"]:
                    # fast forward and skip to next
                    ff.offset += int(tagSize)
                    continue

            match tagType:
                case 20:
                    chd = readTagGp(ff, lv + 1)
                case 21:
                    chd = readTag(ff, lv + 1, label)

            if notList:
                setattr(Gp,label,chd)
            else:
                Gp.append(chd)
        
        return Gp

    def dmInfo(file):
        """return DMinfo"""

        ff = struct()
        ff.file = file

        ff.id = open(ff.file, 'rb')

        # Message printing options
        ff.m = 0

        # Setup DM3 & 4 differences
        ff.v = np.fromfile(ff.file,dtype=">u4",count=1)[0]
        match ff.v:
            case 3:
                ff.w = 'u4'
            case 4:
                ff.w = 'u8'
            case other:
                DMinfo = 'Not a DM3/4 file.'
                return
        ff.wSize = np.dtype(ff.w).itemsize


        # Size of the root tag group, i.e. 24/16 bytes for DM4/3 (header + footer) smaller than the file size
        ff.size = np.fromfile(ff.file,dtype='>'+ff.w,count=1,offset=4)[0]
        ff.offset = 4 + ff.wSize

        # Data endianness; probably only little ff.bo for DM4
        endian = np.fromfile(ff.file,dtype='>u4',count=1,offset = int(ff.offset))[0]
        ff.offset += 4
        if endian:
            ff.bo = '<'
        else:
            ff.bo = '>'

        # Read TagGroup
        Tg = readTagGp(ff, 0)

        # Finished file reading
        ff.id.close()

        # Deal with `ImageSourceList`
        nImgs = len(Tg.ImageSourceList)
        R = np.zeros(nImgs,dtype=int)
        for i in range(nImgs):
            R[i] = int(Tg.ImageSourceList[i].ImageRef)


        # Deal with  `ImageList[i]:ImageData:DataType` & `ImageList[i].Name`
        for i in range(nImgs):
            dt = Tg.ImageList[R[i]].ImageData.DataType
            Tg.ImageList[R[i]].ImageData.ImageDataType = imgDataType(dt)
            Tg.ImageList[R[i]].ImageData.Name = "".join([chr(let) for let in Tg.ImageList[R[i]].Name])


        # Setup return
        d = struct()
        if ff.v == 4:
            d.fileSize = ff.size + 24
        else:
            d.fileSize = ff.size + 20

        d.version = ff.v
        d.liEndian = endian

        DMinfo = []
        for i in range(nImgs):
            DMinfo.append(Tg.ImageList[R[i]].ImageData)

        DMinfo.append(d)

        return DMinfo

    # filename from import dialog
    filename = self.D.fileName

    self.T.dm = dmInfo(filename)
    
    self.ImportWindow.ImpSubImg.setEnabled(True)

    # List all images' names in `self.ImpSubImg`
    # Select sub-image with the largest dimension; unless manually selected
    if self.sender() is not self.ImportWindow.ImpSubImg:
        pdim = np.zeros(len(self.T.dm)-1)
        self.ImportWindow.ImpSubImg.blockSignals(True)
        for i in range(pdim.size):
            self.ImportWindow.ImpSubImg.addItem(self.T.dm[i].Name)
            pdim[i] = np.array(self.T.dm[i].Dimensions).prod()
        self.ImportWindow.ImpSubImg.blockSignals(False)
        self.ImportWindow.ImpSubImg.setCurrentIndex(pdim.argmax())

    # Info of selected sub-image
    dm = self.T.dm[self.ImportWindow.ImpSubImg.currentIndex()]
    finfo = self.T.dm[-1]

    # Read dimensions
    dims = np.array(dm.Dimensions)

    for i in range(4):
        if i > dims.size:
            dims[i] = 1 # Fill missing dimensions as 1

    self.ImportWindow.DNPxX.setMaximum(np.iinfo(np.int32).max)
    self.ImportWindow.DNPxY.setMaximum(np.iinfo(np.int32).max)
    self.ImportWindow.DNFrX.setMaximum(np.iinfo(np.int32).max)
    self.ImportWindow.DNFrY.setMaximum(np.iinfo(np.int32).max)

    self.ImportWindow.DNPxX.setValue(dims[0])
    self.ImportWindow.DNPxY.setValue(dims[1])
    self.ImportWindow.DNFrX.setValue(dims[2])
    self.ImportWindow.DNFrY.setValue(dims[3])

    # Find offset, file tail, data type, byte-order of dataset
    self.ImportWindow.DataOffset.setMaximum(self.T.FileSize)
    self.ImportWindow.DataOffset.setValue(dm.Data.offset) #TODO
    try:
        self.ImportWindow.ImpDataType.setCurrentIndex(self.ImportWindow.ImpDataType.findData(dm.Data.dataType[0])) #TODO
    except:
        pass

    self.T.fileTail = int(finfo.fileSize - dm.Data.offset - dm.Data.size)

    if dm.ImageDataType.pixel != "scalar": # If pixels are not scalars (e.g. complex image)
        self.ImportWindow.ImpDataType.setCurrentIndex(self.ImportWindow.ImpDataType.findData("unknown"))

    # Is it little endian?
    if finfo.liEndian==1:
        self.ImportWindow.ImpByteOrder.setCurrentIndex(0)
        bo = 'Little Endian'
    else:
        self.ImportWindow.ImpByteOrder.setCurrentIndex(1)
        bo = 'Big Endian'

    notes = "Dim: X = {:d}, Y = {:d}, Z = {:d}, W = {:d}\nDM{:d}, {:s}\nData-type: {:s}\nSelected sub-image's offset is {:d} bytes.".format(dims[0],dims[1],dims[2],dims[3], finfo.version, bo, dm.ImageDataType.full, dm.Data.offset)

    #if dims[3] == 1: #TODO
    #    guessFramesFromDimZ(dims[2])

    self.ImportWindow.FrHead.setValue(0)
    self.ImportWindow.FrFoot.setValue(0)

def readFile(self):
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

def prepareData(self):
    #self.T.progDLG = progDLG(self, 'Preparing data ...', "Data Preparation"); #TODO
    
    # block slots/signals whilst initializing UI components
    self.blockAllSignals = True

    # move to alignment mode
    self.DetrMode.setCurrentIndex(self.DetrMode.findData("AlignMod"))

    # Detector controls
    self.P.ScanDirInit = 0              # Reset alignments
    self.NSeg.setValue(4)               # DPC defaults: 4 segments for DPC
    self.NRung.setValue(1)              #               1 rung for DPC
    self.DetRot.setValue(0)             #               0 detector rotation
    self.DetRot_NF.setValue(0)          #
    self.ScanDir.setValue(0)            #               0 scan rotation
    self.ScanDir_NF.setValue(0)         #

    self.VrApSymm.setCurrentIndex(0)    # default to one virtual aperture 
    self.VrApInvert.setChecked(False)   # without inversion
    self.VrApMirror.setChecked(False)   # without mirror symmetry
    self.VrApMirrRot.setValue(0)        # initialize mirror symmetry to 0 degrees
    self.VrApMirrRot_NF.setValue(0)     # 

    # Alignments
    self.P.DfCtr = self.D.NPx/2+.5      # Exact center of the Diffraction image
    self.P.RsCtr = self.D.NFr/2+.5      # Exact center of the Real-space image
    self.Alpha.setValue(12)             # initialize alpha to 12 mrad
    self.P.VrApXY = self.P.DfCtr        # initialize virtual aperture to diffraction center

    # Axes limits, restrict to avoid rounding to pixels outside the image. Origin upper left as in raster scanning
    self.P.DfrnAxLim = np.array([0, self.D.NPxX, self.D.NPxY, 0]) - 0.5
    self.P.RealAxLim = np.array([0, self.D.NFrX, self.D.NFrY, 0]) - 0.5

    # initialize diffraction space axis limits for all diffraction space images
    for id in self.G.DfrnID:
        self.Fig[id].ax.set_xbound(self.P.DfrnAxLim[0:2])
        self.Fig[id].ax.set_ybound(self.P.DfrnAxLim[2:4])
        self.Fig[id].canvas.draw_idle()

    # initialize real space axis limits for all real space images
    for id in self.G.RealID:
        self.Fig[id].ax.set_xbound(self.P.RealAxLim[0:2])
        self.Fig[id].ax.set_ybound(self.P.RealAxLim[2:4])
        self.Fig[id].canvas.draw_idle()

    # Transmitted Beam controls
    if self.sender() is not self.SettingsWindow.SwapRealXY: # Keep transmitted beam alignment if swapping Real-space X/Y
        self.P.TransBeamInit = 0
        # set transmitted beam ranges and values for sliders and number fields
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
    self.RealROIInvert.setChecked(False) # do not invert the real space ROI picker on initialization
    self.RealROIShape.setCurrentIndex(self.RealROIShape.findData("full")) # display PACBED from the entire dataset

    # Export controls #TODO
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
    self.SettingsWindow.SettingsTabGroup.setCurrentWidget(self.SettingsWindow.DisplayTab)
    pos = self.SettingsWindow.geometry()
    pos.moveLeft(self.geometry().getRect()[0]+self.geometry().getRect()[2]+self.C.decorPad*2)
    pos.moveTop(self.geometry().getRect()[1])
    self.SettingsWindow.setGeometry(pos)
    self.SettingsWindow.show()

    self.DetrMode.setCurrentIndex(self.DetrMode.findData("AlignMod"))
    detectorModeCallbacks(self)

    #flashBackground(self, [self.DfrnCalibGrid self.TransBeamAlignGrid])

def finishImport(self):
    # push annular integration to a worker threadpool #TODO
    #print("finishImport(self) on thread {}".format(int(qtc.QThread.currentThreadId())))
    #print("worker established: {}".format(datetime.now()))
    #worker = Worker(integrateAnnular,self)
    #worker.signals.result.connect(self.receiveWorkerData)
    #worker.signals.finished.connect(lambda: reinitializeUI(self))
    #print("threadpool established: {}".format(datetime.now()))
    #self.threadpool = qtc.QThreadPool()
    #print("threadpool started: {}".format(datetime.now()))
    #self.threadpool.start(worker)
    
    # quit the import thread
    self.workerThread.quit()

    # generate placeholder images
    self.Fig.Preview.Image = np.zeros(self.D.NPx)
    self.Fig.Dfrn.Image = np.zeros(self.D.NPx)
    self.Fig.Dfrn.ImageMask = np.zeros(self.D.NPx)
    self.Fig.Dfrn.Real = np.zeros(self.D.NFr)
    self.Fig.Dfrn.RealMask = np.zeros(self.D.NFr)

    prepareData(self)
    reinitializeUI(self)

def reinitializeUI(self):
    # finalize progressBar
    self.progressBar.setMaximum(100)
    self.progressBar.setValue(100)
    self.progressBar.setTextVisible(False)

    self.progressBar.setEnabled(False)

    # make control panels visible again
    self.RealSpacePanel.setVisible(True)
    self.progressBarPanel.setVisible(True)
    self.DfrnDetrTabGroup.setVisible(True)
    self.DetectorModeGroup.setVisible(True)

    # turn ALL actions back on
    for action in self.findChildren(qtw.QAction):
        action.setEnabled(True)

    # update annular QRangeSlider to match
    self.AnnRi.blockSignals(True)
    self.AnnRi.setValue((self.AnnRi.minimum(),self.AnnRi.maximum()))
    self.AnnRi.blockSignals(False)

    # re-enable windows
    enableWindows(self,True)

    # start alignment mode
    self.DetrMode.setCurrentIndex(self.DetrMode.findData("AlignMod"))

def startupFcn(self):
    from callbacks.guiClass import ImageWindow, SettingsWindow, SaveWindow, ImportWindow

    def getGPU(self):
        self.ImportWindow.ImpGPU.clear()
        self.C.nGPU = 0
        self.C.GPUmem = []
        self.C.GPUname = []

        # Check if CUDA capable GPU is available for acceleration
        self.C.nGPU = torch.cuda.device_count()
            
        # Find GPU devices and turn on/off GPU support; self.ImportWindow.ImgGPU.currentData() = None is always "GPU off"
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
            self.ImportWindow.ImpGPU.addItem('GPU off',None)

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
        if [self.C.decorPad,self.C.titleHeight]==[0,0]: #TODO
            self.C.decorPad = 5
            self.C.titleHeight = 25
        self.C.mplDecor = tmp.size()-qtc.QSize(400,400)
        tmp.close()

        # available monitor space
        self.C.monitorAvailWidth = self.C.monitorWidth - self.C.toolbarWidth
        self.C.monitorAvailHeight = self.C.monitorHeight - self.C.toolbarHeight

        # current monitor dpi
        self.C.dpi = self.screen().physicalDotsPerInch()

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
        # create figure windows
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
        self.Fig.Preview = ImageWindow("Preview","Preview","Preview","Preview","gray",[self.C.l, (self.C.ScreenSize[3]-self.C.sz)/2, self.C.sz + self.C.mplDecor.width(), self.C.sz + self.C.mplDecor.height()])
        self.Fig.ColorWheel = ImageWindow(id = "ColorWheel", name = "Color Wheel for Phase Direction", space = "ColorWheel", typ = "CoM", cmap = "hsv", pos = [self.C.shc-self.C.sz-self.C.mplDecor.width(), self.C.sz+2*(self.C.decorPad+self.C.titleHeight)+self.C.mplDecor.height() + self.C.vOffset, self.C.sz/2 + self.C.mplDecor.width(), self.C.sz/2 + self.C.mplDecor.height()])
        
        # AND their Axes/Figure objects, as well as the gray overlay to disable them
        self.G.ImgAx = [self.Fig[ii].ax for ii in self.Fig]
        self.G.ImgFig = [self.Fig[ii] for ii in self.Fig]
        
        # connect image resizeEvent signal to slot; updates window size numerical fields in SettingsWindow
        for fig in self.G.ImgFig:
            fig.imageResize.connect(lambda size,space: updateImageWindowSize(self,size,space))
            fig.activateFigure.connect(lambda id: updateDispImg(self,id))

        # Axes objects for all diffraction-sized figures/axes/images
        self.G.DfrnAx = [self.Fig[ii].ax for ii in self.G.DfrnID]

        # Axes objects for all real-space-sized figures/axes/images
        self.G.RealAx = [self.Fig[ii].ax for ii in self.G.RealID]

        # Group all "Show ... Window" buttons related to CoM/DPC
        self.G.CoM_btns = [obj for obj in self.SettingsWindow.findChildren(qtw.QPushButton) if "CoM" in obj.objectName()]
        self.G.CoM_btns.extend([self.ShowColorWheelWdw,self.SettingsWindow.ShowColorWheelWdw_2])

        # Group all window `figure` `uifigure`
        self.G.AllFig = self.G.ImgFig.copy()
        self.G.AllFig.extend([self,self.SettingsWindow,self.ImportWindow,self.SaveWindow])

    def updateImageWindowSize(self,size,space):
        match space:
            case "Dfrn":
                self.SettingsWindow.WdwHDfrn.setValue(self.SettingsWindow.WdwHDfrn.value()+size.height())
                self.SettingsWindow.WdwWDfrn.setValue(self.SettingsWindow.WdwWDfrn.value()+size.width())
            case "Real":
                self.SettingsWindow.WdwHReal.setValue(self.SettingsWindow.WdwHReal.value()+size.height())
                self.SettingsWindow.WdwWReal.setValue(self.SettingsWindow.WdwWReal.value()+size.width())

    def updateDispImg(self,id):
        self.SettingsWindow.DispImage.setCurrentIndex(self.SettingsWindow.DispImage.findData(id))

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
        self.ImportWindow.ImpGPU.addItem('GPU off',None)

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

    # get lock and unlock icons for later user
    self.unlock = qtg.QIcon('./gui/icons/unlock.png')
    self.lock = qtg.QIcon('./gui/icons/lock.png')

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

    # start with a mostly blank UI
    self.RealSpacePanel.setVisible(False)
    self.progressBarPanel.setVisible(False)
    self.DfrnDetrTabGroup.setVisible(False)
    self.DetectorModeGroup.setVisible(False)

    # always keep "Import Preview" hidden from QComboBox
    self.DetrMode.view().setRowHidden(0,True)

    # Import Data is the only option to start
    # turn off ALL actions
    for action in self.findChildren(qtw.QAction):
        if "debug" not in action.iconText():
            action.setEnabled(False)
    
    # make sure top level menu (File, Settings, Window, Help) is enabled
    for menu in self.menubar.actions():
        menu.setEnabled(True)
    
    # only allow user to import data
    self.ShowImportWdw.setEnabled(True)

    resetQuant4DCallbacks

def resetQuant4DCallbacks(self):
    unloadData(self,False)
    self.DetrMode.setCurrentIndex(self.DetrMode.findData("PrvwMod"))

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
            if type(getattr(self.A,ii)) in (InteractivePoint,InteractiveCircle,matplotlib.lines.Line2D):#,InteractiveBox #TODO
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
    #setattr(self,'D',D()) #TODO #DELTE
    setattr(self,"D",None)
    setattr(self,'Prev',Prev())

def enableWindows(self,sw=True):
    """ Function to enable/disable windows/UI; disable is only for notification/progress bar/busy background etc """
    assert isinstance(sw,bool)

    prvw = self.DetrMode.currentData() == "PrvwMod" # Preview mode or not
    # Detector Mode UI, keep disabled in Import Preview Mode unless a dataset is loaded
    self.DetrMode.setEnabled(sw and not prvw) #(sw and (not prvw or self.D is not None))

    # Real-space ROI controls, keep disabled in Import Preview Mode
    self.RealSpacePanel.setEnabled(sw and not prvw)

    # Other UIs can be enabled in Import Preview Mode
    self.toolBar.setEnabled(sw)
    self.DfrnDetrTabGroup.setEnabled(sw)
    self.SettingsWindow.setEnabled(sw)
    self.SaveWindow.setEnabled(sw)
    self.ImportWindow.setEnabled(sw)
       
    # Also reset all windows' mouse pointer when enabling UIs
    if sw:
        [ii.setCursor(qtc.Qt.ArrowCursor) for ii in self.G.AllFig]

def importData(self):
    assert(os.path.isfile(self.ImportWindow.ImpFilePath.text())), "File does not exist at the specified location"
    
    # bypass execution if signals are actively being blocked (i.e. for programmatically updating UI values)
    if self.blockAllSignals:
        return
    
    if os.path.isfile(self.ImportWindow.ImpFilePath.text()):
        # Set save/export filenames etc.
        self.setWindowTitle(self.fileName)
        self.SaveWindow.SaveDir.setText(self.fileDir)
        self.SaveWindow.SaveImgPrefix.setText(self.fileName.replace(self.fileExt,"")+"_")
                
        # TODO
        #if self.ImportWindow.MedipixButton.isChecked():
        #     readMRC(self)
        #elif self.ImportWindow.EMPADButton.isChecked():
        try:
            readFile(self)
        except:
            unloadData(self)
            notifDLG(self, self,'error','Error during Import!','Error!')
            enableWindows(self,True)

        # Start file reading here
        #if ~isempty(self.D.h5ds) % HDF5 import
        #    data = zeros(npx, npy, nfx, nfy, dtype1); % Pre-allocate array
        #    fid = H5F.open(self.D.filePath);   dset_id = H5D.open(fid, self.D.h5ds);
        #    file_space_id = H5S.create_simple(4, [dnfy dnfx dnpy dnpx], []);
        #    mem_space_id = H5S.create_simple(2, [npy*pd npx*pd], []);
        #    % data = H5D.read(dset_id,'H5ML_DEFAULT','H5S_ALL','H5S_ALL','H5P_DEFAULT'); % Read whole
        #    for ify = 1:nfy
        #      for ifx = 1:nfx
        #        if ~isvalid(self.T.progDLG), err = -1; break; end % Cancel if progress window closed
        #        self.T.frameJ(1) = (ify-1)*nfx + ifx; % Update processed Frame Number for progress update
        #        H5S.select_hyperslab(file_space_id, 'H5S_SELECT_SET', [fy1+(ify-1)*fd, fx1+(ifx-1)*fd, py1, px1]-1, ...
        #          [],[], [1 1 npy*pd npx*pd]); % Read 1 frame at a time; C-like array indices for H5 low-level APIs
        #        frame = H5D.read(dset_id, 'H5ML_DEFAULT', mem_space_id, file_space_id, 'H5P_DEFAULT');
        #        if pd > 1, frame = squeeze(sum(reshape(frame, [pd npx pd npy]), [1 3])); end % Pixel binning
        #        data(:, :, ifx, ify) = frame; % Store frame
        #      end
        #      if err == -1, break; end
        #    end
        #    % Close opened handles
        #    H5S.close(mem_space_id);  H5S.close(file_space_id);  H5D.close(dset_id);  H5F.close(fid);
        #    data = reshape(data, self.D.NPxS, self.D.NFrS); % Make dataset a 2D array
        #    self.Data = data;
        #  elseif self.D.mem == "Physical Memory" % General reading method; read data into physical memory
        #if self.D.mem == "Physical Memory": #General reading method; read data into physical memory
          #  data = zeros(npx, npy, nfx, nfy, dtype1) # Pre-allocate array
          #  dfrSize = hdr+dnpx*dnpy*bsize+ftr # frame size including header/footer
          #  fid = fopen(self.D.filePath,'r')
          #  for ify = 1:nfy:
          #      for ifx = 1:nfx:
          #          if ~isvalid(self.T.progDLG):
          #              err = -1
          #              break # Cancel if progress window closed
          #          self.T.frameJ(1) = (ify-1)*nfx + ifx # Update processed Frame Number for progress update
          #          # Read 1 frame at a time; move cursor to "frame offset" + "pixel Y offset" in file dataset
          #          dfx = fx1+(ifx-1)*fd;  dfy = fy1+(ify-1)*fd; % Frame indices in dataset file
          #          fseek(fid, offs + (dfx-1 + (dfy-1)*dnfx) * dfrSize + hdr + ((px1-1) + (py1-1)*dnpx) * bsize, 'bof')
          #          frame = fread(fid, [dnpx, npy*pd], dtype, 0, order) # Read including "pixel X offset"
          #          if npx*pd ~= dnpx:
          #              frame = frame(px1:px1+npx*pd-1, :) # Crop "pixel X offset" off from array memory
          #          if pd > 1:
          #              frame = squeeze(sum(reshape(frame, [pd npx pd npy]), [1 3])) # Pixel binning
          #          data[:, :, ifx, ify] = frame # Store frame
          #  if err == -1:
          #      break
          #  
          #  data = reshape(data,self.D.NPxS,self.D.NFrS) # Make dataset a 2D array
          #  self.Data = data;
          #elseif self.D.mem == "Virtual Mapping" % Virtual memory mapping
          #  % Create a memory mapped file, rather than reading the file directly into memory
          #  if ~strcmp(self.C.SysEndian, order)
          #    error("Dataset's endianness is different to that of the system's!")
          #  end
          #  
          #  if hdr == 0 and ftr == 0:
          #      self.Memfile = memmapfile(self.D.filePath,'Offset',offs, 'Format',{dtype1,[self.D.NPxS self.D.NFrS],'data'}, 'Repeat',1)
          #      self.Data = self.Memfile.Data.data
          #  else:
          #      error("Virtual memory with header/footer > 0 not supported yet.")

    else:
        msg = "File: "+self.ImportWindow.ImpFilePath.text()+" is not found!"
        ttl = "File not found!"
        notifDLG(self, self.ImportWindow, 'error', msg,ttl)

def getDecorSize(self):
        decorSize = [self.geometry().x()-self.pos().x(), self.geometry().y()-self.pos().y()]
        return decorSize

def displayCallbacks(self):

    # bypass execution if signals are actively being blocked (i.e. for programmatically updating UI values)
    if self.blockAllSignals:
        return
    
    id = self.SettingsWindow.DispImage.currentData()
    fig = self.Fig[id]
    ax = self.ImageAx[id]

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
            fig.cmap = self.SettingsWindow.DispCMap.currentText() # chosen colormap

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
            fig.gamma = max(self.sender().value(),np.finfo(np.single).eps) # Gamma

        case self.SettingsWindow.DispMaskOpa|self.SettingsWindow.DispMaskOpa_NF:
            fig.maskOpa = self.sender().value() # Mask opacity
            
        case other: # e.g. self.SettingsWindow.DispImage
            # Update GUIs by values stored in `self.ImageAx.(id).UserData` for the current selected image
            self.Fig[id].show()
            self.Fig[id].activateWindow() # Bring selected image to front
            self.DispVecField.setCurrentIndex(self.DispVecField.findData(fig.vecField))
            self.SettingsWindow.DispCMap.setCurrentIndex(self.SettingsWindow.DispCMap.findText(fig.cmap))
            self.SettingsWindow.DispCMapInvert.setChecked(fig.invert)
            self.DispVecColor.setStyleSheet("background-color:"+fig.vecColor.name())
            
            # Enable vector field UIs if: 1) in CoM/DPC mode AND 2) real-space image selected
            enabledState = (self.DetrMode.currentData() in ["CoMMod","DPCMod"]) and (fig.space == "Real")
            self.DispVecField.setEnabled(enabledState)
            self.DispVecFieldLabel.setEnabled(enabledState)
            self.DispVecColor.setEnabled(enabledState)
            
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

    # block signals during UI update
    self.blockAllSignals = False

    # Update UI
    self.SettingsWindow.DispBrightness_NF.setValue(fig.brightness)
    self.SettingsWindow.DispBrightness.setValue(fig.brightness)
    self.SettingsWindow.DispContrast_NF.setValue(fig.contrast)
    self.SettingsWindow.DispContrast.setValue(fig.contrast)
    self.SettingsWindow.DispGamma_NF.setValue(fig.gamma)
    self.SettingsWindow.DispGamma.setValue(fig.gamma)
    self.SettingsWindow.DispMaskOpa_NF.setValue(fig.maskOpa)
    self.SettingsWindow.DispMaskOpa.setValue(fig.maskOpa)

    # unblock signals
    self.blockAllSignals = False

    # Update image
    plotImage(self, id); # Re-plot image

def plotImage(self,id):
    """Generic function for plotting an image on a given axis with brightness/contrast/gamma values"""

    # Special case for plotting the color wheel - can get unloaded
    if id == "ColorWheel":
        plotColorWheel(self)
        return

    # get image figure and axes
    fig = self.Fig[id]  # ImageWindow
    ax = fig.ax         # AxesSubplot
    im = np.ma.masked_invalid(self.Fig[id].Image) # numpy masked array

    # clear old image(s)
    #[ii.remove() for ii in self.Fig[id].ax.get_images()]

    # return if image not yet plotted
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
        CoMMagNorm  = self.Fig.Dfrn.CoMMag
        CoMMagNorm -= np.nanmin(CoMMagNorm)
        CoMMagNorm /= np.nanmax(CoMMagNorm)
        self.ImageAx.CoMPhMag.set_alpha(self.ImageAx.CoMPhMag.get_alpha()*CoMMagNorm)

    plotVectorField(self,id) # Plot vector field, if selected #TODO
        
    # Only update statistics if not in changing Event AND it is the "selected" image 
    if (id == self.SettingsWindow.DispImage.currentData()): # and isStaticEvt(evt): #TODO
        # don't update stats while things are changing, only when finished to increase responsiveness
        updateDispImgStats(self,id,minVal,maxVal,limitLow,limitHigh,limitRange)

    # set colormap
    self.ImageAx[id].set_cmap(fig.cmap+["","_r"][fig.invert]) # append "_r" if inverted

    # update plot
    if id != "Dfrn":
        fig.canvas.draw_idle()
    fig.canvas.flush_events()


def updateDispImgStats(self,id,minVal,maxVal,limitLow,limitHigh,limitRange):
    """Function to update image's statistics"""
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
        # Create histogram ROI on first call; afterwards just reposition it
        if self.A.histBox is None:
            from callbacks.histBoxWidget import HistBox, histbox_to_sliders
            hist_ax = self.SettingsWindow.HistAxes.axes

            def _on_histbox_change(lo, hi):
                """Convert dragged limits back to brightness/contrast sliders."""
                b_new, c_new = histbox_to_sliders(lo, hi, minVal, maxVal)
                # Block the other spinbox while updating to avoid re-entry
                for w in [self.SettingsWindow.DispBrightness,
                          self.SettingsWindow.DispContrast,
                          self.SettingsWindow.DispBrightness_NF,
                          self.SettingsWindow.DispContrast_NF]:
                    w.blockSignals(True)
                self.SettingsWindow.DispBrightness.setValue(int(round(b_new)))
                self.SettingsWindow.DispBrightness_NF.setValue(b_new)
                self.SettingsWindow.DispContrast.setValue(int(round(c_new)))
                self.SettingsWindow.DispContrast_NF.setValue(c_new)
                for w in [self.SettingsWindow.DispBrightness,
                          self.SettingsWindow.DispContrast,
                          self.SettingsWindow.DispBrightness_NF,
                          self.SettingsWindow.DispContrast_NF]:
                    w.blockSignals(False)
                # Trigger a display refresh
                fig.brightness = int(round(b_new))
                fig.contrast   = int(round(c_new))
                displayCallbacks(self)

            self.A.histBox = HistBox(hist_ax, limitLow, limitHigh,
                                     on_change=_on_histbox_change)

        # Reposition ROI if the caller is NOT the histBox itself (avoid loop)
        elif self.sender() is not self.A.histBox:
            self.A.histBox.update_position(limitLow, limitHigh)

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

def plotVectorField(self,id):
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
    if (not vec) or (self.DetrMode.currentData() not in ["CoMMod", "DPCMod"]):
        return
    
    # Plot vector arrows over the selected image
    x,y = np.meshgrid(np.arange(0,self.D.NFrX,vec),np.arange(0,self.D.NFrY,vec))
    u = self.Fig.Dfrn.CoMX[0::vec, 0::vec]
    v = self.Fig.Dfrn.CoMY[0::vec, 0::vec] 
    self.A.vecField[id] = fig.ax.quiver(x, y, u, v, color=fig.vecColor,units='xy')
    fig.canvas.draw_idle()



def isDiffToPrev(self,name,val):
    """Function to check whether the named given value is changed compared to the previous value, and store the new value"""
    c = (not hasattr(self.Prev, name)) or (getattr(self.Prev,name)!=val)
    
    # in case an image is being compared to an image, c will be an array of bool, not a single bool
    if isinstance(c,np.ndarray):
        c = c.all()

    if c:
        setattr(self.Prev,name,val)
    return c

def showWindowCallbacks(self):
    id = self.SettingsWindow.DispImage.currentData()
    match self.sender():
        case self.SettingsWindow.ShowImageWdw: # Show selected image
          self.Fig[id].show()
          self.Fig[id].activateWindow()
        case self.SettingsWindow.ShowMaskWdw: # Show diffraction or Real `space` mask for the selected image
            id = self.Fig[id].space + "Mask"
            self.Fig[id].show()
            self.Fig[id].activateWindow()
        case other: # All other `self.Show***Wdw` buttons
            id = self.sender().accessibleName()
            if id in self.G.ImgID:
                self.Fig[id].show()
                self.Fig[id].activateWindow()
                # If `id` is one of the available images, select it
                if (not self.SettingsWindow.DispLock.isChecked()) and (self.SettingsWindow.DispImage.currentData() != id) and (self.SettingsWindow.DispImage.findData(id) != -1):
                    self.SettingsWindow.DispImage.setCurrentIndex(self.SettingsWindow.DispImage.findData(id))

# Function to import mask for given (diffraction/real) space
def importMask(self, space):
    if space == "Real":
        spaceName = "Real-space"
        imShape = self.D.NFr
    else: # "Dfrn"
        spaceName = "Diffraction"
        imShape = self.D.NPx

    im = []
    msg = ""

    fDialog  = qtw.QFileDialog(self)
    fDialog.setWindowTitle("Select a mask image with shape [{:d},{:d}]".format(*imShape))
    fDialog.setNameFilter("('*.tif;*.tiff;*.png;*.jpg;*.jpeg;*.bmp;*.gif);;(*.*)")
    fDialog.setFileMode(qtw.QFileDialog.ExistingFile)
    fDialog.setDirectory(qtc.QDir.currentPath())
    file = None
    if fDialog.exec_() == qtw.QDialog.Accepted:
        file = fDialog.selectedFiles()
    
    _,ext = os.path.splitext(file)

    match ext.lower(): # force lowercase
        case '.tif'|'.tiff'|'.png'|'.jpg'|'.jpeg'|'.bmp'|'.gif':

            # directly convert image to grayscale floating point numpy array
            im = np.array(Image.open(file).convert("L")).astype(np.float64)
            
            # get mask shape
            isize = im.shape

            # if imported dimensions do not matched data dimensions
            if ~all(isize == imShape):
                # check for a transpose
                if all(isize == np.flip(imShape)):
                    im = im.T
                    msg += "Image shape ({:d},{:d}) transposed to fit data's {:s} shape ({:d},{:d}).\n".format(*isize, spaceName, *imShape)
                else: # throw error
                    notifDLG(self, self, 'warn', "Image size ({:d},{:d}) does not fit data's {:s} size ({:d},{:d})!".format(*isize, spaceName, *imShape),'Dimension Mismatch')
                    return

        case "": # Canceled, etc.
            return
        
        case other: # unsupported filetype
            _ = notifDLG(self, self, 'warn', "File type '*"+ext+"' currently unsupported!", 'Import Failed')
            return
    
    # check for invalid data (nan or inf) and replace with zeros
    invalidMask = np.ma.masked_invalid(im).mask
    if invalidMask.any():
        im[invalidMask]=0
        msg += "NaN/Inf found in image, and set to 0.\n"

    # scale the maximum to 1
    imax = im.max() 
    if (imax != 0) and (imax != 1):
        im /= imax
        msg += "The maximum was {:d}; now scaled to 1, by `IMG = IMG/{:d}`.\n".format(imax,imax)

    # notify user of what has been done and return the mask
    if msg != "":
        msg = "Please note:\n"+msg+"\n"

    _ = notifDLG(self, self, 'help', msg+"Please check the "+spaceName+" Mask image.",'Mask Imported')
    self.Fig[space+"Mask"].activateWindow()

    return im