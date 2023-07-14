import sys
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtGui as qtg
from PyQt5 import QtCore as qtc
from PyQt5 import uic


import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt 
import numpy as np

from annotationsClasses.interactiveCircle import InteractiveCircle

# Convert .ui Files from QT Designer to python
# Main window
MW_Ui, MW_Base = uic.loadUiType("C:/Users/bess0001/Documents/dataStorage/research/code/pyQuant4D/gui/Quant4D_FigForm.ui")

class ImageWindow(qtw.QMainWindow):
    imageResize = qtc.pyqtSignal((qtc.QSize,str))
    activateFigure = qtc.pyqtSignal(str)

    def __init__(self, id, name, space, typ, cmap, pos):
        super().__init__
        qtw.QMainWindow.__init__(self)

        self.setObjectName(id)

        self.imageWidget = qtw.QWidget(self)
        self.setCentralWidget(self.imageWidget)
        layout = qtw.QVBoxLayout(self.imageWidget)

        # add radio button group
        bw = qtw.QWidget()
        hlayout = qtw.QHBoxLayout()
        bw.setLayout(hlayout)
        b0 = qtw.QRadioButton("all")
        b1 = qtw.QRadioButton("resize")
        b2 = qtw.QRadioButton("translate")
        b3 = qtw.QRadioButton("none")
        hlayout.addWidget(b0)
        hlayout.addWidget(b1)
        hlayout.addWidget(b2)
        hlayout.addWidget(b3)
        self.bg = qtw.QButtonGroup(bw)
        self.bg.addButton(b0)
        self.bg.addButton(b1)
        self.bg.addButton(b2)
        self.bg.addButton(b3)
        b0.setChecked(True)
        

        layout.addWidget(bw)

        px = 1/plt.rcParams['figure.dpi']
        self.fig = Figure(figsize=(pos[2]*px,pos[3]*px))
        self.ax = self.fig.add_subplot(111)
        self.fig.subplots_adjust(bottom=0,right=1,top=1,left=0)
        self.fig.canvas = FigureCanvas(self.fig)
        self.ax.axis('off')
        self.ax.set_facecolor('black')

        layout.addWidget(self.fig.canvas)

        self.toolbar = NavigationToolbar(self.fig.canvas, self)
        layout.addWidget(self.toolbar)
        layout.setStretch(0,0)
        layout.setStretch(1,1)
        layout.setStretch(2,0)

        # Set defaults for the given window
        self.setWindowTitle(name)

        self.id = id             # window id
        self.space = space       # real or diffraction space?
        self.type = typ          # type of image: Primary (Dfrn and Real), Mask, CoM
        self.cmap = cmap         # colormap
        self.invert = 0          # invert colormap?
        self.maskOpa = 0         # mask opacity
        self.Tag = space+" "+typ # tag used for finding windows
        self.name = name         # image name
        self.brightness = 50     # brightness value
        self.contrast = 50       # contrast value
        self.gamma = 1           # gamma value
        self.vecField = 0        # vector field display logical
        self.isShown = False     # help with hiding/showing groups of windows
        
        # set defaul vector color for overlays
        if cmap=="gray":
            self.vecColor = qtg.QColor('red') # red
        else:
            self.vecColor = qtg.QColor('white') # white
        
        # only use self.move() for dummy window test, it triggers a moveEvent which draws the decoration so they can be measured
        pos = np.rint(pos).astype(int) # make sure position is type int
        if id=="":
            self.move(pos[0],pos[1])
            self.show()
        else:
            self.setGeometry(qtc.QRect(pos[0],pos[1],pos[2],pos[3]))
        
        self.fig.canvas.mpl_connect('button_press_event', lambda id: self.activateFigure.emit(self.id))
        
    # change closeEvent behavior to hide rather than close window
    def closeEvent(self, a0: qtg.QCloseEvent) -> None:
        self.hide()
        self.isShown = False
        a0.ignore()
        return super().closeEvent(a0)
    
    def resizeEvent(self, a0: qtg.QResizeEvent) -> None:
        sizeChange = a0.size() - a0.oldSize()
        self.imageResize.emit(sizeChange,self.space)
        return super().resizeEvent(a0)
    
    def mousePressEvent(self, a0: qtg.QMouseEvent) -> None:
        self.activateFigure.emit(self.id)
        return super().mousePressEvent(a0)
    
    #TODO: clicking title bar activates window, but does not trigger a mousePressEvent; 
    #      using qtc.QEvent.ActivationChange falls into a recursive spiral as when one window activates
    #      another deactivates, sending two competing signals
    #
    # def changeEvent(self, a0: qtc.QEvent) -> None:
    #     if hasattr(self,'id'):
    #         print(self.id,dict([(getattr(a0,ii),ii) for ii in dir(a0) if ((not ii.startswith("_")) and not (callable(getattr(a0,ii))))])[a0.type()],self.hasFocus())
    #     else:
    #         print(dict([(getattr(a0,ii),ii) for ii in dir(a0) if ((not ii.startswith("_")) and not (callable(getattr(a0,ii))))])[a0.type()],self.hasFocus())

    #     if (a0.type() == qtc.QEvent.ActivationChange) and (not self.isActiveWindow()):
    #         print(self.id,self.isActiveWindow())
    #         self.activateFigure.emit(self.id)
    #     return super().changeEvent(a0)
    
    # def focusInEvent(self, a0: qtg.QFocusEvent) -> None:
    #     print(999)
    #     return super().focusInEvent(a0)