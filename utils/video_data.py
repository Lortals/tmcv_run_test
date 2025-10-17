import os
import math
from math import isfinite
import numpy as np
from utils.common   import log_transform, inverse_log_transform
from utils.video    import Video
from utils.v3c.type import V3CUnitType, Quantization, Format, Packing, ColorStandard  

#######################################################################################################

def _ensure_dir(path: str):
  if path and not os.path.exists(path):
    os.makedirs(path, exist_ok=True)

#######################################################################################################

class VideoData:

  def __init__( self, 
                type           = V3CUnitType.NUM_V3C_UNIT_TYPE,
                list_params    = [],
                bitdepth       = 0,
                bitdepth_pos   = [0,0],
                qp             = 0, 
                codec_id       = 0,
                format         = Format.YUV444,
                packing        = Packing.TEMPORAL,
                quantization   = Quantization.LINEAR,
                trans_position = False,
                sh_conversion  = ColorStandard.NONE,
                subsampling    = 0,
                verbose        = False):
    # V3C nalu unit type
    self.type              = type 
    # Video parameters  
    self.bitdepth          = bitdepth
    self.qp                = qp
    self.codec_id          = codec_id
    self.list_params       = list_params
    self.format            = format
    self.packing           = packing 
    # Transform parameters
    self.bitdepth_pos      = bitdepth_pos
    self.trans_position    = trans_position
    self.sh_conversion     = sh_conversion
    self.subsampling       = subsampling
    # Quantization parameters
    self.quantization      = quantization
    self.min               = [0] * 3
    self.max               = [0] * 3
    self.center            = [0] * 3
    self.sigma             = [0] * 3
    # Video data
    self.width             = 0 
    self.height            = 0
    self.num_components    = 0
    self.num_planes        = 0
    self.video_src         = Video()
    self.video_uint        = Video()
    self.video_dec         = Video()
    self.video_res         = Video()
    # Bitstream  
    self.bitstream         = []
    # Define grid size based on the number of parameters
    if self.packing == Packing.PLANAR:     
      self.grid_width, self.grid_height = self.__get_grid_size()      
    else:
      self.grid_width  = 1
      self.grid_height = 1
    self.block_width  = 0
    self.block_height = 0
    if verbose: 
      print("create_video %-10s %6s %8s grid = %2d %2d params = %s" % (type.name, format.name, packing.name, 
        self.grid_width, self.grid_height, self.name(True)))

  #######################################################################################################
  
  def name(self, all=False):
    def shorten(param):
      if param in ('x', 'y', 'z'):
        return param
      elif param in ('x_add', 'y_add', 'z_add'):
        return param[0] + 'a'   
      elif param in ('x_odd', 'y_odd', 'z_odd'):
        return param[0] + 'o'   
      elif param == 'opacity':
        return 'o'
      elif param == 'zero':
        return '_'
      elif param.startswith('scale_'):
        return 's' + param.split('_')[1]
      elif param.startswith('rot_'):
        return 'r' + param.split('_')[1]
      elif param.startswith('f_dc_'):
        return 'dc' + param.split('_')[2]
      elif param.startswith('f_rest_'):
        return 'sh' + param.split('_')[2]
      else:
        return param
    if all: 
      return ','.join(shorten(param) for param in self.list_params)
    parts = []
    has_dc = any(name.startswith('f_dc_') for name in self.list_params)
    has_sh = any(name.startswith('f_rest_') for name in self.list_params)
    for name in self.list_params:
      if name in ('x', 'y', 'z'):
        parts.append(name)
      elif name in ('x_add', 'y_add', 'z_add'):
        parts.append(name[0] + 'a')
      elif name in ('x_odd', 'y_odd', 'z_odd'):
        parts.append(name[0] + 'o')   
      elif name == 'opacity':
        parts.append('o')
      elif name == 'zero':
        parts.append('-')
      elif name.startswith('scale_'):
        parts.append('s' + name.split('_')[1])
      elif name.startswith('rot_'):
        parts.append('r' + name.split('_')[1])
    if has_dc:
      parts.append('dc')
    if has_sh:
      parts.append('sh')
    return ''.join(parts)

  #######################################################################################################

  def num_frames(self, type, verbose=False):
    video = { "src": self.video_src, "uint": self.video_uint, "dec": self.video_dec, "res": self.video_res }.get(type)    
    num_params = len(self.list_params)
    total_frames = video.num_frames()
    if video is None:
      raise ValueError(f"Unknown video type: {type}")
    result = 0
    if self.packing == Packing.TEMPORAL: 
      if self.format != Format.YUV400: 
        result = total_frames // ( num_params // 3 )
      else:
        result = total_frames // num_params
    else: 
      result = total_frames 
    if verbose:
      print("num_frames: %4s %-6s %-8s total = %3d params = %3d => frames = %3d " % (type, self.format.name, self.packing.name, 
        total_frames, num_params, result))
    return result

  #######################################################################################################
  
  def number_of_video_frames_by_frames(self, type):
    video = { "src": self.video_src, "uint": self.video_uint, "dec": self.video_dec, "res": self.video_res }.get(type)
    if video is None:
      raise ValueError("Unknown video type: %s" % type)
    num_params = len(self.list_params)
    if self.packing == Packing.TEMPORAL:
      if self.format != Format.YUV400:
        factor = (( num_params + 2 ) // 3)
      else:
        factor = num_params
      return factor
    elif self.packing == Packing.PLANAR:
      return 1
    else:
      raise ValueError(f"Unsupported packing mode: {self.packing.name}")

  #######################################################################################################

  def print(self,file=None):
    print("  %-10s f = %2d: bd = %2d min = " % (self.type.name, 
          self.video_uint.num_frames(), self.bitdepth), end='',file=file) 
    for i in range(3): 
      print("%10s " % ( ( '%8.4f' % self.min[i] ) if i < self.num_components else "" ), end='',file=file ) 
    print('Max = ', end='',file=file) 
    for i in range(3): 
      print("%10s " % ( ( '%8.4f' % self.max[i] ) if i < self.num_components else "" ), end='',file=file ) 
    print("%-6s %-8s %-8s " % (self.format.name,self.packing.name,self.quantization.name), end='',file=file) 
    print("comp = ", self.name(True), end='',file=file)  
    print('',file=file)

  #######################################################################################################
  
  def set_grid_size(self, block_width, block_height, verbose=False):
    self.block_width  = block_width
    self.block_height = block_height    
    self.grid_width  = 1
    self.grid_height = 1
    if self.packing == Packing.PLANAR:
      self.grid_width, self.grid_height = self.__get_grid_size()
    self.width  = self.block_width * self.grid_width
    self.height = self.block_height * self.grid_height

  #######################################################################################################

  def __get_grid_size(self):
    N = len(self.list_params)
    if self.format != Format.YUV400:
      N = math.ceil(N / 3)
    h = math.isqrt(N)
    while h > 0:
      w = math.ceil(N / h)
      if w * h >= N:
        return w, h
      h -= 1

  #######################################################################################################

  def get_pack_position(self, position_index):
    num_components = 1 if self.format == Format.YUV400 else 3
    blocks_per_frame = self.grid_width * self.grid_height * num_components
    if self.packing == Packing.TEMPORAL:
      f = position_index // blocks_per_frame
      position_index = position_index % blocks_per_frame
    elif self.packing == Packing.PLANAR:
      f = 0
    else:
      raise ValueError("Unsupported packing type for YUV400: %s" % self.packing.name)         
    block_index = position_index // num_components
    col = block_index % self.grid_width
    row = block_index // self.grid_width
    x = col * self.block_width
    y = row * self.block_height
    c = position_index % num_components  
    return f, x, y, c

  #######################################################################################################

  def pack_one_frame(self, pointcloud, list_params=None, verbose=False):
    self.block_width    = pointcloud.sidelen  
    self.block_height   = pointcloud.sidelen  
    self.width          = self.block_width  * self.grid_width
    self.height         = self.block_height * self.grid_height   
    self.num_components = 1 if self.format == Format.YUV400 else 3
    num_frames          = -1
    if verbose:
      print("  Pack one frame:  %s %s %s, comp = %d, grid = %d x %d block = %dx %d frame = %d x %d " %( 
          self.type.name, self.format.name, self.packing.name, self.num_components, self.grid_width, self.grid_height, 
          self.block_width, self.block_height, self.width, self.height) )
    for i, id in enumerate(self.list_params if list_params is None else list_params):
      if id not in { 'zero', 'x_add', 'y_add', 'z_add' }:
        data = pointcloud.df[id].values.reshape(pointcloud.sidelen, pointcloud.sidelen, -1)
        data = data[:,:,0]
        if self.trans_position == 1 and id in ['x', 'y', 'z']:
          data = log_transform( data ) 
      else:
        data = np.zeros((pointcloud.sidelen, pointcloud.sidelen), dtype=np.float32)
      f, x, y, c = self.get_pack_position(i)
      if f != num_frames:
        self.video_src.add_empty_frame( width=self.width,  height=self.height, bits=32, format=self.format.video_name(), verbose=verbose ) 
        num_frames = f      
      self.video_src.pack_plane(data=data, f=-1, x=x, y=y, c=c, verbose=verbose)
      if verbose: 
        print("  pack %-10s size = %4d x % 4d, f = %3d pos = %4d %4d c = %2d bd = %2d => pc = %20.12f => %20.12f" % (
              id, self.width, self.height, f, x, y, c, self.bitdepth, data[0,0], self.video_src.c(-1, c)[0,0]) ) 
       
  #######################################################################################################

  def get_block(self, param_name: str, frame_index: int, type: str, verbose=False) -> np.ndarray:  
    if param_name not in self.list_params:
      raise ValueError(f"get_block: '{param_name}' not found in list_params.")
    param_index     = self.list_params.index(param_name)
    f, x, y, c      = self.get_pack_position(param_index)    
    frame_factor    = self.number_of_video_frames_by_frames(type)
    vid_frame_index = f + frame_index * frame_factor    
    # if verbose:
    #   print("      Get block %10s f = %2d type = %s => video frame = %3d comp = %d pos = %4d %4d " % 
    #     ( param_name, frame_index, type, vid_frame_index, c, x, y ))
    video = { "src": self.video_src, "uint": self.video_uint, "dec": self.video_dec, "res": self.video_res }.get(type)
    if video is None or video.num_frames() <= vid_frame_index:
      raise ValueError(f"Video '{type}' not available or frame_index {vid_frame_index} is out of range.")
    if self.format == Format.YUV400 and c != 0:
      raise ValueError(f"YUV400 format has only one component, invalid c = {c} for param '{param_name}'")
    plane = video.c(vid_frame_index, c)
    block = plane[y:y + self.block_height, x:x + self.block_width]
    return block

  #######################################################################################################

  def set_block(self, param_name: str, frame_index: int, block: np.ndarray, type: str, verbose=False):   
    if param_name not in self.list_params:
      raise ValueError(f"set_block: '{param_name}' not found in list_params.")
    param_index = self.list_params.index(param_name)
    f, x, y, c = self.get_pack_position(param_index)
    frame_factor = self.number_of_video_frames_by_frames(type)
    vid_frame_index = f + frame_index * frame_factor    
    video = { "src": self.video_src, "uint": self.video_uint, "dec": self.video_dec, "res": self.video_res }.get(type)
    if video is None or video.num_frames() <= vid_frame_index:
      raise ValueError(f"Video '{type}' not available or frame_index {vid_frame_index} is out of range.")
    if self.format == Format.YUV400 and c != 0:
      raise ValueError(f"YUV400 format has only one component, invalid c = {c} for param '{param_name}'")
    # if verbose:
    #   try:
    #     ref_dtype = video.frames[0][0].dtype
    #   except (IndexError, TypeError, AttributeError):
    #     ref_dtype = "N/A"
    #   print(f"      Set block {param_name:<10s} frame = {frame_index:2d} type = {type} dtype = {block.dtype} in {ref_dtype}")
    video.frames[vid_frame_index][c][y:y + self.block_height, x:x + self.block_width] = block

  #######################################################################################################
  ###################################### Create Pointcloud ##############################################
  #######################################################################################################
  
  def get_pointcloud(self, frame_index, pointcloud, verbose=False):
    if verbose:
      print("Get pointcloud: packing = %-8s quant = %-8s format = %-6s frames = %2d grid = %dx%d image = %dx%d trans_position = %d" % (
        self.packing.name, self.quantization.name, self.format.name,
        self.video_dec.num_frames(), self.block_width, self.block_height,
        self.width, self.height, self.trans_position))
    for param in self.list_params:
      if param not in { 'zero', 'x_add', 'y_add', 'z_add' }:
        data = self.get_block(param, frame_index, type='dec', verbose=verbose)
        flat_data = data.flatten()
        if self.trans_position == 1 and param in ['x', 'y', 'z']:
          flat_data = inverse_log_transform(flat_data)
        pointcloud.df[param] = flat_data
        if verbose:
          print("  rec. %-16s: [ %12.8f %12.8f %12.8f %12.8f ... ] " % (param, flat_data[0], flat_data[1], flat_data[2], flat_data[3]))

  #######################################################################################################
  ###################################### Quantization ###################################################
  #######################################################################################################

  def quantize(self, verbose=False):
    if self.quantization == Quantization.LINEAR:
      self._quantize_linear(verbose)
    elif self.quantization == Quantization.GAUSSIAN:
      self._quantize_gaussian(verbose)
    else:
      raise ValueError(f"Unsupported quantization method: {self.quantization.name}")

  #######################################################################################################

  def dequantize(self, verbose = False):
    if self.quantization == Quantization.LINEAR:
      self._dequantize_linear(verbose)
    elif self.quantization == Quantization.GAUSSIAN:
      self._dequantize_gaussian(verbose)
    else:
      raise ValueError(f"Unsupported dequantization method: {self.quantization.name}")

  #######################################################################################################
  ###################################### Linear quantization ############################################
  #######################################################################################################

  def _quantize_linear(self, verbose=False):
    if verbose:
      print(f"Quantization (linear): packing = {self.packing.name}, type = {self.type.name}")
    self.min         = []
    self.max         = []
    num_frames       = self.num_frames('src')
    num_frames_video = self.video_src.num_frames()
    num_blocks       = len(self.list_params)
    self.video_uint.alloc(num_frames_video, self.width, self.height, self.bitdepth, format=self.format.video_name() )
    self.video_res.alloc(num_frames_video, self.width, self.height, self.bitdepth, force_type=np.uint32, format=self.format.video_name())
    for block_index in range(num_blocks):
      param = self.list_params[block_index]
      if param in ['zero', 'x_add', 'y_add', 'z_add']:
        self.min.append(0)
        self.max.append(0)
        continue
      values = []
      for frame_index in range(num_frames):
        block = self.get_block(param, frame_index, type='src', verbose=verbose)
        values.append(block.flatten())
      values = np.concatenate(values)
      min_val = np.min(values)
      max_val = np.max(values)
      self.min.append(min_val)
      self.max.append(max_val)

    for frame_index in range(num_frames):
      for block_index, param in enumerate(self.list_params):        
        if param not in [ 'zero', 'x_add', 'y_add', 'z_add' ]: 
          block = self.get_block(param, frame_index, type='src', verbose=verbose)
          min_val, max_val = self.min[block_index], self.max[block_index]
          if max_val - min_val < 1e-8:
            normed = np.zeros_like(block)
          else:
            normed = (block - min_val) / (max_val - min_val)
          if param in ['x', 'y', 'z']:
            bitdepth = self.bitdepth_pos[0] + self.bitdepth_pos[1] 
            bit_max = (2 ** bitdepth) - 1
            quantized = np.clip(np.round(normed * (bit_max + 1)), 0, bit_max).astype(np.uint32)
            self.set_block(param, frame_index, quantized, type='uint', verbose=verbose)            
            self.set_block(param, frame_index, quantized, type='res', verbose=verbose)
          else: 
            bitdepth = self.bitdepth
            bit_max = (2 ** bitdepth) - 1 
            quantized = np.clip(np.round(normed * (bit_max + 1)), 0, bit_max).astype(np.uint8 if self.bitdepth <= 8 else np.uint32)          
            self.set_block(param, frame_index, quantized, type='uint', verbose=verbose)
          if verbose:
            print("  quant %-10s size = %4d x %4d, f = %3d pos = %4d %4d c = %2d bd = %2d min = %12.8f max = %12.8f : %20.12f => %6d" % ( param, self.width, self.height, 
                  frame_index, *self.get_pack_position(block_index)[1:], bitdepth, min_val, max_val, block[0,0], quantized[0,0]) )
                  
  #######################################################################################################

  def _dequantize_linear(self, verbose=False):
    if verbose:
      print(f"Dequantization (linear): packing = {self.packing.name}, type = {self.type.name}")
    num_frames       = self.num_frames('uint')
    num_frames_video = self.video_uint.num_frames()
    self.video_dec.alloc(num_frames_video, self.width, self.height, 32, format=self.format.video_name())        
    for frame_index in range(num_frames):
      for block_index, param in enumerate(self.list_params):        
        if param not in [ 'zero', 'x_add', 'y_add', 'z_add' ]: 
          if param in ['x', 'y', 'z']:
            bitdepth = self.bitdepth_pos[0] + self.bitdepth_pos[1]
            if self.bitdepth_pos[1] > 0:
              block    = self.get_block(param, frame_index, type='res', verbose=verbose)
            else:
              block    = self.get_block(param, frame_index, type='uint', verbose=verbose)
          else:
            bitdepth = self.bitdepth
            block = self.get_block(param, frame_index, type='uint', verbose=verbose)
          bit_max = (2 ** bitdepth) - 1
          min_val, max_val = self.min[block_index], self.max[block_index]
          normed = block.astype(np.float32) / (bit_max + 1)
          dequantized = normed * (max_val - min_val) + min_val
          self.set_block(param, frame_index, dequantized, type='dec', verbose=verbose)
          if verbose:
            print("  dequ %-10s size = %4d x %4d, f = %3d pos = %4d %4d c = %2d bd = %2d min = %12.8f max = %12.8f : %6d => %20.12f " % (
                  param, self.width, self.height, frame_index, *self.get_pack_position(block_index)[1:], bitdepth, min_val, max_val,
                  block[0,0], dequantized[0,0]) )

#######################################################################################################
###################################### Gaussian quantization ##########################################
#######################################################################################################
  
  def _safe_compute_levels(self,min_val, max_val, center, sigma, levels_count):
    sigma = float(max(sigma, 1e-6))
    fine_grid = np.linspace(min_val, max_val, 10000, dtype=np.float64)
    coef = 1.0 / (sigma * np.sqrt(2.0 * np.pi))
    pdf = coef * np.exp(-0.5 * ((fine_grid - center) / sigma) ** 2)
    cdf = np.cumsum(pdf)
    cdf /= cdf[-1] if cdf[-1] != 0 else 1.0
    target_cdf = np.linspace(0.0, 1.0, levels_count, dtype=np.float64)
    return np.interp(target_cdf, cdf, fine_grid)

#######################################################################################################

  def _get_levels(self, block_index, levels_count):
    min_val = self.min[block_index]
    max_val = self.max[block_index]
    center  = self.center[block_index]
    sigma   = self.sigma[block_index]
    if hasattr(self, "_QuantizeGaussian__compute_levels"):  
      return self._QuantizeGaussian__compute_levels(min_val, max_val, center, sigma, levels_count)
    if hasattr(self, "__compute_levels"):
      return self.__compute_levels(min_val, max_val, center, sigma, levels_count)
    return self._safe_compute_levels(min_val, max_val, center, sigma, levels_count)

#######################################################################################################

  def _quantize_gaussian(self, verbose=False):
    if verbose:
      print(f"Quantization (gaussian): packing = {self.packing.name}, type = {self.type.name}")
    self.min, self.max, self.center, self.sigma = [], [], [], []
    num_frames       = self.num_frames('src')
    num_frames_video = self.video_src.num_frames()
    num_blocks       = len(self.list_params)
    self.video_uint.alloc(num_frames_video, self.width, self.height, self.bitdepth, self.format.video_name())
    for block_index in range(num_blocks):
      param = self.list_params[block_index]
      if param in ['zero', 'x_add', 'y_add', 'z_add']:
        self.min.append(0); self.max.append(0); self.center.append(0); self.sigma.append(1.0)
        continue
      bitdepth = self.bitdepth_pos[0] if param in ['x','y','z'] and self.bitdepth_pos[0] != 0 else self.bitdepth
      levels_count = 2 ** bitdepth
      values = []
      for frame_index in range(num_frames):
        block = self.get_block(param, frame_index, type='src', verbose=verbose)
        values.append(block.flatten())
      values = np.concatenate(values).astype(np.float64)
      min_val = float(np.min(values))
      max_val = float(np.max(values))
      hist_counts, bin_edges = np.histogram(values, bins=levels_count, range=(min_val, max_val))
      bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
      center = float(bin_centers[np.argmax(hist_counts)])
      sigma = float(np.std(values))
      if not isfinite(sigma) or sigma <= 0.0:
        sigma = 1.0
      self.min.append(min_val); self.max.append(max_val); self.center.append(center); self.sigma.append(sigma)
    for frame_index in range(num_frames):
      for block_index, param in enumerate(self.list_params):
        if param in ['zero', 'x_add', 'y_add', 'z_add']:
          continue
        bitdepth = self.bitdepth_pos[0] if param in ['x','y','z'] and self.bitdepth_pos[0] != 0 else self.bitdepth
        levels_count = 2 ** bitdepth
        block = self.get_block(param, frame_index, type='src', verbose=verbose).astype(np.float64).flatten()
        levels = self._get_levels( block_index, levels_count)
        idx = np.searchsorted(levels, block, side='left')

        right_idx = np.clip(idx, 0, levels_count - 1)
        left_idx  = np.clip(idx - 1, 0, levels_count - 1)
        choose_left = (np.abs(block - levels[left_idx]) <= np.abs(block - levels[right_idx]))
        idx = np.where(choose_left, left_idx, right_idx)
        idx = np.clip(idx, 0, levels_count - 1)
        q_dtype = np.uint8 if self.bitdepth <= 8 else np.uint16
        quantized = idx.astype(q_dtype).reshape(self.block_height, self.block_width)
        self.set_block(param, frame_index, quantized, type='uint', verbose=verbose)
        if verbose:
          print("  Block %2d %-10s: min = %8.4f max = %8.4f center = %8.4f sigma = %8.4f : %20.12f => %6d " % 
            (block_index, param, min_val, max_val, center, sigma, block[0], quantized[0,0]))

#######################################################################################################

  def _dequantize_gaussian(self, verbose=False):
    if verbose:
      print(f"Dequantization (gaussian): packing = {self.packing.name}, type = {self.type.name}")
    num_frames       = self.num_frames('uint')
    num_frames_video = self.video_uint.num_frames()
    self.video_dec.alloc(num_frames_video, self.width, self.height, 32, format=self.format.video_name())
    self.video_res.alloc(num_frames_video, self.width, self.height, 32, force_type=np.uint32,format=self.format.video_name())

    levels_cache = {} 
    for frame_index in range(num_frames):
      for block_index, param in enumerate(self.list_params):
        if param in ['zero', 'x_add', 'y_add', 'z_add']:
          continue
        bitdepth = self.bitdepth_pos[0] if param in ['x','y','z'] and self.bitdepth_pos[0] != 0 else self.bitdepth
        levels_count = 2 ** bitdepth        
        key = (block_index, levels_count)
        if key not in levels_cache:
          levels_cache[key] = self._get_levels(block_index, levels_count)
        levels = levels_cache[key]
        indices = self.get_block(param, frame_index, type='uint', verbose=verbose).astype(np.int32).flatten()
        indices = np.clip(indices, 0, levels_count - 1)
        dequantized = levels[indices].reshape(self.block_height, self.block_width)
        self.set_block(param, frame_index, dequantized, type='dec', verbose=verbose)
        if verbose:
          min_val = self.min[block_index]
          max_val = self.max[block_index]
          center  = self.center[block_index]
          sigma   = self.sigma[block_index]
          print("  Block %2d %-10s: min = %8.4f max = %8.4f center = %8.4f sigma = %8.4f : %20.12f => %6d " % 
            (block_index, param, min_val, max_val, center, sigma, dequantized[0,0], indices[0]))
            
#######################################################################################################