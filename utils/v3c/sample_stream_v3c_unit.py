# utils/v3c.py
# Module providing V3C (Video-based Point Cloud Compression) utilities.

import math
from utils.v3c.type import V3CUnitType
from utils.v3c.v3c_unit  import V3CUnit

########################################################################################################
#################################### Sample stream v3c unit ############################################
########################################################################################################

class SampleStreamV3CUnit:

  def __init__(self):
    self.v3c_units = []
    self.unit_size_precision_bytes_minus1 = 0
  
  #######################################################################################################

  def add_v3c_unit(self, type: V3CUnitType = None ) -> V3CUnit:
    unit = V3CUnit(type)
    self.v3c_units.append(unit)
    return unit

  def get_v3c_units(self) -> list:
    return self.v3c_units

  def get_size_overhead(self):
    return 8 * ( 1 + len( self.v3c_units ) * ( self.unit_size_precision_bytes_minus1 + 1 ) ) 

  #######################################################################################################

  def __write_header(self, bitstream):
    bitstream.write_bits( self.unit_size_precision_bytes_minus1, 3 )                    # u(3)
    bitstream.write_bits( 0, 5 )                                                        # u(5)  

  def __read_header(self, bitstream):
    self.unit_size_precision_bytes_minus1 = bitstream.read_bits( 3 )                    # u(3)
    zero                                  = bitstream.read_bits( 5 )                    # u(5)  

  #######################################################################################################

  def __write_v3c_unit(self, bitstream, v3c_unit, ):
    bitstream.write_bits( v3c_unit.get_size(), 8 * ( self.unit_size_precision_bytes_minus1 + 1 ) )
    bitstream.write_buffer( v3c_unit.bitstream.get_bytes() )

  def __read_v3c_unit(self, bitstream ):
    v3c_unit = V3CUnit()
    size   = bitstream.read_bits( 8 * ( self.unit_size_precision_bytes_minus1 + 1 ) )
    buffer = bitstream.read_buffer( size )
    v3c_unit.bitstream.from_bytes( buffer )
    return v3c_unit
  
  #######################################################################################################

  def write( self, bitstream ):
    self.__compute_unit_size_precision_bytes_minus1()
    self.__write_header( bitstream )
    for v3c_unit in self.v3c_units:
      self.__write_v3c_unit( bitstream, v3c_unit )

  def read( self, bitstream ): 
    self.__read_header( bitstream )
    while bitstream.more_data():      
      self.v3c_units.append( self.__read_v3c_unit( bitstream ) )
  
  #######################################################################################################

  def print(self):
    for index, v3c_unit in enumerate( self.v3c_units ):
      print("  v3c_unit[%2d] : type = %-16s size = %8d " % ( index, v3c_unit.type.name, v3c_unit.get_size()))

  #######################################################################################################

  def __compute_unit_size_precision_bytes_minus1(self, forced_prec = 1):
    max_size = 0
    for unit in self.v3c_units:
      size = unit.get_size()
      if size > max_size:
        max_size = size
    if max_size > 0:
      bits = math.ceil(math.log2(max_size))
    else:
      bits = 0
    precision = max(math.ceil(bits / 8.0), 1)
    precision = min(max(precision, forced_prec), 8)
    self.unit_size_precision_bytes_minus1 = precision - 1   

#######################################################################################################
