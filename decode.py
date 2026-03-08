import os
import sys
import argparse
import time
import concurrent.futures
from utils.common           import handler_ctrl_c, remove_extension, print_args, create_output_dir
from utils.group_of_frames  import GroupOfFrames
from utils.video_codec      import decode_video
from utils.v3c.type         import ColorStandard

#######################################################################################################

# Parse input arguments
def parse_args():
  parser = argparse.ArgumentParser(
    description='Decode 3DGS point cloud from v3C bitstream',
    epilog='Example: \n' + '  ./' + os.path.basename(__file__) + ' -b file.v3c -d %04d_dec.ply \n',
    prog=os.path.basename(__file__),
    formatter_class=argparse.RawTextHelpFormatter)
  main = parser.add_argument_group('Input')    
  main.add_argument('-b', '--bin',          help='Input bin path',                    default='enc.v3c',      type=str )
      
  main = parser.add_argument_group('Output')
  main.add_argument('-d', '--dec',          help='Output ply path',                   default='',             type=str )
  main.add_argument('--ascii',              help='Ascii output format',               default=False,          action='store_true')
  main.add_argument('--first_frame',        help='Index of the first frame',          default=0,              type=int )
  
  main = parser.add_argument_group('Plot and traces')        
  main.add_argument('-v','--verbose',       help='Verbose',                           default=False,          action='store_true')
  main.add_argument('--bitstream_log',      help='Bitstream write and read logs',     default=False,          action='store_true')

  try:
    args = parser.parse_args()
  except Exception as exc:
    raise RuntimeError("Argument parsing failed") from exc     
  if args.verbose:
    print_args(parser, args)
  return args 

#######################################################################################################

if __name__ == '__main__':

  # Initialize
  start_time = time.time() 
  handler_ctrl_c()
  args = parse_args()
  
  t_dec_geo = 0
  t_dec_attr = 0
  t_dec_vid = 0

  if not os.path.exists( args.bin ):  
    print("Error: %s not exists " % args.bin )
    exit()
  if args.dec != '':
    output_dir = create_output_dir( args.dec, verbose=args.verbose )
  else:
    output_dir = os.path.dirname(args.bin)

  # Read gof of frame data
  gof_dec = GroupOfFrames()
  gof_dec.read( args.bin, bitstream_log=bool(args.bitstream_log), verbose=args.verbose ) 

  # Decode video in parallel
  video_names = {}
  t0_vid = time.time()
  t_dec_geo_vid = 0
  t_dec_attr_vid = 0
  videos_list = list(gof_dec.videos.values()) # Keep order consistent
  
  with concurrent.futures.ThreadPoolExecutor() as executor:
    futures = [
      executor.submit(decode_video, 
                        name       = video.name(), 
                        index      = index, 
                        output_dir = output_dir, 
                        bitstream  = video.bitstream, 
                        width      = video.width, 
                        height     = video.height, 
                        fps        = gof_dec.fps, 
                        bits       = video.bitdepth, 
                        format     = video.format, 
                        video      = video.video_uint, 
                        codec      = gof_dec.codecs[video.codec_id],
                        verbose    = args.verbose)
      for index, video in enumerate(videos_list)
    ]
    for future in concurrent.futures.as_completed(futures):
      index, recon, elapsed = future.result()
      video = videos_list[index]
      
      # Accumulate video decoding time
      # Check if geometry or attribute video based on parameters
      params = getattr(video, 'list_params', [])
      # If list_params is empty (maybe not populated correctly?), check name/type?
      # Assuming list_params is populated.
      is_geometry = any(p in ['x','y','z','opacity'] or p.startswith('rot') or p.startswith('scale') for p in params)
      if is_geometry:
        t_dec_geo_vid += elapsed
      else:
        t_dec_attr_vid += elapsed
      
  t_dec_vid += time.time() - t0_vid

  # Upsample videos (when Format is YUV420)
  t0_attr = time.time()
  gof_dec.upsample(verbose=args.verbose)

  # Convert SH
  gof_dec.yuv2rgb(verbose=args.verbose)

  # Dequantize  
  gof_dec.dequantize(verbose=args.verbose)
  t_dec_attr += time.time() - t0_attr
  
  # Verbose
  if args.verbose:
    gof_dec.print( "dec" )
    print("num decoded frames  = %2d " % ( gof_dec.num_frames('dec') ) )

  # Decoder
  for frame_index in range(gof_dec.num_frames('dec')):
    # Get decoded pointcloud
    t0_geo = time.time()
    dec = gof_dec.get_pointcloud(frame_index, args.verbose)
    t_dec_geo += time.time() - t0_geo
    
    t0_attr = time.time()
    if gof_dec.sh_ac_transform_flag:
      # Load transformation metadata and reconstruct SH AC coefficients
      metadata = gof_dec.get_sh_ac_transform_metadata(frame_index, verbose=args.verbose)
      # Inverse transformation to SH AC coefficients
      dec.inv_trans_sh_ac(metadata, verbose=args.verbose)

    # Dec color conversion
    if gof_dec.src_sh_conversion != ColorStandard.NONE:
      dec.yuv2rgb(gof_dec.src_sh_conversion, verbose=args.verbose)

    # Quaternion denormalization
    if not 'rot_0' in [p for v in gof_dec.videos.values() for p in getattr(v, "list_params", None)]:
      dec.reconstruct_quat(verbose=args.verbose)
    t_dec_attr += time.time() - t0_attr

    # Save decoded pointcloud
    if args.verbose:
      dec.print("PC_dec", num = 1)

    dec.write(args.dec if args.dec != '' else (remove_extension(args.bin) + '_%04d_dec.ply'),
              args.first_frame + frame_index, ascii=args.ascii, verbose=args.verbose)

  # Stat
  gof_dec.stat.log()
  end_time = time.time() 
  elapsed = end_time - start_time
  print(f"Time: {elapsed:.4f} secondes")
  # Add video decoding time to geometry/attribute time
  t_dec_geo_total = t_dec_geo + t_dec_geo_vid
  t_dec_attr_total = t_dec_attr + t_dec_attr_vid
  print(f"DecT Geometry: {t_dec_geo_total:.4f}")
  print(f"DecT Attributes: {t_dec_attr_total:.4f}")
  print(f"DecT Video: {t_dec_vid:.4f}")

#######################################################################################################