import numpy as np
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
import callbacks.appClass as appClass
from callbacks.appClass import *
from callbacks.annotationsClass import DraggablePoint
import os
import importlib
import matplotlib

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
        for image in dir(self.Image):
            if not image.startswith("_"):
                setattr(self.Image,image,None)
                fig = getattr(self.Fig,image)
                fig.ax.cla()
                fig.canvas.draw()
        
        # clear annotations (lines and draggable points)
        for ii in dir(self.A):
            if type(getattr(self.A,ii)) in (DraggablePoint,matplotlib.lines.Line2D):
                setattr(self.A,ii,None)

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

#def importData(self):
def on_ImportDataButton_clicked(self):
    from callbacks.ioUtils import readEMPAD
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

