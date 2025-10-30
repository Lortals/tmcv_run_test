
import os
import subprocess
import platform
import json
from pathlib import Path
import shutil
import ffmpeg
from ffmpeg._run import run_async
from utils.common import write_bin, read_bin, create_yuv_filename, to_bash_path, fixpath, reformat
from utils.v3c.type import Format 
if shutil.which("ffmpeg") is None:
  print("FFmpeg is not found please update path.")
  exit(1)


#######################################################################################################

def get_binary_path(codec, mode ):
  json_path = (Path(__file__).resolve().parent.parent  / "dependencies/binary_path.json").resolve()
  if not json_path.exists():
    raise FileNotFoundError(f"JSON file not found: {json_path}")
  with open(json_path, "r", encoding="utf-8") as f:
    binaries = json.load(f)
  if codec not in binaries:
    raise ValueError(f"Unknown codec '{codec}'. Available: {', '.join(binaries.keys())}")      
  if mode not in binaries[codec]:
    raise ValueError(f"Mode must be 'encoder' or 'decoder', not '{mode}'")  
  path = (Path(__file__).resolve().parent.parent  / binaries[codec][mode]).resolve()
  if not os.path.exists( fixpath( path ) ):
    print('Error: codec path is not correct: codec = %s mode = %s: %s ' % ( codec, mode, path))
    print('')
    print('   Please use the script: ./scripts/install_dependencies.sh, to install software dependencies ')
    print('')
    exit()
  return path
 
#######################################################################################################

def encode_video( type, name, index, output_dir, video, codec, config, qp, dqp, verbose=False): 
  if codec == 'x264' or codec == 'x265':
    bin = encode_ffmpeg(name=name, index=index, output_dir=output_dir, video=video, codec=codec, config=config, qp=qp, verbose=verbose)
  elif codec == 'hm' or codec == 'hmr' or codec == 'hmd':
    bin = encode_hm(name=name, index=index, output_dir=output_dir, video=video, codec=codec, config=config, qp=qp, dqp=dqp, verbose=verbose)
  elif codec == 'vtm' or codec == 'vtr':
    bin = encode_vtm(name=name, index=index, output_dir=output_dir, video=video, codec=codec, config=config, qp=qp, verbose=verbose)
  else:
    raise ValueError(f"encode function not support codec: {codec}")
  return type, bin

#######################################################################################################

def decode_video(name, index, output_dir, bitstream, width, height, fps, bits, format, video, codec, verbose=False):
  if codec == 'x264' or codec == 'x265':
    decode_ffmpeg(name=name, index=index, output_dir=output_dir, bitstream=bitstream, width=width, height=height, 
                  fps=fps, bits=bits, format=format, video=video, codec=codec, verbose=verbose)
  elif codec == 'hm' or codec == 'hmr' or codec == 'hmd':
    decode_hm(name=name, index=index, output_dir=output_dir, bitstream=bitstream, width=width, height=height, 
              fps=fps, bits=bits, format=format, video=video, codec=codec, verbose=verbose)
  elif codec == 'vtm' or codec == 'vtr':
    decode_vtm(name=name, index=index, output_dir=output_dir, bitstream=bitstream, width=width, height=height, 
               fps=fps, bits=bits, format=format, video=video, codec=codec, verbose=verbose)
  else:
    raise ValueError(f"encode function not support codec: {codec}")
        
#######################################################################################################
###################################### HM #############################################################
#######################################################################################################

def encode_hm(name, index, output_dir, video, codec, config, qp, dqp, verbose=False):   
  path   = get_binary_path(codec, 'encoder' )
  name   = "%02d_%s_enc" % (index, name)
  if video.format == '400':
    video.convert_400_to_420()    
  input  = video.write( directory=output_dir, path=name, verbose=verbose )
  output = to_bash_path( os.path.join( output_dir, name + '.hm' ))
  log_path = os.path.join(output_dir, name + '.log')
  if verbose:
    print("ENC HM    : video %s => %d x %d bits = %d format = %s comp = %d " % 
      ( input, video.width, video.height, video.bits, video.format, video.get_num_comp() ))
  cmd = [ fixpath( path ) ]
  for cfg in config:
    cfg_path = to_bash_path( str( (Path(__file__).resolve().parent.parent  / cfg ).resolve() ) )
    cmd += [ '-c', cfg_path ]
    print("cfg_path = %s " % cfg_path )
  cmd += [
    '--InputFile='             + input,
    '--BitstreamFile='         + output,
    '--InputChromaFormat='     + video.format, 
    '--FramesToBeEncoded='     + str( video.num_frames() ),
    '--FrameRate=30',   
    '--SourceWidth='           + str( video.width ),
    '--SourceHeight='          + str( video.height ),
    '--InputBitDepth='         + str( max( video.bits, 8 ) ),
    '--InternalBitDepth='      + str( max( video.bits, 8 ) ),
    '--InternalBitDepthC='     + str( max( video.bits, 8 ) ),
    '--OutputBitDepth='        + str( max( video.bits, 8 ) ),
    '--QP='                    + str( qp ),
    '--ReconFile='             + 'NUL' if platform.system() == 'Windows' else '/dev/null',
    '--ConformanceWindowMode=1',
    '--ExtendedPrecision=0',
    '--IntraReferenceSmoothing=1',
    '--SEIDecodedPictureHash=1'
  ]  
  print(f"dqp file = {dqp}")
  if os.path.exists(dqp):
    cmd.append('--dQPFile=' + to_bash_path(dqp))
  # cmd.append(  '--ReconFile=' + recName )  
  if verbose:
    print( reformat(  ' '.join( cmd ) )  )
  with open(log_path, 'w', encoding='utf-8') as logfile:
    result = subprocess.run(cmd, stdout=logfile, stderr=subprocess.STDOUT, text=True, check=True)
    if result.returncode != 0:
      print("Command failed: ", reformat(  ' '.join( cmd ) ) ) 
      raise RuntimeError("Video encoding failed")           
    with open(log_path, 'r', encoding='utf-8') as logfile:
      for line in logfile:
        print(line.rstrip())
    print(f"ENC HM    : encoded: {input} in {output}")
  bin = read_bin(output)
  # cleanup
  # os.remove(input)
  # os.remove(output)
  return bin

#######################################################################################################

def decode_hm(name, index, output_dir, bitstream, width, height, fps, bits, format, video, codec, verbose=False):
  path   = get_binary_path(codec, 'decoder' )
  name   = "%02d_%s_dec" % (index, name)
  input  = to_bash_path( os.path.join( output_dir, name + '.hm' ))
  output = to_bash_path( os.path.join(output_dir, create_yuv_filename(name, "", width, height, fps, bits, "444" if format == Format.YUV444 else "420") ) )
  log_path = os.path.join(output_dir, name + '.log')
  write_bin( input, bitstream )
  cmd = [
     fixpath( path ),
    '--BitstreamFile='  + input,
    '--ReconFile='      + output,    
    '--OutputBitDepth=' + str( max( bits, 8 ) )
  ]
  if verbose:
    print( ' '.join( cmd ) )

  with open(log_path, 'w', encoding='utf-8') as logfile:
    result = subprocess.run(cmd, stdout=logfile, stderr=subprocess.STDOUT, text=True, check=True)
    if result.returncode != 0:
      print("Command failed: ", reformat(  ' '.join( cmd ) ) ) 
      raise RuntimeError("Video decoding failed")           
  if verbose:
    with open(log_path, 'r', encoding='utf-8') as logfile:
      for line in logfile:
        print(line.rstrip())
  video.read( output, verbose )
  if format == Format.YUV400:
    video.convert_420_to_400()
  if verbose:
    print(f"DEC HM    : decoded: {input} in {output}")
  # cleanup
  # os.remove(input)
  # os.remove(output)

#######################################################################################################
###################################### VTM ############################################################
#######################################################################################################

def encode_vtm(name, index, output_dir, video, codec, config, qp, verbose=False):   
  path   = get_binary_path(codec, 'encoder' )
  name   = "%02d_%s_enc" % (index, name)
  if video.format == '400':
    video.convert_400_to_420()
  input    = video.write( directory=output_dir, path=name, verbose=verbose )
  output   = to_bash_path( os.path.join( output_dir, name + '.vtm' ))    
  log_path = os.path.join(output_dir, name + '.log')
  if verbose:
    print("ENC VTM   : video %s => %d x %d bits = %d format = %s comp = %d " % 
      ( input, video.width, video.height, video.bits, video.format, video.get_num_comp() ))
  cmd = [ fixpath( path ) ]
  for cfg in config:
    cfg_path = to_bash_path( str( (Path(__file__).resolve().parent.parent / cfg ).resolve() ) )
    cmd += [ '-c', cfg_path ]
    if verbose:
      print("cfg_path = %s " % cfg_path )
  cmd += [
      '--InputFile='             + input,
      '--BitstreamFile='         + output,
      '--InputChromaFormat='     + video.format, 
      '--FramesToBeEncoded='     + str( video.num_frames() ),
      '--FrameRate=10',   
      '--SourceWidth='           + str( video.width ),
      '--SourceHeight='          + str( video.height ),
      '--InputBitDepth='         + str( max( video.bits, 8 ) ),
      '--InternalBitDepth='      + str( max( video.bits, 8 ) ),
      '--OutputBitDepth='        + str( max( video.bits, 8 ) ),
      '--QP='                    + str( qp ),
      '--ConformanceWindowMode=1',
      "--TemporalSubsampleRatio=1" ]
  # cmd.append(  '--ReconFile=' + recName )
  if verbose:
    print( ' '.join( cmd ) )        
  with open(log_path, 'w', encoding='utf-8') as logfile:
    result = subprocess.run(cmd, stdout=logfile, stderr=subprocess.STDOUT, text=True, check=True)    
    if result.returncode != 0:
      print("Command failed: ", reformat(  ' '.join( cmd ) ) ) 
      raise RuntimeError("Video encoding failed")           
  if verbose:
    with open(log_path, 'r', encoding='utf-8') as logfile:
      for line in logfile:
        print(line.rstrip())
    print(f"ENC VTM   : encoded: {input} in {output}")
    return read_bin(output)

#######################################################################################################

def decode_vtm(name, index, output_dir, bitstream, width, height, fps, bits, format, video, codec, verbose=False):
  path   = get_binary_path(codec, 'decoder' )
  name   = "%02d_%s_dec" % (index, name)
  input  = to_bash_path( os.path.join( output_dir, name + '.vtm' ))
  output = to_bash_path( os.path.join(output_dir, create_yuv_filename(name, "", width, height, fps, bits, "444" if format == Format.YUV444 else "420")) ) 
  log_path = os.path.join(output_dir, name + '.log')
  write_bin( input, bitstream )
  cmd = [
      fixpath( path ),
      '--BitstreamFile='  + input,
      '--ReconFile='      + output,    
      '--OutputBitDepth=' + str( max( bits, 8 ) )
  ]
  if verbose:
    print( ' '.join( cmd ) )
  with open(log_path, 'w', encoding='utf-8') as logfile:
    result = subprocess.run(cmd, stdout=logfile, stderr=subprocess.STDOUT, text=True, check=True)    
    if result.returncode != 0:
      print("Command failed: ", reformat(  ' '.join( cmd ) ) ) 
      raise RuntimeError("Video encoding failed")           
  if verbose:
    with open(log_path, 'r', encoding='utf-8') as logfile:
      for line in logfile:
        print(line.rstrip())
    print(f"DEC VTM   : decoded: {input} in {output}")
  video.read( output, verbose )
  if format == Format.YUV400:
    video.convert_420_to_400()

#######################################################################################################
###################################### FFMPEG #########################################################
#######################################################################################################

def get_pix_fmt_ffmpeg( bits=0, format=Format.YUV420 ):
  formats = { Format.YUV400: { 8:  'gray8',   10: 'gray10le',    12: 'gray12le',    16: 'gray16le',    'default': 'gray16le'    },
              Format.YUV420: { 8:  'yuv420p', 10: 'yuv420p10le', 12: 'yuv420p12le', 16: 'yuv420p16le', 'default': 'yuv420p16le' },
              Format.YUV444: { 8:  'yuv444p', 10: 'yuv444p10le', 12: 'yuv444p12le', 16: 'yuv444p16le', 'default': 'yuv444p16le' } }  
  fmt_group = formats.get(format, formats[Format.YUV420])
  return fmt_group.get(bits, fmt_group['default'])

#######################################################################################################

def encode_ffmpeg(name, index, output_dir, video, codec, config, qp, verbose=False): 
  name    = "%02d_%s_enc" % (index, name)
  input   = video.write( directory=output_dir, path=name,  verbose=verbose )
  output  = to_bash_path( os.path.join( output_dir, name + '.mp4' ))
  if verbose:
    print("ENC FFMPEG: video %s => bits = %d format = %s comp = %d " % ( input, video.bits, video.format, video.get_num_comp() ))
  pix_fmt = get_pix_fmt_ffmpeg(video.bits, video.get_num_comp())    
  if verbose:
    print(f"ENC FFMPEG: Encode : {input} in {output} format = %s %s " %( video.format, pix_fmt ))       
    try:
      if codec == 'x264':
        if qp == 0:
          if verbose:
            print("Encoding lossless x264")
          ( ffmpeg.input(input, format='rawvideo', pix_fmt=pix_fmt, s=f'{video.width}x{video.height}', framerate=video.fps)
                  .output(output, vcodec='libx264', crf=0, preset='veryslow')  
                  .global_args('-an').overwrite_output().run(capture_stdout=True, capture_stderr=True) )                  
        else:
          if verbose:
            print("Encoding lossy x264")
          ( ffmpeg.input(input, format='rawvideo', pix_fmt=pix_fmt, s=f'{video.width}x{video.height}', framerate=video.fps)
                  .output(output, vcodec='libx264', qp=qp, preset='veryslow')  
                  .global_args('-an').overwrite_output().run(capture_stdout=True, capture_stderr=True) )   
      elif codec == 'x265':   
        if qp == 0:
          if verbose:
            print("Encoding lossless x265")
          ( ffmpeg.input(input, format='rawvideo', pix_fmt=pix_fmt, s=f'{video.width}x{video.height}', framerate=video.fps)
                  .output(output, vcodec='libx265', qp=qp, preset='veryslow', **{'x265-params': 'lossless=1'})  
                  .global_args('-an').overwrite_output().run(capture_stdout=True, capture_stderr=True) )
        else:
          if verbose:
            print("Encoding lossy x265")
          ( ffmpeg.input(input, format='rawvideo', pix_fmt=pix_fmt, s=f'{video.width}x{video.height}', framerate=video.fps)
                  .output(output, vcodec='libx265', qp=qp, preset='veryslow')  
                  .global_args('-an').overwrite_output().run(capture_stdout=True, capture_stderr=True) )
    except ffmpeg.Error as e:
      print("FFmpeg stderr output:")
      print(e.stderr.decode())
      raise
  if verbose:
    print(f"ENC FFMPEG: encoded: {input} in {output}") 
  return read_bin( output )

#######################################################################################################

def decode_ffmpeg(name, index, output_dir, bitstream, width, height, fps, bits, format, video, codec, verbose=False):
  name  = "%02d_%s_dec" % (index, name)
  input = to_bash_path( os.path.join( output_dir, name + '.mp4' ))
  write_bin( input, bitstream )   
  num_comp = 1 if format == '400' else 3  
  pix_fmt = get_pix_fmt_ffmpeg( bits, num_comp )
  output  = to_bash_path( os.path.join(output_dir, create_yuv_filename( name, "", width, height, fps, bits, format.video_name()  ) ) )
  try:
    (
      ffmpeg
        .input(input)
        .output(output, format='rawvideo', pix_fmt=pix_fmt)
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )
  except ffmpeg.Error as e:
    print("FFmpeg stderr output:")
    print(e.stderr.decode())
    raise    
  video.read( output, verbose )
  if verbose:
    print(f"DEC FFMPEG: decoded: {input} in {output}")

#######################################################################################################