
from utils.v3c.type import V3CUnitType
from utils.bitstream import Bitstream

#######################################################################################################
################################### V3c unit ##########################################################
#######################################################################################################

class V3CUnit:
  def __init__(self, type = None,bitstream_log=False):
    self.type      = type     
    self.bitstream = Bitstream(bitstream_log=bitstream_log)    

  def get_size(self) -> int:    
    return self.bitstream.get_size_bytes()

  def get_bitstream(self) -> Bitstream:
    self.bitstream.beginning()
    return self.bitstream

  def set_type(self, unit_type: V3CUnitType):
    self.type = unit_type
  
  #######################################################################################################
  ################################### V3C unit header ###################################################
  #######################################################################################################

  def write_header(self):
    self.bitstream.write_bits( self.type.value, 5 )
    if self.type == V3CUnitType.V3C_AVD or self.type == V3CUnitType.V3C_GVD or \
       self.type == V3CUnitType.V3C_OVD or self.type == V3CUnitType.V3C_AD: 
      self.bitstream.write_bits( 0, 4 )                                             # vuh_v3c_parameter_set_id  u(4)
      self.bitstream.write_bits( 0, 6 )                                             # vuh_atlas_id  u(6)
    if self.type == V3CUnitType.V3C_AVD:        
      self.bitstream.write_bits( 0, 7 )                                             # vuh_attribute_index  u(7)
      self.bitstream.write_bits( 0, 5 )                                             # vuh_attribute_partition_index  u(5)
      self.bitstream.write_bits( 0, 4 )                                             # vuh_map_index  u(4)
      self.bitstream.write_bits( 0, 1 )                                             # vuh_auxiliary_video_flag  u(1)
    elif self.type == V3CUnitType.V3C_GVD:
      self.bitstream.write_bits( 0,  4 )                                            # vuh_map_index  u(4)
      self.bitstream.write_bits( 0,  1 )                                            # vuh_auxiliary_video_flag  u(1)
      self.bitstream.write_bits( 0, 12 )                                            # vuh_reserved_zero_12bits  u(12)
    elif self.type == V3CUnitType.V3C_OVD or self.type == V3CUnitType.V3C_AD:
      self.bitstream.write_bits( 0, 17 )                                            # vuh_reserved_zero_17bits  u(17)
    else:
      self.bitstream.write_bits( 0, 27 )                                            # vuh_reserved_zero_27bits  u(27)      

  def read_header(self):
    self.type = V3CUnitType( self.bitstream.read_bits( 5 ) )
    if self.type == V3CUnitType.V3C_AVD or self.type == V3CUnitType.V3C_GVD or \
       self.type == V3CUnitType.V3C_OVD or self.type == V3CUnitType.V3C_AD: 
      self.bitstream.read_bits( 4 )                                                 # vuh_v3c_parameter_set_id  u(4)
      self.bitstream.read_bits( 6 )                                                 # vuh_atlas_id  u(6)
    if self.type == V3CUnitType.V3C_AVD:
      self.bitstream.read_bits( 7 )                                                 # vuh_attribute_index  u(7)
      self.bitstream.read_bits( 5 )                                                 # vuh_attribute_partition_index  u(5)
      self.bitstream.read_bits( 4 )                                                 # vuh_map_index  u(4)
      self.bitstream.read_bits( 1 )                                                 # vuh_auxiliary_video_flag  u(1)
    elif self.type == V3CUnitType.V3C_GVD:
      self.bitstream.read_bits(  4 )                                                # vuh_map_index  u(4)
      self.bitstream.read_bits(  1 )                                                # vuh_auxiliary_video_flag  u(1)
      self.bitstream.read_bits( 12 )                                                # vuh_reserved_zero_12bits  u(12)
    elif self.type == V3CUnitType.V3C_OVD or self.type == V3CUnitType.V3C_AD:
      self.bitstream.read_bits( 17 )                                                # vuh_reserved_zero_17bits  u(17)
    else:
      self.bitstream.read_bits( 27 )                                                # vuh_reserved_zero_27bits  u(27)     

#######################################################################################################