#######################################################################################################
################################### profile tier level ################################################
#######################################################################################################

class ProfileTierLevel:

  def __init__(self): 
    self.tierFlag                   = False
    self.profileCodecGroupIdc       = 1  
    self.profileToolsetIdc          = 0  
    self.profileReconstructionIdc   = 0  
    self.maxDecodesIdc              = 15 
    self.levelIdc                   = 0 
    self.numSubProfiles             = 0 
    self.extendedSubProfileFlag     = False
    self.toolConstraintsPresentFlag = False

  def write(self, bitstream):
    zero = 0
    fff  = 0xfff
    bitstream.write_bits(self.tierFlag                , 1)                          # u(1) 
    bitstream.write_bits(self.profileCodecGroupIdc    , 7)                          # u(7) 
    bitstream.write_bits(self.profileToolsetIdc       , 8)                          # u(8) 
    bitstream.write_bits(self.profileReconstructionIdc, 8)                          # u(8) 
    bitstream.write_bits(zero                         , 16)                         # u(16)
                    
    bitstream.write_bits(self.maxDecodesIdc           , 4)                          # u(4) 
    bitstream.write_bits(fff                          , 12)                         # u(12)
    bitstream.write_bits(self.levelIdc                , 8)                          # u(8) 
    bitstream.write_bits(self.numSubProfiles          , 6)                          # u(6) 
    bitstream.write_bits(self.extendedSubProfileFlag  , 1)                          # u(1) 
    # for i in range(0):                    
    #   v = ptl.getExtendedSubProfileFlag() == 0 ? 32 : 64;                   
    #   bitstream.write_bits(ptl.getSubProfileIdc(i), v);                           # u(v)    
    bitstream.write_bits(self.toolConstraintsPresentFlag, 1)                        # u(1) 
    # if (ptl.getToolConstraintsPresentFlag()) {
    #   profileToolsetConstraintsInformation(
    #     ptl.getProfileToolsetConstraintsInformation(), bitstream);
    # }

  def read(self, bitstream):
    self.tierFlag                 = bitstream.read_bits(1)                          # u(1)  
    self.profileCodecGroupIdc     = bitstream.read_bits(7)                          # u(7)  
    self.profileToolsetIdc        = bitstream.read_bits(8)                          # u(8)  
    self.profileReconstructionIdc = bitstream.read_bits(8)                          # u(8)  
    zero                          = bitstream.read_bits(16)                         # u(16) 
    self.maxDecodesIdc            = bitstream.read_bits(4)                          # u(4)  
    fff                           = bitstream.read_bits(12)                         # u(12)   
    self.levelIdc                 = bitstream.read_bits(8)                          # u(8)   
    self.numSubProfiles           = bitstream.read_bits(6)                          # u(6)   
    self.extendedSubProfileFlag   = bitstream.read_bits(1)                          # u(1)   
    # for i in range(0):  
    #   v = ptl.getExtendedSubProfileFlag() == 0 ? 32 : 64; 
    #   ptl.getSubProfileIdc(i) = bitstream.read_bits(, v);                         # u(v)    
    self.toolConstraintsPresentFlag = bitstream.read_bits(1)                        # u(1)
    # if (ptl.getToolConstraintsPresentFlag()) {
    #   profileToolsetConstraintsInformation(
    #     ptl.getProfileToolsetConstraintsInformation(), bitstream);
    # }

#######################################################################################################
