import os
import re
import hashlib
import numpy as np

from utils.common import create_yuv_filename, to_bash_path

#######################################################################################################

class Video:

  def __init__(self, path = ''):
    self.width  = 0
    self.height = 0
    self.fps    = 30
    self.bits   = 8
    self.format = '444'
    self.frames = []
    if path != '':
      self.read(path)

  #######################################################################################################

  def num_frames(self):
    return len(self.frames)

  #######################################################################################################

  def num_planes(self):
    return 1 if self.format == '400' else 3

  #######################################################################################################

  def c(self, index, c ):
    return self.frames[index][c]

  #######################################################################################################
    
  def get_last_frame_c(self, c ):
    return self.frames[len(self.frames)-1][c]

  #######################################################################################################

  def alloc(self, num_frames, width, height, bits=8, format='420', force_type=None):
    self.width  = width
    self.height = height
    self.format = format
    self.bits   = bits
    median_value = 1 << (bits - 1)
    for _ in range(num_frames):
      if force_type is not None:
        type = force_type
      else:
        type = np.uint8 if self.bits <= 8 else np.uint16 if self.bits <= 16 else np.float32 
      if self.format == '400':
        y = np.zeros((self.height, self.width), dtype=type)
        u = None
        v = None
      elif self.format == '420':
        y = np.zeros(( self.height, self.width, ), dtype=type)
        u = np.full((self.height, self.width), median_value, dtype=type)
        v = np.full((self.height, self.width), median_value, dtype=type)
      elif self.format == '444':
        y = np.zeros((self.height, self.width), dtype=type)
        u = np.full((self.height, self.width), median_value, dtype=type)
        v = np.full((self.height, self.width), median_value, dtype=type)
      else:
        raise ValueError(f"Unsupported video format: {self.format}")
      self.frames.append((y, u, v))

  #######################################################################################################

  def add_frame(self, bits, c0, c1=None, c2=None, verbose=False):
    if verbose:
      print("bits = ", bits, " c0.type = ", c0.dtype, " c1.type = ", c1.dtype, " c2.type = ", c2.dtype, " c0 = ", c0, " c1 = ", c1, " c2 = ", c2)
    self.format = '400' if c1 is None and c2 is None else ('444' if c0.shape[0] == c1.shape[0] else '420')
    self.bits = bits
    self.height, self.width = c0.shape
    self.frames.append((c0, c1, c2))
  
  #######################################################################################################

  def add_empty_frame(self, width, height, bits=8, format='420', verbose=False):
    self.width  = width
    self.height = height  
    self.format = format
    self.bits   = bits
    if self.width == 0 or self.height == 0:
      raise ValueError("Video dimensions are not set")
    dtype = np.uint8 if self.bits <= 8 else np.uint16 if self.bits <= 16 else np.float32
    if verbose:
      print("  Adding empty frame: width = %d, height = %d, bits = %d, format = %s " % (self.width, self.height, self.bits, self.format))
    if self.format == '400':
      y = np.zeros((self.height, self.width), dtype=dtype)
      u = None
      v = None
    elif self.format == '420':
      # 444 and 420 us the same logic initially
      y = np.zeros((self.height, self.width), dtype=dtype)
      u = np.zeros((self.height, self.width), dtype=dtype)
      v = np.zeros((self.height, self.width), dtype=dtype)
    elif self.format == '444':
      y = np.zeros((self.height, self.width), dtype=dtype)
      u = np.zeros((self.height, self.width), dtype=dtype)
      v = np.zeros((self.height, self.width), dtype=dtype)
    elif self.format == '444':
      y = np.zeros((self.height, self.width), dtype=dtype)
      u = np.zeros((self.height, self.width), dtype=dtype)
      v = np.zeros((self.height, self.width), dtype=dtype)
    else:
      raise ValueError(f"Unsupported video format: {self.format}")
    self.frames.append((y, u, v))

  #######################################################################################################

  def pack_plane(self, data, f, x, y, c,verbose=False):
    # if verbose:
    #   print("Packing plane: f = %d, x = %d, y = %d, c = %d, format = %s shape = %s " % (f, x, y, c, self.format, str(data.shape)))
    if self.num_frames() == 0:
      raise ValueError("Video has no frames")
    yc, uc, vc = self.frames[f]
    h0, w0 = data.shape
    if y + h0 > self.height or x + w0 > self.width:
      raise ValueError("Packing region out of bounds  y + h0 = %d > height = %d or x + w0 = %d > width = %d" % (y + h0, self.height, x + w0, self.width))
    if c == 0:
      yc[y:y+h0, x:x+w0] = data
    elif c == 1 and self.format != '400':
      uc[y:y+h0, x:x+w0] = data
    elif c == 2 and self.format != '400':
      vc[y:y+h0, x:x+w0] = data
    else:
      raise ValueError(f"Unsupported format {self.format}")
    self.frames[f] = (yc, uc, vc)

  #######################################################################################################

  def unpack_plane(self, f, x, y, c, w, h, verbose=False):
    if self.num_frames() == 0:
      raise ValueError("Video has no frames")
    yc, uc, vc = self.frames[f]
    if y + h > self.height or x + w > self.width:
      raise ValueError("Y block out of bounds")
    if c == 0:
      data = yc[y:y+h, x:x+w]
    elif c == 1 and self.format == '444':
      data = uc[y:y+h, x:x+w]
    elif c == 2 and self.format == '444':
      data = vc[y:y+h, x:x+w]
    else:
      raise ValueError(f"Unsupported format {self.format}")
    return data

  #######################################################################################################

  def unpack_frame(self, x, y, w, h):
    if self.num_frames() == 0:
      raise ValueError("Video has no frames")
    _, uc, vc = self.frames[-1]
    if y + h > self.height or x + w > self.width:
      raise ValueError("Y block out of bounds")
    c0 = y[y:y+h, x:x+w]
    if self.format == '420':
      if uc is None or vc is None:
        raise ValueError("U/V components missing for 420 format")
      uy, ux = y // 2, x // 2
      uh, uw = h // 2, w // 2
      if uy + uh > uc.shape[0] or ux + uw > uc.shape[1]:
        raise ValueError("UV block out of bounds")
      c1 = uc[uy:uy+uh, ux:ux+uw]
      c2 = vc[uy:uy+uh, ux:ux+uw]
    elif self.format == '444':
      if uc is None or vc is None:
        raise ValueError("U/V components missing for 444 format")
      if y + h > self.height or x + w > self.width:
        raise ValueError("UV block out of bounds")
      c1 = uc[y:y+h, x:x+w]
      c2 = vc[y:y+h, x:x+w]
    elif self.format == '400':
      c1 = None
      c2 = None
    else:
      raise ValueError(f"Unsupported format {self.format}")
    return c0, c1, c2

  #######################################################################################################

  def get_frame(self, index, direct=True):
    frame = np.zeros((self.width, self.height), dtype=self.frames[index][0].dtype)
    if direct:
      frame = self.frames[index][0]
    else:
      for i in range(0, self.height):
        for j in range(0, self.width):
          frame[j][i] = self.frames[index][0][i][j]
    return frame

  #######################################################################################################

  def log(self, name=""):
    print("VIDEO: %s frame = %d dim = %d x %d %d bits format = %s md5 = %s size = %s %s %s  " % \
        ( name, self.num_frames(), self.width, self.height, self.bits, self.format, self.md5(), \
         str( self.frames[0][0].shape ) , \
         str( self.frames[0][0].shape ) , \
         str( self.frames[0][0].shape )  ) )

  #######################################################################################################

  def print(self, name=""):
    dimx, dimy = 8, 4
    print("VIDEO: %s frame = %d dim = %d x %d (%d x %d and %d x %d ) %d bits format = %s md5 = %s dtype = " %
        (name, self.num_frames(), self.width, self.height, 
        self.frames[0][0].shape[1], self.frames[0][0].shape[0], 
        self.frames[0][1].shape[1] if self.frames[0][1] is not None else 0,
        self.frames[0][1].shape[0] if self.frames[0][1] is not None else 0,
        self.bits, self.format, self.md5()), self.frames[0][0].dtype)
    for f in range(self.num_frames()):
      print("%-10s j =   : " % ' ', end=' ')      
      for j in range(min(dimx, self.width)):
        print(f'{j:6d}', end=' ') 
      print(" frame %d dim = %d x %d / %d x %d " % (f, 
          self.frames[f][0].shape[1], self.frames[f][0].shape[0],
          self.frames[f][1].shape[1] if self.frames[f][1] is not None else 0,
          self.frames[f][1].shape[0] if self.frames[f][1] is not None else 0))

      for i in range(min(dimy, self.height)):
        print("%-10s i = %4d: " % (' ' if j != 0 else ('F%04d' % f), i), end=' ') 
        for j in range(min(dimx, self.width)):
          print(f'{self.frames[f][0][i][j]:6.2f}', end=' ')
        if self.frames[f][1] is not None:
          print("  ", end=' ') 
          for j in range(min(dimx, self.width)):
            print(f'{self.frames[f][1][i][j]:6.2f}', end=' ')
        if self.frames[f][2] is not None:
          print("  ", end=' ') 
          for j in range(min(dimx, self.width)):
            print(f'{self.frames[f][2][i][j]:6.2f}', end=' ')
        print(end='\n')

  #######################################################################################################

  def convert_400_to_420(self):
    if self.format != '400':
      raise ValueError("convert_400_to_420() can only be called on videos with format '400'")      
    median_value = 1 << (self.bits - 1)
    type = np.uint8 if self.bits <= 8 else np.uint16 if self.bits <= 16 else np.float32
    new_frames = []
    for (y, _, _) in self.frames:
      u = np.full((self.height // 2, self.width // 2), median_value,  dtype=type)
      v = np.full((self.height // 2, self.width // 2), median_value,  dtype=type)
      new_frames.append((y.copy(), u, v))
    self.frames = new_frames
    self.format = '420'

  #######################################################################################################

  def convert_420_to_400(self):
    if self.format != '420':
      raise ValueError("convert_420_to_400() can only be called on videos with format '420'")
    new_frames = []
    for (Y, _, _) in self.frames:
      new_frames.append((Y.copy(), None, None))
    self.frames = new_frames
    self.format = '400'

  #######################################################################################################

  def md5(self):
    md5_hash = hashlib.md5()
    for y, u, v in self.frames:
      md5_hash.update(y.tobytes())
      if u is not None:
        md5_hash.update(u.tobytes())
      if v is not None:
        md5_hash.update(v.tobytes())
    return md5_hash.hexdigest()

  #######################################################################################################

  def read(self, path, verbose=False):
    self.width, self.height, self.fps, self.bits, self.format = self.extract_yuv_info(path)
    if not os.path.exists(path):
      print("ERROR: %s not exists " % path)
      exit(-1)
    file = open(path, 'rb')
    self.frames = []
    while True:
      frame = self.__read_frame(file)
      if frame is None:
        break
      self.frames.append(frame)
    if verbose:      
      print("Read %s size = %dx%d bits = %d format = %s num_frames = %d" %
          (path, self.width, self.height, self.bits, self.format, self.num_frames()))
    file.close()

  #######################################################################################################

  def __read_frame(self, file):
    frame_size = self.__get_frame_size()
    frame_data = file.read(frame_size)
    if not frame_data:
      return None
    return self.__unpack_frame(frame_data)

  #######################################################################################################

  def __write_frame(self, file, y, u=None, v=None):
    if self.format == '400':
      if u is not None or v is not None:
        raise ValueError("YUV400 format does not have U or V components")
      # y = np.zeros(( self.width, self.height ), dtype=Y.dtype)
      file.write(y.tobytes())
    else:
      file.write(y.tobytes())
      if u is None:
        if self.format == '420':
          u = np.zeros((self.height // 2, self.width // 2), dtype=y.dtype)  # + (1<<(self.bits-1))
        elif self.format == '444':
          u = np.zeros((self.height, self.width), dtype=y.dtype)
      file.write(u.tobytes())
      if v is None:
        if self.format == '420':
          v = np.zeros((self.height // 2, self.width // 2), dtype=y.dtype)  # + (1<<(self.bits-1))
        elif self.format == '444':
          v = np.zeros((self.height, self.width), dtype=y.dtype)
      file.write(v.tobytes())

  #######################################################################################################

  def write(self, directory='', path='', suffix='', verbose=False):    
    filename = self.__create_yuv_filename(path, suffix)
    if directory != '':
      filename = to_bash_path(os.path.join(directory, filename))
    file = open(filename, 'wb')
    for y, u, v in self.frames:
      self.__write_frame(file, y, u, v)
    file.close()
    return filename

  # #######################################################################################################

  def get_num_comp(self):
    if self.format == '444':
      return 3
    elif self.format == '420':
      return 3
    elif self.format == '400':
      return 1

  #######################################################################################################

  def __get_frame_size(self):
    num_bytes = 1 if self.bits <= 8 else 2
    if self.format == '420':
      return num_bytes * self.height * self.width * 3 // 2
    elif self.format == '444':
      return num_bytes * self.height * self.width * 3
    elif self.format == '400':
      return num_bytes * self.height * self.width
    else:
      raise ValueError("Unsupported YUV format")

  #######################################################################################################

  def __unpack_frame(self, data):
    size = self.width * self.height * (1 if self.bits <= 8 else 2)
    type = np.uint8 if self.bits <= 8 else np.uint16
    if self.format == '400':
      # copy() is needed to modify the frame in yuv2rgb
      y = np.frombuffer(data, dtype=type).reshape((self.height, self.width)).copy()
      return (y, None, None)
    elif self.format == '420':
      y = np.frombuffer(data[:size], dtype=type).reshape((self.height, self.width)).copy()
      chroma_size = size // 4  # U and V are each 1/4 the size of Y
      u = np.frombuffer(data[size:size + chroma_size], dtype=type).reshape((self.height // 2, self.width // 2)).copy()
      v = np.frombuffer(data[size + chroma_size:size + 2 * chroma_size], dtype=type).reshape((self.height // 2, self.width // 2)).copy()
      return (y, u, v)
    else: # self.format == '444'
      y = np.frombuffer(data[:size], dtype=type).reshape((self.height, self.width)).copy()
      u = np.frombuffer(data[size:size * 2], dtype=type).reshape((self.height, self.width)).copy()
      v = np.frombuffer(data[size * 2:], dtype=type).reshape((self.height, self.width)).copy()
      return (y, u, v)

  #######################################################################################################

  def extract_yuv_info(self, path):
    pattern = r'(\d+)x(\d+)_([0-9.]+)_([0-9]+)b_p(\d{3})'
    match = re.search(pattern, os.path.basename(path))
    if match:
      width  = int(match.group(1))
      height = int(match.group(2))
      fps    = int(match.group(3))
      bits   = int(match.group(4))
      format = match.group(5)
      return width, height, fps, bits, format
    else:
      raise ValueError("Filename does not match expected YUV format: %s " % os.path.basename(path))

  #######################################################################################################

  def __create_yuv_filename(self, prefix, suffix=''):
    return create_yuv_filename( prefix, suffix, self.width, self.height, self.fps, self.bits, self.format)

#######################################################################################################
