import numpy as np
from callbacks.allFunctions import displayCallbacks


# Sub function for ROI update
def moveHistHiLo(self, src, evt):
    if hasattr(evt,'CurrentPosition'):
        p = evt.CurrentPosition
        
        # Get preset values
        a = self.A.histBox
        [iax,imax,imin,irange,hi,lo] = deal(a.Box.UserData{:})
        yl = self.SettingsWindow.HistAxes.YLim
        match self.sender():
            case a.Box:
                lo = p(1)
                hi = p(1)+p(3)
            case a.Lo:
                lo = p(1)
            case a.Hi:
                hi = p(1)
          
        hi = max(lo,hi)
        lo = min(lo,hi) # Sort out upper/lower limits

        # Find mid-height of the histogram, log- or linear-scale
        if self.HistLog.Value:
            ymid = sqrt(prod(yl))
        else:
            ymid = mean(yl)
        
        # Update ROI
        set([a.Box a.Hi a.Lo], {'Position'},{[lo, yl(1), hi-lo, yl(2)-yl(1)] [hi ymid] [lo ymid]})
        # Limit ROI translating area
        da = [self.SettingsWindow.HistAxes.XLim(1),ymid,range(self.SettingsWindow.HistAxes.XLim),0]
        if any(isinf(da)):
            da='auto'
        set([a.Box a.Hi a.Lo],'DrawingArea',da,'Visible',self.DispContrast.Enable)
        # Update UI and image if called from ROIs
        if self.sender() is a.Box:
            iax.UserData.brightness = max(min(double(50+(imax+imin-hi-lo)/2/irange*100),100),0)
            iax.UserData.contrast = max(min(double(2^((imax-imin-hi+lo)/2/irange*2)*50),100),0)
            displayCallbacks(self, evt)


