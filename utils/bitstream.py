import struct
import hashlib
from bitarray import bitarray
import numpy as np 
import inspect
import re

#######################################################################################################

class Bitstream:
  
  #######################################################################################################

  def __init__(self, data: bytes = b"", bitstream_log=False):
    self.bits = bitarray(endian="big")
    self.bits.frombytes(data)
    self.bit_pos = 0  
    self.bitstream_log = bool(bitstream_log)
  
  #######################################################################################################

  def load(self, path: str):
    with open(path, "rb") as f:
      data = f.read()
      self.bits = bitarray(endian="big")
      self.bits.frombytes(data)
      self.bit_pos = 0  
  
  #######################################################################################################

  def save(self, path: str):
    with open(path, "wb") as f:
      f.write(self.bits.tobytes())
  
  #######################################################################################################

  def clear(self):
    self.bits.clear()
    self.bit_pos = 0

  def get_size_bytes(self):
    return len(self.bits) // 8

  def get_size_bits(self):
    return len(self.bits) 

  def get_size_rest(self):
    return ( len( self.bits ) - self.bit_pos ) // 8  
    
  def more_data(self):
    return self.bit_pos < len(self.bits)

  def more_rbsp_data(self):
    if self.bit_pos >= len(self.bits):
      return False  
    for i in range(self.bit_pos, len(self.bits)):
      if self.bits[i] == 1:
        for j in range(i + 1, ((i + 8) // 8) * 8):
          if j < len(self.bits) and self.bits[j] != 0:
            return True  
        return False 
      elif self.bits[i] != 0:
        return True  
    return False

  def get_bytes(self) -> bytes:
    return self.bits.tobytes()

  def from_bytes(self, data: bytes):
    self.bits = bitarray(endian="big")
    self.bits.frombytes(data)
    self.bit_pos = 0

  def peek_byte_at(self, index: int) -> int:
    start_bit = index * 8
    return int(self.bits[start_bit:start_bit + 8].to01(), 2)

  def md5sum(self) -> str:
    return hashlib.md5(self.bits.tobytes()).hexdigest()
  
  #######################################################################################################
  # Copy 

  def copy_from(self, other: "Bitstream", start: int, size: int):
    bitstream_log = self.bitstream_log
    if self.bitstream_log:       
      self.bitstream_log = False
    data = other.bits.tobytes()
    for i in range( start, start + size):
        self.write_bits( data[i], 8 )
    if bitstream_log:
      print("copy bitstream size = %d " % size )
      self.bitstream_log = bitstream_log

  def copy_to(self, other: "Bitstream", size: int):    
    bitstream_log = self.bitstream_log
    if self.bitstream_log:       
      self.bitstream_log = False
    if bitstream_log:
      print("copy bitstream size = %d / %d " % ( size, len(other.bits) ) )
    data = bytearray(size)
    for i in range(size):
        data[i] = self.read_bits(8)
    other.from_bytes(bytes(data))
    if bitstream_log:
      print("copy bitstream size = %d / %d " % ( size, len(other.bits) ) )
      self.bitstream_log = bitstream_log
  
  #######################################################################################################
  # Alignemnts

  def byte_aligned(self):
    return self.bit_pos % 8 == 0
    
  #######################################################################################################

  def write_length_alignment(self):
    zero = 0
    while not self.byte_aligned():
      self.write_bits(0, 1);                                  # f(1): equal to 0

  def read_length_alignment(self):
    while not self.byte_aligned():
      self.write_bits(0, 1);                                  # f(1): equal to 0
      
  #######################################################################################################

  def write_byte_alignment(self):
    one  = 1
    zero = 0
    self.write_bits(one, 1);                                  # f(1): equal to 1
    while not self.byte_aligned():                          
      self.write_bits(zero, 1);                               # f(1): equal to 0

  def read_byte_alignment(self):
    one = self.read_bits(1);                                  # f(1): equal to 1
    while not self.byte_aligned():                          
      zero = self.read_bits(1);                               # f(1): equal to 0

  #######################################################################################################

  def write_rbsp_trailing_bits(self): 
    one  = 1
    zero = 0
    self.write_bits(one, 1)                                   # f(1): equal to 1
    while not self.byte_aligned(): 
      self.write_bits(zero, 1)                                # f(1): equal to 0

  def read_rbsp_trailing_bits(self): 
    one = self.read_bits(1)                                   # f(1): equal to 1
    while not self.byte_aligned(): 
      zero = self.read_bits(1)                                # f(1): equal to 0
  
  #######################################################################################################
  # Log

  def __infer_name_from_write(self) -> str:
    try:
      frame = inspect.currentframe().f_back.f_back
      src = inspect.getframeinfo(frame).code_context[0].strip()
      m = re.search(r"\.write_(?:bits|uvlc|float|string)\(\s*([^,\)]+)", src)
      if m:
        raw = m.group(1).strip()
        return re.sub(r'^(?:self|other|gof)\.', '', raw)
    except Exception:
        pass
    return ''

  def __infer_name_from_read(self) -> str:
    try:
      frame = inspect.currentframe().f_back.f_back
      src = inspect.getframeinfo(frame).code_context[0].strip()
      m = re.search(r"([\w\.]+)\s*=\s*\w+\.(?:read_bits|read_float|read_uvlc|read_string)\(", src)

      if m:
        raw = m.group(1).strip()
        return re.sub(r'^(?:self|other|gof)\.', '', raw)
    except Exception:
      pass
    return ''

  def __log_bits(self, name, value, n ):
      print("[%8d:%1d] CodU[%2d] %-30s = %12d " % (self.bit_pos / 8, self.bit_pos % 8, n, name, value ) )

  def __log_string(self, name, value ):
      print("[%8d:%1d] CodStr   %-30s = %-s " % ( self.bit_pos / 8, self.bit_pos % 8, name, value ) )

  def __log_float(self, name, value ):
      print("[%8d:%1d] CodFloat %-30s = %12f " % ( self.bit_pos / 8, self.bit_pos % 8, name, value ) )

  def __log_uvlc(self, name, value ):
      print("[%8d:%1d] CodUvlc  %-30s = %12d " % ( self.bit_pos / 8, self.bit_pos % 8, name, value ) )

  #######################################################################################################
  # Bits

  def write_bits(self, value: int, n: int ):
    bits_to_write = bin(value)[2:].zfill(n)
    for b in bits_to_write:
      if self.bit_pos >= len(self.bits):
        self.bits.append(0)
      self.bits[self.bit_pos] = int(b)
      self.bit_pos += 1
    if self.bitstream_log: 
      self.__log_bits( self.__infer_name_from_write(), value, n)

  def read_bits(self, n: int ) -> int:
    if self.bit_pos + n > len(self.bits):
      raise EOFError("End of stream: bitstream len = %d bit_pos = %d n = %d " % ( len(self.bits), self.bit_pos, n  ))
    value = 0
    for _ in range(n):
      value = (value << 1) | self.bits[self.bit_pos]
      self.bit_pos += 1     
    if self.bitstream_log: 
      self.__log_bits( self.__infer_name_from_read(), value, n)
    return value

  #######################################################################################################
  # String

  def write_string(self, string: str):
    bitstream_log = self.bitstream_log
    if self.bitstream_log:       
      self.bitstream_log = False
    while not self.byte_aligned():
      self.write_bits(0, 1)
    for c in string:
      self.write_bits(ord(c), 8)
    self.write_bits(0, 8) 
    if bitstream_log: 
      self.bitstream_log = bitstream_log
      self.__log_string( self.__infer_name_from_write(), string)

  def read_string(self) -> str:
    bitstream_log = self.bitstream_log
    if self.bitstream_log:       
      self.bitstream_log = False
    while not self.byte_aligned():
      self.read_bits(1)
    result = []
    char = self.read_bits(8)
    while char != 0:
      result.append(chr(char))
      char = self.read_bits(8)
    string = ''.join(result)
    if bitstream_log: 
      self.bitstream_log = bitstream_log
      self.__log_string( self.__infer_name_from_read(), string)
    return string

  #######################################################################################################
  # Float

  def write_float(self, value: float):
    bitstream_log = self.bitstream_log
    if self.bitstream_log:       
      self.bitstream_log = False
    packed = struct.pack(">f", value)
    for b in packed:
      self.write_bits(b,8)
    if bitstream_log: 
      self.bitstream_log = bitstream_log
      self.__log_float( self.__infer_name_from_write(), value)

  def read_float(self) -> float:
    bitstream_log = self.bitstream_log
    if self.bitstream_log:       
      self.bitstream_log = False
    bytes_ = bytes([self.read_bits(8) for _ in range(4)])
    value = struct.unpack(">f", bytes_)[0]
    if bitstream_log: 
      self.bitstream_log = bitstream_log
      self.__log_float( self.__infer_name_from_read(), value)
    return value

  #######################################################################################################
  # Double 

  def write_double(self, value: float):
    packed = struct.pack(">d", value)
    for b in packed:
      self.write_bits(b,8)

  def read_double(self) -> float:
    bytes_ = bytes([self.read_bits(8) for _ in range(8)])
    return struct.unpack(">d", bytes_)[0]

  #######################################################################################################
  # UVLC (Unsigned Variable Length Code)

  def write_uvlc(self, value: int):
    bitstream_log = self.bitstream_log
    if self.bitstream_log:       
      self.bitstream_log = False
    code = int(value)
    code += 1
    length = 1
    temp = code
    while temp != 1:
      temp >>= 1
      length += 2
    self.write_bits(0, length >> 1)
    self.write_bits(code, (length + 1) >> 1)
    if bitstream_log: 
      self.bitstream_log = bitstream_log
      self.__log_uvlc( self.__infer_name_from_write(), value)

  def read_uvlc(self) -> int:
    bitstream_log = self.bitstream_log
    if self.bitstream_log:       
      self.bitstream_log = False
    value = 0
    code = self.read_bits(1)
    if code == 0:
      length = 0
      while code == 0:
        code = self.read_bits(1)
        length += 1
      value = self.read_bits(length)
      value += (1 << length) - 1
    if bitstream_log: 
      self.bitstream_log = bitstream_log
      self.__log_uvlc( self.__infer_name_from_read(), value)
    return value

  #######################################################################################################
  # SVLC (Signed Variable Length Code)

  def write_svlc(self, value: int):
    code = int(value)
    mapped = (-code << 1) if code <= 0 else (code << 1) - 1 
    self.write_uvlc(mapped)

  def read_svlc(self) -> int:
    bits = self.read_uvlc()
    return (bits >> 1) + 1 if (bits & 1) else -(bits >> 1) 

  #######################################################################################################
  # Buffer witht size

  def write_buffer_with_size(self, buffer):
      if not self.byte_aligned():
          self.write_bits(0, 8 - (self.bit_pos % 8))
      self.write_bits(len(buffer), 32)   
      ba = bitarray(endian="big")
      ba.frombytes(bytes(buffer))
      bit_start = self.bit_pos
      bit_end = bit_start + len(ba)
      if bit_end > len(self.bits):
          self.bits.extend([0] * (bit_end - len(self.bits)))
      self.bits[bit_start:bit_end] = ba
      self.bit_pos = bit_end

  def read_buffer_with_size(self):
    if not self.byte_aligned():
      self.read_bits(8 - (self.bit_pos % 8))  
    size = self.read_bits(32)  
    byte_pos = self.bit_pos // 8
    end_byte_pos = byte_pos + size
    if end_byte_pos > len(self.bits) // 8:
      raise EOFError("Trying to read beyond the stream size.")
    raw_bytes = self.bits.tobytes()[byte_pos:end_byte_pos]
    self.bit_pos += size * 8
    return np.frombuffer(raw_bytes, dtype=np.uint8) 

  #######################################################################################################
  # Buffer 

  def write_buffer(self, buffer):
    ba = bitarray(endian="big")
    ba.frombytes(bytes(buffer))
    bit_start = self.bit_pos
    bit_end = bit_start + len(ba)
    if bit_end > len(self.bits):
        self.bits.extend([0] * (bit_end - len(self.bits)))
    self.bits[bit_start:bit_end] = ba
    self.bit_pos = bit_end

  def read_buffer(self, size ):
    byte_pos = self.bit_pos // 8
    end_byte_pos = byte_pos + size
    if end_byte_pos > len(self.bits) // 8:
      raise EOFError("Trying to read beyond the stream size.")
    raw_bytes = self.bits.tobytes()[byte_pos:end_byte_pos]
    self.bit_pos += size * 8
    return np.frombuffer(raw_bytes, dtype=np.uint8) 

    #######################################################################################################