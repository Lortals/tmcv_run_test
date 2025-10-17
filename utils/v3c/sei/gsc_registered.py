from utils.v3c.type    import NalUnitType, SeiPayloadType, V3CUnitType, Packing, Format, ColorStandard, Quantization
from utils.v3c.sei.sei import Sei

#######################################################################################################
######################## SEI Gsc Registered ########################################################### 
#######################################################################################################

class SeiGscRegistered(Sei):
  
  def __init__(self):
    super().__init__()    
    self.sei_payload_type = SeiPayloadType.GSC_REGISTERED
  
  #######################################################################################################

  def write(self, bitstream, type: NalUnitType = None, gof=None):
    num_videos_minus_1 = len(gof.videos) -1
    first_video        = next(iter(gof.videos.values()))
    trans_position     = first_video.trans_position 
    sh_conversion      = first_video.sh_conversion.value
    src_sh_conversion  = gof.src_sh_conversion.value
    code_bd_pos_0      = first_video.bitdepth_pos[0] != 0  
    code_bd_pos_1      = first_video.bitdepth_pos[1] != 0  
    bitstream.write_bits(num_videos_minus_1, 5)                           # u(5)
    bitstream.write_bits(trans_position, 1)                               # u(1)
    bitstream.write_bits(sh_conversion, 2)                                # u(2)
    bitstream.write_bits(src_sh_conversion, 2)                            # u(2)
    bitstream.write_bits(code_bd_pos_0, 1)                                # u(1)
    if code_bd_pos_0:   
      bd_pos_0 = first_video.bitdepth_pos[0]  
      bitstream.write_bits(bd_pos_0, 5)                                   # u(5)
    bitstream.write_bits(code_bd_pos_1, 1)                                # u(1)
    if code_bd_pos_1: 
      bd_pos_1 = first_video.bitdepth_pos[1]  
      bitstream.write_bits(bd_pos_1, 5)                                   # u(5)    
    for _, (_, video) in enumerate(gof.videos.items()):   
      type_value     = video.type.value   
      codec_id       = video.codec_id     
      packing_id     = video.packing.value    
      format_id      = video.format.value   
      bitdepth       = video.bitdepth   
      quantization_type  = video.quantization.value    
      num_components_minus1 = len(video.min) - 1    
      bitstream.write_bits(type_value, 5)                                 # u(5)
      bitstream.write_bits(bitdepth, 5)                                   # u(5)
      bitstream.write_bits(codec_id, 2)                                   # u(2)
      bitstream.write_bits(packing_id, 1)                                 # u(1)
      bitstream.write_bits(format_id, 2)                                  # u(2)
      bitstream.write_bits(quantization_type, 2)                          # u(2)                      
      bitstream.write_bits(num_components_minus1, 7)                      # u(7)
      for j in range( num_components_minus1 + 1 ):    
        min_value = video.min[j]    
        max_value = video.max[j]    
        bitstream.write_float(min_value)                                  # f(32)
        bitstream.write_float(max_value)                                  # f(32)
        if video.quantization == Quantization.GAUSSIAN: 
          dtm_center_value = video.center[j]
          dtm_signa_value  = video.sigma[j]
          bitstream.write_float(dtm_center_value)                         # f(32)
          bitstream.write_float(dtm_signa_value)                          # f(32)
  
  
  #######################################################################################################

  def read(self, bitstream, type: NalUnitType = None, gof=None):
    from utils.group_of_frames import VideoData  
    num_videos_minus_1 = bitstream.read_bits(5)                           # u(5)
    trans_position     = bitstream.read_bits(1)                           # u(1)
    sh_conversion      = bitstream.read_bits(2)                           # u(2)
    src_sh_conversion  = bitstream.read_bits(2)                           # u(2)
    code_bd_pos_0      = bitstream.read_bits(1)                           # u(1) 
    bd_pos_0           = bitstream.read_bits(5) if code_bd_pos_0 else 0   # u(5)  
    code_bd_pos_1      = bitstream.read_bits(1)                           # u(1)    
    bd_pos_1           = bitstream.read_bits(5) if code_bd_pos_1 else 0   # u(5)
    gof.src_sh_conversion = ColorStandard( src_sh_conversion )
    for _ in range( num_videos_minus_1 + 1 ):   
      type_value             = bitstream.read_bits(5)                     # u(5)
      bitdepth               = bitstream.read_bits(5)                     # u(5)
      codec_id               = bitstream.read_bits(2)                     # u(2)
      packing_id             = bitstream.read_bits(1)                     # u(1)
      format_id              = bitstream.read_bits(2)                     # u(2)
      quantization_type      = bitstream.read_bits(2)                     # u(2)
      num_components_minus1  = bitstream.read_bits(7)                     # u(7)
      type                   = V3CUnitType(type_value)  
      if type not in gof.videos:  
        gof.videos[type] = VideoData(type=type) 
      gof.videos[type].bitdepth          = bitdepth  
      gof.videos[type].bitdepth_pos      = [bd_pos_0, bd_pos_1]
      gof.videos[type].codec_id          = codec_id  
      gof.videos[type].packing           = Packing( packing_id ) 
      gof.videos[type].format            = Format( format_id ) 
      gof.videos[type].trans_position    = trans_position  
      gof.videos[type].sh_conversion     = ColorStandard( sh_conversion )      
      gof.videos[type].quantization      = Quantization(quantization_type)          
      gof.videos[type].num_components    = num_components_minus1 + 1 
      gof.videos[type].min               = [0.0] * (num_components_minus1 + 1)  
      gof.videos[type].max               = [0.0] * (num_components_minus1 + 1)  
      gof.videos[type].center            = [0.0] * (num_components_minus1 + 1)  
      gof.videos[type].sigma             = [0.0] * (num_components_minus1 + 1)        
      for j in range( gof.videos[type].num_components ):  
        min_value = bitstream.read_float()                                # f(32)
        max_value = bitstream.read_float()                                # f(32)
        gof.videos[type].min[j] = min_value
        gof.videos[type].max[j] = max_value
        if gof.videos[type].quantization == Quantization.GAUSSIAN:
          dtm_center_value = bitstream.read_float()                     # f(32)
          dtm_signa_value  = bitstream.read_float()                     # f(32)
          gof.videos[type].center[j] = dtm_center_value
          gof.videos[type].sigma[j]  = dtm_signa_value

#######################################################################################################
