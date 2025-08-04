from utils.v3c.type    import NalUnitType

#######################################################################################################
################################### Nal unit ##########################################################
#######################################################################################################

class NalUnit(): 

  def __init__(self, type : NalUnitType = None, layer_id = 0, temporal_id = 0, data: bytearray = None): 
    self.type         = type
    self.layer_id     = layer_id 
    self.temporaly_id = temporal_id
    self.data         = bytearray(data) if data is not None else bytearray()

  #######################################################################################################

  def get_size(self):
    return len(self.data) + 2  # +2 for header size

  #######################################################################################################

  def __write_header(self, bitstream ):
    forbidden_zero_bit  = 0      
    type                = self.type.value
    layer_id            = self.layer_id
    temporaly_id_plus_1 = self.temporaly_id + 1
    bitstream.write_bits( forbidden_zero_bit, 1 )                                       # f(1)
    bitstream.write_bits( type, 6 )                                                     # u(6)
    bitstream.write_bits( layer_id, 6 )                                                 # u(6)  
    bitstream.write_bits( temporaly_id_plus_1, 3 )                                      # u(3)    
                                    
  def __read_header(self, bitstream ):                                    
    forbidden_zero_bit  = bitstream.read_bits(1)                                        # f(1)
    type                = bitstream.read_bits(6)                                        # u(6)
    layer_id            = bitstream.read_bits(6)                                        # u(6)  
    temporaly_id_plus_1 = bitstream.read_bits(3)                                        # u(3)       
    self.type           = NalUnitType(type)
    self.layer_id       = layer_id            
    self.temporaly_id   = temporaly_id_plus_1 - 1

  #######################################################################################################

  def write(self, bitstream):
    self.__write_header(bitstream)
    bitstream.write_buffer(self.data)

  def read(self, bitstream, size):
    self.__read_header(bitstream)
    self.data = bitstream.read_buffer(size - 2)

#######################################################################################################