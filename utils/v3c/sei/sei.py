from utils.v3c.type import NalUnitType, SeiPayloadType
      
#######################################################################################################
######################## Supplemental enhancement Information ######################################### 
#######################################################################################################

class Sei():
  def __init__(self):
    self.sei_payload_type = None

  #######################################################################################################

  def write(self, bitstream, type: NalUnitType = None, gof=None):
    raise NotImplementedError("Must be implemented in subclass")

  #######################################################################################################

  def read(self, bitstream, type: NalUnitType = None, gof=None):
    raise NotImplementedError("Must be implemented in subclass")    

  #######################################################################################################

  def create(sei_payload_type: SeiPayloadType, *args, **kwargs) -> "Sei":
    from utils.v3c.sei.component_codec_mapping            import SeiComponentCodecMapping
    from utils.v3c.sei.gsc_registered                     import SeiGscRegistered
    from utils.v3c.sei.video_type_mapping_registered      import SeiVideoTypeMappingRegistered
    from utils.v3c.sei.input_camera_information           import SeiInputCameraInformation
    from utils.v3c.sei.dequantization_mapping_registered  import SeiDequantizationMappingRegistered
    sei_map = {
      SeiPayloadType.GSC_REGISTERED:                    SeiGscRegistered,
      SeiPayloadType.COMPONENT_CODEC_MAPPING:           SeiComponentCodecMapping,
      SeiPayloadType.VIDEO_TYPE_MAPPING_REGISTERED:     SeiVideoTypeMappingRegistered,
      SeiPayloadType.DEQUANTIZATION_MAPPING_REGISTERED: SeiDequantizationMappingRegistered,
      SeiPayloadType.INPUT_CAMERA_INFORMATION:          SeiInputCameraInformation,
    }
    sei_class = sei_map.get(sei_payload_type )
    if sei_class is None:
        raise ValueError(f"SEI payload type {sei_payload_type} not supported")
    return sei_class( *args, **kwargs)

#######################################################################################################