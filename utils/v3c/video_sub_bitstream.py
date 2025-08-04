from utils.bitstream import Bitstream

#######################################################################################################
################################### Video sub-bitstream ###############################################
#######################################################################################################

class VideoSubBitstream:
  def __init__(self):
    pass

  #######################################################################################################

  def __get_end_of_nalu_position(self, data: bytearray, start_index: int) -> int:
    size = len(data)
    if size < start_index + 4:
      print("get_end_of_nalu_position: size < start_index + 4 => return size = %d " % size)
      return size
    for i in range(start_index, size - 4):
      if (data[i] == 0x00 and data[i+1] == 0x00 and (data[i+2] == 0x01 or (data[i+2] == 0x00 and data[i+3] == 0x01))):
        print("get_end_of_nalu_position: return i = %d " % i)
        return i
    print("get_end_of_nalu_position: Not found: return size = %d " % size)
    return size

  #######################################################################################################

  def __byte_stream_to_sample_stream( self, data: bytearray, precision = 4, emulation_prevention_bytes = False ) -> None:    
    start_index = 0
    data_len    = len(data)
    new_data    = bytearray()
    while start_index < data_len:
      size_start_code = 4 if data[start_index + 2] == 0x00 else 3
      end_index = self.__get_end_of_nalu_position( data, start_index + size_start_code)
      print("Write end index = %8d  start_index = %8d size_start_code = %2d " % ( end_index, start_index, size_start_code)  )
      header_index = len(new_data)
      new_data.extend(b'\x00' * precision)
      if emulation_prevention_bytes:
        zero_count = 0
        for i in range(start_index + size_start_code, end_index):
          byte = data[i]
          if zero_count == 3 and byte <= 3:
            zero_count = 0
          else:
            zero_count = zero_count + 1 if byte == 0 else 0
            new_data.append(byte)
      else:
        new_data.extend(data[start_index + size_start_code:end_index])

      nalu_size = len(new_data) - (header_index + precision)
      print("Write nalu size = %d" % nalu_size)
      for i in range(precision):
        shift = 8 * (precision - (i + 1))
        new_data[header_index + i] = (nalu_size >> shift) & 0xFF
      start_index = end_index
    data = new_data

  #######################################################################################################

  def __sample_stream_to_byte_stream( self, data: bytearray, is_avc = False, is_vvc  = False, precision = 4, emulation_prevention_bytes = False , change_start_code_size = True ) -> None:
    size_start_code = 4
    start_index     = 0
    end_index       = 0
    data_len        = len(data)
    new_data        = bytearray()
    new_frame       = True
    print("Precision   = %d " % precision)
    print("start_index = %d " % start_index)
    while end_index < data_len:
      nalu_size = 0
      for i in range(precision):
        nalu_size = (nalu_size << 8) | data[start_index + i]
      print("Read  nalu size = %d " % nalu_size)

      end_index = start_index + precision + nalu_size
      new_data.extend(b'\x00' * (size_start_code - 1))
      new_data.append(0x01)
      if emulation_prevention_bytes:
        zero_count = 0
        for i in range(start_index + precision, end_index):
          b = data[i]
          if zero_count == 3 and b <= 0x03:
            new_data.append(0x03)
            zero_count = 0
          zero_count = zero_count + 1 if b == 0x00 else 0
          new_data.append(b)
      else:
        new_data.extend(data[start_index + precision:end_index])
      start_index = end_index
      if (start_index + precision) < data_len:
        nalu_type = 0
        use_long  = False
        new_frame = False
        if is_avc:
          use_long = True
        elif is_vvc:
          b = data[start_index + precision + 1]
          nalu_type = (b & 0xF8) >> 3
          use_long = new_frame or (12 <= nalu_type < 20)
          if nalu_type < 12:
            new_frame = True
        else:
          b = data[start_index + precision]
          nalu_type = (b & 0x7E) >> 1
          use_long = new_frame or (32 <= nalu_type < 41)
          if nalu_type < 12:
            new_frame = True
        size_start_code = 4 if use_long else 3
      data = new_data

  #######################################################################################################

  def write(self, bitstream, data: bytearray, convert = False ):
      if convert:
        self.__byte_stream_to_sample_stream( data )
      bitstream.write_buffer( data )

  #######################################################################################################

  def read(self, bitstream, size, convert = False  ):
      data = bitstream.read_buffer( size )
      if convert:
        self.__sample_stream_to_byte_stream( data )
      return data

#######################################################################################################