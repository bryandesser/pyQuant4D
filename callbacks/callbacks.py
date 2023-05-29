import os
import re
import torch
import gc
import numpy as np
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from callbacks.utils import on_ImportDataButton_clicked, rangeImportExport, gatherImportOptions#, on_actionShow_Diffraction_Pattern_triggered
from callbacks.ioUtils import prepEMPAD, prepDM
from callbacks.imageUtils import moveAnnR, maskOpacity

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

    # add to combobox
    self.ImportWindow.ImpDataType.clear()
    for dtt,dt in zip(dataTypeText,dataType):
        self.ImportWindow.ImpDataType.addItem(dtt,dt)
    
    # default to "Select Data Type..." prompt
    self.ImportWindow.ImpDataType.setCurrentIndex(0)
    
    # default to "little endian"
    self.ImportWindow.ImpByteOrder.setCurrentIndex(0)

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
    dfrn_src = self.sender()
    real_src = self.sender()

    if os.path.isfile(self.ImportWindow.ImpFilePath.text()):
        # Update Diffraction and Real-space import ranges; use dummy event if source is not a range UI
        if not "Dfrn" in self.sender().accessibleDescription():
            dfrn_src = self.ImportWindow.IPxD
        if not "Real" in self.sender().accessibleDescription():
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

def on_DetrMode_currentIndexChanged(self):
    dmod = self.DetrMode.currentData()
    if dmod=="PrvwMod":
        self.DfrnDetrTabGroup.setCurrentIndex(0)
    elif dmod=="AlignMod":
        self.DfrnDetrTabGroup.setCurrentIndex(1)
    elif dmod=="AnnMod":
        self.DfrnDetrTabGroup.setCurrentIndex(2)
        self.dpcControls.setVisible(False)
        self.comControls.setVisible(False)
        # self.DetRot_NF.setEnabled(False)
        # self.NSeg.setEnabled(False)
        # self.NRung.setEnabled(False)
        # self.DetRot.setEnabled(False)
        # self.ScanDir_NF.setEnabled(False)
        # self.ScanDirYFlip.setEnabled(False)
        # self.ScanDirUnlock.setEnabled(False)
        # self.ScanDir.setEnabled(False)
    elif dmod=="DPCMod":
        self.DfrnDetrTabGroup.setCurrentIndex(2)
        self.dpcControls.setVisible(True)
        self.comControls.setVisible(True)
        # self.DetRot_NF.setEnabled(True)
        # self.NSeg.setEnabled(True)
        # self.NRung.setEnabled(True)
        # self.DetRot.setEnabled(True)
        # self.ScanDir_NF.setEnabled(True)
        # self.ScanDirYFlip.setEnabled(True)
        # self.ScanDirUnlock.setEnabled(True)
        # self.ScanDir.setEnabled(True)
    elif dmod=="CoMMod":
        self.DfrnDetrTabGroup.setCurrentIndex(2)
        self.dpcControls.setVisible(False)
        self.comControls.setVisible(True)
        # self.DetRot_NF.setEnabled(False)
        # self.NSeg.setEnabled(False)
        # self.NRung.setEnabled(False)
        # self.DetRot.setEnabled(True)
        # self.ScanDir_NF.setEnabled(True)
        # self.ScanDirYFlip.setEnabled(True)
        # self.ScanDirUnlock.setEnabled(True)
        # self.ScanDir.setEnabled(True)
    elif dmod=="VrApMod":
        self.DfrnDetrTabGroup.setCurrentIndex(3)
    elif dmod=="CustMod":
        self.DfrnDetrTabGroup.setCurrentIndex(4)

def datasetOptCallbacks():
    pass

def previewCallbacks():
    pass

def transBeamCallbacks():
    pass

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

def resizeWindowCallbacks():
    pass

def updateImagesCallbacks():
    pass

def enableAllUICallbacks():
    pass

def slotsSignals(self):
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

    self.DetrMode.currentIndexChanged.connect(lambda: on_DetrMode_currentIndexChanged(self))

    # detector slider/numerical field connections
    self.AnnRi_NF.valueChanged.connect(lambda: moveAnnR(self))
    self.AnnRo_NF.valueChanged.connect(lambda: moveAnnR(self))
    self.AnnRi.valueChanged.connect(lambda: moveAnnR(self))
    self.DetrMode.currentIndexChanged.connect(lambda: moveAnnR(self))
    self.UpdateImages.triggered.connect(lambda: moveAnnR(self))
    
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
    self.Image.ColorWheel = np.arctan2(ygrid, xgrid)

    # shift the negative values of atan up by 2*pi
    self.Image.ColorWheel[self.Image.ColorWheel<0]+=2*np.pi

    # make colorwheel circular by masking at outer radius
    colorWheelMask = (xgrid**2 + ygrid**2) < r**2

    # add colorwheel image to axis
    self.Fig.ColorWheel.ax.imshow(self.Image.ColorWheel,alpha=colorWheelMask.astype(float),cmap='hsv',interpolation="None")