

from utils.v3c.type import V3CExtensionType, V3CUnitType
from utils.v3c.profile_level_tier import ProfileTierLevel
from utils.v3c.vps_extension import VpsExtension  
from utils.bitstream import Bitstream

#######################################################################################################
################################### V3c parameter set #################################################
#######################################################################################################

class V3cParameterSet():
  
  def __init__(self): 
    self.profile_tier_level        = ProfileTierLevel()
    self.v3CParameterSetId         = 0
    self.atlasCountMinus1          = 0 
    self.atlasId                   = 0 
    self.frameWidth                = 0
    self.frameHeight               = 0
    self.mapCountMinus1            = 0
    self.auxiliaryVideoPresentFlag = False
    self.occupancyVideoPresentFlag = False
    self.geometryVideoPresentFlag  = False
    self.attributeVideoPresentFlag = False
    self.packedVideoPresentFlag    = False
    self.extensionPresentFlag      = True
    self.extensionCount            = 0

  def initialize( self, gof, use_sei=False):
    from utils.group_of_frames import GroupOfFrames
    self.v3CParameterSetId    = 5
    self.frameWidth           = gof.block_width 
    self.frameHeight          = gof.block_height
    self.extensionPresentFlag = not use_sei
    self.extensionCount       = 1 if not use_sei else 0 
    self.gof                  = gof 

  def write(self, bitstream, gof, use_sei=False ):
    self.initialize( gof=gof, use_sei=use_sei )
    zero = 0
    self.profile_tier_level.write(bitstream)
    bitstream.write_bits(self.v3CParameterSetId, 4);                            # u(4) 
    bitstream.write_bits(zero, 8);                                              # u(8) 
    bitstream.write_bits(self.atlasCountMinus1, 6);                             # u(6) 
    for j in range( self.atlasCountMinus1 + 1 ) :                            
      bitstream.write_bits(self.atlasId, 6);                                    # u(6)   
      bitstream.write_uvlc(self.frameWidth);                                    # ue(v)  
      bitstream.write_uvlc(self.frameHeight);                                   # ue(v)  
      bitstream.write_bits(self.mapCountMinus1, 4);                             # u(4)   
      # Remove map count > 0 if and loop                
      bitstream.write_bits(self.auxiliaryVideoPresentFlag, 1);                  # u(1) 
      bitstream.write_bits(self.occupancyVideoPresentFlag, 1);                  # u(1) 
      bitstream.write_bits(self.geometryVideoPresentFlag , 1);                  # u(1) 
      bitstream.write_bits(self.attributeVideoPresentFlag, 1);                  # u(1) 
      bitstream.write_bits(self.packedVideoPresentFlag   , 1);                  # u(1) 
      # Remove video present flag == true parsing process                 

    bitstream.write_bits( self.extensionPresentFlag, 1);                        # u(1)  
    if self.extensionPresentFlag:                                          
      bitstream.write_bits(self.extensionCount, 8);                             # u(8)  
    if self.extensionCount > 0 :                                               
      # Code vps extension
      vpsExtensionsLength = 3 * self.extensionCount
      tempBitstreams = []
      for i in range( self.extensionCount ) :
        tempBitstreams.append( Bitstream(bitstream_log=bitstream.bitstream_log) )
        vpsExtension = VpsExtension()
        vpsExtension.write( V3CExtensionType.VPS_EXT_GSC, tempBitstreams[i], self.gof)
        vpsExtensionsLength += tempBitstreams[i].get_size_bytes()
      # Write vps extension
      vpsExtensionsLengthMinus1 = int(vpsExtensionsLength - 1)
      bitstream.write_uvlc( vpsExtensionsLengthMinus1 );                        # ue(v)      
      for i in range( self.extensionCount ):                
        extensionType   = V3CExtensionType.VPS_EXT_GSC.value                
        extensionLength = tempBitstreams[i].get_size_bytes()                
        bitstream.write_bits( extensionType  , 8 );                             # u(8)
        bitstream.write_bits( extensionLength, 16);                             # u(16)  
        bitstream.copy_from( tempBitstreams[i], 0, tempBitstreams[i].get_size_bytes() )
    bitstream.write_byte_alignment()

  def read(self, bitstream, gof ):
    from utils.group_of_frames import GroupOfFrames   
    self.profile_tier_level.read(bitstream)
    self.v3CParameterSetId = bitstream.read_bits(4);                            # u(4)  
    zero                   = bitstream.read_bits(8);                            # u(8)  
    self.atlasCountMinus1  = bitstream.read_bits(6);                            # u(6)  
    for j in range( 1 ) :                                                              
      self.atlasId         = bitstream.read_bits(6);                            # u(6)  
      self.frameWidth      = bitstream.read_uvlc();                             # ue(v) 
      self.frameHeight     = bitstream.read_uvlc();                             # ue(v) 
      self.mapCountMinus1  = bitstream.read_bits(4);                            # u(4)  
      # Remove map count > 0 if and loop                
      self.auxiliaryVideoPresentFlag = bitstream.read_bits(1);                  # u(1) 
      self.occupancyVideoPresentFlag = bitstream.read_bits(1);                  # u(1) 
      self.geometryVideoPresentFlag  = bitstream.read_bits(1);                  # u(1) 
      self.attributeVideoPresentFlag = bitstream.read_bits(1);                  # u(1) 
      self.packedVideoPresentFlag    = bitstream.read_bits(1);                  # u(1) 
      # Remove video present flag == true parsing process                 
    self.extensionPresentFlag = bitstream.read_bits(1);                         # u(1)
    if self.extensionPresentFlag > 0:                                         
      self.extensionCount =  bitstream.read_bits(8);                            # u(8) 
      if self.extensionCount > 0 :                                            
        vpsExtensionsLengthMinus1 = bitstream.read_uvlc();                      # ue(v) 
        for i in range( self.extensionCount ) :               
          extensionType   = bitstream.read_bits(8);                             # u(8) 
          extensionLength = bitstream.read_bits(16);                            # u(16) 
          tempBitstream   =  Bitstream(bitstream_log=bitstream.bitstream_log)          
          bitstream.copy_to( tempBitstream, extensionLength )          
          vpsExtension = VpsExtension()
          vpsExtension.read( V3CExtensionType( extensionType ), tempBitstream, gof )

    bitstream.read_byte_alignment()
    gof.block_width, gof.block_height = self.frameWidth, self.frameHeight
    
#######################################################################################################