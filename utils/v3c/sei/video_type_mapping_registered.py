from utils.v3c.type    import NalUnitType, SeiPayloadType, VideoComponentId, V3CUnitType, Packing
from utils.v3c.sei.sei import Sei

#######################################################################################################
######################## SEI Video Type Mapping Registered ############################################ 
#######################################################################################################

class SeiVideoTypeMappingRegistered(Sei):

  def __init__(self,videos=None):
    super().__init__()
    self.sei_payload_type = SeiPayloadType.VIDEO_TYPE_MAPPING_REGISTERED
  
  #######################################################################################################   
    
  def write(self, bitstream, type: NalUnitType = None, gof=None):
    vtm_video_type_cancel_flag = 1 if gof.videos is None else 0   
    bitstream.write_bits(vtm_video_type_cancel_flag, 1)                       # u(1)
    if vtm_video_type_cancel_flag == 0:
      vtm_video_type_mappings_count_minus1 = len( gof.videos) - 1
      bitstream.write_bits(vtm_video_type_mappings_count_minus1, 8)           # u(8)
      for i, (_, video) in enumerate( gof.videos.items()):
        dtm_video_type_id        = video.type.value
        vtm_num_components_minus1 = len(video.list_params) - 1        
        bitstream.write_bits(dtm_video_type_id, 5)                            # u(5)
        bitstream.write_bits(vtm_num_components_minus1, 7)                    # u(7)         
        for j, comp in enumerate( video.list_params ):
          component_id = VideoComponentId.from_param_name(comp).value
          bitstream.write_bits(component_id, 6)                               # u(6) 
  
  #######################################################################################################       

  def read(self, bitstream, type: NalUnitType = None, gof=None):
    from utils.group_of_frames import VideoData 
    vtm_video_type_cancel_flag = bitstream.read_bits(1)                       # u(1)
    if vtm_video_type_cancel_flag == 0:
      vtm_video_type_mappings_count_minus1 = bitstream.read_bits(8)           # u(8) 
      for i in range(vtm_video_type_mappings_count_minus1 + 1):
        vtm_video_type_id         = bitstream.read_bits(5)                    # u(5)
        vtm_num_components_minus1 = bitstream.read_bits(7)                    # u(7)
        vtm_component_id = []
        for j in range(vtm_num_components_minus1 + 1):
          component_id = bitstream.read_bits(6)                               # u(6) 
          vtm_component_id.append( VideoComponentId(component_id).get_param_names() )                
        # Store the video information in the group of frames
        type = V3CUnitType(vtm_video_type_id)        
        if type not in gof.videos:
          gof.videos[type] = VideoData(type=type)
        gof.videos[type].list_params = vtm_component_id        

#######################################################################################################