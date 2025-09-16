

from enum import Enum
import numpy as np
import re

#######################################################################################################
################################### V3C unit type #####################################################
#######################################################################################################

class V3CUnitType(Enum):
  V3C_VPS           =  0  #  0: Sequence parameter set (v3c_parameter_set)
  V3C_AD            =  1  #  1: Patch Data Group (Atlas sub-bitstream)
  V3C_OVD           =  2  #  2: Occupancy Video Data (video_sub_bitstream)
  V3C_GVD           =  3  #  3: Geometry Video Data (video_sub_bitstream)
  V3C_AVD           =  4  #  4: Attribute Video Data (video_sub_bitstream)
  V3C_PVD           =  5  #  5: Packed Video Data
  V3C_CAD           =  6  #  6: Common Atlas Data
  V3C_BMD           =  7  #  7: Basemesh Data
  V3C_GSC_0         =  8  #  8: GSC 0 
  V3C_GSC_1         =  9  #  9: GSC 1 
  V3C_GSC_2         = 10  # 10: GSC 2 
  V3C_GSC_3         = 11  # 11: GSC 3 
  V3C_GSC_4         = 12  # 12: GSC 4 
  V3C_GSC_5         = 13  # 13: GSC 5 
  V3C_GSC_6         = 14  # 14: GSC 6 
  V3C_GSC_7         = 15  # 15: GSC 7 
  V3C_GSC_8         = 16  # 16: GSC 8 
  V3C_GSC_9         = 17  # 17: GSC 9 
  V3C_GSC_10        = 18  # 18: GSC 10
  V3C_GSC_11        = 19  # 19: GSC 11
  V3C_GSC_12        = 20  # 20: GSC 12
  V3C_GSC_13        = 21  # 21: GSC 13
  V3C_GSC_14        = 22  # 22: GSC 14
  V3C_GSC_15        = 23  # 23: GSC 15
  V3C_GSC_16        = 24  # 24: GSC 16
  V3C_GSC_17        = 25  # 25: GSC 17
  V3C_GSC_18        = 26  # 26: GSC 18
  V3C_GSC_19        = 27  # 27: GSC 19
  V3C_GSC_20        = 28  # 28: GSC 20
  V3C_RSVD_29       = 29  # 29: Reserved
  V3C_RSVD_30       = 30  # 30: Reserved
  V3C_RSVD_31       = 32  # 32: Reserved
  NUM_V3C_UNIT_TYPE = 33  # 33: undefined
   
#######################################################################################################
################################### V3C extension type ################################################
#######################################################################################################

class V3CExtensionType(Enum):
  VPS_EXT_UNSPECIFIED = 0
  VPS_EXT_PACKED      = 1  
  VPS_EXT_MIV         = 2
  VPS_EXT_MIV2        = 3 
  VPS_EXT_VDMC        = 4 
  VPS_EXT_GSC         = 5 

#######################################################################################################
################################### Video codec group id ##############################################
#######################################################################################################

class VideoCodecGroupId(Enum):
  AVC_Progressive_High  = 0   # 
  HEVC_Main10           = 1   # 
  HEVC444               = 2   # 
  VVC_Main10            = 3   # 
  HEVC_Main             = 4   # 
  AC_CODED              = 5   #  AC_CODED + HEVC_Main10  
  MP4RA                 = 127 #

#######################################################################################################
################################### Video Encoder id ##################################################
#######################################################################################################

class VideoEncoderId (Enum):
  HM                    = 0
  VTM                   = 1
  VV                    = 2
  JM                    = 3
  UNKNOWN_VIDEO_ENCODER = 255 

#######################################################################################################
################################### Quantization id ###################################################
#######################################################################################################

class Quantization(Enum):
  LINEAR   = 0   
  GAUSSIAN = 1    
  NONE     = 31

  @classmethod
  def from_string(cls, name: str) -> "Quantization":
    name_mapping = {        
      "linear":   Quantization.LINEAR,
      "gaussian": Quantization.GAUSSIAN,
      "none":     Quantization.NONE
    }
    try:
      return name_mapping[name.lower()]
    except KeyError:
      raise ValueError(f"Unknown quantization type: {name}")

#######################################################################################################
################################### Color standart ####################################################
#######################################################################################################

class ColorStandard(Enum):
  NONE = 0
  BT601 = 1
  BT709 = 2
  BT2020 = 3

  @classmethod
  def from_string(cls, name: str) -> "ColorStandard | None":
    name_mapping = {
      "0": ColorStandard.NONE,
      "601": ColorStandard.BT601,
      "709": ColorStandard.BT709,
      "2020": ColorStandard.BT2020,
    }
    try:
      return name_mapping[name.lower()]
    except KeyError:
      raise ValueError(f"Unknown color standard: {name}")
    
  def rgb2yuv_uint16(self, block_r: np.ndarray, block_g: np.ndarray, block_b: np.ndarray, bitdepth: int):
    max_val = 2**bitdepth - 1
    R = block_r.astype(np.float32) / max_val
    G = block_g.astype(np.float32) / max_val
    B = block_b.astype(np.float32) / max_val
    coeffs = {
      ColorStandard.BT601: (0.2990, 0.5870, 0.1140, 0.5640, 0.7130),
      ColorStandard.BT709: (0.2126, 0.7152, 0.0722, 0.5389, 0.6350),
      ColorStandard.BT2020: (0.2627, 0.6780, 0.0593, 0.6780, 0.6350),
    }
    if self not in coeffs:
      raise ValueError(f"Unsupported color standard: {self}")
    Kr, Kg, Kb, cb_fac, cr_fac = coeffs[self]
    Yf  = Kr * R + Kg * G + Kb * B
    Cbf = cb_fac * (B - Yf) + 0.5
    Crf = cr_fac * (R - Yf) + 0.5
    Y  = np.clip(np.round(Yf * max_val),  0, max_val).astype(np.uint16)
    Cb = np.clip(np.round(Cbf * max_val), 0, max_val).astype(np.uint16)
    Cr = np.clip(np.round(Crf * max_val), 0, max_val).astype(np.uint16)
    return Y, Cb, Cr

  def yuv2rgb_uint16(self, block_y: np.ndarray, block_cb: np.ndarray, block_cr: np.ndarray, bitdepth: int):
      max_val = 2**bitdepth - 1
      Yf  = block_y.astype(np.float32) / max_val
      Cbf = block_cb.astype(np.float32) / max_val
      Crf = block_cr.astype(np.float32) / max_val
      coeffs = {
        ColorStandard.BT601: (0.2990, 0.5870, 0.1140, 1.4020, 1.7720),
        ColorStandard.BT709: (0.2126, 0.7152, 0.0722, 1.5748, 1.8556),
        ColorStandard.BT2020: (0.2627, 0.6780, 0.0593, 1.4746, 1.8814),
      }
      if self not in coeffs:
        raise ValueError(f"Unsupported color standard: {self}")

      Kr, Kg, Kb, cr_gain, cb_gain = coeffs[self]
      Rf = Yf + cr_gain * (Crf - 0.5)
      Bf = Yf + cb_gain * (Cbf - 0.5)
      Gf = (Yf - Kr*Rf - Kb*Bf) / Kg
      R = np.clip(np.round(Rf * max_val), 0, max_val).astype(np.uint16)
      G = np.clip(np.round(Gf * max_val), 0, max_val).astype(np.uint16)
      B = np.clip(np.round(Bf * max_val), 0, max_val).astype(np.uint16)
      return R, G, B

  def rgb2yuv_float(self, R: np.ndarray, G: np.ndarray, B: np.ndarray):
      coeffs = {
          ColorStandard.BT601: (0.2990, 0.5870, 0.1140, 0.5640, 0.7130),
          ColorStandard.BT709: (0.2126, 0.7152, 0.0722, 0.5389, 0.6350),
          ColorStandard.BT2020: (0.2627, 0.6780, 0.0593, 0.6780, 0.6350),
      }
      if self not in coeffs:
          raise ValueError(f"Unsupported color standard: {self}")
      Kr, Kg, Kb, cb_fac, cr_fac = coeffs[self]
      Y  = Kr * R + Kg * G + Kb * B
      Cb = cb_fac * (B - Y) + 0.5
      Cr = cr_fac * (R - Y) + 0.5
      return Y, Cb, Cr

  def yuv2rgb_float(self, Y: np.ndarray, Cb: np.ndarray, Cr: np.ndarray):
      coeffs = {
          ColorStandard.BT601: (0.2990, 0.5870, 0.1140, 1.4020, 1.7720),
          ColorStandard.BT709: (0.2126, 0.7152, 0.0722, 1.5748, 1.8556),
          ColorStandard.BT2020: (0.2627, 0.6780, 0.0593, 1.4746, 1.8814),
      }
      if self not in coeffs:
          raise ValueError(f"Unsupported color standard: {self}")
      Kr, Kg, Kb, cr_gain, cb_gain = coeffs[self]
      R = Y + cr_gain * (Cr - 0.5)
      B = Y + cb_gain * (Cb - 0.5)
      G = (Y - Kr*R - Kb*B) / Kg
      return R, G, B

#######################################################################################################
################################### Format id #########################################################
#######################################################################################################

class Format(Enum):
  YUV444 = 0   
  YUV420 = 1    
  YUV400 = 2

  @classmethod
  def from_string(cls, name: str) -> "Format":
    name_mapping = {        
      "yuv444": Format.YUV444,
      "yuv420": Format.YUV420,
      "yuv400": Format.YUV400
    }
    try:
      return name_mapping[name.lower()]
    except KeyError:
      raise ValueError(f"Unknown video format: {name}")

  def video_name(self) -> str:
      mapping = {
          Format.YUV444: "444",
          Format.YUV420: "420",
          Format.YUV400: "400",
      }
      return mapping[self]

#######################################################################################################
################################### Packing id ########################################################
#######################################################################################################

class Packing(Enum):
  PLANAR = 0   
  TEMPORAL = 1    

  @classmethod
  def from_string(cls, name: str) -> "Packing":
    name_mapping = {        
      "planar":   Packing.PLANAR,
      "temporal": Packing.TEMPORAL
    }
    try:
      return name_mapping[name.lower()]
    except KeyError:
      raise ValueError(f"Unknown patcking type: {name}")

#######################################################################################################
################################### Nal unit type #####################################################
#######################################################################################################

class NalUnitType(Enum):
    NAL_TRAIL_N         = 0   # Coded tile of a non-TSA, non STSA trailing atlas frame ACL
    NAL_TRAIL_R         = 1   # Coded tile of a non-TSA, non STSA trailing atlas frame ACL
    NAL_TSA_N           = 2   # Coded tile of a TSA atlas frame ACL
    NAL_TSA_R           = 3   # Coded tile of a TSA atlas frame ACL
    NAL_STSA_N          = 4   # Coded tile of a STSA atlas frame ACL
    NAL_STSA_R          = 5   # Coded tile of a STSA atlas frame ACL
    NAL_RADL_N          = 6   # Coded tile of a RADL atlas frame ACL
    NAL_RADL_R          = 7   # Coded tile of a RADL atlas frame ACL
    NAL_RASL_N          = 8   # Coded tile of a RASL atlas frame ACL
    NAL_RASL_R          = 9   # Coded tile of a RASL atlas frame ACL
    NAL_SKIP_N          = 10  # Coded tile of a skipped atlas frame ACL
    NAL_SKIP_R          = 11  # Coded tile of a skipped atlas frame ACL
    NAL_RSV_ACL_N12     = 12  # Reserved non-IRAP sub-layer non-reference ACL NAL unit types ACL
    NAL_RSV_ACL_R13     = 13  # Reserved non-IRAP sub-layer reference ACL NAL unit types ACL
    NAL_RSV_ACL_N14     = 14  # Reserved non-IRAP sub-layer non-reference ACL NAL unit types ACL
    NAL_RSV_ACL_R15     = 15  # Reserved non-IRAP sub-layer reference ACL NAL unit types ACL
    NAL_BLA_W_LP        = 16  # Coded tile of a BLA atlas frame ACL
    NAL_BLA_W_RADL      = 17  # Coded tile of a BLA atlas frame ACL
    NAL_BLA_N_LP        = 18  # Coded tile of a BLA atlas frame ACL
    NAL_GBLA_W_LP       = 19  # Coded tile of a GBLA atlas frame ACL
    NAL_GBLA_W_RADL     = 20  # Coded tile of a GBLA atlas frame ACL
    NAL_GBLA_N_LP       = 21  # Coded tile of a GBLA atlas frame ACL
    NAL_IDR_W_RADL      = 22  # Coded tile of an IDR atlas frame ACL
    NAL_IDR_N_LP        = 23  # Coded tile of an IDR atlas frame ACL
    NAL_GIDR_W_RADL     = 24  # Coded tile of a GIDR atlas frame ACL
    NAL_GIDR_N_LP       = 25  # Coded tile of a GIDR atlas frame ACL
    NAL_CRA             = 26  # Coded tile of a CRA atlas frame ACL
    NAL_GCRA            = 27  # Coded tile of a GCRA atlas frame ACL
    NAL_RSV_IRAP_ACL_28 = 28  # Reserved IRAP ACL NAL unit types ACL
    NAL_RSV_IRAP_ACL_29 = 29  # Reserved IRAP ACL NAL unit types ACL
    NAL_RSV_ACL_30      = 30  # Reserved non-IRAP ACL NAL unit types ACL
    NAL_RSV_ACL_31      = 31  # Reserved non-IRAP ACL NAL unit types ACL
    NAL_RSV_ACL_32      = 32  # Reserved non-IRAP ACL NAL unit types ACL
    NAL_RSV_ACL_33      = 33  # Reserved non-IRAP ACL NAL unit types ACL
    NAL_RSV_ACL_34      = 34  # Reserved non-IRAP ACL NAL unit types ACL
    NAL_RSV_ACL_35      = 35  # Reserved non-IRAP ACL NAL unit types ACL
    NAL_ASPS            = 36  # Atlas sequence parameter set non-ACL
    NAL_AFPS            = 37  # Atlas frame parameter set non-ACL
    NAL_AUD             = 38  # Access unit delimiter non-ACL
    NAL_V3C_AUD         = 39  # V3C access unit delimiter non-ACL
    NAL_EOS             = 40  # End of sequence non-ACL
    NAL_EOB             = 41  # End of bitstream non-ACL
    NAL_FD              = 42  # Filler non-ACL
    NAL_PREFIX_NSEI     = 43  # Non-essential supplemental enhancement information non-ACL
    NAL_SUFFIX_NSEI     = 44  # Non-essential supplemental enhancement information non-ACL
    NAL_PREFIX_ESEI     = 45  # Essential supplemental enhancement information non-ACL
    NAL_SUFFIX_ESEI     = 46  # Essential supplemental enhancement information non-ACL
    NAL_AAPS            = 47  # Atlas adaptation parameter set non-ACL
    NAL_RSV_NACL_48     = 48  # Reserved non-ACL NAL unit types non-ACL
    NAL_RSV_NACL_49     = 49  # Reserved non-ACL NAL unit types non-ACL
    NAL_RSV_NACL_50     = 50  # Reserved non-ACL NAL unit types non-ACL
    NAL_RSV_NACL_51     = 51  # Reserved non-ACL NAL unit types non-ACL
    NAL_RSV_NACL_52     = 52  # Reserved non-ACL NAL unit types non-ACL
    NAL_UNSPEC_53       = 53  # Unspecified non-ACL NAL unit types non-ACL
    NAL_UNSPEC_54       = 54  # Unspecified non-ACL NAL unit types non-ACL
    NAL_UNSPEC_55       = 55  # Unspecified non-ACL NAL unit types non-ACL
    NAL_UNSPEC_56       = 56  # Unspecified non-ACL NAL unit types non-ACL
    NAL_UNSPEC_57       = 57  # Unspecified non-ACL NAL unit types non-ACL
    NAL_UNSPEC_58       = 58  # Unspecified non-ACL NAL unit types non-ACL
    NAL_UNSPEC_59       = 59  # Unspecified non-ACL NAL unit types non-ACL
    NAL_UNSPEC_60       = 60  # Unspecified non-ACL NAL unit types non-ACL
    NAL_UNSPEC_61       = 61  # Unspecified non-ACL NAL unit types non-ACL
    NAL_UNSPEC_62       = 62  # Unspecified non-ACL NAL unit types non-ACL
    NAL_UNSPEC_63       = 63  # Unspecified non-ACL NAL unit types non-ACL

#######################################################################################################
################################### Sei payload type ##################################################
#######################################################################################################

class SeiPayloadType(Enum):
    BUFFERING_PERIOD                  = 0
    ATLAS_FRAME_TIMING                = 1
    FILLER_PAYLOAD                    = 2
    USER_DATA_REGISTERED_ITUTT35      = 3
    USER_DATA_UNREGISTERED            = 4
    RECOVERY_POINT                    = 5
    NO_RECONSTRUCTION                 = 6
    TIME_CODE                         = 7
    SEI_MANIFEST                      = 8
    SEI_PREFIX_INDICATION             = 9
    ACTIVE_SUB_BITSTREAMS             = 10
    COMPONENT_CODEC_MAPPING           = 11
    SCENE_OBJECT_INFORMATION          = 12
    OBJECT_LABEL_INFORMATION          = 13
    PATCH_INFORMATION                 = 14
    VOLUMETRIC_RECTANGLE_INFORMATION  = 15
    ATLAS_OBJECT_INFORMATION          = 16
    VIEWPORT_CAMERA_PARAMETERS        = 17
    VIEWPORT_POSITION                 = 18
    DECODED_ATLAS_INFORMATION_HASH    = 19
    ATTRIBUTE_TRANSFORMATION_PARAMS   = 64
    OCCUPANCY_SYNTHESIS               = 65
    GEOMETRY_SMOOTHING                = 66
    ATTRIBUTE_SMOOTHING               = 67
    VPCC_REGISTERED                   = 68
    RESERVED_MESSAGE                  = 69
    VIEWING_SPACE                     = 128
    VIEWING_SPACE_HANDLING            = 129
    GEOMETRY_UPSCALING_PARAMETERS     = 130
    ATLAS_VIEW_ENABLED                = 131
    OMAF_V1_COMPATIBLE                = 132
    GEOMETRY_ASSISTANCE               = 133
    EXTENDED_GEOMETRY_ASSISTANCE      = 134
    MIV_REGISTERED                    = 135
    VDMC_REGISTERED                   = 192
    GSC_REGISTERED                    = 193
    VIDEO_TYPE_MAPPING_REGISTERED     = 194
    DEQUANTIZATION_MAPPING_REGISTERED = 195
    INPUT_CAMERA_INFORMATION          = 196

#######################################################################################################
################################### Sei payload type ##################################################
#######################################################################################################

class VideoComponentId(Enum):
    X         = 0
    Y         = 1
    Z         = 2
    OPACITY   = 3
    SCALE_X   = 4
    SCALE_Y   = 5
    SCALE_Z   = 6
    ROT_X     = 7
    ROT_Y     = 8
    ROT_Z     = 9    
    ROT_W     = 10
    F_DC_0    = 11
    F_DC_1    = 12
    F_DC_2    = 13
    F_REST_0  = 14
    F_REST_1  = 15
    F_REST_2  = 16
    F_REST_3  = 17
    F_REST_4  = 18
    F_REST_5  = 19
    F_REST_6  = 20
    F_REST_7  = 21
    F_REST_8  = 22
    F_REST_9  = 23
    F_REST_10 = 24
    F_REST_11 = 25
    F_REST_12 = 26
    F_REST_13 = 27
    F_REST_14 = 28
    F_REST_15 = 29
    F_REST_16 = 30
    F_REST_17 = 31
    F_REST_18 = 32
    F_REST_19 = 33
    F_REST_20 = 34
    F_REST_21 = 35
    F_REST_22 = 36
    F_REST_23 = 37
    F_REST_24 = 38
    F_REST_25 = 39
    F_REST_26 = 40
    F_REST_27 = 41
    F_REST_28 = 42
    F_REST_29 = 43
    F_REST_30 = 44
    F_REST_31 = 45
    F_REST_32 = 46
    F_REST_33 = 47
    F_REST_34 = 48
    F_REST_35 = 49
    F_REST_36 = 50
    F_REST_37 = 51
    F_REST_38 = 52
    F_REST_39 = 53
    F_REST_40 = 54
    F_REST_41 = 55
    F_REST_42 = 56
    F_REST_43 = 57
    F_REST_44 = 58
    F_REST_45 = 59  
    X_ADD     = 60
    Y_ADD     = 61
    Z_ADD     = 62
    ZERO      = 63  

    def get_param_names(self) -> str:
      if self in {VideoComponentId.X, VideoComponentId.Y, VideoComponentId.Z,
                  VideoComponentId.X_ADD, VideoComponentId.Y_ADD, VideoComponentId.Z_ADD}:
        return self.name.lower()
      if self == VideoComponentId.OPACITY:
        return 'opacity'
      if VideoComponentId.SCALE_X.value <= self.value <= VideoComponentId.SCALE_Z.value:
        return f'scale_{self.value - VideoComponentId.SCALE_X.value}'
      if VideoComponentId.ROT_X.value <= self.value <= VideoComponentId.ROT_W.value:
        return f'rot_{self.value - VideoComponentId.ROT_X.value}'
      if VideoComponentId.F_DC_0.value <= self.value <= VideoComponentId.F_DC_2.value:
        return f'f_dc_{self.value - VideoComponentId.F_DC_0.value}'
      if VideoComponentId.F_REST_0.value <= self.value <= VideoComponentId.F_REST_45.value:
        return f'f_rest_{self.value - VideoComponentId.F_REST_0.value}'
      if self == VideoComponentId.ZERO:
        return 'zero'
      raise ValueError(f"Unsupported component: {self}")

    def from_param_name(name: str) -> "VideoComponentId":
      name = name.lower()
      if name in {'x', 'y', 'z', 'x_add', 'y_add', 'z_add'}:
        return VideoComponentId[name.upper()]
      elif name == 'opacity':
        return VideoComponentId.OPACITY
      elif name.startswith('scale_'): 
        return VideoComponentId(VideoComponentId.SCALE_X.value + int(name[len('scale_'):]))
      elif name.startswith('rot_'): 
        return VideoComponentId(VideoComponentId.ROT_X.value + int(name[len('rot_'):]))
      elif name.startswith('f_dc_'): 
        return VideoComponentId(VideoComponentId.F_DC_0.value + int(name[len('f_dc_'):]))
      elif name.startswith('f_rest_'): 
        return VideoComponentId(VideoComponentId.F_REST_0.value + int(name[len('f_rest_'):]))
      elif name == 'zero':
        return VideoComponentId.ZERO
      raise ValueError(f"Unsupported parameter name: {name}")
      
#######################################################################################################