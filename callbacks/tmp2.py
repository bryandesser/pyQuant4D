import numpy as np
from callbacks.annotationsClass import InteractiveCircle

# Auto-align transmitted beam
# def autoAlign(self):
#     self.T.progDLG = progDLG(app, 'Finding transmitted beam ...', "Auto Alignment")
#     # Reset any zoom on the transmitted beam
#     self.Fig.Dfrn.ax.set_xlim(self.P.DfrnAxLim[:2])
#     self.Fig.Dfrn.ax.set_ylim(self.P.DfrnAxLim[2:])
#     self.Fig.Dfrn.canvas.draw()

#     # Align transmitted beam by trying to find the transmitted disk in the diffraction pattern (self.Image.Dfrn),
#     # apply slight gaussaian blur of 5 pixels to help the fit if necessary
#     try:
#         [center, radius, ~] = imfindcircles(self.Image.Dfrn, [1 round(max(self.D.NPx)/2)]);
#         if center==[]:
#             [center, radius, ~] = imfindcircles(imgaussfilt(self.Image.Dfrn,5), [1 round(max(self.D.NPx)/2)]);
#     except:
#         center = [];  radius = []
    
#     transBeam_old = [self.B0,self.TBR.value()]; # Store old transmitted beam values

#     # Find circle closest to the center of the diffraction pattern, plot for user confirmation
#     if center==[]:
#         notifDLG(self,'warn',"No transmitted beam detected. Please align the transmitted beam manually.",'Auto-align Failed')
#         sel = "No. Revert"
#     else:
#         # Assign radius and center value(s) found above using imfindcircles based on whichever is found to be
#         # closest to the diffraction pattern center `self.P.DfCtr`
#         [~,im] = min(sqrt(sum((center-self.P.DfCtr).^2,2)));
#         self.TBX.Value = center(im,1);  self.TBY.Value = center(im,2);  self.TBR.Value = radius(im);
#         # To update annotation/panel values
#         transBeamCallbacks(app,struct("Source","","EventName",""));

#         sel = notifDLG(app,'quest',"Is the auto-alignment correct?",'Auto-align',["Yes","No. Revert"])

#     # Revert alignment if not correctly detected
#     if sel == "No. Revert":
#         self.TBX.Value = transBeam_old[0]
#         self.TBY.Value = transBeam_old[1]
#         self.TBR.Value = transBeam_old[2]


# # align transmitted beam at the crossing of two lines
# def crossAlign(): #TODO
#     self.A.line1 = drawline("Position",self.D.NPx.*[1 1;3 3]/4,"Color","r","Deletable",false)
#     self.A.line2 = drawline("Position",self.D.NPx.*[1 3;3 1]/4,"Color","r","Deletable",false)

#     addlistener(self.A.line1,'ROIMoved',@moveTB)
#     addlistener(self.A.line1,'MovingROI',@moveTB)
#     addlistener(self.A.line2,'ROIMoved',@moveTB)
#     addlistener(self.A.line2,'MovingROI',@moveTB)

#     h = helpdlg('Push OK when finished')
#     uiwait(h)

#     delete(self.A.line1)
#     delete(self.A.line2)

#     def moveTB():
#         x1 = self.A.line1.Position(1,1)
#         x2 = self.A.line1.Position(2,1)
#         x3 = self.A.line2.Position(1,1)
#         x4 = self.A.line2.Position(2,1)

#         y1 = self.A.line1.Position(1,2)
#         y2 = self.A.line1.Position(2,2)
#         y3 = self.A.line2.Position(1,2)
#         y4 = self.A.line2.Position(2,2)

#         self.B0 = [x1*y2-x2*y1,x3*y4-x4*y3]/[y2-y1,y4-y3;-(x2-x1),-(x4-x3)]

#         self.TBX.Value = self.B0(1)
#         self.TBX_NF.Value = self.B0(1)
#         self.TBY.Value = self.B0(2)
#         self.TBY_NF.Value = self.B0(2)

#         self.A.tbCirc.center = self.B0