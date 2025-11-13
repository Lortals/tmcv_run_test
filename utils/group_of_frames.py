from typing import Dict
import numpy as np 
import sys
from utils.video_data                 import VideoData
from utils.bitstream                  import Bitstream
from utils.pointcloud                 import Pointcloud
from utils.stat                       import Stat
from utils.v3c.type                   import NalUnitType, V3CUnitType, SeiPayloadType, Format, ColorStandard
from utils.v3c.v3c_parameter_set      import V3cParameterSet
from utils.v3c.atlas_sub_bitstream    import AtlasSubBitstream
from utils.v3c.video_sub_bitstream    import VideoSubBitstream
from utils.v3c.sample_stream_v3c_unit import SampleStreamV3CUnit
from utils.v3c.sei.sei_rbsp           import SeiRbsp
from utils.v3c.sei.sei                import Sei

#######################################################################################################
#################################### Group of frames ##################################################
#######################################################################################################

class GroupOfFrames:
  videos: Dict[V3CUnitType, VideoData]

  #######################################################################################################

  def __init__(self, index=0, codecs=None, src_sh_conversion=ColorStandard.NONE, trans_sh_ac=None, sh_ac_mean_flag=True, sh_ac_std_flag=True): 
    self.index                 = index
    self.videos                = {}
    self.stat                  = Stat()
    self.codecs                = codecs if codecs is not None else []
    self.fps                   = 30 
    self.block_width           = 0
    self.block_height          = 0  
    self.src_sh_conversion     = src_sh_conversion
    self.camera_df             = None
    self.sh_ac_transform_flag  = trans_sh_ac is not None
    self.sh_ac_mean_flag       = sh_ac_mean_flag
    self.sh_ac_std_flag        = sh_ac_std_flag
    self.sh_ac_dim             = 0
    self.sh_ac_transform_dim   = 0
    self.sh_ac_transform_per_frame      = []
    
#######################################################################################################

  def create_video(self, video_index, list_params, bitdepth, bitdepth_pos, qp, codec_id, format, packing, quantization, 
                   trans_position, sh_conversion, subsampling, verbose=False):
    type = V3CUnitType( V3CUnitType.V3C_GSC_0.value + video_index )
    self.videos[type] = VideoData(type               = type,
                                  list_params        = list_params,
                                  bitdepth           = bitdepth, 
                                  bitdepth_pos       = bitdepth_pos,
                                  qp                 = qp, 
                                  codec_id           = codec_id, 
                                  format             = format,
                                  packing            = packing,
                                  quantization       = quantization,
                                  trans_position     = trans_position, 
                                  sh_conversion      = sh_conversion,
                                  subsampling        = subsampling,
                                  verbose            = verbose)
    
  #######################################################################################################

  def set_video(self, pointcloud, verbose=False):
    self.block_width  = pointcloud.sidelen_w
    self.block_height = pointcloud.sidelen_h
    self.camera_df    = pointcloud.camera_df

    if self.sh_ac_transform_flag and len(self.sh_ac_transform_per_frame) == 1:
      cols = [c for c in pointcloud.df.columns if c.startswith('f_rest_')]
      for vtype, vid in self.videos.items():
        if any(p.startswith('f_rest_') for p in vid.list_params):
          vid.list_params = [p for p in vid.list_params if not p.startswith('f_rest_')] + cols
          vid.set_grid_size(self.block_width, self.block_height)

    for _, (_, video) in enumerate(self.videos.items()):
      if verbose:
        print("set_video %-10s %10s %10s list_params = " % ( video.type.name, video.format.name, video.packing.name ), video.name(True))
      video.pack_one_frame(pointcloud=pointcloud, verbose=verbose)

  #######################################################################################################

  def save_sh_ac_transform_metadata(self, metadata):
    if self.sh_ac_transform_flag is True:

      if self.sh_ac_dim == 0 or self.sh_ac_transform_dim == 0:
        self.sh_ac_dim = metadata['sh_ac_dim']
        self.sh_ac_transform_dim = metadata['sh_ac_transform_dim']

      # self.sh_ac_transform_per_frame.append({k: metadata[k] for k in ['sh_ac_transform_basis', 'sh_ac_mean', 'sh_ac_std']})
      sh_ac_transform_per_frame = {'sh_ac_transform_basis': metadata['sh_ac_transform_basis']}
      if self.sh_ac_mean_flag:
        sh_ac_transform_per_frame['sh_ac_mean'] = metadata['sh_ac_mean']
      if self.sh_ac_std_flag:
        sh_ac_transform_per_frame['sh_ac_std'] = metadata['sh_ac_std']
      self.sh_ac_transform_per_frame.append(sh_ac_transform_per_frame)

  #######################################################################################################

  def get_sh_ac_transform_metadata(self, frame_idx, verbose=False):
    if self.sh_ac_transform_flag:
      return self.sh_ac_transform_per_frame[frame_idx]

  #######################################################################################################

  def get_pointcloud(self, frame_index, verbose=False):
    pc = Pointcloud()

    sh_params = [p for v in self.videos.values() for p in v.list_params if p.startswith('f_rest_')]
    
    if sh_params:
      default_sh = [c for c in pc.ply_columns if c.startswith('f_rest_')]
      pc.ply_columns = [c for c in pc.ply_columns if not c.startswith('f_rest_')]
      pc.df = pc.df.drop(columns=[c for c in pc.df.columns if c.startswith('f_rest_')])

      sorted_sh = sorted(set(sh_params), key=lambda x: int(x.split('_')[2]))
      pc.ply_columns.extend(sorted_sh)
      for sh in sorted_sh:
        pc.df[sh] = 0.0

    for _, video in self.videos.items():
      video.get_pointcloud(frame_index, pc, verbose)

    if self.camera_df is not None and not self.camera_df.empty:
      pc.camera_df = self.camera_df

    return pc

  #######################################################################################################
  
  def get_position_bitdepths(self):
    bd = {}  
    for param in ['x', 'y', 'z']:
      for video in self.videos.values():
        if param in video.list_params:
          bd[param] = video.bitdepth 
          break
      else:
        bd[param] = 0
    return bd

  #######################################################################################################

  def get_video_with_param( self, params):
    for _, video in self.videos.items():
      if params in video.list_params:
        return video    
    raise ValueError("Cant' find param %s in any videos." % params )


  #######################################################################################################

  def quantize(self, verbose=False):

    # Quantize all primary parameters
    for _, video in self.videos.items():
      video.quantize(verbose=verbose)

    # Quantize position
    has_add_pos_param = any( add_param in video.list_params for add_param in ['x_add', 'y_add', 'z_add'] for video in self.videos.values() )
    if has_add_pos_param:      
      for args_add in ['x_add', 'y_add', 'z_add']:
        for _, video_add in self.videos.items():
          if args_add in video_add.list_params:
            args_xyz = args_add[0]
            bits_main, bits_add = video_add.bitdepth_pos
            total_bits = bits_main + bits_add
            for _, video_xyz in self.videos.items():
              num_frames_xyz = video_xyz.num_frames("uint") 
              if args_xyz in video_xyz.list_params:    
                msb_mask = (1 << bits_main) - 1 
                lsb_mask = (1 << bits_add ) - 1          
                for frame_index in range(num_frames_xyz):        
                  block = video_xyz.get_block(args_xyz, frame_index,  type='res', verbose=verbose)
                  msb = (block >> bits_add) &  msb_mask
                  msb = msb.astype(np.uint8 if bits_main <= 8 else np.uint16)
                  lsb = block & lsb_mask
                  lsb = lsb.astype(np.uint8 if bits_add <= 8 else np.uint16)    
                  if verbose:
                    print("  quant %-10s bd = %2d = %2d + %2d : %6d => msb = %6d lsb = %6d " % ( args_add, 
                      total_bits, bits_main, bits_add, block[0,0], msb[0,0], lsb[0,0]) )
                  video_xyz.set_block(args_xyz, frame_index, msb, type='uint', verbose=verbose)
                  video_add.set_block(args_add, frame_index, lsb, type="uint", verbose=verbose)
                
                      
  #######################################################################################################

  def dequantize(self, verbose=False):
    has_add_pos_param = any( add_param in video.list_params for add_param in ['x_add', 'y_add', 'z_add' ] for video in self.videos.values() )
    if has_add_pos_param:            
      for args_add in ['x_add', 'y_add', 'z_add']:      
        for _, video_add in self.videos.items():
          if args_add in video_add.list_params:
            num_frames       = video_add.num_frames('uint')
            num_frames_video = video_add.video_uint.num_frames()
            video_add.video_res.alloc(num_frames_video, video_add.width, video_add.height, 32, force_type=np.uint32, format=video_add.format.video_name())
            args_xyz = args_add[0]
            bits_main, bits_add = video_add.bitdepth_pos
            total_bits = bits_main + bits_add
            for _, video_xyz in self.videos.items():
              if args_xyz in video_xyz.list_params:
                num_frames = video_add.num_frames("uint")
                for frame_index in range(num_frames):
                  msb = video_xyz.get_block(args_xyz, frame_index, type="uint", verbose=verbose)
                  lsb = video_add.get_block(args_add, frame_index, type="uint", verbose=verbose)
                  block = ((msb.astype(np.uint32) << bits_add) | lsb.astype(np.uint32))
                  if verbose:
                    print("  quant %-10s bd = %2d = %2d + %2d : %6d <= msb = %6d lsb = %6d " % ( args_add, 
                            total_bits, bits_main, bits_add, block[0,0], msb[0,0], lsb[0,0]) )
                  video_xyz.set_block(args_xyz, frame_index, block, type="res", verbose=verbose)
              
    for _, video in self.videos.items():
      video.dequantize(verbose=verbose)

  #######################################################################################################      
  
  def rgb2yuv(self, verbose=False):    
    for _, video in self.videos.items():
      if video.sh_conversion != ColorStandard.NONE:
        print("  rgb2yuv: sh_conversion = %s " % ( video.sh_conversion.name ))
        num_frames = video.num_frames('uint')
        for frame_index in range(num_frames):          
          for _, id in enumerate(video.list_params):
            # f, x, y, c = video.get_pack_position(i)
            if id.startswith('f_dc'):
              rest_num = int(id.split('_')[-1])
              if rest_num == 0:
                block_r = video.get_block('f_dc_0', frame_index, type='uint', verbose=verbose)
                block_g = video.get_block('f_dc_1', frame_index, type='uint', verbose=verbose)
                block_b = video.get_block('f_dc_2', frame_index, type='uint', verbose=verbose)
                block_y, block_cb, block_cr = video.sh_conversion.rgb2yuv_uint16(block_r, block_g, block_b, video.bitdepth)
                video.set_block('f_dc_0', frame_index, block_y, type='uint', verbose=verbose)
                video.set_block('f_dc_1', frame_index, block_cb, type='uint', verbose=verbose)
                video.set_block('f_dc_2', frame_index, block_cr, type='uint', verbose=verbose)
            elif id.startswith('f_rest'):
              rest_num = int(id.split('_')[-1])
              if rest_num // 15 == 0:
                block_r = video.get_block(f'f_rest_{rest_num}', frame_index, type='uint', verbose=verbose)
                block_g = video.get_block(f'f_rest_{rest_num + 15}', frame_index, type='uint', verbose=verbose)
                block_b = video.get_block(f'f_rest_{rest_num + 30}', frame_index, type='uint', verbose=verbose)
                block_y, block_cb, block_cr = video.sh_conversion.rgb2yuv_uint16(block_r, block_g, block_b, video.bitdepth)
                y_num = rest_num
                cb_num = rest_num + 15
                cr_num = rest_num + 30
                video.set_block(f'f_rest_{y_num}', frame_index, block_y, type='uint', verbose=verbose)
                video.set_block(f'f_rest_{cb_num}', frame_index, block_cb, type='uint', verbose=verbose)
                video.set_block(f'f_rest_{cr_num}', frame_index, block_cr, type='uint', verbose=verbose)

  ####################################################################################################### 
  
  def yuv2rgb(self, verbose=False):
    for _, video in self.videos.items():
      if video.sh_conversion != ColorStandard.NONE:
        print("  yuv2rgb: sh_conversion = %s " % ( video.sh_conversion.name ))
        num_frames = video.num_frames('uint')
        for frame_index in range(num_frames):
          for _, id in enumerate(video.list_params):            
            # f, x, y, c = video.get_pack_position(i)
            if id.startswith('f_dc'):
              rest_num = int(id.split('_')[-1])
              if rest_num == 0:
                block_y  = video.get_block('f_dc_0', frame_index, type='uint', verbose=verbose)
                block_cb = video.get_block('f_dc_1', frame_index, type='uint', verbose=verbose)
                block_cr = video.get_block('f_dc_2', frame_index, type='uint', verbose=verbose)
                block_r, block_g, block_b = video.sh_conversion.yuv2rgb_uint16(block_y, block_cb, block_cr, video.bitdepth )
                video.set_block('f_dc_0', frame_index, block_r, type='uint', verbose=verbose)
                video.set_block('f_dc_1', frame_index, block_g, type='uint', verbose=verbose)
                video.set_block('f_dc_2', frame_index, block_b, type='uint', verbose=verbose)
            elif id.startswith('f_rest'):
              rest_num = int(id.split('_')[-1])
              if rest_num // 15 == 0:
                block_y  = video.get_block(f'f_rest_{rest_num}', frame_index, type='uint', verbose=verbose)
                block_cb = video.get_block(f'f_rest_{rest_num + 15}', frame_index, type='uint', verbose=verbose)
                block_cr = video.get_block(f'f_rest_{rest_num + 30}', frame_index, type='uint', verbose=verbose)
                block_r, block_g, block_b = video.sh_conversion.yuv2rgb_uint16(block_y, block_cb, block_cr, video.bitdepth)
                y_num  = rest_num
                cb_num = rest_num + 15
                cr_num = rest_num + 30
                video.set_block(f'f_rest_{y_num}', frame_index, block_r, type='uint', verbose=verbose)
                video.set_block(f'f_rest_{cb_num}', frame_index, block_g, type='uint', verbose=verbose)
                video.set_block(f'f_rest_{cr_num}', frame_index, block_b, type='uint', verbose=verbose)

  #######################################################################################################      

  def subsample(self, verbose=False):
    for atlas_id, video in self.videos.items():
      if video.format == Format.YUV420:            
        num_frames = video.video_uint.num_frames() 
        if verbose:
          print("Subsampling video %s format = %s subsampling = %d num_frames = %d " % (atlas_id, video.format.name, video.subsampling, num_frames))          
        for frame_index in range(num_frames):
          if video.subsampling == 0:
            continue
          y = video.video_uint.c(frame_index, 0)
          u = video.video_uint.c(frame_index, 1)
          v = video.video_uint.c(frame_index, 2)
          if video.subsampling == 1:
            u2 = self.subsample_drop(u)
            v2 = self.subsample_drop(v)
            video.video_uint.frames[frame_index] = (y, u2, v2)
          elif video.subsampling == 2:
            u2 = self.subsample_average(u)
            v2 = self.subsample_average(v)
            video.video_uint.frames[frame_index] = (y, u2, v2)

  ####################################################################################################### 

  def subsample_average(self, data):
    h, w = data.shape
    if h % 2 != 0 or w % 2 != 0:
      raise ValueError(f"Subsample average requires even dimensions, got ({h}, {w})")
    arr = np.ascontiguousarray(data)
    out = arr.reshape(h//2, 2, w//2, 2).mean(axis=(1, 3))
    return out.astype(data.dtype)

  ####################################################################################################### 

  def subsample_drop(self, data):
    return data[::2, ::2]
  
  ####################################################################################################### 
  
  def upsample(self, verbose=False):
    for  _, video in self.videos.items():
      if video.format == Format.YUV420:
        num_frames = video.video_uint.num_frames() 
        for frame_index in range(num_frames):
          u, v = video.video_uint.c(frame_index, 1), video.video_uint.c(frame_index, 2)
          u2 = self.upsample_b_3_6(u, video.bitdepth)
          v2 = self.upsample_b_3_6(v, video.bitdepth)
          y  = video.video_uint.c(frame_index, 0)
          video.video_uint.frames[frame_index] = (y, u2, v2)

  ######################################################################################################
  def upsample_b_3_6(self, data, bitdepth):
    # ISO/IEC 23090-5 B.3.6 4-tap x 4-tap filter for 4:2:0 to 4:4:4 upsampling
    c = data.astype(np.int32)
    hc, wc = c.shape
    max_val = (1 << bitdepth) - 1

    # Horizontal 2x upsampling
    # Pad with edge values (2 columns on each side)
    px = np.pad(c, ((0, 0), (2, 2)), mode='edge')
    
    # Even columns: simple copy x16, Odd columns: -1 9 9 -1 filter
    even_cols = 16 * c
    odd_cols = (-px[:, 1:-3] + 9*px[:, 2:-2] + 9*px[:, 3:-1] - px[:, 4:])
    
    h_up = np.empty((hc, wc * 2), dtype=np.int32)
    h_up[:, 0::2] = even_cols
    h_up[:, 1::2] = odd_cols

    # Vertical 2x upsampling
    py = np.pad(h_up, ((2, 2), (0, 0)), mode='edge')
    
    even_rows = 16 * h_up
    odd_rows = -py[1:-3] + 9*py[2:-2] + 9*py[3:-1] - py[4:]
    
    out = np.empty((hc * 2, wc * 2), dtype=np.int32)
    out[0::2] = even_rows
    out[1::2] = odd_rows

    # Normalize (+128)>>8 and clip
    out = (out + 128) >> 8
    out = np.clip(out, 0, max_val).astype(np.float32)
    return out

  #######################################################################################################
  def num_frames(self, type):
    for _, (_, video) in enumerate(self.videos.items()):      
      return video.num_frames(type)

  #######################################################################################################

  def print(self, name='', file=None):
    print("Gof[%2d]: %s " % (self.index, name ),file=file)            
    for _, (_, video) in enumerate(self.videos.items()):
      video.print(file=file)
    sys.stdout.flush()

  #######################################################################################################
 
  def print_component_codec_mapping(self):
    print("ComponentCodecMapping:")
    for codec_id, codec_4cc in enumerate(self.codecs):
      print(f"  id={codec_id}  4CC='{codec_4cc}'")

  #######################################################################################################

  def save(self, path='', bitstream_log=False, add_camera_position_sei=True, verbose=False):      
    ssvu = SampleStreamV3CUnit()

    if verbose:
      print("GroupOfFrames.save_v3c: path = %s  num_videos = %d " % (path, len(self.videos)) )
      for video in self.videos.values():
        print("  video.type = %-16s %-16s %-16s " % (video.type.name, video.format.name, video.packing.name) )

    ##################
    # V3c parameter set  
    ##################    
    if verbose:
      print("GroupOfFrames.save_v3c: V3c parameter set" )
    v3c_unit = ssvu.add_v3c_unit(V3CUnitType.V3C_VPS) 
    v3c_unit.write_header()
    vps = V3cParameterSet()
    vps.write( v3c_unit.bitstream, gof=self, use_sei=True )
    self.stat.add_size( "VPS", v3c_unit.bitstream.get_size_bits() )    
    
    ##################
    # Atlas sample stream
    ##################
    if verbose:
      print("GroupOfFrames.save_v3c: Atlas sample stream" )
    v3c_unit = ssvu.add_v3c_unit(V3CUnitType.V3C_AD)  
    v3c_unit.write_header() 

    # Create SEI messages
    sei = []
    sei.append( Sei.create( SeiPayloadType.COMPONENT_CODEC_MAPPING  ) )
    sei.append( Sei.create( SeiPayloadType.VIDEO_TYPE_MAPPING_REGISTERED ) )
    # sei.append( Sei.create( SeiPayloadType.DEQUANTIZATION_MAPPING_REGISTERED ) )
    sei.append( Sei.create( SeiPayloadType.GSC_REGISTERED ) )
    sei.append( Sei.create( SeiPayloadType.TRANS_SH_AC_REGISTERED ) )
    if add_camera_position_sei and self.camera_df is not None and not self.camera_df.empty:
      sei.append( Sei.create( SeiPayloadType.INPUT_CAMERA_INFORMATION ) )

    # Store SEI message into SEI RBSP 
    if verbose:
      print("GroupOfFrames.save_v3c: Store SEI message into SEI RBSP " )
    sei_rbsp       = SeiRbsp()
    sei_bitstream  = Bitstream(bitstream_log=bitstream_log)
    sei_rbsp.write(sei_bitstream, type=NalUnitType.NAL_PREFIX_ESEI, sei=sei, gof=self)    

    # Store SEI RBSP into Atlas sub-bitstream   
    if verbose:
      print("GroupOfFrames.save_v3c: Store SEI RBSP into Atlas sub-bitstream   " )
    atlas          = AtlasSubBitstream()
    atlas.add_nal_unit(type=NalUnitType.NAL_PREFIX_ESEI, data=sei_bitstream.get_bytes() )
    atlas.write(v3c_unit.bitstream)
    self.stat.add_size( "Atlas", v3c_unit.bitstream.get_size_bits())    

    ##################
    # Video sub bitstream
    ##################
    for _, (_, video) in enumerate(self.videos.items()):        
      if verbose:
        print("GroupOfFrames.save_v3c: Video sub bitstream type = %5s size = %8d " % (video.type.name, len(video.bitstream) ) )
      v3c_unit = ssvu.add_v3c_unit( video.type )
      v3c_unit.write_header()
      vsb = VideoSubBitstream()
      vsb.write( v3c_unit.bitstream, video.bitstream )
      self.stat.add_size( video.type.name, v3c_unit.bitstream.get_size_bits())

    ##################
    # Write sample stream V3C units (ssvu)
    ##################
    if verbose:
      print("GroupOfFrames.save_v3c: Write sample stream V3C units (ssvu)" )
    bitstream = Bitstream(bitstream_log=bitstream_log)
    ssvu.write( bitstream )
    self.stat.add_size( "ssvu",  ssvu.get_size_overhead() )    

    # Save bitstream
    if verbose:
      print("GroupOfFrames.save_v3c: Save bitstream" )
    bitstream.save( path )

    # Verbose
    if verbose:
      ssvu.print()
      print("GroupOfFrames saved to %s" % path) 

  #######################################################################################################

  def read(self, path='', bitstream_log=False, verbose=False):

    ##################
    # Read bitstream
    ##################
    bitstream = Bitstream(bitstream_log=bitstream_log)
    bitstream.load( path )

    ##################
    # Read sample stream V3C units (ssvu)
    ##################  
    ssvu = SampleStreamV3CUnit()
    ssvu.read( bitstream )
    self.stat.add_size( "ssvu", ssvu.get_size_overhead() )

    # Decode v3c units
    for _, v3c_unit in enumerate( ssvu.get_v3c_units() ):
      v3c_unit.read_header()

      ##################
      # VPS  
      ##################
      if v3c_unit.type == V3CUnitType.V3C_VPS:
        vps = V3cParameterSet() 
        vps.read(v3c_unit.bitstream, self )
        self.stat.add_size( "VPS", v3c_unit.bitstream.get_size_bits() )
        self.print()
        
      ##################
      # Atlas sub-bitstream (e.g., SEI)
      ##################
      elif v3c_unit.type == V3CUnitType.V3C_AD:
        atlas = AtlasSubBitstream()
        atlas.read(v3c_unit.bitstream)
        self.stat.add_size("Atlas", v3c_unit.bitstream.get_size_bits())
        for nal_unit in atlas.nal_units:
          if nal_unit.type == NalUnitType.NAL_PREFIX_ESEI:
            sei_bitstream = Bitstream(bitstream_log=bitstream_log)
            sei_bitstream.from_bytes(nal_unit.data)
            sei_rbsp = SeiRbsp()
            sei_messages = sei_rbsp.read(sei_bitstream, type=nal_unit.type,gof=self)
            for sei in sei_messages:
              print("SEI found: %-40s payload type: %3s" %(  sei.__class__.__name__, sei.sei_payload_type.name ) )

      ##################
      # Video sub bitstream
      ##################
      elif v3c_unit.type.name.startswith('V3C_GSC'): 
        vsb = VideoSubBitstream()
        self.videos[v3c_unit.type].bitstream = vsb.read( v3c_unit.bitstream, v3c_unit.bitstream.get_size_rest())
        self.stat.add_size( v3c_unit.type.name, v3c_unit.bitstream.get_size_bits()) 
      else: 
        print("v3c_unit type not supported") 
        exit()

    # Set video parameters
    for video in self.videos.values():
      video.set_grid_size(self.block_width, self.block_height)
      if verbose:
        print("video.type = %-16s grid_width = %2d grid_height = %2d " % (video.type.name, video.grid_width, video.grid_height) )

    # Verbose
    if verbose:
      ssvu.print()
      print("GroupOfFrames read to %s" % path) 
      self.print()

  #######################################################################################################