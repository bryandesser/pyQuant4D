import numpy as np
import re
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from callbacks.imageUtils import integrateAnnular, detrCoordCallbacks, drawAnnDetr

class importThread(qtc.QObject):
    result = qtc.pyqtSignal(np.ndarray)
    finished = qtc.pyqtSignal()

    def __init__(self,filename,dataType,frameCount):
        super().__init__()
        self.filename = filename
        self.dataType = dataType
        self.frameCount = frameCount

    def run(self):
        self.Data = np.fromfile(self.filename, dtype=self.dataType, count=self.frameCount)["data"]
        self.result.emit(self.Data)
        self.finished.emit()

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

def readEMPAD(self):
    self.ImportWindow.hide()
    self.ShowImportWdw.setChecked(False)

    # initialize progressBar
    self.progressBar.setTextVisible(False)
    self.progressBar.setMaximum(0)

    #while not importDialog.wasCanceled():
    filename = self.ImportWindow.ImpFilePath.text()

    # dataset header/foot sizes (in bytes)
    header = self.ImportWindow.FrHead.value()
    footer = self.ImportWindow.FrFoot.value()

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

    # Read in the file on a separate thread
    if self.ImportWindow.ImpMemType.currentIndex()==0: # physical memory
        self.workerThread = qtc.QThread()
        self.worker = importThread(filename,dataType,framesx*framesy)
        self.worker.moveToThread(self.workerThread)
        self.workerThread.started.connect(self.worker.run)
        self.worker.result.connect(self.receiveThreadData)
        self.worker.finished.connect(lambda: finishImport(self))
        self.workerThread.start()

    else: # lazy loading
        self.Data = np.memmap(filename, dataType,'r')["data"]

def finishImport(self):
    # integrate annular images #TODO #TEMPORARY
    self.B0 = [64.3641,63.7125]
    integrateAnnular(self)
            
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

    reinitializeUI(self)
    detrCoordCallbacks(self) #TODO - add alignment routines

def reinitializeUI(self):
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