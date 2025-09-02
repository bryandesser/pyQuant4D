import sys
import PyQt5.QtWidgets as qtw
from callbacks.guiClass import MainWindow
import os
os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"


if __name__ == '__main__':
    app = qtw.QApplication(sys.argv)
    Quant4D_MainWindow = MainWindow()
    sys.exit(app.exec())