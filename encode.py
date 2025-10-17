import os
import sys
import argparse
import time
import concurrent.futures
from utils.common           import handler_ctrl_c, make_path, remove_extension, min_num_gaussian_in_gof, \
                                   print_args, preprocess_args_with_config, create_output_dir, get_bd_by_comp, create_codec_list
from utils.pointcloud       import Pointcloud
from utils.group_of_frames  import GroupOfFrames
from utils.video_codec      import encode_video, decode_video
from utils.v3c.type         import Quantization, Format, Packing, ColorStandard
from utils.plas             import sort, init_device

#######################################################################################################

# Parse input arguments
def parse_args():
    
  def pair(s: str):
    try:
      a_str, b_str = s.split(",", 1)
      return int(a_str), int(b_str)
    except Exception as exc:
      raise argparse.ArgumentTypeError("Format must be: a,b (ex: 10,8)") from exc

  def find_video_bitdepth(list_args, names):
    for i in range(21):
      comps = getattr(list_args, f'comp_{i}', [])
      if any(c in comps for c in names):
        return getattr(list_args, f'bd_{i}', [])
    return 0

  sys.argv = preprocess_args_with_config(sys.argv)
  global parser 
  def comma_separated_list(s):
    return s.split(',')
  parser = argparse.ArgumentParser(
    description='Encode 3DGS point cloud to v3C bitstream',
    epilog='Example:\n' + '  ./' + os.path.basename(__file__) + ' -i %04d.ply -n 1 -b test.bin -r %04d_rec.ply\n',
    prog=os.path.basename(__file__), formatter_class=argparse.RawTextHelpFormatter )
  main = parser.add_argument_group('Input')    
  main.add_argument('-c', '--config',       help='Path to config file')
  main.add_argument('-i,', '--input',       help='Input ply path',                    default='%06d.ply',     type=str )
  main.add_argument('-n','--num_frames',    help='Number of frames',                  default=1,              type=int )
  main.add_argument('--first_frame',        help='Index of the first frame',          default=0,              type=int )

  main = parser.add_argument_group('Output')
  main.add_argument('-b,', '--bin',         help='Output bin path',                   default='',             type=str )
  main.add_argument('-r,', '--rec',         help='Output ply path',                   default='',             type=str )
  main.add_argument('--ascii',              help='Ascii output format',               default=False,          action='store_true')

  main = parser.add_argument_group('Sorting')         
  main.add_argument('--min_block_size',     help='Minimum block size',                default=16,             type=int )
  main.add_argument('--sort_params',        help='sorting parameters',                default=['x', 'y', 'z', 'f_dc_0', 'f_dc_1', 'f_dc_2'], type=list )        

  main = parser.add_argument_group('Videos')
  main.add_argument('--bd_0..31',           help='Bitdepht values for nth video',                       default=argparse.SUPPRESS)
  main.add_argument('--qp_0..31',           help='QP values for nth video ',                            default=argparse.SUPPRESS)
  main.add_argument('--dq_0..31',           help='Delta QP values for nth video ',                      default=argparse.SUPPRESS)
  main.add_argument('--format_0..31',       help='Format values for nth video: yuv400, yuv420, yuv444', default=argparse.SUPPRESS)
  main.add_argument('--packing_0..31',      help='Packing values for nth video: planar, temporal',      default=argparse.SUPPRESS)
  main.add_argument('--quant_0..31',        help='Quantization type for nth video: linear, gaussian',   default=argparse.SUPPRESS)
  main.add_argument('--codec_0..31',        help='Codec ID for nth video\n'
                                                 '  Codec ID can be:\n'
                                                 '    - x264: ffmpeg x264\n'
                                                 '    - x265: ffmpeg x265\n'
                                                 '    - hm:  hm reference software\n'
                                                 '    - vtm: VTM reference software\n'
                                                 '    - vtr: VTM reference software with R-Ext\n',     default=argparse.SUPPRESS)
  main.add_argument('--config_0..31',       help='Video encoder configuration files',                   default=argparse.SUPPRESS)
  main.add_argument('--dqp_0..31',          help='Video encoder dQP files',                             default=argparse.SUPPRESS)
  main.add_argument('--comp_0..31',         help='List of components for nth video (comma-separated)\n'
                                                 '  Components can be:\n'
                                                 '    - x,y,z: main position coordinates\n'
                                                 '    - x_add,y_add,z_add: LSB parts, MSB are stored in main coordinates\n'
                                                 '    - opacity: opacity\n'
                                                 '    - scale_0,scale_1,scale_2: scale\n'
                                                 '    - rot_0,rot_1,rot_2,rot_3: rotation\n' 
                                                 '    - f_dc_0,f_dc_1,f_dc_2: colors\n'
                                                 '    - f_rest_0,f_rest_1,...,f_rest_44: spherical harmonics\n' 
                                                 '    - zero: add zero component to the video',          default=argparse.SUPPRESS)                                                 
  main.add_argument('--subsampling_0..31',  help='Subsampling method for nth video\n'
                                                 '  0: none\n'
                                                 '  1: Simple drop (420)\n'
                                                 '  2: Average (420)',                default=argparse.SUPPRESS)
  for i in range(31):
    main.add_argument(f'--bd_{i}',          help=argparse.SUPPRESS,                   default=10,             type=int)
    main.add_argument(f'--qp_{i}',          help=argparse.SUPPRESS,                   default=0,              type=int)
    main.add_argument(f'--dq_{i}',          help=argparse.SUPPRESS,                   default=0,              type=int)
    main.add_argument(f'--format_{i}',      help=argparse.SUPPRESS,                   default='yuv400',       type=str, choices=['yuv400', 'yuv420', 'yuv444'])
    main.add_argument(f'--packing_{i}',     help=argparse.SUPPRESS,                   default='planar',       type=str, choices=['planar', 'temporal'])
    main.add_argument(f'--quant_{i}',       help=argparse.SUPPRESS,                   default='linear',       type=str, choices=['linear', 'gaussian'])
    main.add_argument(f'--codec_{i}',       help=argparse.SUPPRESS,                   default=None,           type=str, choices=['x264','x265','hm', 'hmr', 'hmd', 'vtm', 'vtr'])
    main.add_argument(f'--config_{i}',      help=argparse.SUPPRESS,                   default=[],             type=comma_separated_list)
    main.add_argument(f'--comp_{i}',        help=argparse.SUPPRESS,                   default=[],             type=comma_separated_list)
    main.add_argument(f'--dqp_{i}',         help=argparse.SUPPRESS,                   default="",             type=str)    
    main.add_argument(f'--subsampling_{i}', help=argparse.SUPPRESS,                   default=2,              type=int)

  main = parser.add_argument_group('Transform')
  main.add_argument('--bd_pos',             help='Position coordinate bit depth specification\n'
                                                 ' Two integers separated by a comma (e.g. 8,4):\n'
                                                 '    - the first value is the number of bits kept in the MSB part (main x,y,z).\n'
                                                 '    - the second value is the number of bits stored in the LSB part (x_add,y_add,z_add).\n'
                                                 '  - If value is 0,0, the corresponding depth is automatically set from video bit depths.\n' , default=(0, 0), type=pair)  
  main.add_argument('--trans_position',     help='Transform position: signed log',    default=1,              type=int)
  main.add_argument('--sh_conversion',      help='Spherical harmonics conversion method applied on videos\n'
                                                 '  - 0: None\n'
                                                 '  - 601: BT. 601\n'
                                                 '  - 709: BT. 709\n'
                                                 '  - 2020: BT. 2020\n',             default='601',           type=str, choices=['0', '601', '709', '2020'])

  main.add_argument('--src_sh_conversion',  help='Spherical harmonics conversion method applied on source pointclouds\n'
                                                 '  - 0: None\n'
                                                 '  - 601: BT. 601\n'
                                                 '  - 709: BT. 709\n'
                                                 '  - 2020: BT. 2020\n',             default='0',            type=str, choices=['0', '601', '709', '2020'])

  main.add_argument('--cov_norm',           help='Covariance normalization: 0: off 1: on\n', default=0, type=int)

  main = parser.add_argument_group('Bitstream')
  main.add_argument('--add_camera_position_sei', help='Add camera position SEI message', default=False, action='store_true')
   
  main = parser.add_argument_group('Plot and traces')        
  main.add_argument('-v','--verbose',       help='Verbose',                           default=False,          action='store_true')
  main.add_argument('--decode_only',        help='Decode only',                       default=False,          action='store_true')
  main.add_argument('--bitstream_log',      help='Bitstream write and read logs',     default=False,          action='store_true')
  main.add_argument('--remove',             help='Remove previous directory',         default=False,          action='store_true')

  try:
    args = parser.parse_args()
  except Exception as exc:
    raise RuntimeError("Argument parsing failed") from exc     
 
  if tuple(args.bd_pos) == (0, 0):
    bd_0 = find_video_bitdepth(args, {'x', 'y', 'z'})
    bd_1 = find_video_bitdepth(args, { 'x_add','y_add','z_add' })
    args.bd_pos = (bd_0, bd_1)
    if args.verbose:
      print(f"[info] bd_pos set from videos: {bd_0},{bd_1}")
  if args.verbose:
    print_args(parser, args) 
  return args

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
    gof_enc = GroupOfFrames( 0, codecs=codecs, src_sh_conversion = ColorStandard.from_string( args.src_sh_conversion ) )
    for j in range(21):
      if getattr(args, f'comp_{j}') != []:
        gof_enc.create_video( video_index       = j, 
                              list_params       = getattr(args, f'comp_{j}'),
                              bitdepth          = getattr(args, f'bd_{j}'), 
                              bitdepth_pos      = args.bd_pos,
                              qp                = getattr(args, f'qp_{j}') + getattr(args, f'dq_{j}'), 
                              codec_id          = codecs.index(getattr(args, f'codec_{j}')), 
                              format            = Format.from_string( getattr(args, f'format_{j}')), 
                              packing           = Packing.from_string( getattr(args, f'packing_{j}')), 
                              quantization      = Quantization.from_string( getattr(args, f'quant_{j}')), 
                              trans_position    = args.trans_position,
                              sh_conversion     = ColorStandard.from_string( args.sh_conversion ),
                              subsampling       = getattr(args, f'subsampling_{j}'),
                              verbose           = args.verbose )

    # Get number of of gaussian in gof 
    min_num_gaussian = min_num_gaussian_in_gof( path=args.input, first_frame=args.first_frame, num_frames=args.num_frames, verbose=args.verbose )

    # Loop over frames
    for frame_index in range(args.num_frames):

      # Read point cloud 
      pc = Pointcloud( path=args.input, index = args.first_frame + frame_index, verbose = args.verbose )

      # Normalize scale and rotation
      if args.cov_norm != 0:
        pc.normalize_scale_rotation(verbose=args.verbose)
        
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
                    
      # Src color conversion
      if gof_enc.src_sh_conversion != ColorStandard.NONE:
        pc.rgb2yuv(gof_enc.src_sh_conversion, verbose=args.verbose)

      if args.verbose: 
        pc.print("yuv", num = 1)

      # Set videos
      gof_enc.set_video(pointcloud = pc, verbose = args.verbose )
       
      if args.verbose:
        print("Frame %2d: " % (args.first_frame + frame_index))
        for type, video in gof_enc.videos.items():
          print("  Video src: %10s: %4d x %4d grid = %3d %3d x %2d %2d format = %s frame = %d dim = %4d x %4d / %4d x %4d " %  
            (type.name, video.width, video.height, gof_enc.block_width, gof_enc.block_height, video.grid_width, video.grid_height, 
             video.format, video.video_src.num_frames(),
             video.video_src.frames[0][0].shape[0], video.video_src.frames[0][0].shape[1], 
             video.video_src.frames[0][1].shape[0] if video.video_src.frames[0][1] is not None else 0,
             video.video_src.frames[0][1].shape[1] if video.video_src.frames[0][1] is not None else 0) )     
        sys.stdout.flush()     
 
    # Quantize videos 
    gof_enc.quantize(verbose=args.verbose)

    # Convert SH
    gof_enc.rgb2yuv(verbose=args.verbose)

    # Subsample videos
    gof_enc.subsample(verbose=args.verbose)

    # Verbose
    if args.verbose:
      for type, video in gof_enc.videos.items():
        print("  Video enc: %10s: %4d x %4d grid = %3d %3d x %2d %2d format = %s frame = %2d dim = %4d x %4d / %4d x %4d " %  
          (type.name, video.width, video.height, gof_enc.block_width, gof_enc.block_height, video.grid_width, video.grid_height, 
           video.format.name, video.video_src.num_frames(),  
           video.video_uint.frames[0][0].shape[0], video.video_uint.frames[0][0].shape[1], 
           video.video_uint.frames[0][1].shape[0] if video.video_uint.frames[0][1] is not None else 0,
           video.video_uint.frames[0][1].shape[1] if video.video_uint.frames[0][1] is not None else 0) ) 
      sys.stdout.flush()

    # Encode video in parallel
    if args.verbose:
      print('Encode videos...')
      sys.stdout.flush()
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
                        dqp        = getattr(args, f'dqp_{index}'),
                        qp         = video.qp,
                        verbose    = args.verbose)
        for index, (type, video) in enumerate(gof_enc.videos.items())
      ]
      for future in concurrent.futures.as_completed(futures):
        type, bitstream = future.result() 
        gof_enc.videos[type].bitstream = bitstream
        
    if args.verbose:
      print('All videos encoded.') 
      sys.stdout.flush()

    # Save V3C bitstream
    gof_enc.save( args.bin, bitstream_log=bool(args.bitstream_log), add_camera_position_sei=args.add_camera_position_sei, verbose=args.verbose )
    if args.verbose:
      gof_enc.print( "enc" )
  
  #########################################################################################
  ######################################## Decoder ########################################
  ######################################################################################### 

  if not os.path.exists( args.bin ):  
    print("Error: %s not exists " % args.bin )
    sys.stdout.flush()
    exit()

  # Read gof of frame data
  gof_dec = GroupOfFrames() 
  gof_dec.read( args.bin, verbose=args.verbose ) 

  # Decode video in parallel  
  if args.verbose:
    for index, (type, video) in enumerate(gof_dec.videos.items()):
      print("video size = %4d %4d grid = %3d %3d x %2d %2d " %  
        ( video.width, video.height, gof_dec.block_width, gof_dec.block_height, video.grid_width, video.grid_height))
    sys.stdout.flush()

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
      for index, (type, video) in enumerate(gof_dec.videos.items())
    ]
    for future in concurrent.futures.as_completed(futures):
      future.result()

  # Upsample videos (when Format is YUV420)
  gof_dec.upsample(verbose=args.verbose)

  # Convert SH  
  gof_dec.yuv2rgb(verbose=args.verbose)

  # Dequantize
  gof_dec.dequantize(verbose=args.verbose)
  
  # Decoder 
  if args.verbose:
    print("num decoded frames  = %2d " % ( gof_dec.num_frames('dec') ) )
    sys.stdout.flush()

  for frame_index in range(gof_dec.num_frames('dec')):
    # Get decoded pointcloud
    dec = gof_dec.get_pointcloud( frame_index, args.verbose )

    # Dec color conversion
    if gof_dec.src_sh_conversion != ColorStandard.NONE:
      dec.yuv2rgb(gof_dec.src_sh_conversion, verbose=args.verbose)

    # Quaternion denormalization
    if not 'rot_0' in [p for v in gof_dec.videos.values() for p in getattr(v, "list_params", None)]:
      dec.reconstruct_quat(verbose=args.verbose)      

    # Save decoded pointcloud
    if args.verbose:
      dec.print("PC_dec", num = 1)  
    # cleanup
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
  sys.stdout.flush()

#######################################################################################################

