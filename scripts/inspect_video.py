import sys
import os
# Ensure project root is on sys.path so `utils` can be imported
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
from utils.group_of_frames import GroupOfFrames
from utils.video_data import VideoData


def print_video_info(gof):
    for vtype, video in gof.videos.items():
        try:
            name = video.name()
        except Exception:
            name = str(vtype)
        print(f"--- Video: {vtype.name} ({name}) ---")
        print("  list_params:", video.list_params)
        print("  bitdepth:", video.bitdepth)
        print("  format:", video.format)
        print("  packing:", video.packing.name)
        try:
            print("  video_uint.num_frames:", video.video_uint.num_frames())
            print("  video_src.num_frames:", video.video_src.num_frames())
            print("  video_dec.num_frames:", video.video_dec.num_frames())
        except Exception as e:
            print("  (error getting frame counts):", e)
        print("  width,height:", video.width, video.height)
        print("  video_uint frames shapes (first up to 4):")
        try:
            nf = min(4, video.video_uint.num_frames())
            for i in range(nf):
                y = video.video_uint.c(i, 0)
                u = video.video_uint.c(i, 1) if video.video_uint.num_planes() > 1 else None
                v = video.video_uint.c(i, 2) if video.video_uint.num_planes() > 1 else None
                print(f"    frame {i}: Y {y.shape} U {u.shape if u is not None else None} V {v.shape if v is not None else None}")
        except Exception as e:
            print("    (could not inspect frames):", e)

        # print mapping param -> (f,x,y,c)
        print("  param -> (frame, x, y, c):")
        for idx, param in enumerate(video.list_params):
            try:
                f, x, y, c = video.get_pack_position(idx)
                print(f"    {idx:02d} {param:20s} -> f={f} x={x} y={y} c={c}")
            except Exception as e:
                print(f"    {idx:02d} {param:20s} -> error: {e}")
        print()


def _build_arg_parser():
    """Build a minimal argument parser for the video config arguments,
    replicating the subset of encode.py's parser that controls video layout.
    Does NOT import encode.py (which requires ffmpeg) so the script can
    run in environments where only Python packages are available.
    """
    import argparse
    from utils.common import preprocess_args_with_config

    def comma_separated_list(s):
        return [x.strip() for x in s.split(',') if x.strip()]

    def pair(s):
        parts = s.split(',')
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1]))
        return (int(s), int(s))

    parser = argparse.ArgumentParser(
        description='Inspect video packing layout for a TMCV config.',
        add_help=True,
    )
    parser.add_argument('-c', '--config',  default='', type=str)
    parser.add_argument('-i', '--input',   default='', type=str)
    parser.add_argument('-n', '--num_frames', default=1, type=int)
    parser.add_argument('--first_frame',   default=0,  type=int)
    parser.add_argument('--min_block_size', default=16, type=int)
    parser.add_argument('--block_size',    default=128, type=int,
                        help='Tile size (px) for PLANAR-packing position display (default: 128)')
    parser.add_argument('--colmap_path',   default='', type=str)
    parser.add_argument('--trans_sh_ac',   default=None, type=str, choices=['pca', None])
    parser.add_argument('--bd_pos',        default=(0, 0), type=pair)
    parser.add_argument('--trans_position', default=1, type=int)
    parser.add_argument('--sh_conversion',  default='601', type=str,
                        choices=['0', '601', '709', '2020'])
    parser.add_argument('--src_sh_conversion', default='0', type=str,
                        choices=['0', '601', '709', '2020'])
    parser.add_argument('-v', '--verbose', default=False, action='store_true')

    for i in range(21):
        parser.add_argument(f'--bd_{i}',         default=10,      type=int)
        parser.add_argument(f'--qp_{i}',         default=0,       type=int)
        parser.add_argument(f'--dq_{i}',         default=0,       type=int)
        parser.add_argument(f'--format_{i}',     default='yuv400',type=str,
                            choices=['yuv400', 'yuv420', 'yuv444'])
        parser.add_argument(f'--packing_{i}',    default='planar',type=str,
                            choices=['planar', 'temporal'])
        parser.add_argument(f'--quant_{i}',      default='linear',type=str,
                            choices=['linear', 'gaussian'])
        parser.add_argument(f'--codec_{i}',      default=None,    type=str)
        parser.add_argument(f'--comp_{i}',       default=[],      type=comma_separated_list)
        parser.add_argument(f'--subsampling_{i}', default=2,      type=int)

    expanded = preprocess_args_with_config(sys.argv[1:])
    args, _ = parser.parse_known_args(expanded)
    return args


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python inspect_video.py -c <config_file> [options] [--block_size N]')
        print()
        print('  Loads the video packing layout defined by a config file and prints per-video')
        print('  details: components, bit depth, format, packing, and the param->(frame,x,y,c) map.')
        print()
        print('  Accepts the same video options as encode.py (--format_2, --bd_0, --bd_pos, etc.).')
        print('  Use --block_size N (default: 128) to set the tile size used when computing')
        print('  pixel positions for PLANAR-packed videos.')
        print()
        print('Example (CTC RP4: yuv420 color video, bd0=9 MSB + bd1=6 LSB geometry):')
        print('  python scripts/inspect_video.py -c cfg/hm/ctc/cfg_3_videos.cfg \\')
        print('      --format_2 yuv420 --bd_0 9 --bd_pos 9,6 --qp_1 8 --qp_2 16')
        sys.exit(1)

    from utils.v3c.type import Format, Packing, Quantization, ColorStandard

    args = _build_arg_parser()
    block_size = args.block_size

    # Collect distinct codec names (for codec_id assignment)
    codecs = []
    for j in range(21):
        c = getattr(args, f'codec_{j}', None)
        if c is not None and c not in codecs:
            codecs.append(c)
    if not codecs:
        codecs = ['hmr']  # fallback

    gof = GroupOfFrames(
        0,
        codecs=codecs,
        src_sh_conversion=ColorStandard.from_string(args.src_sh_conversion),
        trans_sh_ac=args.trans_sh_ac,
    )

    for j in range(21):
        if getattr(args, f'comp_{j}') != []:
            codec_name = getattr(args, f'codec_{j}')
            codec_id = codecs.index(codec_name) if codec_name in codecs else 0
            gof.create_video(
                video_index    = j,
                list_params    = getattr(args, f'comp_{j}'),
                bitdepth       = getattr(args, f'bd_{j}'),
                bitdepth_pos   = args.bd_pos,
                qp             = getattr(args, f'qp_{j}') + getattr(args, f'dq_{j}'),
                codec_id       = codec_id,
                format         = Format.from_string(getattr(args, f'format_{j}')),
                packing        = Packing.from_string(getattr(args, f'packing_{j}')),
                quantization   = Quantization.from_string(getattr(args, f'quant_{j}')),
                trans_position = args.trans_position,
                sh_conversion  = ColorStandard.from_string(args.sh_conversion),
                subsampling    = getattr(args, f'subsampling_{j}'),
                verbose        = args.verbose,
            )

    # If a PLY file is provided, compute the actual block size from the point count
    if args.input and os.path.isfile(args.input):
        try:
            import math
            from utils.group_of_pointclouds import GroupOfPointclouds
            pcs = GroupOfPointclouds(
                pointcloud_path = args.input,
                colmap_path     = args.colmap_path,
                num_frames      = args.num_frames,
                start_frame     = args.first_frame,
                verbose         = args.verbose,
            )
            n_pts = pcs.get_min_num_gaussian_in_gof()
            n = int(math.sqrt(n_pts))
            bs = n // args.min_block_size * args.min_block_size
            if bs > 0:
                block_size = bs
            print(f"[inspect] PLY '{args.input}': {n_pts} Gaussians => block_size={block_size}")
        except Exception as e:
            print(f"[inspect] Could not derive block_size from PLY: {e}")

    # Set block size on all videos so get_pack_position returns pixel coordinates
    for video in gof.videos.values():
        video.set_grid_size(block_width=block_size, block_height=block_size)

    print(f"\n=== Video packing layout (block_size={block_size}) ===\n")
    print_video_info(gof)
