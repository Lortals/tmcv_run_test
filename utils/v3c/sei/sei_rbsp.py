from utils.v3c.type            import NalUnitType
from utils.v3c.sei.sei_message import SeiMessage

#######################################################################################################
######################## Supplemental enhancement Information Raw byte sequence payloads ############## 
#######################################################################################################

class SeiRbsp():

  def __init__(self):
    pass

  #######################################################################################################

  def write(self, bitstream, type: NalUnitType = None, sei = [], gof=None ):  
    for i in range( len(sei) ):
      sei_message = SeiMessage()
      sei_message.write(bitstream, type, sei[i],gof=gof)
    bitstream.write_rbsp_trailing_bits()

  #######################################################################################################

  def read(self, bitstream, type: NalUnitType = None, gof=None ):
    sei = []
    while bitstream.more_rbsp_data():
      sei_message = SeiMessage()
      el = sei_message.read(bitstream, type=type,gof=gof)
      sei.append(el)
    bitstream.read_rbsp_trailing_bits()
    return sei

####################################################################################################### 