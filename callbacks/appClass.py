import sys
from PyQt5 import QtWidgets as qtw
from PyQt5 import uic

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

class C:
    ScreenSize = []
    MonitorPositions = []
    ScreenPxScale = 1
    monitorWidth = []
    monitorHeight = []
    monitorAvailWidth = []
    monitorAvailHeight = []
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

class Image:
    ColorWheel = None
    ColorWheelMask = None
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
    pass

class Mask:
    pass

class G:
    pass

class ByteSize:
    uint8 = 1
    int8 = 1
    uint16 = 2
    int16 = 2
    single = 4
    int32 = 4
    uint32 = 4
    double = 8
    int64 = 8
    uint64 = 8

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

def appStruct(self):
    setattr(self,'B0',[0,0])
    setattr(self,'B0',[0,0])
    setattr(self,'RB0',[0,0])
    setattr(self,'DfPxR',1)
    setattr(self,'RsPxR',1)
    setattr(self,'path','')
    setattr(self,'T',T())
    setattr(self,'D',D())
    setattr(self,'Data',None)
    setattr(self,'C',C())
    setattr(self,'P',P())
    setattr(self,'Prev',Prev())
    setattr(self,'Image',Image())
    setattr(self,'A',A())
    setattr(self,'Mask',Mask())
    setattr(self,'G',G())
    setattr(self,'ByteSize',ByteSize())
    setattr(self,'Fig',Fig())