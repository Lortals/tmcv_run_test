from utils.v3c.type    import NalUnitType, SeiPayloadType
from utils.v3c.sei.sei import Sei
from utils.bitstream   import Bitstream

#######################################################################################################
######################## Supplemental enhancement Information meassage ################################ 
#######################################################################################################

class SeiMessage():

  def __init__(self):
    pass 

  #######################################################################################################   

  def write(self, bitstream, type: NalUnitType = None, sei: Sei = None, gof=None):
    if sei is None:
      raise ValueError("sei is None")
    payload_type = sei.sei_payload_type.value
    ff = 0xff
    while payload_type >= 0xff: 
      bitstream.write_bits(ff, 8)                                               # u(8)
      payload_type -= 0xff
    bitstream.write_bits(payload_type, 8)                                       # u(8)
    sub_bitstream = Bitstream(bitstream_log=bitstream.bitstream_log)
    sei.write(sub_bitstream, type=type,gof=gof)
    sub_bitstream.write_length_alignment()
    payload_size = sub_bitstream.get_size_bytes()
    while payload_size >= 0xff: 
      bitstream.write_bits(ff, 8)                                               # u(8)
      payload_size -= 0xff
    bitstream.write_bits(payload_size, 8)                                       # u(8)
    bitstream.copy_from(sub_bitstream, 0, sub_bitstream.get_size_bytes() )
  
  #######################################################################################################   
    
  def read(self, bitstream, type: NalUnitType = None, gof=None):
    payload_type = 0
    while True:
      byte = bitstream.read_bits(8)                                            # u(8)
      if byte == 0xff:
        payload_type += 0xff
      else: 
        payload_type += byte
        break
    payload_size = 0
    while True:
      byte = bitstream.read_bits(8)                                           # u(8)
      if byte == 0xff:
        payload_size += 0xff
      else:
        payload_size += byte
        break          
    sub_bitstream = Bitstream(bitstream_log=bitstream.bitstream_log)
    bitstream.copy_to(sub_bitstream, payload_size)
    sei = Sei.create( SeiPayloadType(payload_type) )
    sei.read(sub_bitstream, type=type, gof=gof)
    return sei

#######################################################################################################