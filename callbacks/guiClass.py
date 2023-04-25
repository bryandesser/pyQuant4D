import sys
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtGui as qtg
from PyQt5 import QtCore as qtc
from PyQt5 import uic
from callbacks.setupUtils import startupFcn

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt 

# Convert .ui Files from QT Designer to python
# Main window
#MW_Ui, MW_Base = uic.loadUiType(sys.path[0]+"/gui/Quant4D_FigForm.ui")
MW_Ui, MW_Base = uic.loadUiType(sys.path[0]+"/gui/Quant4D_FigForm.ui")
# Import window
IW_Ui, IW_Base = uic.loadUiType(sys.path[0]+"/gui/ImportDataForm.ui")
# Settings window
SW_Ui, SW_Base = uic.loadUiType(sys.path[0]+"/gui/SettingsPanelForm.ui")
# Save/Export window
EW_Ui, EW_Base = uic.loadUiType(sys.path[0]+"/gui/SavePanelForm.ui")


class MainWindow(MW_Base, MW_Ui):
    pointPickerRadius = qtc.pyqtSignal(float)
    
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # startup function
        startupFcn(self)

        # place gui and show
        self.move(self.C.hOffset,self.C.vOffset)
        self.show()

        # connect screenChange slot/signal
        self.windowHandle().screenChanged.connect(lambda: self.C.__setattr__("dpi",self.screen().physicalDotsPerInch()))
        self.windowHandle().screenChanged.connect(lambda: self.pointPickerRadius.emit(self.screen().physicalDotsPerInch()))

    def closeEvent(self, event):
        reply = qtw.QMessageBox.question(self, 'Window Close', 'Are you sure you want to quit?',
            qtw.QMessageBox.No | qtw.QMessageBox.Yes, qtw.QMessageBox.No)

        if reply == qtw.QMessageBox.Yes:
            event.accept()
            # close all windows and quit application
            sys.exit()
        else:
            event.ignore()
    
    def receiveThreadData(self,data):
        self.Data = data
    
    def receiveWorkerData(self,adfImages):
        self.adfImages = adfImages

    

class ImportWindow(IW_Base, IW_Ui):

    def __init__(self):
        super().__init__()
        self.setupUi(self)
    
    def closeEvent(self, a0: qtg.QCloseEvent) -> None:
        self.hide()
        a0.ignore()
        return super().closeEvent(a0)

class SettingsWindow(SW_Base, SW_Ui):

    def __init__(self):
        super().__init__()
        self.setupUi(self)
    
    def closeEvent(self, a0: qtg.QCloseEvent) -> None:
        self.hide()
        a0.ignore()
        return super().closeEvent(a0)

class SaveWindow(EW_Base, EW_Ui):

    def __init__(self):
        super().__init__()
        self.setupUi(self)
    
    def closeEvent(self, a0: qtg.QCloseEvent) -> None:
        self.hide()
        a0.ignore()
        return super().closeEvent(a0)

class ImageWindow(qtw.QMainWindow):
    def __init__(self, id, name, sp, typ, cmap, pos):
        super().__init__
        qtw.QMainWindow.__init__(self)
        self.setWindowTitle(name)

        self.setObjectName(id)

        self.imageWidget = qtw.QWidget(self)
        self.setCentralWidget(self.imageWidget)
        layout = qtw.QVBoxLayout(self.imageWidget)

        px = 1/plt.rcParams['figure.dpi']
        self.fig = Figure(figsize=(pos[2]*px,pos[3]*px))
        self.ax = self.fig.add_subplot(111)
        self.fig.subplots_adjust(bottom=0,right=1,top=1,left=0)
        self.canvas = FigureCanvas(self.fig)
        self.ax.axis('off')

        layout.addWidget(self.canvas)

        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)

        # Set defaults for the given window
        self.setWindowTitle(name)

        self.id = id            # window id
        self.space = sp         # real or diffraction space?
        self.type = typ         # type of image
        self.cmap = cmap        # colormap
        self.invert = 0         # invert colormap?
        self.maskOpa = 0        # mask opacity
        self.Tag = sp+" "+typ   # 
        self.name = name        # image name
        self.brightness = 50    # brightness value
        self.contrast = 50      # contrast value
        self.gamma = 1          # gamma value
        self.vecField = 0       # vector field display logical
        self.isShown = False    # help with hiding/showing groups of windows
        
        # set defaul vector color for overlays
        if cmap=="gray":
            self.vecColor = 'r' # red
        else:
            self.vecColor = 'w' # white
        
        # only use self.move() for dummy window test, it triggers a moveEvent which draws the decoration so they can be measured
        if id=="":
            self.move(pos[0],pos[1])
            self.show()
        else:
            self.setGeometry(qtc.QRect(int(pos[0]),int(pos[1]),int(pos[2]),int(pos[3])))
        
    # change closeEvent behavior to hide rather than close window
    def closeEvent(self, a0: qtg.QCloseEvent) -> None:
        self.hide()
        self.isShown = False
        a0.ignore()
        return super().closeEvent(a0)
