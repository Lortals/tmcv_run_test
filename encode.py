import os
import sys
import argparse
import time
from collections import Counter
import concurrent.futures
from utils.common           import handler_ctrl_c, make_path, remove_extension, min_num_gaussian_in_gof, \
                                   to_bash_path, print_args, preprocess_args_with_config, create_output_dir                                   
from utils.pointcloud       import Pointcloud
from utils.group_of_frames  import GroupOfFrames
from utils.video_codec      import encode_video, decode_video
from utils.video            import Video
from utils.video_data       import VideoData
from utils.v3c.type         import Quantization, V3CUnitType, Format, Packing
from utils.plas             import sort, init_device

#######################################################################################################

# Parse input arguments
def parse_args():
  sys.argv = preprocess_args_with_config(sys.argv)
  global parser 
  def comma_separated_list(s):
    return s.split(',')
  parser = argparse.ArgumentParser(
    description='Encode 3DGS point cloud to v3C bitstream',
    epilog='Example: \n' + '  ./' + os.path.basename(__file__) + ' -i %04d.ply -n 1 -b test.bin -r %04d_rec.ply \n',
    prog=os.path.basename(__file__), formatter_class=argparse.RawTextHelpFormatter )
  main = parser.add_argument_group('Input')    
  main.add_argument('-c', '--config',       help='Path to config file')
  main.add_argument('-i,', '--input',       help='Input ply path',                    default='%06d.ply',     type=str )
  main.add_argument('-n','--num_frames',    help='Number of frames',                  default=1,              type=int )
  main.add_argument('--first_frame',        help='Index of the first frame',          default=0,              type=int )
  main.add_argument('--bit_depth_pos',      help='Bit depth of input position',       default=32,             type=int )
  main.add_argument('--bit_depth_att',      help='Bit depth of input attribute',      default=32,             type=int )  

  main = parser.add_argument_group('Output')
  main.add_argument('-b,', '--bin',         help='Output bin path',                   default='',             type=str )
  main.add_argument('-r,', '--rec',         help='Output ply path',                   default='',             type=str )
  main.add_argument('--ascii',              help='Ascii output format',               default=False,          action='store_true')

  main = parser.add_argument_group('Sorting')         
  main.add_argument('--min_block_size',     help='Minimum block size',                default=64,             type=int )
  main.add_argument('--sort_params',        help='sorting parameters',                default=['x', 'y', 'z', 'f_dc_0', 'f_dc_1', 'f_dc_2'], type=list )      
    
  main = parser.add_argument_group('Videos')
  main.add_argument('--bd_0..31',           help='Bitdepht values for nth video',                       default=argparse.SUPPRESS)
  main.add_argument('--qp_0..31',           help='QP values for nth video ',                            default=argparse.SUPPRESS)
  main.add_argument('--format_0..31',       help='Format values for nth video: yuv400, yuv420, yuv444', default=argparse.SUPPRESS)
  main.add_argument('--packing_0..31',      help='Packing values for nth video: planar, temporal',      default=argparse.SUPPRESS)
  main.add_argument('--quant_0..31',        help='Quantization type for nth video: linear, gaussian',   default=argparse.SUPPRESS)
  main.add_argument('--codec_0..31',        help='Codec ID for nth video\n'
                                                 '  Codec ID can be: \n'
                                                 '    - x264: ffmpeg x264 \n'
                                                 '    - x265: ffmpeg x265 \n'
                                                 '    - hm:  hm reference software \n'
                                                 '    - vtm: VTM reference software\n'
                                                 '    - vtr: VTM reference software with high bit depht support \n',   
                                                                            default=argparse.SUPPRESS)
  main.add_argument('--config_0..31',       help='Video encoder configuration files',                   default=argparse.SUPPRESS)
  main.add_argument('--comp_0..31',         help='List of components for nth video (comma-separated)\n'
                                                 '  Components can be: \n'
                                                 '    - x,y,z: position coordinates (LSB)\n'
                                                 '    - x_add,y_add,z_add: additional position coordinates (MSB) \n'
                                                 '    - opacity: opacity\n'
                                                 '    - scale_0,scale_1,scale_2: scale \n'
                                                 '    - rot_0,rot_1,rot_2,rot_3: rotation \n' 
                                                 '    - f_dc_0,f_dc_1,f_dc_2: colors \n'
                                                 '    - f_rest_0,f_rest_1,...,f_rest_44: spherical harmonics \n' 
                                                 '    - zero: add zero component to the video',          default=argparse.SUPPRESS)
  for i in range(21):
    main.add_argument(f'--bd_{i}',          help=argparse.SUPPRESS,                   default=10,             type=int)
    main.add_argument(f'--qp_{i}',          help=argparse.SUPPRESS,                   default=0,              type=int)
    main.add_argument(f'--format_{i}',      help=argparse.SUPPRESS,                   default='yuv400',       type=str, choices=['yuv400', 'yuv420', 'yuv444'])
    main.add_argument(f'--packing_{i}',     help=argparse.SUPPRESS,                   default='planar',       type=str, choices=['planar', 'temporal'])
    main.add_argument(f'--quant_{i}',       help=argparse.SUPPRESS,                   default='linear',       type=str, choices=['linear', 'gaussian'])
    main.add_argument(f'--codec_{i}',       help=argparse.SUPPRESS,                   default=None,           type=str, choices=['x264','x265','hm', 'vtm', 'vtr'])
    main.add_argument(f'--config_{i}',      help=argparse.SUPPRESS,                   default=[],             type=comma_separated_list)
    main.add_argument(f'--comp_{i}',        help=argparse.SUPPRESS,                   default=[],             type=comma_separated_list)

  main = parser.add_argument_group('Transform')
  main.add_argument('--trans_position',     help='Transform position: signed log',    default=1,              type=int )

  main = parser.add_argument_group('Plot and traces')        
  main.add_argument('-v','--verbose',       help='Verbose',                           default=False,          action='store_true')
  main.add_argument('--decode_only',        help='Decode only',                       default=False,          action='store_true')
  main.add_argument('--bitstream_log',      help='Bitstream write and read logs',     default=False,          action='store_true')
  main.add_argument('--remove',             help='Remove previous directory',         default=False,          action='store_true')

  try:   
    args = parser.parse_args()
  except:
    sys.exit(0)
  
  if args.verbose:
    print_args(parser, args)

  # Check components
  ply_columns = ['x', 'y', 'z', 'x_add', 'y_add', 'z_add', 'f_dc_0', 'f_dc_1', 'f_dc_2', *[f'f_rest_{i}' for i in range(45)],
               'opacity', 'scale_0', 'scale_1', 'scale_2', 'rot_0', 'rot_1', 'rot_2', 'rot_3']
  all_elements = []
  for i in range(21):
      comp = getattr(args, f"comp_{i}")
      all_elements.extend(comp)    
  element_counts = Counter(all_elements)
  duplicates     = [elem for elem, count in element_counts.items() if count > 1]
  missing        = [elem for elem in ply_columns if elem not in element_counts]
  if not duplicates and not missing:
    if args.verbose:
      print("All elements appear exactly once across the 21 lists.")
  else:
    if duplicates:
      print("Warning: Duplicates found in video components:", duplicates)
    if missing:
      print("Warning: Missing elements in video components:", missing)   
  if args.bin == '':
    bistream_name = get_name( args ) 
  else:
    bistream_name = args.bin
  
  if ( args.bit_depth_pos != 32 or args.bit_depth_att != 32 ) and args.trans_position == 1:
    args.trans_position = 0
    print("Check: disable trans_position because bit_depth_pos or bit_depth_att != 32")
  return args

#######################################################################################################

def get_name(args):
  if args.bin == '':
    prefix = remove_extension(os.path.basename(args.input))
    if any(pattern in prefix for pattern in ['%06d', '%05d', '%04d', '%03d', '%02d', '%01d', '%d']):      
      prefix = prefix.split('%', 1)[0]
    if prefix == '':
      prefix = os.path.basename(os.path.normpath(os.path.dirname(args.input)))
      if prefix == '.' or prefix == '' :
        prefix = os.path.basename(os.getcwd())
    name  = prefix \
            + '_bd%02d_%02d_%02d_%02d_%02d_%02d_%02d' % ( args.bd_0, args.bd_1, args.bd_2, args.bd_3, args.bd_4, args.bd_5, args.bd_6 ) \
            + '_qp%02d_%02d_%02d_%02d_%02d_%02d_%02d' % ( args.qp_0, args.qp_1, args.qp_2, args.qp_3, args.qp_4, args.qp_5, args.qp_6 ) \
            + '_c%02d' % ( args.force_comp )
    return to_bash_path(os.path.join( name, name + '.v3c' ) )
  else:
    return to_bash_path(args.bin)

#######################################################################################################

def get_bd_by_comp(args, comp_name):
    for i in range(21):
        comp_list = getattr(args, f'comp_{i}', [])
        if comp_name in comp_list:
            return getattr(args, f'bd_{i}', None)
    return None

#######################################################################################################

def create_codec_list(args):
  codecs = []
  for i in range(32):
    v = getattr(args, f'codec_{i}', None)
    if v is not None and v not in codecs:
      codecs.append( v )
  return codecs

#######################################################################################################

if __name__ == '__main__':

  # Initialize
  handler_ctrl_c()
  start_time = time.time() 
  args       = parse_args()
  device     = init_device(args.verbose)
  output_dir = create_output_dir( args.bin, args.remove and not args.decode_only, args.verbose )
  codecs     = create_codec_list(args)
  if args.rec != '': 
    create_output_dir( args.rec, args.remove and not args.decode_only, args.verbose )
  if args.verbose:
    print("bitstream  = %s " % args.bin)
    print("output_dir = %s " % output_dir)
    print("Codecs     = ", codecs)

  #########################################################################################
  ######################################## Encoder ########################################
  ######################################################################################### 

  if not args.decode_only:

    # Create group of frames object
    gof_enc = GroupOfFrames( 0, codecs=codecs, bit_depth_pos=args.bit_depth_pos, bit_depth_att=args.bit_depth_att )
    for j in range(21):
      if getattr(args, f'comp_{j}') != []:
        gof_enc.create_video( video_index    = j, 
                              list_params    = getattr(args, f'comp_{j}'), 
                              bitdepth       = getattr(args, f'bd_{j}'), 
                              qp             = getattr(args, f'qp_{j}'), 
                              codec_id       = codecs.index(getattr(args, f'codec_{j}')), 
                              format         = Format.from_string( getattr(args, f'format_{j}')), 
                              packing        = Packing.from_string( getattr(args, f'packing_{j}')), 
                              quantization   = Quantization.from_string( getattr(args, f'quant_{j}')), 
                              trans_position = args.trans_position,
                              verbose        = args.verbose )

    # Get number of of gaussian in gof 
    min_num_gaussian = min_num_gaussian_in_gof( path=args.input, first_frame=args.first_frame, num_frames=args.num_frames, verbose=args.verbose )

    # Loop over frames
    for frame_index in range(args.num_frames):

      # Read point cloud 
      pc = Pointcloud( path=args.input, index = args.first_frame + frame_index, verbose = args.verbose )

      # Sorting
      sort( pointcloud       = pc,     
            num_points_gof   = min_num_gaussian,
            sort_params      = args.sort_params, 
            min_block_size   = args.min_block_size, 
            bitdepth_xyz     = get_bd_by_comp(args, "x"), 
            bitdepth_opacity = get_bd_by_comp(args, "opacity"), 
            bitdepth_scale   = get_bd_by_comp(args, "scale_0"), 
            bitdepth_rotate  = get_bd_by_comp(args, "rot_0"), 
            bitdepth_dc      = get_bd_by_comp(args, "f_dc_0"), 
            bitdepth_sh      = get_bd_by_comp(args, "f_rest_0"), 
            trans_position   = args.trans_position,
            device           = device, 
            verbose          = args.verbose )

      # Set videos       
      gof_enc.set_video(pointcloud = pc, verbose = args.verbose )
      
      if args.verbose:
        print("Frame %2d: " % (args.first_frame + frame_index))
        for type, video in gof_enc.videos.items():
          print("  Video %10s: %4d x %4d grid = %3d %3d x %2d %2d num frame = %d " %  
            (type.name, video.width, video.height, gof_enc.block_width, gof_enc.block_height, video.grid_width, video.grid_height, video.video_src.num_frames() ) ) 

    # Quantize videos
    if gof_enc.bit_depth_pos == 32 and gof_enc.bit_depth_att == 32:
      gof_enc.quantize(verbose=args.verbose)
    else:
      gof_enc.reduce_bitdepth(verbose=args.verbose)

    # Verbose
    if args.verbose:
      for type, video in gof_enc.videos.items():
        print("  Video %10s: %4d x %4d grid = %3d %3d x %2d %2d num frame = %d " %  
          (type.name, video.width, video.height, gof_enc.block_width, gof_enc.block_height, video.grid_width, video.grid_height, video.video_src.num_frames() ) ) 

    # Encode video in parallel
    if args.verbose:
      print('Encode videos...')
    with concurrent.futures.ThreadPoolExecutor() as executor:
      futures = [
        executor.submit(encode_video, 
                          type       = type,
                          name       = video.name(), 
                          index      = index, 
                          output_dir = output_dir, 
                          video      = video.video_uint, 
                          codec      = gof_enc.codecs[video.codec_id], 
                          config     = getattr(args, f'config_{index}'), 
                          qp         = video.qp,
                          verbose    = args.verbose)
        for index, (type, video) in enumerate(gof_enc.videos.items())
      ]
      for future in concurrent.futures.as_completed(futures):
        type, bitstream = future.result() 
        gof_enc.videos[type].bitstream = bitstream
        
    if args.verbose:
      print('All videos encoded.') 

    # Save V3C bitstream
    gof_enc.save( args.bin, bitstream_log=bool(args.bitstream_log), verbose=args.verbose )
    if args.verbose:
      gof_enc.print( "enc" )
  
  #########################################################################################
  ######################################## Decoder ########################################
  ######################################################################################### 

  if not os.path.exists( args.bin ):  
    print("Error: %s not exists " % args.bin )
    exit()

  # Read gof of frame data
  gof_dec = GroupOfFrames() 
  gof_dec.read( args.bin, verbose=args.verbose ) 

  # Decode video in parallel  
  if args.verbose:
    for index, (type, video) in enumerate(gof_dec.videos.items()):
      print("video size = %4d %4d grid = %3d %3d x %2d %2d " %  
        ( video.width, video.height, gof_dec.block_width, gof_dec.block_height, video.grid_width, video.grid_height))

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
                        video      = video.video_uint, 
                        codec      = gof_dec.codecs[video.codec_id],
                        verbose    = args.verbose)
      for index, (type, video) in enumerate(gof_dec.videos.items())
    ]
    for future in concurrent.futures.as_completed(futures):
      future.result()

  # Dequantize
  if gof_dec.bit_depth_pos == 32 and gof_dec.bit_depth_att == 32:
    gof_dec.dequantize(verbose=args.verbose)
  else:
    gof_dec.restore_bitdepth(verbose=args.verbose)

  # Decoder 
  if args.verbose:
    print("num decoded frames  = %2d " % ( gof_dec.num_frames('dec') ) )

  for frame_index in range(gof_dec.num_frames('dec')):
    # Get decoded pointcloud
    dec = gof_dec.get_pointcloud( frame_index, args.verbose )

    # Save decoded pointcloud
    dec.write(args.rec if args.rec != '' else ( remove_extension(args.bin) + '_%04d_rec.ply'), 
              args.first_frame + frame_index, ascii=args.ascii, verbose=args.verbose )

  #########################################################################################
  ######################################## Stat ###########################################
  #########################################################################################

  # Verbose
  if args.verbose:  
    gof_dec.print( "dec" )

  # Stat
  if not args.decode_only:
    gof_enc.stat.log()
  sizeBin = os.path.getsize( args.bin )
  sizeSrc = sum(os.path.getsize( make_path( args.input, args.first_frame + i )) for i in range(args.num_frames))  
  print("Compression ratio: bits = %12d / %12d bytes: %12d / %12d <=> => %12.8f " %( sizeSrc * 8, sizeBin * 8, sizeSrc, sizeBin, sizeSrc / sizeBin ))
  print("Bitstream = %s " % args.bin )
    
  # Save log 
  with open(remove_extension( args.bin ) + '_enc.log', 'w', encoding='utf-8') as f:    
    print_args(parser, args, file=f)
    gof_dec.print( "dec", file=f )
    if not args.decode_only:
      gof_enc.stat.log(file=f)
    print("Compression ratio: bits = %12d / %12d bytes: %12d / %12d <=> => %12.8f " %( sizeSrc * 8, sizeBin * 8, sizeSrc, sizeBin, sizeSrc / sizeBin ), file=f)
    print("Bitstream = %s " % args.bin, file=f )

  end_time = time.time() 
  elapsed = end_time - start_time
  print(f"Time: {elapsed:.4f} secondes")

#######################################################################################################

