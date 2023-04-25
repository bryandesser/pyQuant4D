import numpy as np
import re
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from callbacks.imageUtils import integrateAnnular, detrCoordCallbacks, Worker
from multiprocessing.pool import ThreadPool
import psutil
from datetime import datetime

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
    filename = self.ImportWindow.ImpFilePath.text()

    # dataset offset
    dataOffset = int(self.ImportWindow.DataOffset.value())

    # dataset header/foot sizes (in bytes)
    header = int(self.ImportWindow.FrHead.value())
    footer = int(self.ImportWindow.FrFoot.value())

    # detector shape
    nopix = self.ImportWindow.DNPxX.value()
    nopiy = self.ImportWindow.DNPxY.value()

    # real space scan shape
    framesx = self.ImportWindow.DNFrX.value()
    framesy = self.ImportWindow.DNFrY.value()
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
    self.DetrMode.blockSignals(True)
    self.DetrMode.setCurrentIndex(self.DetrMode.findData("AlignMod"))
    self.DetrMode.blockSignals(False)
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
        #transBeamCallbacks(self,evt) # Update Transmitted Beam dependant variables #TODO

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

    #mockUICallbacks(self,self.UpdateImages) # Update all images #TODO
    #delete(self.T.progDLG);  # Close progress bar and Enable panel objects #TODO
    #mockUICallbacks(self,self.DetrMode)  # Enter intializing alignment #TODO

    #initialize SettingsWindow and move next to main UI window
    self.SettingsWindow.SettingsTabGroup.setCurrentIndex(0) # "Display" tab
    self.SettingsWindow.setVisible(True)
    pos = self.SettingsWindow.geometry()
    pos.moveLeft(self.geometry().getRect()[0]+self.geometry().getRect()[2]+self.C.decorPad*2)
    pos.moveTop(self.geometry().getRect()[1])
    self.SettingsWindow.setGeometry(pos)

    #flashBackground(self, [self.DfrnCalibGrid self.TransBeamAlignGrid])

def finishImport(self):
    # integrate annular images #TODO
    self.B0 = [64.3641,63.7125] # ga2o3 empad
    #self.B0 = [259.5970,270.3951] # mrc triangle
    #self.B0 = [462.6025,521.6588] # PIO dm4
    
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

    prepareData(self)
    integrateAnnular(self)
    reinitializeUI(self)

def reinitializeUI(self):
    print("threadpool finished: {}".format(datetime.now()))
    # finalize progressBar
    self.progressBar.setMaximum(100)
    self.progressBar.setValue(100)
    self.progressBar.setTextVisible(False)

    # display the total pacbed and resulting image to start
    self.Image.Dfrn = self.Fig.Dfrn.ax.imshow(self.Data.sum(axis=0).reshape(self.D.NPx))
    self.Image.Real = self.Fig.Real.ax.imshow(self.Data.sum(axis=1).reshape(self.D.NFr))
    self.Fig.Dfrn.setVisible(True)
    self.Fig.Real.setVisible(True)

    # update annular QRangeSlider to match
    self.AnnRi.setValue((self.AnnRi.minimum(),self.AnnRi.maximum()))

    self.progressBar.setEnabled(False)

    # make control panels visible again
    self.RealSpacePanel.setVisible(True)
    self.progressBarPanel.setVisible(True)
    self.DfrnDetrTabGroup.setVisible(True)
    self.DetectorModeGroup.setVisible(True)

    # start in alignment mode
    self.DetrMode.setCurrentIndex(1)

    # Import Data is the only option to start
    # turn off ALL actions
    for action in self.findChildren(qtw.QAction):
        if not action.isSeparator():
            action.setEnabled(True)
    
    detrCoordCallbacks(self)