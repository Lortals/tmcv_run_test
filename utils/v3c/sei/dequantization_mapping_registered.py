from utils.v3c.type    import NalUnitType, SeiPayloadType, Quantization, V3CUnitType, Format
from utils.v3c.sei.sei import Sei

#######################################################################################################
######################## SEI Dequantization Mapping Registered ########################################
#######################################################################################################

class SeiDequantizationMappingRegistered(Sei):
  def __init__(self):
    super().__init__()    
    self.sei_payload_type = SeiPayloadType.DEQUANTIZATION_MAPPING_REGISTERED
  
  #######################################################################################################

  def write(self, bitstream, type: NalUnitType = None, gof=None):
    dtm_dequantize_type_cancel_flag = 1 if gof.videos is None else 0   
    bitstream.write_bits(dtm_dequantize_type_cancel_flag, 1)                  # u(1)
    if dtm_dequantize_type_cancel_flag == 0:
      dtm_dequantize_type_mappings_count_minus1 = len( gof.videos) - 1
      bitstream.write_bits(dtm_dequantize_type_mappings_count_minus1, 8)      # u(8)
      for i, (_, video) in enumerate( gof.videos.items()):
        dtm_video_type_id         = video.type.value
        dtm_bitdepth              = video.bitdepth
        dtm_quantization_type     = video.quantization.value
        dtm_num_components_minus1 = len(video.min) - 1
        bitstream.write_bits(dtm_video_type_id, 5)                            # u(5)
        bitstream.write_bits(dtm_bitdepth, 5)                                 # u(5)
        bitstream.write_bits(dtm_quantization_type, 5)                        # u(5)       
        bitstream.write_bits(dtm_num_components_minus1, 6)                    # u(6)
        for j in range( dtm_num_components_minus1 + 1 ):
          dtm_min_value = video.min[j]
          dtm_max_value = video.max[j]
          bitstream.write_float(dtm_min_value)                                # f(32)
          bitstream.write_float(dtm_max_value)                                # f(32)
          if video.quantization == Quantization.GAUSSIAN: 
            dtm_center_value = video.center[j]
            dtm_signa_value  = video.sigma[j]
            bitstream.write_float(dtm_center_value)                           # f(32)
            bitstream.write_float(dtm_signa_value)                            # f(32)
  
  #######################################################################################################

  def read(self, bitstream, type: NalUnitType = None, gof=None):
    from utils.group_of_frames import VideoData 
    dtm_dequantize_type_cancel_flag = bitstream.read_bits(1)                  # u(1)
    if dtm_dequantize_type_cancel_flag == 0:
      dtm_dequantize_type_mappings_count_minus1 = bitstream.read_bits(8)      # u(8)
      for i in range(dtm_dequantize_type_mappings_count_minus1 + 1):
        dtm_video_type_id         = bitstream.read_bits(5)                    # u(5)
        dtm_bitdepth              = bitstream.read_bits(5)                    # u(5)
        dtm_quantization_type     = bitstream.read_bits(5)                    # u(5)
        dtm_quantization_type     = Quantization(dtm_quantization_type)   
        dtm_num_components_minus1 = bitstream.read_bits(6)                    # u(6)
        type = V3CUnitType(dtm_video_type_id)        
        if type not in gof.videos:
          gof.videos[type] = VideoData(type=type)
        gof.videos[type].bitdepth     = dtm_bitdepth
        gof.videos[type].quantization = dtm_quantization_type        
        gof.videos[type].min          = [0.0] * (dtm_num_components_minus1 + 1)
        gof.videos[type].max          = [0.0] * (dtm_num_components_minus1 + 1)
        gof.videos[type].center       = [0.0] * (dtm_num_components_minus1 + 1)
        gof.videos[type].sigma        = [0.0] * (dtm_num_components_minus1 + 1)
        for j in range(dtm_num_components_minus1 + 1 ):
            dtm_min_value = bitstream.read_float()                            # f(32)
            dtm_max_value = bitstream.read_float()                            # f(32)
            gof.videos[type].min[j] = dtm_min_value
            gof.videos[type].max[j] = dtm_max_value            
            print("Read min max %s = %8.6f %8.6f  " % ( gof.videos[type].name(), gof.videos[type].min[j], gof.videos[type].max[j]))
            if gof.videos[type].quantization == Quantization.GAUSSIAN:
                dtm_center_value = bitstream.read_float()                     # f(32)
                dtm_signa_value  = bitstream.read_float()                     # f(32)
                gof.videos[type].center[j] = dtm_center_value
                gof.videos[type].sigma[j]  = dtm_signa_value

#######################################################################################################
