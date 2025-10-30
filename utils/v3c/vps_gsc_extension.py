from utils.v3c.type  import V3CUnitType, Packing, Format, ColorStandard
import numpy as np

#######################################################################################################
################################### vps gsc extension #################################################
#######################################################################################################

class VpsGscExtension:
  
  def __init__(self): 
    pass
  
  #######################################################################################################
    
  def write(self, bitstream, gof):
    from utils.group_of_frames import GroupOfFrames
    num_videos_minus_1 = len(gof.videos) - 1 
    first_video        = next(iter(gof.videos.values()))
    trans_position     = first_video.trans_position 
    sh_conversion      = first_video.sh_conversion.value
    src_sh_conversion  = gof.src_sh_conversion.value
    code_bd_pos_0      = first_video.bitdepth_pos[0] != 0 
    code_bd_pos_1      = first_video.bitdepth_pos[1] != 0  
    bitstream.write_bits(num_videos_minus_1, 5)                             # u(5)
    bitstream.write_bits(trans_position, 1)                                 # u(1)
    bitstream.write_bits(sh_conversion, 2)                                  # u(2)
    bitstream.write_bits(src_sh_conversion, 2)                              # u(2)
    bitstream.write_bits(code_bd_pos_0, 1)                                  # u(1)
    if code_bd_pos_0:     
      bd_pos_0 = first_video.bitdepth_pos[0]    
      bitstream.write_bits(bd_pos_0, 5)                                     # u(5)    
    bitstream.write_bits(code_bd_pos_1, 1)                                  # u(1)
    if code_bd_pos_1:   
      bd_pos_1 = first_video.bitdepth_pos[1]    
      bitstream.write_bits(bd_pos_1, 5)                                     # u(5)   
    for idx, (_, video) in enumerate(gof.videos.items()):   
      type_value     = video.type.value   
      codec_id       = video.codec_id     
      packing_id     = video.packing.value    
      format_id      = video.format.value   
      bitdepth       = video.bitdepth   
      num_components_minus1 = len(video.min) - 1    
      bitstream.write_bits(type_value, 5)                                   # u(5)
      bitstream.write_bits(bitdepth, 5)                                     # u(5)
      bitstream.write_bits(codec_id, 2)                                     # u(2)
      bitstream.write_bits(packing_id, 1)                                   # u(1)
      bitstream.write_bits(format_id, 2)                                    # u(2)
      bitstream.write_bits(num_components_minus1, 7)                        # u(7)      
      for j in range( num_components_minus1 + 1 ):    
        min_value = video.min[j]    
        max_value = video.max[j]    
        bitstream.write_float(min_value)                                    # f(32)
        bitstream.write_float(max_value)                                    # f(32)
    
    sh_pca_flag = gof.sh_pca_flag
    bitstream.write_bits(sh_pca_flag, 1)                                    # u(1)
    if sh_pca_flag:
      sh_pca_orig_dims = gof.sh_pca_original_dims
      sh_pca_reduced_dims = gof.sh_pca_reduced_dims
      bitstream.write_bits(sh_pca_orig_dims, 6)                             # u(6)
      bitstream.write_bits(sh_pca_reduced_dims, 6)                          # u(6)
      num_frames = len(gof.sh_pca_per_frame)
      bitstream.write_bits(num_frames, 16)                                  # u(16)
      for frame_data in gof.sh_pca_per_frame:
        sh_pca_proj_comps = frame_data['sh_pca_proj_comps']
        sh_pca_mean = frame_data['sh_pca_mean']
        sh_pca_std = frame_data['sh_pca_std']
        for i in range(sh_pca_orig_dims):
          for j in range(sh_pca_reduced_dims):
            bitstream.write_float(sh_pca_proj_comps[i, j])                   # f(32)
        for i in range(sh_pca_orig_dims):
          bitstream.write_float(sh_pca_mean[i])                              # f(32)
        for i in range(sh_pca_orig_dims):
          bitstream.write_float(sh_pca_std[i])                               # f(32)
  
  #######################################################################################################

  def read(self, bitstream, gof):
    from utils.group_of_frames import GroupOfFrames, VideoData
    num_videos_minus_1    = bitstream.read_bits(5)                          # u(5)
    trans_position        = bitstream.read_bits(1)                          # u(1) 
    sh_conversion         = bitstream.read_bits(2)                          # u(2)
    src_sh_conversion     = bitstream.read_bits(2)                          # u(2)
    gof.src_sh_conversion = ColorStandard( src_sh_conversion )
    code_bd_pos_0         = bitstream.read_bits(1)                          # u(1)
    bd_pos_0              = bitstream.read_bits(5) if code_bd_pos_0 else 0  # u(5)  
    code_bd_pos_1         = bitstream.read_bits(1)                          # u(1)     
    bd_pos_1              = bitstream.read_bits(5) if code_bd_pos_1 else 0  # u(5)
    for i in range( num_videos_minus_1 + 1 ):   
      type_value            = bitstream.read_bits(5)                        # u(5)
      bitdepth              = bitstream.read_bits(5)                        # u(5)
      codec_id              = bitstream.read_bits(2)                        # u(2)
      packing_id            = bitstream.read_bits(1)                        # u(1)
      format_id             = bitstream.read_bits(2)                        # u(2)
      num_components_minus1 = bitstream.read_bits(7)                        # u(7)
      type       = V3CUnitType(type_value)
      if type not in gof.videos:
        gof.videos[type] = VideoData(type=type)
      gof.videos[type].bitdepth       = bitdepth
      gof.videos[type].bitdepth_pos   = [bd_pos_0, bd_pos_1]
      gof.videos[type].codec_id       = codec_id
      gof.videos[type].packing        = Packing( packing_id )
      gof.videos[type].format         = Format( format_id )
      gof.videos[type].trans_position = trans_position
      gof.videos[type].sh_conversion  = ColorStandard(sh_conversion)
      gof.videos[type].num_components = num_components_minus1 + 1
      gof.videos[type].min            = [0.0] * (num_components_minus1 + 1)
      gof.videos[type].max            = [0.0] * (num_components_minus1 + 1)
      
      for j in range( gof.videos[type].num_components ):
        min_value = bitstream.read_float()                                  # f(32)
        max_value = bitstream.read_float()                                  # f(32)
        gof.videos[type].min[j] = min_value
        gof.videos[type].max[j] = max_value
  
    sh_pca_flag = bitstream.read_bits(1)                                    # u(1)
    gof.sh_pca_flag = sh_pca_flag
    if sh_pca_flag:
      sh_pca_orig_dims = bitstream.read_bits(6)                             # u(6)
      sh_pca_reduced_dims = bitstream.read_bits(6)                          # u(6)
      gof.sh_pca_original_dims = sh_pca_orig_dims
      gof.sh_pca_reduced_dims = sh_pca_reduced_dims
      num_frames = bitstream.read_bits(16)                                  # u(16)
      for frame_idx in range(num_frames):
        sh_pca_proj_comps = np.zeros((sh_pca_orig_dims, sh_pca_reduced_dims))
        for i in range(sh_pca_orig_dims):
          for j in range(sh_pca_reduced_dims):
            sh_pca_proj_comps[i, j] = bitstream.read_float()                 # f(32)

        sh_pca_mean = np.zeros(sh_pca_orig_dims)
        for i in range(sh_pca_orig_dims):
          sh_pca_mean[i] = bitstream.read_float()                            # f(32)

        sh_pca_std = np.zeros(sh_pca_orig_dims)
        for i in range(sh_pca_orig_dims):
          sh_pca_std[i] = bitstream.read_float()                             # f(32)

        gof.sh_pca_per_frame.append({
          'sh_pca_proj_comps': sh_pca_proj_comps,
          'sh_pca_mean': sh_pca_mean,
          'sh_pca_std': sh_pca_std
        })
#######################################################################################################