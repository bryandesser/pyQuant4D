import numpy as np

# Sub sub functions
# Sub sub function for annular radii
def moveSeg(self):
    """ Sub sub function for segemented detector"""
    match self.sender():
        case self.DetRot|self.DetRot_NF:
            dr = evt.Value
        case self.A.SegDetrP0:
            rxy = (evt.CurrentPosition-b0)
            dr = atan2d(rxy(2), rxy(1))
        case self.NSeg|self.NRung:
            drawSegDetr()
          
    # Update UI
    self.DetRot.blockSignals(True)
    self.DetRot.setValue(dr)
    self.DetRot_NF.setValue(dr)
    self.DetRot.blockSignals(False)

    # Update ROI
    pos0 = [ri, 0; ro, 0; (ri+ro)/2, 0]*rotMatD(dr)+b0
    self.A.SegDetrL0.Position = pos[0:1,:]
    self.A.SegDetrP0.Position = pos[2,:]
    self.A.SegDetrCir.Radius = num2cell(np.arange(1,self.NRung.value())/self.NRung.value()*(ro - ri) + ri))
    # Use 3D matrix for positions, then put the 1st/2nd dimensions (2x2 array) in each cell for each segment
    t = dr+360*(reshape(1:self.NSeg.Value,1,1,[])-.5)/self.NSeg.Value;
    set(self.A.SegDetrL,{'Position'},squeeze(num2cell([ri;ro].*[cosd(t) sind(t)]+b0, 1:2)))

# Sub sub function for scan directions
def moveScan(self):
    # Use polar relative pixel coordinates for calculation
    svx = self.A.ScanDir.xc.Center - b0
    svy = self.A.ScanDir.yc.Center - b0
    match self.sender:
        case self.A.ScanDir.xc:
            svx = evt.CurrentCenter - b0
            sd = atan2d(svx(2), svx(1));
        case self.A.ScanDir.yc:
            svy = (evt.CurrentCenter - b0)*syf
            sd = -atan2d(svy(1), svy(2))
        case self.ScanDir|self.ScanDir_NF:
            sd = evt.Value
        case self.ScanDirYFlip:
            pass
        
        # Convert back to cartesian absolute pixel coordiantes for annotations
        [x1,y1] = pol2cart(deg2rad(sd), sqrt(sum(svx.^2)))
        sp1 = [x1,y1]+b0
        [x2,y2] = pol2cart(deg2rad(sd+90*syf), sqrt(sum(svy.^2)))
        sp2 = [x2,y2]+b0

        # Not limiting annotation positions
        set([self.A.ScanDir.xl self.A.ScanDir.yl],{'Position'},{[b0;sp1];[b0;sp2]})
        setExSrc(evt, [self.A.ScanDir.xc self.A.ScanDir.yc],{'Center'},{sp1;sp2})
        setExSrc(evt, [self.ScanDir self.ScanDir_NF],'Value',sd)

# Function to draw Scan Direction alignment annotations
def drawScanDir(self):
        p1 = b0+[self.P.RMax/2 0];  p2 = b0+[0 self.P.RMax/2];
        self.A.ScanDir.xl = drawline(self.Axes.Dfrn,'Position',[b0;p1],'Color','r','LabelTextColor','r','Label','Scan X');
        self.A.ScanDir.yl = drawline(self.Axes.Dfrn,'Position',[b0;p2],'Color','g','LabelTextColor','g','Label','Scan Y');
        self.A.ScanDir.xc = drawcircle(self.Axes.Dfrn,'Center',p1,'Radius',self.TBR.Value);
        self.A.ScanDir.yc = drawcircle(self.Axes.Dfrn,'Center',p2,'Radius',self.TBR.Value);
        addlistener([self.A.ScanDir.xc self.A.ScanDir.yc],'MovingROI',@moveAnnDetr);
        u.Move = addlistener([self.A.ScanDir.xc self.A.ScanDir.yc],'ROIMoved',@moveAnnDetr);
        set([self.A.ScanDir.xc self.A.ScanDir.yc],'Color',[0 .5 1],'FaceAlpha',0,'UserData',u)
        set([self.A.ScanDir.xl self.A.ScanDir.yl],'MarkerSize',1,'LineWidth',1,'LabelAlpha',0,'InteractionsAllowed','none')
        set([self.A.ScanDir.xc self.A.ScanDir.yc self.A.ScanDir.xl self.A.ScanDir.yl],'Deletable',0, ...
          "DrawingArea","unlimited",'Tag','ScanDirAnnot')
        moveAnnDetr(event.Source, event)
      

# Calculate the CoM images
#   `ri` - annular inner radius `self.AnnRi.Value`; `ro` - outer radius `self.AnnRo.Value`
#   `sd` - scan direction `self.ScanDir.Value`; `syf` - flip scan Y or not
#   `dr` - detector rotation `self.DetRot.Value`
def calcCoM(ri, ro, sd, syf, dr):
        dbT = tic;
        if ~isfield(self.Mask, "Ann"), return; end

        [CoMX, CoMY] = integrateCoM();
        self.Image.CoMX = CoMX;
        self.Image.CoMY = CoMY;
        # CoM magnitude is the length of the vector -- in mrad
        self.Image.CoMMag = sqrt(CoMX.^2+CoMY.^2);
        self.Image.CoMMagNorm = rescale(self.Image.CoMMag);
        # CoM angle was calculated from the arctangent of the difference images (CoMX and CoMY)
        self.Image.CoMPh = atan2(CoMY,CoMX);
        # Adjust atan2 range from [-pi/2:pi/2) to [0:2pi)
        self.Image.CoMPh(self.Image.CoMPh < 0) = self.Image.CoMPh(self.Image.CoMPh < 0) + 2*pi;
        self.Image.CoMPhMag = self.Image.CoMPh;

        # Make iCoM/iDPC and dCoM/dDPC images - based on maths from Lazic et al.,
        # (https://doi.org/10.1016/j.ultramic.2015.10.011)
        #         [ky, kx] = meshgrid(floor(-self.D.NFrY/2):floor(-self.D.NFrY/2)+self.D.NFrY-1, ...
        #           floor(-self.D.NFrX/2):floor(-self.D.NFrX/2)+self.D.NFrX-1);
        [ky, kx] = meshgrid((1:self.D.NFrY)-self.P.RsCtr(2), (1:self.D.NFrX)-self.P.RsCtr(1));

        kr = sqrt(kx.^2+ky.^2); # 1:20;   -10 .. 0 .. 9;   -9.5 .. 0  .. 9.5
        kr(kr == 0) = 1; # a zero pixel will mess up the maths here
        kx = fftshift(kx);  ky = fftshift(ky);  kr = fftshift(kr);
        # integrated center of mass
        self.Image.iCoM = real(ifft2(kx.*fft2(CoMX)./(2*pi*1j*kr.^2))+ifft2(ky.*fft2(CoMY)./(2*pi*1j*kr.^2)));
        # differential center of mass
        self.Image.dCoM = real(ifft2(2*pi*1i*kx.*fft2(CoMX)+2*pi*1i*ky.*fft2(CoMY)));

        debugToc(self, [], "", dbT)

        ## Sub sub function
        def [CoMX,CoMY] = integrateCoM()
          Rscan = rotMatD(sd);  Rdetr = rotMatD(dr);
          # Make pixel array for masks
          [ygrid, xgrid] = meshgrid(((1:self.D.NPxY)-b0(2))*syf, (1:self.D.NPxX)-b0(1));
          im_real = cast(reshape(self.Mask.Ann,1,[]),self.D.DataType)*self.Data;

          # switch between detector types (except annular/round)
          if dmod == "CoMMod"
            # Mask off diffraction pattern: less than outer angle & greater than inner angle
            CoM = zeros(self.D.NFrS, 2, 'like',self.Data);
            # Integrated mass of each diffraction pattern within the mask:
            # Center of Mass adjusted to the center of the diffraction pattern
            CoM(:,1) = cast(reshape(xgrid.*self.Mask.Ann,1,[]), self.D.DataType) * self.Data./im_real;
            CoM(:,2) = cast(reshape(ygrid.*self.Mask.Ann,1,[]), self.D.DataType) * self.Data./im_real;
            # Adjust for scan rotation
            CoM = CoM*Rscan;
          elif dmod == "DPCMod"
            nrung = self.NRung.Value;  nseg = self.NSeg.Value;  rdist = ygrid.^2 + xgrid.^2;
            # Calculate the atan of all pixel positions within the image
            a = atan2d(ygrid,xgrid);                  # Get atan from -180 to 180
            a = a - dr;                               # subtract off any detector rotation applied
            a = a + 180/nseg;                         # shift atan by half of a segment span
            a(a < 0) = a(a < 0) + 360;                # shift the negative values of atan up by 360
            a(a >= 360) = a(a >= 360)-360;            # Get total range of atan from [0,360)
            # Preallocate a DPC/CoM vector image that will be the sum of all segments (i.e. DPC_A, DPC_B, ...)
            CoM_length = zeros(nrung*nseg,2,self.D.DataType);
            self.Mask.Seg = zeros(nrung*nseg,self.D.NPxS,'logical');
            for j = 1:nrung
              for i = 1:nseg
                # Define vectors k1 and k2 that correspond to the inner and outer angles of the detector for a given
                # number of rungs
                k1 = (j-1)*(ro-ri)/nrung+ri;
                k2 = (j)*(ro-ri)/nrung+ri;
                # less than outer angle & greater than/equal to inner angle & greater than the start of
                # the segment angle & less than the end of the segmenet angle
                self.Mask.Seg(nseg*(j-1)+i,:) = reshape( ...
                  rdist < k2^2 & rdist >= k1^2 & a >= (i-1)*360/nseg & a < (i)*360/nseg, [], 1);

                # Find center of mass of each segment in each rung, and adjust for scan and detector rotation
                t = (i-1)*360/nseg + dr;
                CoM_length(nseg*(j-1)+i,:) = 2*sind(360/nseg/2) / (3*360/nseg/2) ...
                  * (k1^3-k2^3)/(k1^2-k2^2) * [cosd(t) sind(t)] * Rscan * Rdetr;
              end
            end
            # integrated mass of each diffraction pattern within the mask:
            CoM = (self.Mask.Seg*self.Data./im_real)'*CoM_length;
          end
          # Convert to mrad and pull out x and y components of the CoM
          CoM = gather(reshape(CoM, [self.D.NFr 2])*self.mradPx.Value);
          CoMX = CoM(:,:,1);  CoMY = CoM(:,:,2);
        end
      end