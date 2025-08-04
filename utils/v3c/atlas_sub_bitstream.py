import math
from utils.v3c.type import NalUnitType
from utils.v3c.nal_unit import NalUnit

#######################################################################################################
################################### Atlas sub bitstream ###############################################
#######################################################################################################

class AtlasSubBitstream():
  
  def __init__(self): 
    self.unit_size_precision_bytes_minus1	= 0
    self.nal_units                        = []

  def add_nal_unit(self, type: NalUnitType = None, layer_id = 0, temporal_id = 0, data: bytearray = None):
    unit = NalUnit(type, layer_id, temporal_id, data)
    self.nal_units.append(unit)

  def get_nal_unit(self, index):  
    return self.nal_units[index]

  def get_nal_unit_count(self):
    return len(self.nal_units)  
    
  #######################################################################################################
  
  def __compute_unit_size_precision_bytes_minus1(self, forced_prec = 1):
      max_size = 0
      for unit in self.nal_units:
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
  
  def __write_sample_stream_nal_header(self, bitstream):
    zero = 0
    self.__compute_unit_size_precision_bytes_minus1()
    bitstream.write_bits(self.unit_size_precision_bytes_minus1, 3);                               # u(3) 
    bitstream.write_bits(zero, 5);                                                                # u(5)    

  def __read_sample_stream_nal_header(self, bitstream):
    self.unit_size_precision_bytes_minus1 = bitstream.read_bits(3);                               # u(3)  
    zero                                  = bitstream.read_bits(5);                               # u(5)  

  #######################################################################################################
  
  def __write_sample_stream_nal_unit(self, bitstream, nalu ):
    bitstream.write_bits( nalu.get_size(), 8 * ( self.unit_size_precision_bytes_minus1 + 1 ) );   # u(v)  
    nalu.write(bitstream)
  
  def __read_sample_stream_nal_unit(self, bitstream ):
    size = bitstream.read_bits(8 * ( self.unit_size_precision_bytes_minus1 + 1 ) );               # u(v)
    nalu = NalUnit()  
    nalu.read(bitstream, size)
    self.nal_units.append(nalu)

  #######################################################################################################
  
  def write(self, bitstream):
    self.__write_sample_stream_nal_header(bitstream)
    for unit in self.nal_units:
      self.__write_sample_stream_nal_unit(bitstream, unit)

  def read(self, bitstream):
    self.__read_sample_stream_nal_header(bitstream)
    while bitstream.more_data(): 
      self.__read_sample_stream_nal_unit(bitstream)

#######################################################################################################