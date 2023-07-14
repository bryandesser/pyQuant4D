import sys
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtGui as qtg
from PyQt5 import uic
import numpy as np

diffImages = ['Dfrn', 'DfrnMask']
realImages = ['iCoM', 'dCoM', 'CoMY', 'CoMX', 'CoMMag', 'CoMPh', 'CoMPhMag', 'RealMask', 'Real', 'Preview', 'ColorWheel']
allImages = diffImages + realImages

class propDict(dict):
    """allows for dot indexing"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

class D:
    """ Parameters of the current imported dataset; should be constants (except for data type conversion) """
    @staticmethod
    def swapDiff():
        # Swap diffraction X/Y dimensions
        D.DNPxX,D.DNPxY = D.DNPxY,D.DNPxX
        D.NPxX,D.NPxY = D.NPxY,D.NPxX
        D.PxX1,D.PxY1 = D.PxY1,D.PxX1
        D.NPx = np.flip(D.NPx)
    
    @staticmethod
    def swapReal():
        # Swap real X/Y dimensions
        D.DNFrX,D.DNFrY = D.DNFrY,D.DNFrX
        D.NFrX,D.NFrY = D.NFrY,D.NFrX
        D.FrX1,D.FrY1 = D.FrY1,D.FrX1
        D.NFr = np.flip(D.NFr)

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
    NPx = np.array([1,1])
    NPxS = 1
    NFr = np.array([1,1])
    NFrS = 1
    EstMem = 0
    KeepP = 0
    NoteFileMeta = ''
    NoteImp = ''
    h5ds = []
    annWidth = 0.5 # annuli width for BF/ADF integration

class T:
    """ Temporary global variables, e.g. for progress bar and import etc., should never be cleared """
    FileSize = 0
    dm = []
    h5 = []
    fileTail = 0
    EstSize = 0
    EstMem = 0
    Preview = D()
    prev_D = D()
    frameJ = 0

class C:
    """ Constants for system info that set at app startup """
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
    BgC = qtg.QColor.fromRgbF(0.94,0.94,0.94,1)
    WarnC = qtg.QColor.fromRgbF(1,0.65,0,1)
    SysEndian = 'l'
    EndianTxt = {"l": "Little Endian","b": "Big Endian"}
    MemTot = 0
    MemFree = 0
    nGPU = 1
    GPUmem = []
    GPUname = []
    

class P:
    """ Common parameters, should be cleared when a dataset is unloaded """
    ScanDirInit = 0
    DfCtr = []
    RsCtr = []
    VrApXY = []
    DfrnAxLim = []
    RealAxLim = []
    TransBeamInit = 0
    RMax = 0
    DetrMode = 'AlignMod'
    detWidth = 0
    PreviewAxLim = [0,1,0,1]

class Prev:
    """ Previous values, should be cleared when a dataset is unloaded """
    ims = []
    hist = []
    B0 = []
    AnnR = []
    CoM_P = []

# class Fig:
#     ColorWheel = None
#     Dfrn = None
#     DfrnMask = None
#     Real  = None
#     CoMPhMag = None
#     CoMPh = None
#     CoMMag = None
#     CoMX = None
#     CoMY = None
#     dCoM = None
#     iCoM = None
#     RealMask = None
#     Preview = None

# class Image:
#     ColorWheel = None
#     Dfrn = None
#     DfrnMask = None
#     Real  = None
#     CoMPhMag = None
#     CoMPh = None
#     CoMMag = None
#     CoMX = None
#     CoMY = None
#     dCoM = None
#     iCoM = None
#     RealMask = None
#     Preview = None

class A:
    """ Image annotations on `axes` `uiaxes`, excluding annotations on `figure` `uifigure` """
    def __init__(self):
        # generic circle starting point
        self.circX = np.cos(np.arange(0,2.01*np.pi,np.pi/100))
        self.circY = np.sin(np.arange(0,2.01*np.pi,np.pi/100))

        # bf/adf detector
        self.adf = None
        
        # transmitted beam
        self.tb = None

        # DPC segments
        self.SegDetrCir = None
        self.SegDetrL = None
        self.SegDetrL0 = None
        self.SegDetrP0 = None

        # scan direction for CoM/DPC
        self.ScanDirXline = None
        self.ScanDirYline = None
        self.ScanDirXcirc = None
        self.ScanDirYcirc = None

        # virtual apertures
        self.VrApMirL = None
        self.VrApMirP = None
        self.VrAp = None

        # ROIs
        self.ROIs = dict()
        self.ROIs["RealROI"] = None
        self.ROIs["CoMPhMagROI"] = None
        self.ROIs["CoMPhROI"] = None
        self.ROIs["CoMMagROI"] = None
        self.ROIs["CoMXROI"] = None
        self.ROIs["CoMYROI"] = None
        self.ROIs["dCoMROI"] = None
        self.ROIs["iCoMROI"] = None

        # vectorField quivers
        self.vectField = dict()
        self.vectField["CoMPhMag"] = None
        self.vectField["Real"] = None
        self.vectField["CoMX"] = None
        self.vectField["CoMY"] = None
        self.vectField["CoMPh"] = None
        self.vectField["dCoM"] = None
        self.vectField["CoMMag"] = None
        self.vectField["iCoM"] = None

        # histogram annotations
        self.histBox = None
        self.histGamma = None

    def removeGroup(self,tag):
        """ allow for groups of annotations to be removed and set to None """
        for item in vars(self):
            if item.startswith(tag):
                
                if not isinstance(getattr(self,item),dict):
                    try:
                        getattr(self,item).remove()
                    except:
                        pass
                    finally:
                        setattr(self,item,None)
                else:
                    for key in getattr(self,item).keys():
                        try:
                            getattr(self,item)[key].remove()
                        except:
                            pass
                        finally:
                            getattr(self,item)[key] = None

class Mask:
    pass

class G:
    pass

class ByteSize:
    """ data size in bytes for the allowed data types"""
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
    setattr(self,'A',A())
    setattr(self,'Mask',Mask())
    setattr(self,'G',G())
    setattr(self,'ByteSize',ByteSize())

    Fig = propDict({})
    Image = propDict({})
    ImageAx = propDict({})

    for ii in allImages:
        Fig[ii] = None
        Image[ii] = None
        ImageAx[ii] = None
    
    setattr(self,'Fig',Fig)
    setattr(self,'Image',Image)
    setattr(self,'ImageAx',ImageAx)
    setattr(self,'blockAllSignals',False)
