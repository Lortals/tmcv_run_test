from typing import Dict
import numpy as np
from utils.video_data                 import VideoData
from utils.bitstream                  import Bitstream
from utils.pointcloud                 import Pointcloud
from utils.stat                       import Stat
from utils.v3c.type                   import NalUnitType, V3CUnitType, SeiPayloadType, Packing, Format
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

  def __init__(self, index=0, codecs=[], bit_depth_pos=32, bit_depth_att=32): 
    self.index          = index
    self.videos         = {}
    self.stat           = Stat()
    self.codecs         = codecs 
    self.fps            = 30 
    self.block_width    = 0
    self.block_height   = 0  
    self.bit_depth_pos  = bit_depth_pos
    self.bit_depth_att  = bit_depth_att
    self.camera_df      = None

  #######################################################################################################

  def create_video(self, video_index, list_params, bitdepth, qp, codec_id, format, packing, quantization, trans_position, verbose=False):
    type = V3CUnitType( V3CUnitType.V3C_GSC_0.value + video_index )
    self.videos[type] = VideoData(type           = type,
                                  list_params    = list_params,
                                  bitdepth       = bitdepth, 
                                  qp             = qp, 
                                  codec_id       = codec_id, 
                                  format         = format,
                                  packing        = packing,
                                  quantization   = quantization,
                                  trans_position = trans_position, 
                                  verbose        = verbose)
    
  #######################################################################################################

  def set_video(self, pointcloud, verbose=False):
    self.block_width  = pointcloud.sidelen
    self.block_height = pointcloud.sidelen  
    self.camera_df    = pointcloud.camera_df
    for index, (type, video) in enumerate(self.videos.items()):
      if verbose:
        print("set_video %-10s %10s %10s list_params = " % ( video.type.name, video.format.name, video.packing.name ), video.name(True))
      video.pack_one_frame( pointcloud=pointcloud, verbose=verbose )

  #######################################################################################################

  def get_pointcloud( self, frame_index, verbose=False ):
    pointcloud = Pointcloud()
    for idx, (_, video) in enumerate(self.videos.items()):      
      video.get_pointcloud( frame_index, pointcloud, verbose )
    if self.camera_df is not None and not self.camera_df.empty:
      pointcloud.camera_df = self.camera_df
    return pointcloud

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
    for name, video in self.videos.items():
      if params in video.list_params:
        return video    
    raise ValueError("Cant' find param %s in any videos." % params )

  #######################################################################################################

  def reduce_bitdepth( self, verbose=False): 
    bd = self.get_position_bitdepths()
    if verbose:
      print("reduce_bitdepth  bd xyz = %8.6f %8.6f %8.6f bd pos = %8.2f bp att = %8.2f" % 
        ( bd['x'], bd['y'], bd['z'], self.bit_depth_pos, self.bit_depth_att))

    if verbose:
      for name, video in self.videos.items():
        if any(p in video.list_params for p in ['x', 'y', 'z']):
          video.video_src.print("video_xyz")

    for name, video in self.videos.items():
      num_frames       = video.num_frames('src')
      num_frames_video = video.video_src.num_frames()                       
      video.video_uint.alloc(num_frames_video, video.width, video.height, video.bitdepth, "444" if video.format == Format.YUV444 else "400")      
      shift_pos = self.bit_depth_pos - video.bitdepth
      shift_att = self.bit_depth_att - video.bitdepth
      if verbose:
        print("  reduce %10s: bit_depth_pos = %d bitdepth = %d = shift  = %d " % (video.name(), self.bit_depth_pos,  video.bitdepth, shift_pos))

      for frame_index in range(num_frames):
        for param in video.list_params:
          if param in ['x', 'y', 'z']:        # Shift MSB for positions    
            block = video.get_block(param, frame_index, type='src', verbose=verbose)
            block_uint = (block.astype(np.uint32) >> shift_pos).astype(np.uint8 if video.bitdepth <= 8 else np.uint16)
            if verbose: 
              print("    %-10s: value %2d bits = %4d >> %2d <=> value %2d bits = %4d" % 
                    ( param, self.bit_depth_pos, block.astype(np.uint32)[0,0], shift_pos, video.bitdepth, block_uint[0,0]))
              print("      block uint = ", block_uint.flatten())
              print("      block s/d  = ", block.flatten())
          elif param in ['x_add', 'y_add', 'z_add']:
            base            = param[0]  # 'x', 'y', 'z'
            video_xyz       = self.get_video_with_param( base )
            full_block      = video_xyz.get_block(base, frame_index, type='src', verbose=verbose)       
            full_block_uint = full_block.astype(np.uint32)     
            total_bits      = self.bit_depth_pos
            used_bits       = bd[base]                # Stored in MSB
            remaining_bits  = total_bits - used_bits  # Must be store in LSB            
            if remaining_bits <= 0:
              block_uint = np.zeros_like(full_block, dtype=np.uint16)
              if verbose:
                print("    %-10s: remaining bits <= 0. New block = 0." % param)        
            else:
              extract_bits = min(remaining_bits, video.bitdepth)
              mask         = (1 << remaining_bits) - 1      # LSB mask 
              shift_bits   = remaining_bits - extract_bits  # keep MSB in the LSB
              block_uint   = full_block_uint & mask                            
              block_uint   = block_uint >> shift_bits           
              block_uint   = block_uint.astype(np.uint8 if video.bitdepth <= 8 else np.uint16)
              if verbose:
                print("    %-10s: value %2d bits = %4d: remain = %2d shift = %2d <=> value %2d bits = %4d" % (
                      param, self.bit_depth_pos, full_block[0,0], remaining_bits, shift_bits, video.bitdepth, block_uint[0,0] ))                      
              print("      block src  = ", full_block_uint.flatten())
              print("      block uint = ", block_uint.flatten())
          else:
            block_src  = video.get_block(param, frame_index, type='src', verbose=verbose)
            block_uint = (block_src.astype(np.uint32) >> shift_att).astype(np.uint8 if video.bitdepth <= 8 else np.uint16)
            if verbose:
              print("    %-10s: value %2d bits = %4d >> %2d <=> value %2d bits = %4d " % (
                  param, self.bit_depth_att, block_src.astype(np.uint32)[0,0], shift_att, video.bitdepth,block_uint[0,0])) 
              print("      block uint = ", block_uint.flatten())
              print("      block s/d  = ", block_src.flatten())
          video.set_block(param, frame_index, block_uint, type='uint', verbose=verbose)
          

  #######################################################################################################

  def restore_bitdepth(self, verbose=False):
    bd = self.get_position_bitdepths()
    if verbose:
      print("restore_bitdepth  bd xyz = %8.6f %8.6f %8.6f bd pos = %8.2f bp att = %8.2f" % 
        ( bd['x'], bd['y'], bd['z'], self.bit_depth_pos, self.bit_depth_att))

    for name, video in self.videos.items():
      num_frames       = video.num_frames('uint')
      num_frames_video = video.video_uint.num_frames()        
      video.video_dec.alloc(num_frames_video, video.width, video.height, 32, "444" if video.format == Format.YUV444 else "400")
      shift_pos = self.bit_depth_pos - video.bitdepth
      shift_att = self.bit_depth_att - video.bitdepth
      if verbose:
        print("  restore %10s: bit_depth_pos = %d bitdepth = %d => shift = %d " % (video.name(), self.bit_depth_pos, video.bitdepth, shift_pos))
      for frame_index in range(num_frames):
        for param in video.list_params:
          if param in ['x', 'y', 'z']:
            block_uint  = video.get_block(param, frame_index, type='uint', verbose=verbose).astype(np.uint32)
            block_dec   = (block_uint << shift_pos).astype(np.float32)                    
            block_src   = video.get_block(param, frame_index, type='dec', verbose=verbose).astype(np.uint32)
            block       = block_dec + block_src
            if verbose:
              print("    %-10s: value %2d bits = %4d >> %2d <=> value %2d bits = %4d" % ( 
                                  param, self.bit_depth_pos, block[0,0], shift_pos, video.bitdepth, block_uint[0,0]))
              print("      block uint = ", block_uint.flatten())
              print("      block s/d  = ", block.flatten())
            video.set_block(param, frame_index, block, type='dec', verbose=verbose)
          elif param in ['x_add', 'y_add', 'z_add']:
            base           = param[0]  # 'x', 'y', or 'z'
            video_xyz       = self.get_video_with_param( base )
            total_bits     = self.bit_depth_pos
            used_bits      = bd[base]
            remaining_bits = total_bits - used_bits
            extract_bits   = min(remaining_bits, video.bitdepth)
            shift_bits     = remaining_bits - extract_bits
            block_uint     = video.get_block(param, frame_index, type='uint', verbose=verbose).astype(np.uint32)
            block_shift    = block_uint << shift_bits    # re-align in LSB
            block_res      = block_shift.astype(np.float32)            
            block_src      = video_xyz.get_block(base, frame_index, type='dec', verbose=verbose).astype(np.uint32)
            block_dec      = block_res + block_src
            video_xyz.set_block(base, frame_index, block_dec, type='dec', verbose=verbose)
            if verbose:
              print("    %-10s: value %2d bits = %4d: remain = %2d shift = %2d <=> value %2d bits = %4d" % (
                    param, self.bit_depth_pos, block[0,0], remaining_bits, shift_bits, video.bitdepth, block_uint[0,0] ))    
              print("      block uint = ", video.get_block(param, frame_index, type='uint', verbose=verbose).astype(np.uint32).flatten())
              print("      block src  = ", block_src.flatten())
              print("      block res  = ", block_res.flatten())
              print("      block dec  = ", block_dec.flatten())
          else:
            block_uint  = video.get_block(param, frame_index, type='uint', verbose=verbose).astype(np.uint32)
            block_dec   = (block_uint << shift_att).astype(np.float32)
            if verbose:
              print("    %-10s: value %2d bits = %4d >> %2d <=> value %2d bits = %4d " % (
                  param, self.bit_depth_att, block_dec.astype(np.uint32)[0,0], shift_att, video.bitdepth, block_uint[0,0])) 
            print("      block uint = ", block_uint.flatten())
            print("      block s/d  = ", block_dec.flatten())
            video.set_block(param, frame_index, block_dec, type='dec', verbose=verbose)

  #######################################################################################################

  def quantize(self, verbose=False):

    # Quantize all primary parameters
    for name, video in self.videos.items():
      video.quantize(verbose=verbose)

    # Quantize residuals 
    has_add_param = any( add_param in video.list_params for add_param in ['x_add', 'y_add', 'z_add'] for video in self.videos.values() )

    # Dequantization position
    if has_add_param:      
      for name, video in self.videos.items():
        if any(p in video.list_params for p in ['x', 'y', 'z']):
          video.dequantize(residual=True, verbose=verbose)

      # Set x/y/z add
      for args_add in ['x_add', 'y_add', 'z_add']:
        for name_add, video_add in self.videos.items():
          if args_add in video_add.list_params:
            if verbose:
              print(f"  Quantize: found {args_add} in {video_add.list_params}")
            args_xyz = args_add[0]
            for name_xyz, video_xyz in self.videos.items():
              if args_xyz in video_xyz.list_params:
                # Extract residual blocks
                residual_float = []
                num_frames_xyz = video_xyz.num_frames("uint")
                for frame_index in range(num_frames_xyz):
                  if verbose:
                    print("get_block %s frame = %d " % ( frame_index, frame_index))                
                  block = video_xyz.get_block(args_xyz, frame_index,  type='res', verbose=verbose)
                  residual_float.append(block)

                # Flatten and normalize
                flat = np.concatenate([b.flatten() for b in residual_float])
                min_val = flat.min()
                max_val = flat.max()
                bit_max = (2 ** video_add.bitdepth) - 1
                residual_uint = []
                for b in residual_float:
                  normed = (b - min_val) / (max_val - min_val) if max_val > min_val else np.zeros_like(b)
                  q = np.clip(normed * bit_max, 0, bit_max).astype(np.uint8 if video_add.bitdepth <= 8 else np.uint16)
                  residual_uint.append(q)

                # Store min/max for the residual in video_add
                for index, args in enumerate(video_add.list_params):
                  if args == args_add:
                    video_add.min[index] = min_val
                    video_add.max[index] = max_val
                    if verbose:
                      print(f"    Set min/max for {args}: {min_val:.6f} {max_val:.6f}")

                # Store the quantized residual blocks into video_add
                for frame_index in range(len(residual_uint)):
                  video_add.set_block(args_add, frame_index, residual_uint[frame_index], type="uint", verbose=verbose)

  #######################################################################################################

  def dequantize(self, verbose=False):
    # Dequantize all primary parameters
    for name, video in self.videos.items():
      video.dequantize(verbose=verbose)

    for args_add in ['x_add', 'y_add', 'z_add']:        
      if verbose:
        print("Dequantize residuals %s " % (args_add))
      for name_add, video_add in self.videos.items():
        if args_add in video_add.list_params:
          if verbose:
            print(f"  Found residual param {args_add} in {video_add.list_params}")
          args_xyz = args_add[0]
          for name_xyz, video_xyz in self.videos.items():
            if args_xyz in video_xyz.list_params:

              # Extract residual uint blocks
              residual_uint = []
              num_frames = video_add.num_frames("uint")
              for frame_index in range(num_frames):
                block = video_add.get_block(args_add, frame_index, type="uint", verbose=verbose)
                residual_uint.append(block)

              # Dequantize residuals
              bit_max = (2 ** video_add.bitdepth) - 1
              min_val = 0.0
              max_val = 0.0
              for index, args in enumerate(video_add.list_params):         
                if args == args_add:
                  min_val = video_add.min[index]
                  max_val = video_add.max[index]
                  if verbose:
                    print("    Set min max %s index = %d : %f %f " % (args,index,min_val,max_val))

              residual_float = []
              for b in residual_uint:
                normed = b.astype(np.float32) / bit_max
                residual_float.append(normed * (max_val - min_val) + min_val)

              # Apply residuals to decoded video of primary param
              for frame_index in range(len(residual_float)):
                base_block = video_xyz.get_block(args_xyz, frame_index, type="dec", verbose=verbose)
                updated = base_block + residual_float[frame_index]
                video_xyz.set_block(args_xyz, frame_index, updated, type="dec", verbose=verbose)

  #######################################################################################################      

  def num_frames(self, type):
    for idx, (_, video) in enumerate(self.videos.items()):      
      return video.num_frames(type)

  #######################################################################################################

  def print(self, name='', file=None):
    print("Gof[%2d]: %s " % (self.index, name ),file=file)            
    for idx, (_, video) in enumerate(self.videos.items()):
      video.print(file=file)

  #######################################################################################################
 
  def print_component_codec_mapping(self):
      print("ComponentCodecMapping:")
      for codec_id, codec_4cc in enumerate(self.codecs):
        print(f"  id={codec_id}  4CC='{codec_4cc}'")

  #######################################################################################################

  def save(self, path='', bitstream_log=False, verbose=False):      
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
    vps.write( v3c_unit.bitstream, gof=self )
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
    if self.bit_depth_pos != 32 or self.bit_depth_att != 32 :
      sei.append( Sei.create( SeiPayloadType.DEQUANTIZATION_MAPPING_REGISTERED ) )   
    sei.append( Sei.create( SeiPayloadType.GSC_REGISTERED ) )    
    if self.camera_df is not None and not self.camera_df.empty:
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
    for idx, (_, video) in enumerate(self.videos.items()):        
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
    for index, v3c_unit in enumerate( ssvu.get_v3c_units() ):
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