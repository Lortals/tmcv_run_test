import os
import re
import sys
import signal
import platform
from pathlib import Path
import shutil
import argparse
import numpy as np 

#######################################################################################################

def handler_ctrl_c():
  def handler(sig, frame):
    print('You pressed Ctrl+C!')
    sys.exit(0)
  signal.signal(signal.SIGINT, handler)

#######################################################################################################

def is_windows():
  return platform.system() == 'Windows'
 
#######################################################################################################

def to_bash_path(win_path: str ) -> str:  
  path = Path(win_path).resolve()
  path_str = path.as_posix()    
  # if change_drive:
  #   if ':' in path_str:
  #     drive_letter = path_str[0].lower()
  #     path_str = f"/{drive_letter}{path_str[2:]}"    
  return path_str

#######################################################################################################

def fixpath(path):
  if is_windows():
    path = os.path.normpath(os.path.expanduser(path))
    if path.startswith('/c'):
      return 'C:' + path[2:]
    if path.startswith('/g'):
      return 'G:' + path[2:]
    if path.startswith('\\c'):
      return 'C:' + path[2:]
    if path.startswith('\\g'):
      return 'G:' + path[2:]
  return path

#######################################################################################################

def print_args(parse, args, file=None):
  print('Argument values:', file=file)
  for group in parse._action_groups:
    if group.title not in ('positional arguments', 'options'):
      group_args = []
      for action in group._group_actions:
        if action.dest != 'help' and action.default != argparse.SUPPRESS:
          value = getattr(args, action.dest)
          help_text = (action.help.strip().split('\n')[0] if action.help != argparse.SUPPRESS else '' )
          group_args.append((action.dest, value, help_text))
      video_indices = set()
      for dest, _, _ in group_args:
        m = re.match(r'.*_(\d+)$', dest)
        if m:
          video_indices.add(int(m.group(1)))
      skip_indices = set()
      for i in video_indices:
        comp_name = f'comp_{i}'
        if hasattr(args, comp_name):
          comp_val = getattr(args, comp_name)
          if comp_val in ([], None, ''):
            skip_indices.add(i)
      video_args = {}
      other_args = []
      for dest, value, help_text in group_args:
        m = re.match(r'.*_(\d+)$', dest)
        if m:
          vid = int(m.group(1))
          if vid not in skip_indices:
            video_args.setdefault(vid, []).append((dest, value, help_text))
        else:
          other_args.append((dest, value, help_text))
      if not other_args and not video_args:
        continue
      print(f'  {group.title}:', file=file)
      for dest, value, help_text in other_args:
        print('    --%-20s = %-40s ( %s )' % (dest, value, help_text), flush=True, file=file)
      for vid in sorted(video_args.keys()):
        print(f'    Video_{vid}:', file=file)
        for dest, value, help_text in video_args[vid]:
          print('      --%-18s = %-40s ( %s )' % (dest, value, help_text), flush=True, file=file)

#######################################################################################################

def preprocess_args_with_config(argv):
  new_argv = []
  skip = False
  for i, arg in enumerate(argv):
    if skip:
      skip = False
      continue
    if arg in ['-c', '--config'] and i + 1 < len(argv):
      config_file = argv[i + 1]
      if not os.path.isfile(config_file):
        raise FileNotFoundError(f"Config file '{config_file}' not found.")
      with open(config_file, 'r',encoding='utf-8') as f:
        for line in f:
          line = line.strip()
          if not line or line.startswith('#'):
            continue
          if ':' not in line:
            continue
          key, value = line.split(':', 1)
          key = key.strip()
          value = value.strip()
          if key:
            new_argv.append(f'--{key}')
            new_argv.append(value)
      skip = True  
    else:
      new_argv.append(arg)
  return new_argv

#######################################################################################################

def create_yuv_filename(prefix, suffix='', width=0, height=0, fps=0, bits=0, format=''):
  return f"{prefix}_{width}x{height}_{fps}_{bits}b_p{format}" + ('' if suffix == '' else ( '_%s' % suffix )) + '.yuv'

#######################################################################################################

def create_output_dir( path, remove=False, verbose=False  ):  
  if not os.path.dirname(path):
    path = os.path.join(os.getcwd(), path)  
  directory = os.path.dirname(path)
  if os.path.isdir(directory) and remove:
    shutil.rmtree(directory)
  if not os.path.exists(directory):
    os.makedirs(directory)
    if verbose:
      print(f"Created directory: {directory}")
  else:
    if verbose:
      print(f"Directory already exists: {directory}")
  return directory

#######################################################################################################

def remove_extension( path ):
  return os.path.splitext(path)[0]

#######################################################################################################

def make_path( path, index ):
  if any(pattern in path for pattern in ['%06d', '%05d', '%04d', '%03d', '%02d', '%01d', '%d']):
    return path % index
  else:
    return path
          
#######################################################################################################

def read_bin(filename):
  with open(filename, 'rb') as file:
    data = file.read()  
    buffer = np.frombuffer(data, dtype=np.uint8) 
  return buffer

#######################################################################################################

def write_bin(filename, buffer):
  with open(filename, 'wb') as file:
    file.write(buffer.tobytes())

#######################################################################################################

def log_transform(x):
  return np.sign(x) * np.log1p(np.abs(x))

#######################################################################################################

def inverse_log_transform(x):
  return np.sign(x) * (np.expm1(np.abs(x))) 

#######################################################################################################

def pca_transform(data, var_thr, n_comp=0, multiple_dim=1):
  if not 0 < var_thr <= 1:
    raise ValueError("Variance threshold must be in (0, 1], got %.2f" % var_thr)
  n_pts, n_orig = data.shape
  _, s_vals, Vt = np.linalg.svd(data, full_matrices=False)
  cum_var = np.cumsum(s_vals ** 2 / np.sum(s_vals ** 2))

  n_comp = np.argmax(cum_var >= var_thr) + 1 if n_comp == 0 else min(n_comp, min(n_pts, n_orig))
  n_comp = (n_comp + multiple_dim - 1) // multiple_dim * multiple_dim
  transform_basis = Vt[:n_comp]
  transform_data = data @ transform_basis.T

  return transform_data, transform_basis

#######################################################################################################

def inverse_pca_transform(transform_data, transform_basis):
  reconstructed = transform_data @ transform_basis.T
  return reconstructed

#######################################################################################################

def linear_normalize(values, bitdepth ):
  scale_max = 2 ** bitdepth - 1
  min_val   = values.min()
  max_val   = values.max()
  range_val = max_val - min_val
  scale_max = 2 ** bitdepth - 1
  normed = (values - min_val) / range_val
  normed = normed * scale_max
  return normed

#######################################################################################################

def min_num_gaussian_in_gof(path=None, first_frame=0, num_frames=1, pc_group=None, verbose=False):
  num_points = 2 ** 31 - 1
  if pc_group is not None:
    for pc in pc_group.pointclouds:
      num_points = min(num_points, len(pc.df))
  else:
    for index in range(first_frame, first_frame + num_frames):
      filename = make_path(path, index)
      if verbose:
        print("Reading file:", filename, flush=True)
      with open(filename, "rb") as f:
        while True:
          line = f.readline()
          if not line:
            break
          try:
            line = line.decode("ascii")
          except UnicodeDecodeError:
            continue
          if line.startswith("element vertex"):
            num_points = min(num_points, int(line.strip().split()[-1]))
            break
          if line.startswith("end_header"):
            break
  if verbose:
    print("Minimum number of points in GoF: %9d " % num_points, flush=True)
  return num_points

#######################################################################################################

def max_num_gaussian_in_gof(path=None, first_frame=0, num_frames=1, pc_group=None, verbose=False):
  num_points = 0
  if pc_group is not None:
    for pc in pc_group.pointclouds:
      num_points = max(num_points, len(pc.df))
  else:
    for index in range(first_frame, first_frame + num_frames):
      filename = make_path(path, index)
      if verbose:
        print("Reading file:", filename, flush=True)
      with open(filename, "rb") as f:
        while True:
          line = f.readline()
          if not line:
            break
          try:
            line = line.decode("ascii")
          except UnicodeDecodeError:
            continue
          if line.startswith("element vertex"):
            num_points = max(num_points, int(line.strip().split()[-1]))
            break
          if line.startswith("end_header"):
            break
  if verbose:
    print("Maximum number of points in GoF: %9d " % num_points, flush=True)
  return num_points

#######################################################################################################

def normalize_path(path: str) -> str:
  m = re.match(r"([A-Za-z]):\\(.*)", path)
  if m:
    drive = m.group(1).lower()
    rest = m.group(2).replace("\\", "/")
    return f"/{drive}/{rest}"
  return path.replace("\\", "/")

#######################################################################################################

def reformat(line: str) -> str:
  parts = line.strip()[:].strip().split()
  if not parts:
    return line
  exe = normalize_path(parts[0])
  args = []
  for p in parts[1:]:
    if p.startswith("--") or p.startswith("-"):
      args.append(" \\\n        " + p)   
    else:
      if args:
        args[-1] += f" {normalize_path(p)}"
      else:
        args.append(normalize_path(p))
  return exe + " " + "".join(args)

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
  
#######################################################################################################1