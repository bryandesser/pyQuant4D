from callbacks.allFunctions import enableWindows
from PyQt5 import QtWidgets as qtw

def notifDLG(self, icon="", msg="", ttl="", opt=[]):
    """ Wrapper for notification dialogs; use `sprintf()` before calling this function to process "\n" in `msg` """
    sel=''

    # predefined Qt icons
    icons = dict()
    icons[""] = qtw.QMessageBox.NoIcon
    icons["help"] = qtw.QMessageBox.Question #TODO ?
    icons["quest"] = qtw.QMessageBox.Question
    icons["none"] = qtw.QMessageBox.Information
    icons["warn"] = qtw.QMessageBox.Warning
    icons["error"] = qtw.QMessageBox.Critical

    enableWindows(self,False) # disable windows

    if icon == 'list':
        sel,ok = qtw.QInputDialog().getItem(self,ttl,msg,opt,0,False) # default option 0, multiselect=False
    
    else: 
        dlg = qtw.QMessageBox(self) # establish a messagebox
        #dlg.setParent(self) # attach to the main UI window
        dlg.setIcon(icons[icon]) # set messagebox icon type
        dlg.setText(msg) # set the message
        dlg.setWindowTitle(ttl) # set the title

        match icon:
            case 'quest':
                for ii in opt:
                    dlg.addButton(ii,qtw.QMessageBox.YesRole)
                            
            case '':
                pass

            case 'help'|'warn'|'error'|'none':
                dlg.setStandardButtons(qtw.QMessageBox.Ok) # only allow for an "Ok" button

        sel = dlg.exec_() # Block background process until `msgbox()` is gone

    enableWindows(self,True) # re-enable windows

    # convert from integer return to text
    match icon:
        case 'list':
            pass # QInputDialog() will return the selected item text
        case 'quest':
            sel = opt[sel]
        case other:
            sel = 'Ok'

    return sel