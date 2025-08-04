import os
import sys
import signal
import platform
from pathlib import Path
import numpy as np 
import shutil
import argparse

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

def print_args( parse, args, file=None ):
  print('Argument values:',file=file )
  for group in parse._action_groups:      
    if group.title not in ('positional arguments', 'options'):
      print(f'  {group.title}:',file=file)
      for action in group._group_actions:
        if action.dest != 'help':
          if action.default != argparse.SUPPRESS:
            print( '    --%-20s = %-40s ( %s )' % ( action.dest, getattr( args, action.dest ), 
                action.help.strip().split('\n')[0] if action.help != argparse.SUPPRESS else '' ), 
                flush=True,file=file)          

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
      with open(config_file, 'r') as f:
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

def min_num_gaussian_in_gof(path, first_frame=0, num_frames=1, verbose=False):
  num_points = 2 ** 31 - 1
  for index in range(first_frame, first_frame + num_frames):    
    filename = make_path(path, index)
    if verbose:
        print("Reading file:", filename, flush=True)
    with open(filename, "rb") as f:
      while True:
        line = f.readline()
        if not line:
          break  # End of file (should not happen in header)
        try:
          line = line.decode("ascii")
        except UnicodeDecodeError:
          continue  # Ignore undecodable lines (shouldn't happen in header)
        if line.startswith("element vertex"):
          num_points = min(num_points, int(line.strip().split()[-1]))
          break
        if line.startswith("end_header"):
          break  # Stop if we reach end of header
  if verbose:
    print(f"Minimum number of points in GoF: %9d " % num_points, flush=True)
  return num_points

#######################################################################################################