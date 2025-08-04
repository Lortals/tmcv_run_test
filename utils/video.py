import os
import re
import sys
import numpy as np
import hashlib
import platform

from utils.common import create_yuv_filename, to_bash_path

#######################################################################################################

class Video:

  def __init__(self, path = '', name = ''):
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
    
  def getLastFrameC(self, c ):
    return self.frames[len(self.frames)-1][c]

  #######################################################################################################

  def alloc(self, num_frames, width, height, bits=8, format='420', verbose=False):
    self.width  = width
    self.height = height
    self.format = format
    self.bits   = bits
    for f in range(num_frames):
      type = np.uint8 if self.bits <= 8 else np.uint16 if self.bits <= 16 else np.float32
      if self.format == '400':
        Y = np.zeros((self.height, self.width), dtype=type)
        U = None
        V = None
      elif self.format == '420':
        Y = np.zeros(( self.height, self.width, ), dtype=type)
        U = np.zeros((self.height // 2, self.width // 2), dtype=type)
        V = np.zeros((self.height // 2, self.width // 2), dtype=type)
      elif self.format == '444':
        Y = np.zeros((self.height, self.width), dtype=type)
        U = np.zeros((self.height, self.width), dtype=type)
        V = np.zeros((self.height, self.width), dtype=type)
      else:
        raise ValueError(f"Unsupported video format: {self.format}")
      self.frames.append((Y, U, V))

  #######################################################################################################

  def remove_uv(self):
    self.format = '400'
    for idx in range(len(self.frames)):
      self.frames[idx] = (self.frames[idx][0], None, None)

  #######################################################################################################

  def add_frame(self, bits, c0, c1=None, c2=None, direct=True, verbose=False):
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
      Y = np.zeros((self.height, self.width), dtype=dtype)
      U = None
      V = None
    elif self.format == '420':
      Y = np.zeros((self.height, self.width), dtype=dtype)
      U = np.zeros((self.height // 2, self.width // 2), dtype=dtype)
      V = np.zeros((self.height // 2, self.width // 2), dtype=dtype)
    elif self.format == '444':
      Y = np.zeros((self.height, self.width), dtype=dtype)
      U = np.zeros((self.height, self.width), dtype=dtype)
      V = np.zeros((self.height, self.width), dtype=dtype)
    else:
      raise ValueError(f"Unsupported video format: {self.format}")
    self.frames.append((Y, U, V))

  #######################################################################################################

  def pack_plane(self, data, f, x, y, c, verbose=False):
    if self.num_frames() == 0:
      raise ValueError("Video has no frames")
    Y, U, V = self.frames[f]
    h0, w0 = data.shape
    if y + h0 > self.height or x + w0 > self.width:
      raise ValueError("c0 out of bounds")
    if c == 0:
      Y[y:y+h0, x:x+w0] = data
    elif c == 1 and self.format == '444':
      U[y:y+h0, x:x+w0] = data
    elif c == 2 and self.format == '444':
      V[y:y+h0, x:x+w0] = data
    else:
      raise ValueError(f"Unsupported format {self.format}")
    self.frames[f] = (Y, U, V)

  #######################################################################################################

  def unpack_plane(self, f, x, y, c, w, h, verbose=False):
    if self.num_frames() == 0:
      raise ValueError("Video has no frames")
    Y, U, V = self.frames[f]
    if y + h > self.height or x + w > self.width:
      raise ValueError("Y block out of bounds")
    if c == 0:
      data = Y[y:y+h, x:x+w]
    elif c == 1 and self.format == '444':
      data = U[y:y+h, x:x+w]
    elif c == 2 and self.format == '444':
      data = V[y:y+h, x:x+w]
    else:
      raise ValueError(f"Unsupported format {self.format}")
    return data

  #######################################################################################################

  def unpack_frame(self, x, y, w, h):
    if self.num_frames() == 0:
      raise ValueError("Video has no frames")
    Y, U, V = self.frames[-1]
    if y + h > self.height or x + w > self.width:
      raise ValueError("Y block out of bounds")
    c0 = Y[y:y+h, x:x+w]
    if self.format == '420':
      if U is None or V is None:
        raise ValueError("U/V components missing for 420 format")
      uy, ux = y // 2, x // 2
      uh, uw = h // 2, w // 2
      if uy + uh > U.shape[0] or ux + uw > U.shape[1]:
        raise ValueError("UV block out of bounds")
      c1 = U[uy:uy+uh, ux:ux+uw]
      c2 = V[uy:uy+uh, ux:ux+uw]
    elif self.format == '444':
      if U is None or V is None:
        raise ValueError("U/V components missing for 444 format")
      if y + h > self.height or x + w > self.width:
        raise ValueError("UV block out of bounds")
      c1 = U[y:y+h, x:x+w]
      c2 = V[y:y+h, x:x+w]
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
    dim = 8
    print("VIDEO: %s frame = %d dim = %d x %d %d bits format = %s md5 = %s dtype = " %
        (name, self.num_frames(), self.width, self.height, self.bits, self.format, self.md5()), self.frames[0][0].dtype)
    sys.stdout.flush()
    for f in range(self.num_frames()):

      print("%-10s j =   : " % ' ', end=' ')
      for j in range(min(dim, self.width)):
        print(f'{j:6d}', end=' ')
      print(end='\n')    
      for i in range(min(dim, self.height)):
        print("%-10s i = %4d: " % (' ' if j != 0 else ('F%04d' % f), i), end=' ') 
        for j in range(min(dim, self.width)):
          print(f'{self.frames[f][0][i][j]:6.2f}', end=' ')

        if self.frames[f][1] is not None:
          print("  ", end=' ') 
          for j in range(min(dim, self.width)):
            print(f'{self.frames[f][1][i][j]:6.2f}', end=' ')
        if self.frames[f][2] is not None:
          print("  ", end=' ') 
          for j in range(min(dim, self.width)):
            print(f'{self.frames[f][2][i][j]:6.2f}', end=' ')
        print(end='\n')

  #######################################################################################################

  def convert_400_to_420(self):
    if self.format != '400':
      raise ValueError("convert_400_to_420() can only be called on videos with format '400'")
    type = np.uint8 if self.bits <= 8 else np.uint16 if self.bits <= 16 else np.float32
    new_frames = []
    for (Y, _, _) in self.frames:
      U = np.zeros((self.height // 2, self.width // 2), dtype=type)
      V = np.zeros((self.height // 2, self.width // 2), dtype=type)
      new_frames.append((Y.copy(), U, V))
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

  def mosaic(self, block_size=16):
    for frame_index, (Y, U, V) in enumerate(self.frames):
      if self.format == '400':
        self.frames[frame_index] = (self.__mosaic(Y, block_size), None, None)
      else:
        self.frames[frame_index] = (self.__mosaic(Y, block_size), self.__mosaic(U, block_size),
                      self.__mosaic(V, block_size))

  #######################################################################################################

  def __mosaic(self, component, block_size):
    for i in range(0, component.shape[0], block_size):
      for j in range(0, component.shape[1], block_size):
        component[i:i + block_size, j:j + block_size] = np.random.randint(1 << self.bits, size=(1))
    return component

  #######################################################################################################

  def md5(self):
    md5_hash = hashlib.md5()
    for Y, U, V in self.frames:
      md5_hash.update(Y.tobytes())
      if U is not None:
        md5_hash.update(U.tobytes())
      if V is not None:
        md5_hash.update(V.tobytes())
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

  def __write_frame(self, file, Y, U=None, V=None):
    if self.format == '400':
      if U is not None or V is not None:
        raise ValueError("YUV400 format does not have U or V components")
      # Y = np.zeros(( self.width, self.height ), dtype=Y.dtype)
      file.write(Y.tobytes())
    else:
      file.write(Y.tobytes())
      if U is None:
        if self.format == '420':
          U = np.zeros((self.height // 2, self.width // 2), dtype=Y.dtype)  # + (1<<(self.bits-1))
        elif self.format == '444':
          U = np.zeros((self.height, self.width), dtype=Y.dtype)
      file.write(U.tobytes())
      if V is None:
        if self.format == '420':
          V = np.zeros((self.height // 2, self.width // 2), dtype=Y.dtype)  # + (1<<(self.bits-1))
        elif self.format == '444':
          V = np.zeros((self.height, self.width), dtype=Y.dtype)
      file.write(V.tobytes())

  #######################################################################################################

  def write(self, directory='', path='', suffix='', verbose=False):    
    filename = self.__create_yuv_filename(path, suffix)
    if directory != '':
      filename = to_bash_path(os.path.join(directory, filename))
    file = open(filename, 'wb')
    for Y, U, V in self.frames:
      self.__write_frame(file, Y, U, V)
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
    numBytes = 1 if self.bits <= 8 else 2
    if self.format == '420':
      return numBytes * self.height * self.width * 3 // 2
    elif self.format == '444':
      return numBytes * self.height * self.width * 3
    elif self.format == '400':
      return numBytes * self.height * self.width
    else:
      raise ValueError("Unsupported YUV format")

  #######################################################################################################

  def __unpack_frame(self, data):
    size = self.width * self.height * (1 if self.bits <= 8 else 2)
    type = np.uint8 if self.bits <= 8 else np.uint16
    if self.format == '400':
      Y = np.frombuffer(data, dtype=type).reshape((self.height, self.width))
      return (Y, None, None)
    elif self.format == '420':
      Y = np.frombuffer(data[:size], dtype=type).reshape((self.height, self.width))
      U = np.frombuffer(data[size:size * 5 // 4], dtype=type).reshape((self.height // 2, self.width // 2))
      V = np.frombuffer(data[size * 5 // 4:], dtype=type).reshape((self.height // 2, self.width // 2))
      return (Y, U, V)
    elif self.format == '444':
      Y = np.frombuffer(data[:size], dtype=type).reshape((self.height, self.width))
      U = np.frombuffer(data[size:size * 2], dtype=type).reshape((self.height, self.width))
      V = np.frombuffer(data[size * 2:], dtype=type).reshape((self.height, self.width))
      return (Y, U, V)

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