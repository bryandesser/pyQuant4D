from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from PyQt5 import QtGui as qtg
from callbacks.guiClass import ImageWindow
import numpy as np

def getMonitorSpecs(self):
     # monitor size
    monitorWidth = qtw.QApplication.desktop().screenGeometry().width()
    monitorHeight = qtw.QApplication.desktop().screenGeometry().height()

    # toolbar size + any horizontal or vertical offsets due to toolbar
    self.hOffset, self.vOffset, self.toolbarWidth, self.toolbarHeight  = abs(np.array(qtw.QApplication.desktop().screenGeometry().getRect())-np.array(qtw.QApplication.desktop().availableGeometry().getRect()))

    # establish window decoration sizes with temporary image window
    tmp = ImageWindow("","","","","",[0, 0, 400, 400])
    self.decorPad,self.titleHeight = [tmp.geometry().x()-tmp.pos().x(), tmp.geometry().y()-tmp.pos().y()]
    if [self.decorPad,self.titleHeight]==[0,0]:
        self.decorPad = 5
        self.titleHeight = 25
    self.mplDecor = tmp.size()-qtc.QSize(400,400)
    tmp.close()

    # available monitor space
    self.monitorAvailWidth = monitorWidth - self.toolbarWidth
    self.monitorAvailHeight = monitorHeight - self.toolbarHeight
    
    # window positioning
    self.sz = np.floor(np.minimum(self.monitorAvailWidth-4*self.decorPad-2*self.mplDecor.width(),self.monitorAvailHeight-2*self.titleHeight-2*self.decorPad-2*self.mplDecor.height()))/2
    self.shc = self.monitorAvailWidth/2
    self.l = self.monitorAvailWidth-self.sz+self.hOffset-self.mplDecor.width()
    self.wb0 = self.monitorAvailHeight-self.sz+self.vOffset

    # Place diffraction windows and CoM ColorWheel along the center line of the monitor
    self.ColorWheelWindow = ImageWindow(id = "ColorWheel", name = "Color Wheel for Phase Direction", sp = "ColorWheel", typ = "CoM", cmap = "hsv", pos = [self.shc-self.sz-self.mplDecor.width(), self.sz+2*(self.decorPad+self.titleHeight)+self.mplDecor.height() + self.vOffset, self.sz/2 + self.mplDecor.width(), self.sz/2 + self.mplDecor.height()])
    self.DiffractionWindow = ImageWindow("Dfrn","Diffraction","Dfrn","Primary","gray",[self.shc-self.sz/2, self.decorPad + self.titleHeight + self.vOffset, self.sz + self.mplDecor.width(), self.sz + self.mplDecor.height()]) # Top-center
    self.DiffractionMaskWindow = ImageWindow("DfrnMask","Diffraction Mask","Dfrn","Mask","gray",[self.shc-self.sz/2, self.sz+2*(self.decorPad + self.titleHeight) + self.mplDecor.height() + self.vOffset, self.sz + self.mplDecor.width(), self.sz + self.mplDecor.height()]) # right of Top-center
    
    # Place Real-space images on the right, from top to bottom
    self.iCoMWindow = ImageWindow("iCoM","iCoM","Real","CoM","gray",[self.l, self.decorPad + self.titleHeight + self.vOffset, self.sz + self.mplDecor.width(), self.sz + self.mplDecor.height()])
    self.dCoMWindow = ImageWindow("dCoM","dCoM","Real","CoM","gray",[self.l, 2*(self.decorPad + self.titleHeight) + self.vOffset, self.sz + self.mplDecor.width(), self.sz + self.mplDecor.height()])
    self.CoMYWindow = ImageWindow("CoMY","CoM Y","Real","CoM","gray",[self.l, 3*(self.decorPad + self.titleHeight) + self.vOffset, self.sz + self.mplDecor.width(), self.sz + self.mplDecor.height()])
    self.CoMXWindow = ImageWindow("CoMX","CoM X","Real","CoM","gray",[self.l, 4*(self.decorPad + self.titleHeight) + self.vOffset, self.sz + self.mplDecor.width(), self.sz + self.mplDecor.height()])
    self.CoMMagWindow = ImageWindow("CoMMag","CoM Magnitude","Real","CoM","gray",[self.l, 5*(self.decorPad + self.titleHeight) + self.vOffset, self.sz + self.mplDecor.width(), self.sz + self.mplDecor.height()])
    self.CoMPhWindow = ImageWindow("CoMPh","CoM Phase","Real","CoM","hsv",[self.l, 6*(self.decorPad + self.titleHeight) + self.vOffset, self.sz + self.mplDecor.width(), self.sz + self.mplDecor.height()])
    self.CoMPhMagWindow = ImageWindow("CoMPhMag","CoM Phase (Magnitude-shaded)","Real","CoM","hsv",[self.l, 7*(self.decorPad + self.titleHeight) + self.vOffset, self.sz + self.mplDecor.width(), self.sz + self.mplDecor.height()])
    self.RealMaskWindow = ImageWindow("RealMask","Real-space Mask","Real","Mask","gray",[self.l, 8*(self.decorPad + self.titleHeight) + self.vOffset, self.sz + self.mplDecor.width(), self.sz + self.mplDecor.height()])
    self.RealSpaceWindow = ImageWindow("Real","Real-space","Real","Primary","gray",[self.l, 9*(self.decorPad + self.titleHeight) + self.vOffset, self.sz + self.mplDecor.width(), self.sz + self.mplDecor.height()])