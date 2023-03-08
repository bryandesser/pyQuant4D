import sys, time
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, QElapsedTimer, QObject, pyqtSlot
from PyQt5.QtWidgets import QWidget, QPushButton, QApplication, QVBoxLayout, QProgressDialog
from matplotlib.pyplot import connect, title

class GenericWorker(QObject):
    def __init__(self, function):
        super(GenericWorker, self).__init__()

        self.function = function
        self.start.connect(self.run)
    
    start = pyqtSignal()
    finish = pyqtSignal()

    @pyqtSlot()
    def run(self):
        self.function()
        self.finish.emit()

class progressBarDialogWidget(QProgressDialog):
    def __init__(self,title="Progress",value=0,range=[0,0]):
        super(progressBarDialogWidget, self).__init__()
        self.setWindowTitle(title)
        self.setValue(value)
        self.setLabelText("")
        self.setRange(range[0],range[1])
        self.resize(300,100)
        self.show()

class controlWindowWidget(QWidget):
    def __init__(self):
        super(controlWindowWidget, self).__init__()
        self.setWindowTitle('Import Data Dialog')
        self.importDataBtn = QPushButton('Import data')
        self.importDataBtn.clicked.connect(self.importDataFunc)
        self.resize(300, 100)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.importDataBtn)
        self.setLayout(self.layout)
        self.show()
    
    def importDataFunc(self):
        self.importDataBtn.setEnabled(False)
        self.importDataBtn.setText("Importing data...")

        self.progressBarWidget = QProgressDialog(parent=self,minimum=0,maximum=0,labelText="0 s")
        self.progressBarWidget.setAutoClose(True)
        self.progressBarWidget.canceled.connect(self.signal_reject)

        self.timer = QTimer(self)
        self.elapsedTimer = QElapsedTimer()
        self.timer.timeout.connect(self.updateTimer)

        self.my_thread = QThread()
        self.my_thread.start()

        self.my_worker = GenericWorker(readEMPAD)
        self.my_worker.finish.connect(self.signal_accept)
        self.my_worker.moveToThread(self.my_thread)
        self.my_worker.start.emit()

        self.elapsedTimer.start()
        self.timer.start(500)
        
    def signal_accept(self):
        self.my_worker.finish
        self.my_thread.quit()
        self.importDataBtn.setEnabled(True)
        self.importDataBtn.setText("Import data")
        self.progressBarWidget.setRange(0,1)
        self.progressBarWidget.setValue(1)
        self.progressBarWidget.hide()
        print("accepted")
        self.timer.stop()

    def signal_reject(self):
        self.my_worker.disconnect()
        self.my_worker.finish
        self.my_thread.quit()
        self.importDataBtn.setEnabled(True)
        self.importDataBtn.setText("Import data")
        self.progressBarWidget.setRange(0,0)
        self.progressBarWidget.setValue(0)
        self.progressBarWidget.hide()
        print("rejected")
        self.timer.stop()
    
    def updateTimer(self):
        self.progressBarWidget.setLabelText("{:.1f} s".format(self.elapsedTimer.elapsed()/1000))

def readEMPAD():
    print("readEMPAD started")
    for ii in range(20):
        time.sleep(0.4)
        print(ii)
    print("readEMPAD finished")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    cw = controlWindowWidget()
    cw.show()
    sys.exit(app.exec_())
    #app.exec()