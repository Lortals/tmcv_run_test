from utils.v3c.type    import NalUnitType, SeiPayloadType
from utils.v3c.sei.sei import Sei
import numpy as np

#######################################################################################################
######################## SEI SH AC Transformation Registered ##########################################
#######################################################################################################

class SeiTransShAcRegistered(Sei):

  def __init__(self):
    super().__init__()
    self.sei_payload_type = SeiPayloadType.TRANS_SH_AC_REGISTERED

  #######################################################################################################

  def write(self, bitstream, type: NalUnitType = None, gof=None):
    sh_ac_transform_present_flag = gof.sh_ac_transform_flag
    sh_ac_mean_present_flag = gof.sh_ac_mean_flag
    sh_ac_std_present_flag = gof.sh_ac_std_flag
    bitstream.write_bits(sh_ac_transform_present_flag, 1)                 # u(1)
    bitstream.write_bits(sh_ac_mean_present_flag, 1)                      # u(1)
    bitstream.write_bits(sh_ac_std_present_flag, 1)                       # u(1)
    if sh_ac_transform_present_flag:
      sh_ac_dim = gof.sh_ac_dim
      sh_ac_dim_minus1 = sh_ac_dim - 1
      sh_ac_transform_dim = gof.sh_ac_transform_dim
      sh_ac_transform_dim_minus1 = sh_ac_transform_dim - 1
      bitstream.write_bits(sh_ac_dim_minus1, 6)                           # u(6)
      bitstream.write_bits(sh_ac_transform_dim_minus1, 6)                 # u(6)
      num_frames = len(gof.sh_ac_transform_per_frame)
      bitstream.write_bits(num_frames, 16)                                # u(16)
      for frame_data in gof.sh_ac_transform_per_frame:
        sh_ac_transform_basis = frame_data['sh_ac_transform_basis']
          
        for i in range(sh_ac_dim):
          for j in range(sh_ac_transform_dim):
            bitstream.write_float(sh_ac_transform_basis[i, j])            # f(32)
            
        if sh_ac_mean_present_flag:
          sh_ac_mean = frame_data['sh_ac_mean']
          for i in range(sh_ac_dim):
            bitstream.write_float(sh_ac_mean[i])                          # f(32)
            
        if sh_ac_std_present_flag:
          sh_ac_std = frame_data['sh_ac_std']
          for i in range(sh_ac_dim):
            bitstream.write_float(sh_ac_std[i])                           # f(32)

  #######################################################################################################

  def read(self, bitstream, type: NalUnitType = None, gof=None):
    sh_ac_transform_present_flag = bitstream.read_bits(1)                 # u(1)
    sh_ac_mean_present_flag = bitstream.read_bits(1)                      # u(1)
    sh_ac_std_present_flag = bitstream.read_bits(1)                       # u(1)
    gof.sh_ac_transform_flag = sh_ac_transform_present_flag
    gof.sh_ac_mean_flag = sh_ac_mean_present_flag
    gof.sh_ac_std_flag = sh_ac_std_present_flag
    if sh_ac_transform_present_flag:
      sh_ac_dim_minus1 = bitstream.read_bits(6)                           # u(6)
      sh_ac_transform_dim_minus1 = bitstream.read_bits(6)                 # u(6)
      sh_ac_dim = sh_ac_dim_minus1 + 1
      sh_ac_transform_dim = sh_ac_transform_dim_minus1 + 1
      gof.sh_ac_dim = sh_ac_dim
      gof.sh_ac_transform_dim = sh_ac_transform_dim
      num_frames = bitstream.read_bits(16)                                # u(16)
      for frame_idx in range(num_frames):
        sh_ac_transform_per_frame = {}
        sh_ac_transform_basis = np.zeros((sh_ac_dim, sh_ac_transform_dim))
        for i in range(sh_ac_dim):
          for j in range(sh_ac_transform_dim):
            sh_ac_transform_basis[i, j] = bitstream.read_float()          # f(32)
        sh_ac_transform_per_frame['sh_ac_transform_basis'] = sh_ac_transform_basis
        if sh_ac_mean_present_flag:
          gof.sh_ac_mean_flag = True
          sh_ac_mean = np.zeros(sh_ac_dim)
          for i in range(sh_ac_dim):
            sh_ac_mean[i] = bitstream.read_float()                         # f(32)
          sh_ac_transform_per_frame['sh_ac_mean'] = sh_ac_mean
        if sh_ac_std_present_flag:
          gof.sh_ac_std_flag = True
          sh_ac_std = np.zeros(sh_ac_dim)
          for i in range(sh_ac_dim):
            sh_ac_std[i] = bitstream.read_float()                          # f(32)
          sh_ac_transform_per_frame['sh_ac_std'] = sh_ac_std

        gof.sh_ac_transform_per_frame.append(sh_ac_transform_per_frame)

#######################################################################################################
