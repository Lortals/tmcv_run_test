from utils.v3c.type    import NalUnitType, SeiPayloadType, V3CUnitType, Packing, Format
from utils.v3c.sei.sei import Sei
from utils.bitstream    import Bitstream

#######################################################################################################
######################## SEI Gsc Registered ########################################################### 
#######################################################################################################

class SeiGscRegistered(Sei):
  
  def __init__(self):
    from utils.group_of_frames import GroupOfFrames
    super().__init__()    
    self.sei_payload_type = SeiPayloadType.GSC_REGISTERED
  
  #######################################################################################################

  def write(self, bitstream, type: NalUnitType = None, gof=None):
    from utils.group_of_frames import GroupOfFrames
    num_videos_minus_1 = len(gof.videos) -1
    first_video = next(iter(gof.videos.values()))
    trans_position = first_video.trans_position 
    code_output_bitdepth = True if gof.bit_depth_pos != 32 or gof.bit_depth_att != 32 else False
    bitstream.write_bits(num_videos_minus_1, 5)                         # u(5)
    bitstream.write_bits(trans_position, 1)                             # u(1)
    bitstream.write_bits(code_output_bitdepth, 1)                       # u(1)    
    if code_output_bitdepth:
      bitstream.write_bits(gof.bit_depth_pos, 5)                               # u(5)
      bitstream.write_bits(gof.bit_depth_att, 5)                               # u(5)
    for idx, (_, video) in enumerate(gof.videos.items()): 
      type_value     = video.type.value 
      codec_id       = video.codec_id   
      packing_id     = video.packing.value  
      format_id      = video.format.value 
      bitdepth       = video.bitdepth 
      num_components_minus1 = len(video.min) - 1  
      bitstream.write_bits(type_value, 5)                               # u(5)
      bitstream.write_bits(bitdepth, 5)                                 # u(5)
      bitstream.write_bits(codec_id, 2)                                 # u(2)
      bitstream.write_bits(packing_id, 1)                               # u(1)
      bitstream.write_bits(format_id, 2)                                # u(2)
      bitstream.write_bits(num_components_minus1, 6 )                   # u(6)
      if not code_output_bitdepth:
        for j in range( num_components_minus1 + 1 ):  
          min_value = video.min[j]  
          max_value = video.max[j]  
          bitstream.write_float(min_value)                              # f(32)
          bitstream.write_float(max_value)                              # f(32)
  
  #######################################################################################################

  def read(self, bitstream, type: NalUnitType = None, gof=None):
    from utils.group_of_frames import GroupOfFrames, VideoData  
    num_videos_minus_1 = bitstream.read_bits(5)                         # u(5)
    trans_position     = bitstream.read_bits(1)                         # u(1)
    code_output_bitdepth = bitstream.read_bits(1)                       # u(1)
    if code_output_bitdepth:
       gof.bit_depth_pos = bitstream.read_bits(5)                              # u(5)
       gof.bit_depth_att = bitstream.read_bits(5)                              # u(5)    
    for i in range( num_videos_minus_1 + 1 ): 
      type_value             = bitstream.read_bits(5)                   # u(5)
      bitdepth               = bitstream.read_bits(5)                   # u(5)
      codec_id               = bitstream.read_bits(2)                   # u(2)
      packing_id             = bitstream.read_bits(1)                   # u(1)
      format_id              = bitstream.read_bits(2)                   # u(2)
      num_components_minus1  = bitstream.read_bits(6)                   # u(6)
      type       = V3CUnitType(type_value)  
      if type not in gof.videos:  
        gof.videos[type] = VideoData(type=type) 
      gof.videos[type].bitdepth       = bitdepth  
      gof.videos[type].codec_id       = codec_id  
      gof.videos[type].packing        = Packing( packing_id ) 
      gof.videos[type].format         = Format( format_id ) 
      gof.videos[type].trans_position = trans_position  
      gof.videos[type].num_components = num_components_minus1 + 1 
      gof.videos[type].min = [0.0] * (num_components_minus1 + 1)  
      gof.videos[type].max = [0.0] * (num_components_minus1 + 1)  
      if not code_output_bitdepth:
        for j in range( gof.videos[type].num_components ):  
          min_value = bitstream.read_float()                            # f(32)
          max_value = bitstream.read_float()                            # f(32)
          gof.videos[type].min[j] = min_value
          gof.videos[type].max[j] = max_value

#######################################################################################################
