import os
import sys
import argparse
import time
import concurrent.futures
from utils.common           import handler_ctrl_c, remove_extension, print_args, create_output_dir
from utils.group_of_frames  import GroupOfFrames
from utils.video_codec      import decode_video
from utils.v3c.type         import Format

#######################################################################################################

# Parse input arguments
def parse_args():
  global parser 
  parser = argparse.ArgumentParser(
    description='Decode 3DGS point cloud from v3C bitstream',
    epilog='Example: \n' + '  ./' + os.path.basename(__file__) + ' -b file.v3c -d %04d_dec.ply \n',
    prog=os.path.basename(__file__),
    formatter_class=argparse.RawTextHelpFormatter)
  main = parser.add_argument_group('Input')    
  main.add_argument('-b,', '--bin',         help='Input bin path',                    default='enc.v3c',      type=str )
      
  main = parser.add_argument_group('Output')
  main.add_argument('-d,', '--dec',         help='Output ply path',                   default='',             type=str )
  main.add_argument('--ascii',              help='Ascii output format',               default=False,          action='store_true')
  main.add_argument('--first_frame',        help='Index of the first frame',          default=0,              type=int )
  
  main = parser.add_argument_group('Plot and traces')        
  main.add_argument('-v','--verbose',       help='Verbose',                           default=False,          action='store_true')
  main.add_argument('--bitstream_log',      help='Bitstream write and read logs',     default=False,          action='store_true')

  try:
    args = parser.parse_args()
  except:
    sys.exit(0)    
  if args.verbose:
    print_args(parser, args)
  return args

#######################################################################################################

if __name__ == '__main__':

  # Initialize
  start_time = time.time() 
  handler_ctrl_c()
  args = parse_args()

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
                        num_comp   = 1 if video.format == Format.YUV400 else 3, 
                        video      = gof_dec.videos[key].video_uint, 
                        codec      = gof_dec.codecs[video.codec_id],
                        verbose    = args.verbose)
      for index, (key, video) in enumerate(gof_dec.videos.items())
    ]
    for future in concurrent.futures.as_completed(futures):
      future.result() 

  # Dequantize  
  if gof_dec.bit_depth_pos == 32 and gof_dec.bit_depth_att == 32:
    gof_dec.dequantize(verbose=args.verbose)
  else:
    gof_dec.restore_bitdepth(verbose=args.verbose)

  # Verbose
  if args.verbose:
    gof_dec.print( "dec" )
    print("num decoded frames  = %2d " % ( gof_dec.num_frames('dec') ) )

  # Decoder 
  for frame_index in range(gof_dec.num_frames('dec')):
    # Decode pointcloud
    dec = gof_dec.get_pointcloud( frame_index, args.verbose )

    # Save decoded pointcloud    
    dec.write(args.dec if args.dec != '' else ( remove_extension(args.bin) + '_%04d_dec.ply'), 
              args.first_frame + frame_index, ascii=args.ascii, verbose=args.verbose )

  # Stat
  gof_dec.stat.log()
  end_time = time.time() 
  elapsed = end_time - start_time
  print(f"Time: {elapsed:.4f} secondes")

#######################################################################################################