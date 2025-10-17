
from utils.v3c.type    import NalUnitType, SeiPayloadType
from utils.v3c.sei.sei import Sei

#######################################################################################################
######################## SEI Component Codec Mapping ################################################## 
#######################################################################################################

class SeiComponentCodecMapping(Sei):
  
  def __init__(self, ccm_codec_mappings = {} ):
    super().__init__()
    self.sei_payload_type = SeiPayloadType.COMPONENT_CODEC_MAPPING

  #######################################################################################################

  def write(self, bitstream, type: NalUnitType = None, gof=None):
    ccm_component_codec_cancel_flag = 0
    ccm_codec_mappings = gof.codecs
    bitstream.write_bits(ccm_component_codec_cancel_flag, 1)        # u(1)
    if ccm_component_codec_cancel_flag == 0:
      count = len(ccm_codec_mappings)
      bitstream.write_bits(count - 1, 8)                            # u(8)
      for codec_id, codec_4cc in enumerate(ccm_codec_mappings):
        bitstream.write_bits(codec_id, 8)                           # u(8)
        bitstream.write_string(codec_4cc)                           # st(v)

  #######################################################################################################

  def read(self, bitstream, type: NalUnitType = None, gof=None):
    from utils.group_of_frames import GroupOfFrames
    ccm_component_codec_cancel_flag = bitstream.read_bits(1)        # u(1)
    if ccm_component_codec_cancel_flag == 0:
      count_minus_1 = bitstream.read_bits(8)                        # u(8)
      for _ in range(count_minus_1 + 1):
        codec_id  = bitstream.read_bits(8)                          # u(8)
        codec_4cc = bitstream.read_string()                         # st(v)
        gof.codecs.append( codec_4cc )

#######################################################################################################