import sys
from PyQt5 import QtWidgets as qtw
from PyQt5 import uic
import numpy as np

class T:
    FileSize = 0
    dm = []
    h5 = []
    fileTail = 0
    EstSize = 0
    EstMem = 0
    Preview = []
    prev_D = 0
    frameJ = 0

class D:
    filePath = ''
    fileDir = ''
    fileName = ''
    fileExt = ''
    subImg = {}
    Offset = 0
    FrHead = 0
    FrFoot = 0
    ByteOrder = 'l'
    DataType = 'single'
    ByteSize = 4
    mem = 'Physical Memory'
    GPU = 1
    DNPxX = 1
    DNPxY = 1
    PxD = 1
    DNFrX = 1
    DNFrY = 1
    FrD = 1
    PxX1 = 1
    PxY1 = 1
    NPxX = 1
    NPxY = 1
    FrX1 = 1
    FrY1 = 1
    NFrX = 1
    NFrY = 1
    NPx = [1,1]
    NPxS = 1
    NFr = [1,1]
    NFrS = 1
    EstMem = 0
    KeepP = 0
    NoteFileMeta = ''
    NoteImp = ''
    h5ds = []
    annWidth = 0.5 # annuli width for BF/ADF integration

class C:
    ScreenSize = []
    MonitorPositions = []
    ScreenPxScale = 1
    monitorWidth = []
    monitorHeight = []
    monitorAvailWidth = []
    monitorAvailHeight = []
    dpi = []
    hOffset = []
    vOffset = []
    toolbarWidth = []
    toolbarHeight = []
    decorPad = []
    titleHeight = []
    mplDecor = []
    sz = []
    shc = []
    l = []
    wb0 = []
    BgC = [0.94,0.94,0.94]
    WarnC = [1.00,0.65,0.00]
    SysEndian = 'l'
    EndianTxt = {"l": "Little Endian","b": "Big Endian"}
    MemTot = 0
    MemFree = 0
    nGPU = 1
    GPUmem = []
    GPUname = []
    

class P:
    ScanDirInit = 0
    DfCtr = []
    RsCtr = []
    VrApXY = []
    DfrnAxLim = []
    RealAxLim = []
    TransBeamInit = 1
    RMax = 0
    DetrMode = 'AlignMod'
    detWidth = 0

class Prev:
    ims = []
    hist = []
    B0 = []
    AnnR = []
    CoM_P = []

class Fig:
    ColorWheel = None
    Dfrn = None
    DfrnMask = None
    Real  = None
    CoMPhMag = None
    CoMPh = None
    CoMMag = None
    CoMX = None
    CoMY = None
    dCoM = None
    iCoM = None
    RealMask = None
    Preview = None

class Image:
    ColorWheel = None
    Dfrn = None
    DfrnMask = None
    Real  = None
    CoMPhMag = None
    CoMPh = None
    CoMMag = None
    CoMX = None
    CoMY = None
    dCoM = None
    iCoM = None
    RealMask = None
    Preview = None

class A:
    # generic circle starting point
    circX = np.cos(np.arange(0,2.01*np.pi,np.pi/100))
    circY = np.sin(np.arange(0,2.01*np.pi,np.pi/100))
    
    # bf/adf detector
    adfInnerCirc = None
    adfOuterCirc = None
    adfPt = None
    
    # transmitted beam
    tbPt = None
    tbCirc = None

    # DPC segments
    SegDetrCir = None
    SegDetrL = None
    SegDetrL0 = None
    SegDetrP0 = None

    # scan direction for CoM/DPC
    ScanDirXline = None
    ScanDirYline = None
    ScanDirXcirc = None
    ScanDirYcirc = None

    # virtual apertures
    VrApMirL = None
    VrApMirP = None
    VrAp = None

    # ROIs
    RealROI = None
    CoMPhMagROI = None
    CoMPhROI = None
    CoMMagROI = None
    CoMXROI = None
    CoMYROI = None
    dCoMROI = None
    iCoMROI = None

class Mask:
    pass

class G:
    pass

class ByteSize:
    u1 = 1
    i1 = 1
    u2 = 2
    i2 = 2
    f4 = 4
    i4 = 4
    u4 = 4
    f8 = 8
    i8 = 8
    u8 = 8
    unknown = 0

def appStruct(self):
    setattr(self,'B0',[0,0])
    setattr(self,'RB0',[0,0])
    setattr(self,'DfPxR',1)
    setattr(self,'RsPxR',1)
    setattr(self,'path','')
    setattr(self,'T',T())
    setattr(self,'D',D())
    setattr(self,'Data',None)
    setattr(self,'Memfile',None)
    setattr(self,'C',C())
    setattr(self,'P',P())
    setattr(self,'Prev',Prev())
    setattr(self,'Fig',Fig())
    setattr(self,'Image',Image())
    setattr(self,'A',A())
    setattr(self,'Mask',Mask())
    setattr(self,'G',G())
    setattr(self,'ByteSize',ByteSize())