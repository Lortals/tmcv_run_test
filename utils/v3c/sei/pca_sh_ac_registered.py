from utils.v3c.type    import NalUnitType, SeiPayloadType
from utils.v3c.sei.sei import Sei
import numpy as np

#######################################################################################################
######################## SEI PCA SH AC Registered ######################################################
#######################################################################################################

class SeiPcaShAcRegistered(Sei):

  def __init__(self):
    super().__init__()
    self.sei_payload_type = SeiPayloadType.PCA_SH_AC_REGISTERED

  #######################################################################################################

  def write(self, bitstream, type: NalUnitType = None, gof=None):
    sh_pca_flag = gof.sh_pca_flag
    bitstream.write_bits(sh_pca_flag, 1)                                  # u(1)
    if sh_pca_flag:
      sh_pca_orig_dims = gof.sh_pca_original_dims
      sh_pca_reduced_dims = gof.sh_pca_reduced_dims
      bitstream.write_bits(sh_pca_orig_dims, 6)                           # u(6)
      bitstream.write_bits(sh_pca_reduced_dims, 6)                        # u(6)
      num_frames = len(gof.sh_pca_per_frame)
      bitstream.write_bits(num_frames, 16)                                # u(16)
      for frame_data in gof.sh_pca_per_frame:
        sh_pca_proj_comps = frame_data['sh_pca_proj_comps']
        sh_pca_mean = frame_data['sh_pca_mean']
        sh_pca_std = frame_data['sh_pca_std']
        for i in range(sh_pca_orig_dims):
          for j in range(sh_pca_reduced_dims):
            bitstream.write_float(sh_pca_proj_comps[i, j])                # f(32)
        for i in range(sh_pca_orig_dims):
          bitstream.write_float(sh_pca_mean[i])                           # f(32)
        for i in range(sh_pca_orig_dims):
          bitstream.write_float(sh_pca_std[i])                            # f(32)

  #######################################################################################################

  def read(self, bitstream, type: NalUnitType = None, gof=None):
    sh_pca_flag = bitstream.read_bits(1)                                  # u(1)
    gof.sh_pca_flag = sh_pca_flag
    if sh_pca_flag:
      sh_pca_orig_dims = bitstream.read_bits(6)                           # u(6)
      sh_pca_reduced_dims = bitstream.read_bits(6)                        # u(6)
      gof.sh_pca_original_dims = sh_pca_orig_dims
      gof.sh_pca_reduced_dims = sh_pca_reduced_dims
      num_frames = bitstream.read_bits(16)                                # u(16)
      for frame_idx in range(num_frames):
        sh_pca_proj_comps = np.zeros((sh_pca_orig_dims, sh_pca_reduced_dims))
        for i in range(sh_pca_orig_dims):
          for j in range(sh_pca_reduced_dims):
            sh_pca_proj_comps[i, j] = bitstream.read_float()              # f(32)
        sh_pca_mean = np.zeros(sh_pca_orig_dims)
        for i in range(sh_pca_orig_dims):
          sh_pca_mean[i] = bitstream.read_float()                         # f(32)
        sh_pca_std = np.zeros(sh_pca_orig_dims)
        for i in range(sh_pca_orig_dims):
          sh_pca_std[i] = bitstream.read_float()                          # f(32)
        gof.sh_pca_per_frame.append({
          'sh_pca_proj_comps': sh_pca_proj_comps,
          'sh_pca_mean': sh_pca_mean,
          'sh_pca_std': sh_pca_std
        })

#######################################################################################################
