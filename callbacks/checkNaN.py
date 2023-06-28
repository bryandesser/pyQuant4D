import numpy as np
from callbacks.notifDLG import notifDLG

def checkNaN(self, image, preview = False):
    """ Function to check nan/inf in data/image """

    if np.ma.masked_invalid(image).mask.any():
        ttl = 'NaN/Inf in Data!'
        msg = "There are NaN/Inf values in the data, which may indicate that the data structure is not correctly set " + \
            "(e.g. wrong Data Type, Byte Order, Data Offset, Frame Header/Footer etc).\n\nIf any data are corrupt, NaNs can be set to 0."

        if preview: # For preview only
            opt = ["Continue","Set NaNs to 0"]

        elif (self.D.PxD > 1) or (self.D.FrFoot + self.D.FrHead > 0):
            msg += "\n\nRe-importing with corrected configuration is suggested."
            opt = ["Continue","Set NaNs to 0"]

        else:
            msg += "\n\nDo you want to swap the byte-order?"
            opt = ["Yes, try to swap the byte-order","No"]
            self.SettingsWindow.activate()
            self.SettingsWindow.SettingsTabGroup.setCurrentWidget(self.SettingsWindow.InfoTab)  # Select the Data Info tab
        
        sel = notifDLG(self, 'quest', msg, ttl, opt)



        # Execute the swap byte order callbacks
        if sel.startswith("Yes"):
            self.SettingsWindow.SwapByteOrder.click()

        return sel #string of button, will be checked outside function for further action
    
    else:
        return None