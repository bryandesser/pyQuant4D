import os, sys, traceback, re, gc, psutil, importlib, matplotlib
import numpy as np
import torch
from multiprocessing.pool import ThreadPool
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from PyQt5 import QtGui as qtg
import callbacks.appClass as appClass
from callbacks.appClass import *
from callbacks.annotationsClass import InteractiveCircle,DraggablePoint


def importCallbacks():
    pass

def on_ImpFileSelect_clicked(self):
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

        # activate preset buttons if file extension matches a known filetype, else custom
        match self.D.fileExt.casefold():
            case ".raw":
                self.ImportWindow.EMPADButton.setChecked(1)
            case ".mib":
                self.ImportWindow.MedipixButton.setChecked(1)
            case ".mrc":
                self.ImportWindow.MRCButton.setChecked(1)
            case ".dm3"|".dm4":
                self.ImportWindow.DM34Button.setChecked(1)
            case ".h5":
                self.ImportWindow.HDF5Button.setChecked(1)
            case other:
                self.ImportWindow.CustomButton.setChecked(1)
    
    # if filename is incorrect/does not exist...
    else:
        self.ImportWindow.ImpActualFilesize.setText("")
    
    importFileType(self)

def importFileType(self):
    # Make an initial guess at the file dimensions (assume ~square field of view: NFrX≈NFrY)
    def guessFramesFromSize():
        bitSize = getattr(self.ByteSize,self.ImportWindow.ImpDataType.currentData())
        if self.ImportWindow.DNPxX.value() > 1 and self.ImportWindow.DNPxY.value() > 1:
            x = np.sqrt((self.T.FileSize-self.ImportWindow.DataOffset.value()-self.T.fileTail) \
                    /(self.ImportWindow.DNPxX.value()*self.ImportWindow.DNPxY.value()*bitSize+self.ImportWindow.FrHead.value()+self.ImportWindow.FrFoot.value()))
            self.ImportWindow.DNFrX.setValue(np.maximum(np.floor(x),1))
            self.ImportWindow.DNFrY.setValue(np.maximum(np.floor(x),1))

    # Guess numbers of Frame X and Y from 3D dataset (with only Frame X)
    def guessFramesFromDimZ(dz):
        self.ImportWindow.DNFrX.setValue(np.round(np.sqrt(dz)).astype(int))
        self.ImportWindow.DNFrY.setValue(np.round(dz/self.ImportWindow.DNFrX.value()).astype(int))

    # Guess dataset size from fileName in the following style (only the first match):
    #   fileName = 'fooAxBxCxDbar', where:  A = NPxX, B = NPxY, C = NFrX, D = NFrY, and are numbers
    def getDimFromName(name):
        s = re.findall("\d+x\d+x\d+x\d+",name)
        if s:
            DNPxX,DNPxY,DNFrX,DNFrY = re.split("x",s[0])
            self.ImportWindow.DNPxX.setValue(int(DNPxX))
            self.ImportWindow.DNPxY.setValue(int(DNPxY))
            self.ImportWindow.DNFrX.setValue(int(DNFrX))
            self.ImportWindow.DNFrY.setValue(int(DNFrY))
    
    
    # Default values/properties
    notes = ""
    err = 0
    self.T.dm = []
    self.T.h5 = []
    self.T.fileTail = 0
    self.ImportWindow.ImpSubImg.clear()
    self.ImportWindow.ImpSubImg.setEnabled(False)
    self.ImportWindow.DataOffset.setValue(0)
    self.ImportWindow.FrHead.setValue(0)
    self.ImportWindow.FrFoot.setValue(0)
    
    # Medipix data are saved as a .mib file of varying bit-depth as unsigned integers of the next highest class
    #   (i.e. 12-bit is saved as a 16-bit unsigned integer) with big-endian ordering.
    # EMPAD data are saved as a .raw file with 32-bit depth with little endian ordering.
    # Fiji/ImageJ tend to save their files with big-endian ordering, though this is also system- and user-dependent.
    # H5 and other binary/raw data types are allowed, but user-dependent.

    # available data types and their plain text names
    dataType = ['unknown','i1','u1','i2','u2','f4','i4','u4','f8','i8','u8']
    dataTypeText = ['Select Data Type...','8-bit Signed','8-bit Unsigned','16-bit Signed','16-bit Unsigned','32-bit Real', \
                    '32-bit Signed','32-bit Unsigned','64-bit Real','64-bit Signed','64-bit Unsigned']

    # block slots/signals
    self.ImportWindow.ImpDataType.blockSignals(True)
    self.ImportWindow.ImpByteOrder.blockSignals(True)

    # add to combobox
    self.ImportWindow.ImpDataType.clear()
    for dtt,dt in zip(dataTypeText,dataType):
        self.ImportWindow.ImpDataType.addItem(dtt,dt)
    
    # default to "Select Data Type..." prompt
    self.ImportWindow.ImpDataType.setCurrentIndex(0)

    # default to "little endian"
    self.ImportWindow.ImpByteOrder.setCurrentIndex(0)

    # unblock slots/signals
    self.ImportWindow.ImpDataType.blockSignals(False)
    self.ImportWindow.ImpByteOrder.blockSignals(False)

    if os.path.isfile(self.ImportWindow.ImpFilePath.text()):
        if self.ImportWindow.EMPADButton.isChecked():
            self.ImportWindow.FrFoot.setValue(1024)
            self.ImportWindow.ImpDataType.setCurrentIndex(5)
            self.ImportWindow.DNPxX.setValue(128)
            self.ImportWindow.DNPxY.setValue(128)

            notes = 'Pixels:\t128x128\n32-bit Real\n** EMPAD data have 1024-byte frame footers'
            prepEMPAD(self)

        elif self.ImportWindow.MedipixButton.isChecked():
            # available data types and their plain text names - Medipix edition
            dataType = ['unknown','u1','u2','u4']
            dataTypeText = ['Select Data Type...','1 or 6-bit Padded Unsigned','12-bit Padded Unsigned','24-bit Padded Unsigned']
            
            # add to combobox
            self.ImportWindow.ImpDataType.clear()
            for dtt,dt in zip(dataTypeText,dataType):
                self.ImportWindow.ImpDataType.addItem(dtt,dt)

            # check .mib file header
            fmeta = np.fromfile(self.ImportWindow.ImpFilePath.text(),dtype=np.uint8,count=128)
            fmeta = re.split(",",''.join(chr(i) for i in fmeta))

            if len(fmeta) >= 7 and fmeta[6][0].casefold() in ("u","r"):
                # Re-read with known header size
                fmeta = np.fromfile(self.ImportWindow.ImpFilePath.text(),dtype=np.uint8,count=int(fmeta[2]))
                fmeta = re.split(",",''.join(chr(i) for i in fmeta))
                datatype = fmeta[6].casefold()
                bitsize = int(fmeta[-2])
                if datatype[0] == 'u':
                    match bitsize:
                        case 1|6:
                            self.ImportWindow.ImpDataType.setCurrentIndex(1)
                        case 12:
                            self.ImportWindow.ImpDataType.setCurrentIndex(2)
                        case 24:
                            self.ImportWindow.ImpDataType.setCurrentIndex(3)
                self.ImportWindow.FrHead.setValue(int(fmeta[2]))
                self.ImportWindow.ImpByteOrder.setValue(1) # 'b'
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
                        self.ImportWindow.ImpDataType.setCurrentIndex(1)
                        tnote = '8-bit Signed Integer'
                    case 1:
                        self.ImportWindow.ImpDataType.setCurrentIndex(3)
                        tnote = '16-bit Signed Integer'
                    case 2:
                        self.ImportWindow.ImpDataType.setCurrentIndex(5)
                        tnote = '32-bit Real Float'
                    case 3:
                        tnote = '16-bit Complex Signed Integer, unsupported'
                    case 4:
                        tnote = '32-bit Complex Float, unsupported'
                    case 6:
                        self.ImportWindow.ImpDataType.Value = 'uint16'
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
            print('HDF5')
        else:
            getDimFromName(self.ImportWindow.ImpFilePath.text())
            self.ImportWindow.ImpDataType.setCurrentIndex(5) # 'single'
            notes = "Custom import"
    else:
        notes = "File path is invalid"
        err = -1
    
    self.ImportWindow.ImpFileMetaNotes.setText(notes)
    if self.ImportWindow.ImpDataType.currentIndex() == 0 and  err != -1:
        warnDiag = qtw.QMessageBox()
        warnDiag.setIcon(qtw.QMessageBox.Warning)
        warnDiag.setText("The data type indicated in the file's metadata is not supported/recognized.")
        warnDiag.setWindowTitle("Invalid Data Type!")

    #% Reset import range selections
    gatherImportOptions(self)
    rangeImportExport(self, self.ImportWindow.DNPxX)
    rangeImportExport(self, self.ImportWindow.DNFrX)
    importBoxInput(self)

def importBoxInput(self):
    # Sub functions
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
        # + np.prod(nFr)*(2*np.floor(np.sqrt(np.sum((nPx/2)**2)))+1) /  # self.Image.IntgAnn
        # + np.prod(nFr)*10 + np.prod(nPx)*2  /                         # self.Image
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

    def checkGPUMEM(nPx,nFr):
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
            
    self.ImportWindow.ImpEstFilesize.setText("")
    notes = ""
    dfrn_src = real_src = self.sender()

    if os.path.isfile(self.ImportWindow.ImpFilePath.text()):
        # Update Diffraction and Real-space import ranges; use dummy event if source is not a range UI
        if (not hasattr(self.sender(),'accessibleDescription')) or (not "Dfrn" in self.sender().accessibleDescription()):
            dfrn_src = self.ImportWindow.IPxD
        if (not hasattr(self.sender(),'accessibleDescription')) or (not "Real" in self.sender().accessibleDescription()):
            real_src = self.ImportWindow.IFrD
    
    gatherImportOptions(self)
    dnote,_,_,nPx,_ = rangeImportExport(self, dfrn_src)
    rnote,_,_,nFr,_ = rangeImportExport(self, real_src)
    
    notes = dnote+rnote
    
    # Current dataset dimensions
    irng = [nPx,nFr]

    # Allow for virtual memory mapping in some situations
    if self.ImportWindow.FrHead.value() == 0 and self.ImportWindow.FrFoot.value() == 0 \
        and (not self.ImportWindow.HDF5Button.isChecked() or self.ImportWindow.DataOffset.value()) \
        and self.ImportWindow.ImpByteOrder.currentData() == self.C.SysEndian \
        and not 'int' in self.ImportWindow.ImpDataType.currentData() \
        and [self.ImportWindow.DNPxX.value(), self.ImportWindow.DNPxY.value(), self.ImportWindow.DNFrX.value(), self.ImportWindow.DNFrY.value()]==irng:
        self.ImportWindow.ImpMemType.setEnabled(True)
    else:
        self.ImportWindow.ImpMemType.setEnabled(False)
        self.ImportWindow.ImpMemType.setCurrentIndex(0) #Physical Memory
    
    # Calculate dataset size and memory usage
    if self.ImportWindow.ImpDataType.currentIndex != 0:
        byte_size = getattr(self.ByteSize,self.ImportWindow.ImpDataType.currentData())
        self.T.EstSize = self.ImportWindow.DataOffset.value() + self.T.fileTail \
            + (self.ImportWindow.FrHead.value()+self.ImportWindow.DNPxX.value()*self.ImportWindow.DNPxY.value()*byte_size+self.ImportWindow.FrFoot.value()) \
            * self.ImportWindow.DNFrX.value()*self.ImportWindow.DNFrY.value()
        self.ImportWindow.ImpEstFilesize.setText("{} bytes, {:.2f} GiB".format(self.T.EstSize,self.T.EstSize/1024**3))

        if (self.ImportWindow.ImpDataType.currentData() != 'unknown') and (np.issubdtype(self.ImportWindow.ImpDataType.currentData(),np.integer)):
            if byte_size > 4:
                f = 'f8'
            else:
                f = 'f4'
            byte_size = getattr(self.ByteSize,f)
            notes = notes+"\nDataset will be converted into "+str(byte_size*8)+"-bit Real."
        
        notes = notes+"\nImport by "+self.ImportWindow.ImpMemType.currentText()+"\n"+checkMem(nPx,nFr,byte_size)
        notes = notes+"\n\n"+checkGPUMEM(nPx,nFr)
    
    # Allow to swap dataset/keep parameters if the dimensions are identical
    #self.ImportWindow.ImpKeepP.Enable = ~isempty(self.D) and isequal(irng, [self.D.NPxX self.D.NPxY self.D.NFrX self.D.NFrY])
    self.ImportWindow.ImpKeepP.setEnabled(irng == [self.D.NPxX, self.D.NPxY, self.D.NFrX, self.D.NFrY])
    if self.ImportWindow.ImpKeepP.isEnabled() == False:
        self.ImportWindow.ImpKeepP.setChecked(False)
    if self.ImportWindow.ImpKeepP.isChecked()==True:
        notes = notes+"\n\nSwapping dataset - keeping current setups/alignments etc."
    
    # update notes in the text field
    self.ImportWindow.ImpNotes.setText(notes)

def saveCallbacks():
    pass

def exportCallbacks():
    pass

def axeDirCallbacks():
    pass

def displayCallbacks():
    pass

def realSpaceROICallbacks():
    pass

def clearDetectors(self):

        detectorList = [
            "adfPt",
            "adfInnerCirc",
            "adfOuterCirc",
            "tbPt",
            "tbCirc"]

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
        #set(findobj(self.Axes.Dfrn.Children,'-regexp','Tag',"Custom "),'Visible',0) #TODO
        # Scan direction alignment
        #delete(findobj(self.Axes.Dfrn,'Tag','ScanDirAnnot')) #TODO

def detectorModeCallbacks(self):
    dmod = self.DetrMode.currentData()
    enableWindows(self,False) # Enable windows
    clearDetectors(self) # Clear ROIs on Diffraction #TODO deletes tbCirc on initial alignment?

    # Clear Real-space images if not switching to alignment or preview
    if dmod not in ["AlignMod","PrvwMod"]:
        for ii in self.G.RealID:
            if not "Mask" in ii:
                getattr(self.Fig,ii).ax.cla()
                getattr(self.Fig,ii).canvas.draw()

    # Enable/Disable CoM/DPC related buttons/images
    for btn in self.G.CoM_btns:
        btn.setEnabled(dmod in ["CoMMod","DPCMod"]) 

    if dmod in ["CoMMod","DPCMod"]:
        # add all images to dropdown list in the Settings Window and
        # Subsitute "CoM"/"DPC" in image names and window titles
        imageNames = [re.sub('DPC|CoM',dmod[:3],ii) for ii in self.G.ImgNm]

        self.SettingsWindow.DispImage.clear()
        for itemText,itemID in zip(imageNames,self.G.ImgID):
            self.SettingsWindow.DispImage.addItem(itemText,itemID) # drop down items
            getattr(self.Fig,itemID).setWindowTitle(itemText) # window title
        
        # Subsitute "CoM"/"DPC" in button text
        for btn in self.G.CoM_btns:
            re.sub('DPC|CoM',dmod[:3],btn.text())
        
    else:
        self.SettingsWindow.DispImage.clear()
        for itemText,itemID in zip(self.G.ImgNm,self.G.ImgID):
            if "CoM" not in itemText:
                self.SettingsWindow.DispImage.addItem(itemText,itemID) # drop down items
            else:
                getattr(self.Fig,itemID).setVisible(False) # Image windows


    # Show primary diffraction/real-space image when mode changes unless in Preview mode
    self.Fig.Dfrn.setVisible(dmod != "PrvwMod")
    self.Fig.Real.setVisible(dmod != "PrvwMod")

    # Special case for Import Preview Mode
    if dmod == "PrvwMod":
        # Keep only "Preview" image
        self.SettingsWindow.DispImage.clear()
        self.SettingsWindow.DispImage.addItem("Preview","Preview")

        # Hide other UIs
        self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.MiscTab),False)
        self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.InfoTab),False)
        self.SaveWindow.SaveTabGroup.setTabVisible(self.SaveWindow.SaveTabGroup.indexOf(self.SaveWindow.ExportTab),False)
        
        self.Fig.Preview.setVisible(True)
        self.ImportWindow.setVisible(True)
        self.SettingsWindow.setVisible(True)
    else:
        self.P.DetrMode = self.DetrMode.currentData() # Note current mode
        # Remove "Preview" image from drop down
        self.SettingsWindow.DispImage.removeItem(self.SettingsWindow.DispImage.findData("Preview"))
        self.Fig.Preview.setVisible(False)

        # Show all UIs
        self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.MiscTab),True)
        self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.InfoTab),True)
        self.SaveWindow.SaveTabGroup.setTabVisible(self.SaveWindow.SaveTabGroup.indexOf(self.SaveWindow.ExportTab),True)

    # Define images in the saving list
    self.SaveWindow.SaveImgList.clear()
    self.SaveWindow.SaveImgList.addItems([self.SettingsWindow.DispImage.itemData(ii) for ii in range(self.SettingsWindow.DispImage.count())])
    #mockUICallbacks(self,self.SaveImgPrefix)  # Update Image saving prefix #TODO
    #mockUICallbacks(self,self.ShowDfrnAxes) # Update diffraction axis annotations #TODO

    # Set detector size when transmitted beam is aligned the first time
    if not(self.P.TransBeamInit) and (dmod != "AlignMod"):
        self.AnnRi.blockSignals(True)
        self.AnnRi.setValue((self.TBR.value(),(self.TBR.value() + self.P.RMax)/3))
        self.AnnRi.blockSignals(False)
        self.VrApR.setValue(self.TBR.value())
        self.P.VrApXY = self.B0
        self.P.TransBeamInit = 1

    #set(self.G.DetrUI,'Visible','off')  # Diffraction detector UI
    # hide custom mask maths tab
    self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.MathTab),False)

    match dmod:
        case "PrvwMod":
            self.DfrnDetrTabGroup.setCurrentIndex(0)
            #previewCallbacks(self) #TODO
        case "AlignMod":
            # Create transmitted beam annotation, allow for disk as large as the entire diffraction pattern
            if self.A.tbCirc is None:
                self.A.tbCirc = InteractiveCircle(center = self.B0, radius = self.TBR.value(), axis=self.Fig.Dfrn.ax, color='r')
                self.A.tbCirc.connect()
                self.A.tbCirc.updateCircle.connect(lambda: moveTransBeam(self))
            
            self.DfrnDetrTabGroup.setCurrentIndex(1)
            transBeamCallbacks(self)
            # display the total pacbed and resulting image to start
            self.Image.Dfrn = self.Fig.Dfrn.ax.imshow(self.Data.sum(axis=0).reshape(self.D.NPx))
            self.Image.Real = self.Fig.Real.ax.imshow(self.Data.sum(axis=1).reshape(self.D.NFrY,self.D.NFrX))
            self.Image.Dfrn.figure.set_facecolor('black')
            self.Image.Real.figure.set_facecolor('black')
            self.Fig.Dfrn.setVisible(True)
            self.Fig.Real.setVisible(True)
            self.Fig.Dfrn.ax.axis(self.P.DfrnAxLim)
            self.Fig.Real.ax.axis(self.P.RealAxLim)
            self.Fig.Dfrn.canvas.draw()
            self.A.tbCirc.updateBackground()
            self.Fig.Real.canvas.draw()
        case "AnnMod":
            self.DfrnDetrTabGroup.setCurrentIndex(2)
            self.dpcControls.setVisible(False)
            self.comControls.setVisible(False)
            #annularDetectorCallbacks(self) #TODO
        case "CoMMod"|"DPCMod":
            self.DfrnDetrTabGroup.setCurrentIndex(2)
            self.dpcControls.setVisible("DPC" in dmod)
            self.comControls.setVisible(True)
            #annularDetectorCallbacks(self) #TODO
            #plotImage(self, 'ColorWheel') # Plot ColorWheel #TODO
            self.Fig.CoMPhMag.activateWindow()
            self.Fig.ColorWheel.activateWindow()
            if not self.P.ScanDirInit:
                pass#flashBackground(self, self.ScanDirGrid) # Flashing to align scan direction #TODO
        case "VrApMod": # 'Virtual Aperture'
            self.DfrnDetrTabGroup.setCurrentIndex(3)
            #virtualApertureCallbacks(self) #TODO
        case "CustMod":
            self.DfrnDetrTabGroup.setCurrentIndex(4)
            self.SettingsWindow.SettingsTabGroup.setTabVisible(self.SettingsWindow.SettingsTabGroup.indexOf(self.SettingsWindow.MathTab),True)
            #customDetectorCallbacks(self) #TODO
            self.Fig.DfrnMask.activateWindow()

def plotImage(self,id):
    pass

def datasetOptCallbacks():
    pass

def previewCallbacks():
    pass

def transBeamCallbacks(self):
    match self.sender():
        case self.DetrMode: # Entering mode
            self.Fig.Dfrn.canvas.draw()
            self.Fig.Dfrn.activateWindow() # Select `Dfrn` image
            # If this is the initializing alignment, then do swap byte check and auto-align
            if not self.P.TransBeamInit:
                pass#datasetOptCallbacks(app, event) #TODO # checks for nans and asks if user wants to swap byteorder
                #autoAlign() #TODO
            #enableWindows(app,true) # Enable windows #TODO

        case self.UpdateImages: # Update images
            # Create a summed image of all diffraction patterns simply for alignment and calibration
            self.Image.DfrnMask = self.Fig.DfrnMask.ax.imshow(np.ones(self.D.NPx,self.D.DataType))
            self.Fig.DfrnMask.canvas.draw()
            self.Image.Real.set_data(np.reshape(self.Data.sum(axis=1), self.D.NFr))
            self.Image.Real.autoscale(True)
            self.Fig.Real.canvas.draw()

        case self.TBAutoAlign: # Auto-align
            pass#autoAlign() #TODO

        case self.TBCrossAlign: # Align transmitted beam via two crossed lines
            pass#crossAlign() #TODO
        
    # Update dependent variables
    moveTransBeam(self)

def moveTransBeam(self):
    """ Function to sync UIs/ROIs depending on the central beam location """
    b0 = np.array([self.TBX.value(),self.TBY.value()])
    r = max(self.TBR.value(),np.finfo(np.single).eps)
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
        case self.A.tbCirc:
            b0 = self.sender().center
            r = self.sender().radius

    # Restrict transmitted beam location/size
    b0 = b0.clip([1,1],nPix)
    self.B0 = b0
    self.P.RMax = np.ceil(np.linalg.norm(abs(self.P.DfCtr-b0)+self.P.DfCtr)) # Find the max allowed radius
    r = np.clip(r,np.finfo(np.single).eps,self.P.RMax) # 0 < r <= RMax

    # avoid triggering a valueChanged loop by blocking signals
    self.TBX.blockSignals(True)
    self.TBY.blockSignals(True)
    self.TBR.blockSignals(True)
    self.TBX_NF.blockSignals(True)
    self.TBY_NF.blockSignals(True)
    self.TBR_NF.blockSignals(True)
    self.AnnRi.blockSignals(True)
    self.Alpha.blockSignals(True)
    self.mradPx.blockSignals(True)
    self.VrApR.blockSignals(True)

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
    if (self.sender() is not self.A.tbCirc) and (self.A.tbCirc is not None):
        self.A.tbCirc.center = b0
        self.A.tbCirc.radius = r
        self.A.tbCirc.redraw()

    # unblock trigger signals
    self.TBX.blockSignals(False)
    self.TBY.blockSignals(False)
    self.TBR.blockSignals(False)
    self.TBX_NF.blockSignals(False)
    self.TBY_NF.blockSignals(False)
    self.TBR_NF.blockSignals(False)
    self.AnnRi.blockSignals(False)
    self.Alpha.blockSignals(False)
    self.mradPx.blockSignals(False)
    self.VrApR.blockSignals(False)

    detrCoordCallbacks(self)


def virtualApertureCallbacks():
    pass

def customDetectorCallbacks():
    pass

def mathCallbacks():
    pass

def saveVect():
    pass

def showWindowCallbacks():
    pass

def resizeWindowCallbacks(self):
    # set the space: `Dfrn` or `Real`; get updated height and width, add mpl decor size
    if self.sender() in [self.SettingsWindow.WdwWDfrn,self.SettingsWindow.WdwHDfrn,self.SettingsWindow.WdwSetDfrn,self.SettingsWindow.WdwSetAllDfrn]:
        sp = "Dfrn"
        width = self.SettingsWindow.WdwWDfrn.value() + self.C.mplDecor.width()
        height = self.SettingsWindow.WdwHDfrn.value() + self.C.mplDecor.height()
    else:
        sp = "Real"
        width = self.SettingsWindow.WdwWReal.value() + self.C.mplDecor.width()
        height = self.SettingsWindow.WdwHReal.value() + self.C.mplDecor.height()

    match self.sender():
        case self.SettingsWindow.WdwSetDfrn|self.SettingsWindow.WdwSetReal: # Set size for just one image window
            id = self.SettingsWindow.DispImage.currentData() # Default image window to resize

            # If the selected image is not of that space, then resize that space's primary image window instead
            if getattr(self.Fig,id).space != sp:
                id = sp
            
            # set the height and wdith
            getattr(self.Fig,id).resize(width,height)
        
        case self.SettingsWindow.WdwSetAllDfrn|self.SettingsWindow.WdwSetAllReal: # Set all image windows of the given space to the same size
            for fig in self.G.ImgFig:
                if fig.space == sp:
                    fig.resize(width,height)

def updateImagesCallbacks(self,event):
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
            if self.DetrMode.Value != "PrvwMod":
                realSpaceROICallbacks(self)

def unlockScanDir(self):
    if self.ScanDirUnlock.isChecked():
        self.ScanDirUnlock.setIcon(self.unlock)
    else:
        self.ScanDirUnlock.setIcon(self.lock)

def debugImport(self):
    self.fname = 'C:/Users/bess0001/Downloads/4DSTEM_data/scan_x128_y128.raw'
    self.ImportWindow.ImpFilePath.setText(self.fname)
    self.ShowImportWdw.trigger()
    for widget in self.ImportWindow.children():
        widget.setEnabled(True)
    on_ImpFileSelect_clicked(self)
    self.ImportWindow.ImportDataButton.click()


def breakpoint(self):
    print()

def slotsSignals(self):
    # debug
    self.enableAllUIs.triggered.connect(lambda:enableWindows(self,True))
    self.debugImport.triggered.connect(lambda:debugImport(self))
    self.breakpoint.triggered.connect(lambda:breakpoint(self))

    # brightness/contrast/gamma
    self.SettingsWindow.DispBrightnessReset.clicked.connect(lambda: self.SettingsWindow.DispBrightness.setValue(50))
    self.SettingsWindow.DispContrastReset.clicked.connect(lambda: self.SettingsWindow.DispContrast.setValue(50))
    self.SettingsWindow.DispGamma.setValue(1)
    self.SettingsWindow.DispGammaReset.clicked.connect(lambda: self.SettingsWindow.DispGamma.setValue(1))


    # resize window callabcks
    self.SettingsWindow.WdwSetDfrn.clicked.connect(lambda:resizeWindowCallbacks(self))
    self.SettingsWindow.WdwSetAllDfrn.clicked.connect(lambda:resizeWindowCallbacks(self))
    self.SettingsWindow.WdwSetReal.clicked.connect(lambda:resizeWindowCallbacks(self))
    self.SettingsWindow.WdwSetAllReal.clicked.connect(lambda:resizeWindowCallbacks(self))

    # change lock/unlock icon when clicked
    self.ScanDirUnlock.clicked.connect(lambda: unlockScanDir(self))

    # Import window slots/signals
    self.ShowImportWdw.triggered.connect(lambda:on_ShowImportWdw_triggered(self))
    self.ImportWindow.ImportCancelButton.clicked.connect(lambda:on_ShowImportWdw_triggered(self))
    self.ImportWindow.ImpFileSelect.clicked.connect(lambda:on_ImpFileSelect_clicked(self))
    self.ImportWindow.ImportDataButton.clicked.connect(lambda:on_ImportDataButton_clicked(self))
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

    # save window slots/signals
    self.SaveWindow.SaveImgSelectAll.clicked.connect(lambda isChecked: self.SaveWindow.SaveImgList.selectAll() if isChecked else self.SaveWindow.SaveImgList.clearSelection())

    # menu action slots/signals
    self.actionShow_Diffraction_Pattern.triggered.connect(lambda: self.Fig.Dfrn.setVisible(self.actionShow_Diffraction_Pattern.isChecked()))
    self.actionShow_Diffraction_Mask.triggered.connect(lambda: self.Fig.DfrnMask.setVisible(self.actionShow_Diffraction_Mask.isChecked()))
    self.actionShow_Real_Space_Image.triggered.connect(lambda: self.Fig.Real.setVisible(self.actionShow_Real_Space_Image.isChecked()))
    self.actionShow_Real_Space_Mask.triggered.connect(lambda: self.Fig.RealMask.setVisible(self.actionShow_Real_Space_Mask.isChecked()))
    self.actionShow_Center_of_Mass_Magnitude_CoM.triggered.connect(lambda: self.Fig.CoMMag.setVisible(self.actionShow_Center_of_Mass_Magnitude_CoM.isChecked()))
    self.actionShow_Center_of_Mass_X.triggered.connect(lambda: self.Fig.CoMX.setVisible(self.actionShow_Center_of_Mass_X.isChecked()))
    self.actionShow_Center_of_Mass_Y.triggered.connect(lambda: self.Fig.CoMY.setVisible(self.actionShow_Center_of_Mass_Y.isChecked()))
    self.actionShow_Colorwheel.triggered.connect(lambda: self.Fig.ColorWheel.setVisible(self.actionShow_Colorwheel.isChecked()))
    self.actionShow_Differential_Center_of_Mass_dCoM.triggered.connect(lambda: self.Fig.dCoM.setVisible(self.actionShow_Differential_Center_of_Mass_dCoM.isChecked()))
    self.actionShow_Integrated_Center_of_Mass_iCoM.triggered.connect(lambda: self.Fig.iCoM.setVisible(self.actionShow_Integrated_Center_of_Mass_iCoM.isChecked()))
    self.actionShow_Phase_Magnitude.triggered.connect(lambda: self.Fig.CoMPhMag.setVisible(self.actionShow_Phase_Magnitude.isChecked()))
    self.actionShow_Phase_Vector_Image.triggered.connect(lambda: self.Fig.CoMPh.setVisible(self.actionShow_Phase_Vector_Image.isChecked()))
    self.actionShow_All_Windows.triggered.connect(lambda: showAllWindows(self))
    self.actionHide_All_Windows.triggered.connect(lambda: hideAllWindows(self))
    self.ShowSettingsWdw.triggered.connect(lambda: self.SettingsWindow.show())
    self.ShowSettingsWdw.triggered.connect(lambda: self.SettingsWindow.activateWindow())
    self.ShowSaveWdw.triggered.connect(lambda: self.SaveWindow.show())
    self.ShowSaveWdw.triggered.connect(lambda: self.SaveWindow.activateWindow())

    self.DetrMode.currentIndexChanged.connect(lambda: detectorModeCallbacks(self))

    # detector slider/numerical field connections
    self.AnnRi_NF.valueChanged.connect(lambda: moveAnnR(self))
    self.AnnRo_NF.valueChanged.connect(lambda: moveAnnR(self))
    self.AnnRi.valueChanged.connect(lambda: moveAnnR(self))

    # transmitted beam controls
    self.TBX.valueChanged.connect(lambda: moveTransBeam(self))
    self.TBY.valueChanged.connect(lambda: moveTransBeam(self))
    self.TBR.valueChanged.connect(lambda: moveTransBeam(self))
    self.Alpha.valueChanged.connect(lambda: moveTransBeam(self))
    self.mradPx.valueChanged.connect(lambda: moveTransBeam(self))

    #self.TBX_NF.valueChanged.connect(lambda: moveTransBeam(self))
    #self.TBY_NF.valueChanged.connect(lambda: moveTransBeam(self))
    #self.TBR_NF.valueChanged.connect(lambda: moveTransBeam(self))
    
    # settings opacity slider
    self.SettingsWindow.DispMaskOpa.valueChanged.connect(lambda: maskOpacity(self))


    
def toggleWindows(self):
    print(self.sender())
    match self.sender():
        case self.Fig.Dfrn:
            print(999)

def showAllWindows(self):
    from callbacks.guiClass import ImageWindow
    for obj in gc.get_objects():
        if isinstance(obj, ImageWindow):
            obj.setVisible(True)
    self.actionShow_All_Windows.setChecked(True)
    self.actionHide_All_Windows.setChecked(False)
    self.activateWindow()

def hideAllWindows(self):
    from callbacks.guiClass import ImageWindow
    for obj in gc.get_objects():
        if isinstance(obj, ImageWindow):
            obj.setVisible(False)
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
    self.ShowImportWdw.setChecked(not self.ImportWindow.isVisible())
    self.ImportWindow.setVisible(self.ShowImportWdw.isChecked())
    
    # set default button to "Select"
    self.ImportWindow.ImportDataButton.setDefault(False)
    self.ImportWindow.ImportDataButton.setAutoDefault(False)
    self.ImportWindow.ImpFileSelect.setDefault(True)
    self.ImportWindow.ImpFileSelect.setAutoDefault(True)

    if self.ShowImportWdw.isChecked():
        hideAllWindows(self)
        self.ImportWindow.activateWindow()
    else:
        unHideOpenWindows(self)
    


def plotColorwheel(self):
    # Make ColorWheel for DPC/CoM imaging - this color scheme will stay constant for all DPC/CoM images
    # regardless of their individual parameters like scan or detector rotation for consistency
    r = 256
    xgrid,ygrid = np.meshgrid(np.linspace(1-r,r,int(2*r)),np.linspace(1-r,r,int(2*r)))
    
    # Get atan from -pi to pi
    a = np.arctan2(ygrid, xgrid)

    # shift the negative values of atan up by 2*pi
    a[a<0]+=2*np.pi
    
    # make circular mask for colorwheel
    mask = (xgrid**2 + ygrid**2) < r**2

    # plot colorwheel with mask    
    self.Image.ColorWheel = self.Fig.ColorWheel.ax.imshow(a,alpha=mask.astype(float),cmap='hsv',interpolation="None")
    self.Fig.ColorWheel.maskOpa = 100

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

def drawAnnDetr(self):
    """ initiallize the annular detector annotations """
    # define center location and starting radii for annular detector
    c = self.B0
    r1 = self.AnnRi.value()[0]/2
    r2 = self.AnnRi.value()[1]/2

    # # generate two points that a user can drag to control the annular detector
    if self.A.adfPt is None:
        self.A.adfPt = DraggablePoint(self.Fig.Dfrn.ax.scatter(c[0]+np.array([r1,r2]),c[1]-np.array([r1,r2]),s=25,c='r'))
        self.A.adfPt.connect()
        self.A.adfPt.redrawCircle.connect(lambda: moveAnnR(self))
        self.pointPickerRadius.connect(lambda: self.A.adfPt.setPointPickerRadius(self.screen().physicalDotsPerInch()))

    # add circles to pacbed plot, these are not draggable
    if self.A.adfInnerCirc is None:
        self.A.adfInnerCirc = self.Fig.Dfrn.ax.plot(self.A.circX*r1*np.sqrt(2)+c[0],self.A.circY*r1*np.sqrt(2)+c[1],color='r')[0]
    if self.A.adfOuterCirc is None:
        self.A.adfOuterCirc = self.Fig.Dfrn.ax.plot(self.A.circX*r2*np.sqrt(2)+c[0],self.A.circY*r2*np.sqrt(2)+c[1],color='r')[0]

def annDetrVisibility(self,state):
    # show/hide adf annotations
    self.A.adfInnerCirc._visible = state
    self.A.adfOuterCirc._visible = state
    self.A.adfPt.point.set_visible(state)
    self.Fig.Dfrn.canvas.draw()
    
def replotCirc(self):
    """ update the ciruclar annotations on the diffraction pattern """
    
    r1 = self.AnnRi.value()[0]/2
    self.A.adfInnerCirc.set_data(self.A.circX*r1+self.B0[0],self.A.circY*r1+self.B0[1])
    
    r2 = self.AnnRi.value()[1]/2
    self.A.adfOuterCirc.set_data(self.A.circX*r2+self.B0[0],self.A.circY*r2+self.B0[1])
    
    # update diffraction pattern figure
    self.Fig.Dfrn.canvas.draw()

def moveAnnR(self):
    # get QRangeSlider values
    innerRadius,outerRadius = self.AnnRi.value()
    
    # get diffraction scale set by user during alignment
    scale = self.DfPxR

    # get inner/outer adf radii from the calling widget
    match self.sender():
        # draggable points on annular detector annothation
        case self.A.adfPt:
            innerRadius, outerRadius = np.rint(np.linalg.norm(self.B0-self.A.adfPt.point.get_offsets(),axis=1)/self.D.annWidth).astype(int)
        # Inner Radius QDoubleSpinBox
        case self.AnnRi_NF:
            innerRadius = round(self.AnnRi_NF.value()/self.D.annWidth/scale)
        # Outer Radius QDoubleSpinBox 
        case self.AnnRo_NF:
            outerRadius = round(self.AnnRo_NF.value()/self.D.annWidth/scale)
            

    # allow user to drag inner/outer annulus over the other, swapping their relationships
    if innerRadius>outerRadius:
        innerRadius,outerRadius = outerRadius,innerRadius
        self.A.adfInnerCirc,self.A.adfOuterCirc = self.A.adfOuterCirc,self.A.adfInnerCirc

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
    if self.sender() is not self.A.adfPt:
        centers = self.A.adfPt.point.get_offsets()-self.B0
        angles = np.arctan2(centers[:,0],centers[:,1])
        centers = np.array([np.sin(angles),np.cos(angles)]).T*np.array([[innerRadius],[outerRadius]])*self.D.annWidth+self.B0
        self.A.adfPt.point.set_offsets(centers)

    # update circles on adf detector and refresh diffraction figure (self.Fig.Dfrn)
    replotCirc(self)

    #if isStaticEvt(evt): #TODO
    #    mockUICallbacks(app,self.SaveImgPrefix) # Update saving prefix

    # Whether to update segments as well #TODO
    #if dmod == "DPCMod":
    #    self.moveSeg()

    # refresh real-space image given new inner/outer radii
    # (add one to outer limit because python doesn't include the last term of the range)
    if len(self.Fig.Real.ax.images)==0:
        self.Image.Real = self.Fig.Real.ax.imshow(self.Data.sum(axis=1).reshape(self.D.NFrY,self.D.NFrX))
    else:
        self.Image.Real.set_data(self.adfImages[:,:,innerRadius:outerRadius+1].sum(axis=2))
    self.Image.Real.autoscale()
    self.Fig.Real.canvas.draw()
    #maskOpacity(self)

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
            drawAnnDetr(self)
            pass#annularDetectorCallbacks(self,struct("Source",self.DCSys,"EventName","UpdateCoord")) #TODO
        case "VrApMod":
            pass#virtualApertureCallbacks(self,struct("Source",self.DCSys,"EventName","UpdateCoord")) #TODO
        case "CustMod":
            pass#customDetectorCallbacks(self,struct("Source",self.DCSys,"EventName","UpdateCoord")) #TODO

def annularDetectorCallbacks(self):
    integrateAnnular(self)

def maskOpacity(self):
    alpha = self.SettingsWindow.DispMaskOpa.value()/100 # mask opacity slider
    k = self.A.k.T # distance from optic axis
    mask = ((k>=self.AnnRi.value()[0])&(k<=self.AnnRi.value()[1]))*(alpha)+1-alpha
    self.Image.Dfrn.set_alpha(mask)
    self.Fig.Dfrn.canvas.draw()

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


    def run(self):
        if self.isInt:
            self.DataMemmap = np.memmap(self.filename, dtype=self.dType, mode = "c", offset=self.dataOffset, shape=(self.frameCount,self.pixCount))
            self.Data = np.zeros(shape=self.DataMemmap.shape,dtype=np.float32)
            nThreads = psutil.cpu_count(logical=False)
            with ThreadPool(processes=nThreads) as pool:
                pool.map(self.convertInt2Float,range(self.DataMemmap.shape[0]))
            pool.join()
        else:
            self.Data = np.fromfile(self.filename, dtype=self.dataType, count=self.frameCount, offset=self.dataOffset)["data"]
        self.result.emit(self.Data)
        self.finished.emit()
    
    def convertInt2Float(self,val):
        self.Data[val,:] = self.DataMemmap[val,:].astype(np.float32)

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
        if re.findall("\d+x\d+x\d+x\d+",filename):
            s = re.findall("\d+x\d+x\d+x\d+",filename)
            nopix,nopiy,framesx,framesy = [int(i) for i in re.split("x",s[0])]
        elif re.findall("_x\d+_y\d+",filename):
            s = re.findall("\d+",filename)
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

    # List all images' names in `self.ImpSubImg`
    pdim = np.zeros(len(self.T.dm)-1)
    self.ImportWindow.ImpSubImg.setEnabled(True)
    for i in range(pdim.size):
        self.ImportWindow.ImpSubImg.addItem(self.T.dm[i].Name)
        pdim[i] = np.array(self.T.dm[i].Dimensions).prod()

    # Select sub-image with the largest dimension; unless manually selected
    if self.sender() is not self.ImportWindow.ImpSubImg:
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

def readEMPAD(self):
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
    from callbacks.guiClass import ImageWindow
    #self.T.progDLG = progDLG(self, 'Preparing data ...', "Data Preparation"); #TODO

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
    self.Alpha.Value = 12
    self.P.VrApXY = self.P.DfCtr

    # Axes limits, restrict to avoid rounding to pixels outside the image
    self.P.DfrnAxLim = [0, self.D.NPxX, 0, self.D.NPxY]
    self.P.RealAxLim = [0, self.D.NFrX, 0, self.D.NFrY]

    # initialize diffraction space axis limits
    self.Fig.Dfrn.ax.set_xbound(self.P.DfrnAxLim[0:2])
    self.Fig.Dfrn.ax.set_ybound(self.P.DfrnAxLim[2:4])
    self.Fig.Dfrn.canvas.draw()

    # initialize real space axis limits
    self.Fig.Real.ax.set_xbound(self.P.RealAxLim[0:2])
    self.Fig.Real.ax.set_ybound(self.P.RealAxLim[2:4])
    self.Fig.Real.canvas.draw()

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
    #exportCallbacks(self, struct("Source",self.ExpPxPart,"EventName",[],"Value",0))#TODO
    #exportCallbacks(self, struct("Source",self.ExpFrPart,"EventName",[],"Value",0))#TODO

    # initiate image display parameters for all ImageWindows
    for ax in [getattr(self.Fig,child) for child in dir(self.Fig)]:
        if isinstance(ax,ImageWindow):
            ax.brightness = 50
            ax.contrast = 50
            ax.gamma = 1
            ax.maskOpa = 0
            ax.vecField = 0

    self.UpdateImages.trigger() # Update all images f
    #delete(self.T.progDLG);  # Close progress bar and Enable panel objects #TODO

    #initialize SettingsWindow and move next to main UI window
    self.SettingsWindow.SettingsTabGroup.setCurrentIndex(0) # "Display" tab
    self.SettingsWindow.setVisible(True)
    pos = self.SettingsWindow.geometry()
    pos.moveLeft(self.geometry().getRect()[0]+self.geometry().getRect()[2]+self.C.decorPad*2)
    pos.moveTop(self.geometry().getRect()[1])
    self.SettingsWindow.setGeometry(pos)

    #mockUICallbacks(self,self.DetrMode)  # Enter intializing alignment #TODO
    self.DetrMode.setCurrentIndex(self.DetrMode.findData("AlignMod"))
    #detectorModeCallbacks(self)

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

    prepareData(self)
    integrateAnnular(self)
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

    # Import Data is the only option to start
    # turn off ALL actions
    for action in self.findChildren(qtw.QAction):
        action.setEnabled(True)

    # update annular QRangeSlider to match
    self.AnnRi.blockSignals(True)
    self.AnnRi.setValue((self.AnnRi.minimum(),self.AnnRi.maximum()))
    self.AnnRi.blockSignals(False)

    # re-enable windows
    enableWindows(self,True)

    # start alignment mode
    self.DetrMode.setCurrentIndex(1)

def startupFcn(self):
    from callbacks.guiClass import ImageWindow, SettingsWindow, SaveWindow, ImportWindow

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
        self.Fig.ColorWheel = ImageWindow(id = "ColorWheel", name = "Color Wheel for Phase Direction", sp = "ColorWheel", typ = "CoM", cmap = "hsv", pos = [self.C.shc-self.C.sz-self.C.mplDecor.width(), self.C.sz+2*(self.C.decorPad+self.C.titleHeight)+self.C.mplDecor.height() + self.C.vOffset, self.C.sz/2 + self.C.mplDecor.width(), self.C.sz/2 + self.C.mplDecor.height()])
        plotColorwheel(self) 

        # Variable names, image names and image types (tag) for all patterns'/images' figures/axes/images
        self.G.ImgID = [obj for obj in self.Fig.__dict__] # ID/fieldnames under `self.Axes` `self.Fig` `self.Image` `self.ImgD` etc
        self.G.ImgSp = [getattr(self.Fig,ImgID).space for ImgID in self.G.ImgID] # Spaces ("Real"/"Dfrn")
        self.G.ImgTyp = [getattr(self.Fig,ImgID).type for ImgID in self.G.ImgID] # Types ("Primary", "CoM" related, "Mask", "Test")
        self.G.ImgNm = [getattr(self.Fig,ImgID).name for ImgID in self.G.ImgID] # Names/Titles

        # AND their Axes/Figure objects, as well as the gray overlay to disable them
        self.G.ImgAx = [getattr(self.Fig,ImgID).ax for ImgID in self.G.ImgID]
        self.G.ImgFig = [getattr(self.Fig,ImgID) for ImgID in self.G.ImgID]

        # Variable names for all diffraction-sized figures/axes/images AND THEN their Axes objects
        self.G.DfrnID = [ImgID for ImgID,space in zip(self.G.ImgID,self.G.ImgSp) if space == "Dfrn"]
        self.G.DfrnAx = [getattr(self.Fig,DfrnID).ax for DfrnID in self.G.DfrnID]

        # Variable names for all real-space-sized figures/axes/images AND THEN their Axes objects
        self.G.RealID = [ImgID for ImgID,space in zip(self.G.ImgID,self.G.ImgSp) if space == "Real"]
        self.G.RealAx = [getattr(self.Fig,RealID).ax for RealID in self.G.RealID]

        # Group all "Show ... Window" buttons related to CoM/DPC
        self.G.CoM_btns = [obj for obj in self.SettingsWindow.findChildren(qtw.QPushButton) if "CoM" in obj.objectName()]
        self.G.CoM_btns.extend([self.ShowColorWheelWdw,self.SettingsWindow.ShowColorWheelWdw_2])

        # Group all window `figure` `uifigure`
        self.G.AllFig = self.G.ImgFig.copy()
        self.G.AllFig.extend([self,self.SettingsWindow,self.ImportWindow,self.SaveWindow])

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

def gatherImportOptions(self):
    self.D.filePath = self.ImportWindow.ImpFilePath.text()
    [self.D.fileDir, self.D.fileName] = os.path.split(self.D.filePath)
    self.D.fileDir = self.D.fileDir+os.sep
    self.D.subImg = self.ImportWindow.ImpSubImg.currentText()

    # BYTES offset of: 1) the dataset from the beginning of file, 2) before and 3) after each frame
    self.D.Offset = self.ImportWindow.DataOffset.value()
    self.D.FrHead = self.ImportWindow.FrHead.value()
    self.D.FrFoot = self.ImportWindow.FrFoot.value()

    # Endianness (big 'b' or little 'l'), Data type of the dataset and Size in bytes of the data type
    self.D.ByteOrder = self.ImportWindow.ImpByteOrder.currentData()
    self.D.DataType = self.ImportWindow.ImpDataType.currentData()
    self.D.ByteSize = self.ByteSize.__getattribute__(self.D.DataType)

    # Physical or virtual memory loading
    self.D.mem = self.ImportWindow.ImpMemType.currentText()

    # Select GPU if acceleration is enabled AND not in Import Preview Mode
    self.D.GPU = self.ImportWindow.ImpGPU.currentText()
    #if not prvw and self.D.GPU: gpuDevice(self.D.GPU) #TODO

    # Dimensions of pixels/frames in file and import binning/sampling distance
    self.D.DNPxX = self.ImportWindow.DNPxX.value()
    self.D.DNPxY = self.ImportWindow.DNPxY.value()
    self.D.PxD = self.ImportWindow.IPxD.value()
    self.D.DNFrX = self.ImportWindow.DNFrX.value()
    self.D.DNFrY = self.ImportWindow.DNFrY.value()
    self.D.FrD = self.ImportWindow.IFrD.value()

    # Starting points and Number of pixels/frames after binning/sampling to import
    self.D.PxX1 = self.ImportWindow.IPxX1.value()
    self.D.PxY1 = self.ImportWindow.IPxY1.value()
    self.D.NPxX = self.ImportWindow.INPxX.value()
    self.D.NPxY = self.ImportWindow.INPxY.value()
    self.D.FrX1 = self.ImportWindow.IFrX1.value()
    self.D.FrY1 = self.ImportWindow.IFrY1.value()
    self.D.NFrX = self.ImportWindow.INFrX.value()
    self.D.NFrY = self.ImportWindow.INFrY.value()

    # Frequently used dimension parameters
    self.D.NPx = np.array([self.D.NPxX,self.D.NPxY])
    self.D.NPxS = self.D.NPxX * self.D.NPxY
    self.D.NFr = np.array([self.D.NFrX,self.D.NFrY])
    self.D.NFrS = self.D.NFrX * self.D.NFrY

    # Estimated memory usage for current dataset
    self.D.EstMem = self.T.EstMem

    # Swap dataset option+self.ImpNotes.Value
    self.D.KeepP = self.ImportWindow.ImpKeepP.isChecked()

    # Notes at import
    self.D.NoteFileMeta = self.ImportWindow.ImpFileMetaNotes.toPlainText()
    self.D.NoteImp = self.ImportWindow.ImpNotes.toPlainText()

    # H5 dataset path within the H5 file. if not set empty, the H5 library API will be called when importing
    self.D.h5ds = []
    if self.ImportWindow.HDF5Button.isChecked() and  "Physical Memory" in self.D.mem:
        self.D.h5ds = self.D.subImg

def rangeImportExport(self, src):
    # spinner upper/lower limits must be different, so now set lower limit `0` but force minimum to `1`
    if hasattr(src,'value'):
        val = np.maximum(src.value(), 1)
    
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
    if src == self.ImportWindow.findChild(qtw.QSpinBox,O+U+"D"):
        binDist = val # Binning/Sampling UI
    elif src == self.ImportWindow.findChild(qtw.QSpinBox,O+U+"X1"):
        initPoint[0] = val # Point-1 X UI
    elif src == self.ImportWindow.findChild(qtw.QSpinBox,O+U+"Y1"):
        initPoint[1] = val # Point-1 Y UI
    elif src == self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"X"):
        numPoints[0] = val # N-Points X UI
    elif src == self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"Y"):
        numPoints[1] = val # N-Points Y UI
    elif src in [self.ImportWindow.findChild(qtw.QSpinBox,"DN"+U+"X"), self.ImportWindow.findChild(qtw.QSpinBox,"DN"+U+"Y"), self.ImportWindow.findChild(qtw.QSpinBox,"Imp"+U+"Part"), self.ImportWindow.findChild(qtw.QSpinBox,"Exp"+U+"Part")]:
        # Reset range options if dataset raw dimension changes OR partial selection enables/disables
        self.ImportWindow.findChild(qtw.QSpinBox,O+U+"D").setMaximum(min(dnp)) # Update binning/sampling UI limits
        if O == "I" and U == "Fr": # Update preview frame limits
            self.PvFrX.setRange(0,dnp[0])
            self.PvFrX.setValue(dnp[0])
            self.PvFrY.setRange(0,dnp[1])
            self.PvFrY.setValue(dnp[1])
        binDist = 1
        initPoint = np.asarray([1,1])
        numPoints = dnp
    
    # In general, N-Points are determined by Point-1 and Binning/Sampling, unless N-Points are the source
    #s = [self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"X"), self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"Y")] != src # Whether N-Points X or Y are not the source
    #s = np.asarray([x in src for x in [self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"X"), self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"Y")]])
    if src==self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"X"):
        s = np.asarray([1])
    elif src==self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"Y"):
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
        pos = [initPoint,(numPoints-1)*binDist]; # Positions for Export ROI
        txt = "Real-space Range (in frames [fr])"
        u = " fr"
        txtb = "sampling "
    
    # Set Point-1 X & Y, N-Points X & Y and Binning/Sampling UIs
    self.ImportWindow.findChild(qtw.QSpinBox,O+U+"X1").setRange(0,l1[0])
    self.ImportWindow.findChild(qtw.QSpinBox,O+U+"Y1").setRange(0,l1[1])
    self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"X").setRange(0,ln[0])
    self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"Y").setRange(0,ln[1])
    self.ImportWindow.findChild(qtw.QSpinBox,O+U+"D").setRange(0,min(dnp))

    self.ImportWindow.findChild(qtw.QSpinBox,O+U+"X1").setValue(initPoint[0])
    self.ImportWindow.findChild(qtw.QSpinBox,O+U+"Y1").setValue(initPoint[1])
    self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"X").setValue(numPoints[0])
    self.ImportWindow.findChild(qtw.QSpinBox,O+"N"+U+"Y").setValue(numPoints[1])
    self.ImportWindow.findChild(qtw.QSpinBox,O+U+"D").setValue(binDist)

    # Try to update Export ROIs
    #if O == "E":
    #    set(findobj(self.G.(sp+"Ax"),'Tag',"Export "+sp+" ROI"), 'Position', pos)
    
    # Range notes
    tp = [x1 + u for x1 in [str(ints) for ints in numPoints]]

    if binDist > 1:
        tp = [x6 + u for x6 in [x4 + x5 for x4,x5 in list(zip([x3 + " from " for x3 in [txtb + x2 for x2 in tp]],[str(ints) for ints in endPoint-initPoint+1]))]]

    # If not from 1st to last
    s = np.maximum(initPoint>1,endPoint<dnp)
    for i in np.arange(len(s)):
        if s[i]:
            tp[i] = str(numPoints[i])+u+", "+str(initPoint[i]-1)+"/"+str(dnp[i]-endPoint[i])+u+" offset from start/end"
    notes = "{}:\n  X = {}-{} ({})\n  Y = {}-{} ({})\n".format(txt,*[items for sublist in zip(initPoint,endPoint,tp) for items in sublist])

    return notes,binDist,initPoint,numPoints,endPoint

# Function to unload data and clean all images
def unloadData(self, keep_p=False):
    importlib.reload(appClass)
    from callbacks.appClass import A,P,Image,Mask,D,Prev,Image

    """ Function to unload data and clean all images """
    enableWindows(self,False) # Disable windows for the data unload process
    self.setWindowTitle('Quant4D')
    # Whether to swap dataset only, without changing any existing parameters
    if not keep_p:
        # clear all axes
        for image in dir(self.Image):
            if not image.startswith("_"):
                setattr(self.Image,image,None)
                fig = getattr(self.Fig,image)
                fig.ax.cla()
                fig.canvas.draw()
        self.SettingsWindow.HistAxes.axes.cla()
        self.SettingsWindow.HistAxes.figure.canvas.draw()

        # clear annotations (lines and draggable points)
        for ii in dir(self.A):
            if type(getattr(self.A,ii)) in (DraggablePoint,matplotlib.lines.Line2D):#,InteractiveBox #TODO
                setattr(self.A,ii,None)

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

#def importData(self):
def on_ImportDataButton_clicked(self):
    assert(os.path.isfile(self.ImportWindow.ImpFilePath.text())), "File does not exist at the specified location"
    
    if os.path.isfile(self.ImportWindow.ImpFilePath.text()):
        # Set save/export filenames etc.
        self.setWindowTitle(self.D.fileName)
        self.SaveWindow.SaveDir.setText(self.D.fileDir)
        self.SaveWindow.SaveImgPrefix.setText(self.D.fileName.replace(self.D.fileExt,"")+"_")
        
        unloadData(self)
        gatherImportOptions(self)
        
        # TODO
        #if self.ImportWindow.MedipixButton.isChecked():
        #     readMRC(self)
        #elif self.ImportWindow.EMPADButton.isChecked():
        readEMPAD(self)

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
        self.warnDiag = qtw.QMessageBox()
        self.warnDiag.setIcon(qtw.QMessageBox.Warning)
        self.warnDiag.setText("File: "+self.ImportWindow.ImpFilePath.text()+" is not found!")
        self.warnDiag.setWindowTitle("File not found!")
        self.warnDiag.show()

def getDecorSize(self):
        decorSize = [self.geometry().x()-self.pos().x(), self.geometry().y()-self.pos().y()]
        return decorSize