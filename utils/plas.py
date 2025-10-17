import os 
import sys
import numpy as np
import torch
from plas import sort_with_plas 
from utils.common import make_path, log_transform, linear_normalize
from utils.pointcloud import Pointcloud
from typing import Optional, Tuple, Dict, Any, Union
import time
if os.name == "nt":  
  import msvcrt  
else:          
  try:
    import fcntl  
  except ImportError:
    fcntl = None
    
#######################################################################################################

class FileLock:
  def __init__(self):      
    self.path = "C:/tmp/gpu_lock.lock" if os.name == "nt" else "/tmp/gpu_lock.lock"
    self.fd = None

  def acquire(self, retry_interval=1):
    self.fd = open(self.path, "w", encoding='utf-8')
    if os.name == "nt":
      print(f"[LOCK] Waiting for lock {self.path} (Windows)...")
      while True:
        try:
          msvcrt.locking(self.fd.fileno(), msvcrt.LK_NBLCK, 1)
          print(f"[LOCK] Lock acquired {self.path}.")
          break
        except OSError:
          time.sleep(retry_interval)
    else:
      print(f"[LOCK] Waiting for lock {self.path} (POSIX)...")
      fcntl.flock(self.fd, fcntl.LOCK_EX)
      print(f"[LOCK] Lock acquired {self.path}.")

  def release(self):
    if self.fd:
      if os.name == "nt":
        msvcrt.locking(self.fd.fileno(), msvcrt.LK_UNLCK, 1)
      else:
        fcntl.flock(self.fd, fcntl.LOCK_UN)
      self.fd.close()
      self.fd = None
      print(f"[LOCK] Lock released {self.path}.")

#######################################################################################################

def init_device(verbose = False):
  torch.manual_seed(42)
  np.random.seed(42)
  if torch.backends.mps.is_available():
    device = torch.device("mps")
  elif torch.cuda.is_available():
    device = torch.device("cuda")
  else:
    device = "cpu"
  if verbose:
    print(f"Using device: {device}")
    sys.stdout.flush()
  return device

#######################################################################################################

def prune_gaussians(pointcloud, num_points):
  """Very crude pruning method that uses scaling and opacity to determine the impact of a Gaussian splat.
  We need this method to drop a few Gaussians to make them fit a square image.

  For a more sophisticated method, see e.g. "LightGaussian: Unbounded 3D Gaussian Compression with 15x Reduction and 200+ FPS"
  https://arxiv.org/abs/2311.17245
  """
  opacity_act = lambda x: 1 / (1 + np.exp(-x))
  pointcloud.df["impact"] = np.exp((pointcloud.df["scale_0"] + pointcloud.df["scale_1"] + pointcloud.df["scale_2"]).astype(np.float64)) \
                    * opacity_act(pointcloud.df["opacity"].astype(np.float64))
  pointcloud.df = pointcloud.df.sort_values("impact", ascending=False)
  pointcloud.df = pointcloud.df.head(num_points)   

#######################################################################################################

def resize( pointcloud, num_points_gof, min_block_size=16, verbose=False ):
  pointcloud.sidelen = int(np.sqrt(num_points_gof))
  pointcloud.sidelen = pointcloud.sidelen // min_block_size * min_block_size
  prune_gaussians( pointcloud, pointcloud.sidelen * pointcloud.sidelen)        

#######################################################################################################

def prepare_tensor(pointcloud, 
                   param_list, 
                   bitdepth_xyz, 
                   bitdepth_opacity, 
                   bitdepth_scale, 
                   bitdepth_rotate, 
                   bitdepth_dc, 
                   bitdepth_sh, 
                   trans_position,
                   device,
                   verbose=False):
  if verbose:
    print(f"Preparing tensor m73254 with parameters: {param_list}")
  tensors = []
  for param in param_list:
    if param in ['x', 'y', 'z']:
      values = pointcloud.df[[param]].values      
      if trans_position:  
        values = log_transform( values )
      norm_values = linear_normalize( values, bitdepth_xyz)
    elif param in ['opacity']:
      values = pointcloud.df[[param]].values
      norm_values = linear_normalize( values, bitdepth_opacity)
    elif param in ['scale_0', 'scale_1', 'scale_2']:
      values = pointcloud.df[[param]].values
      norm_values = linear_normalize( values, bitdepth_scale)
    elif param in ['rot_0', 'rot_1', 'rot_2', 'rot_3']:
      values = pointcloud.df[[param]].values
      norm_values = linear_normalize( values, bitdepth_rotate)
    elif param.startswith('f_dc'):
      dc_vals = pointcloud.df.loc[:, pointcloud.df.columns.str.startswith("f_dc")].values
      norm_values = linear_normalize( dc_vals, bitdepth_dc)
    elif param.startswith('f_rest'):
      values = pointcloud.df[[param]].values
      norm_values = linear_normalize( values, bitdepth_sh)
    else:
      raise ValueError(f"Parameter {param} is not recognized or not handled.")
    tensor_param = torch.from_numpy(norm_values).float().to(device)
    tensors.append(tensor_param)
  params_tensor = torch.cat(tensors, dim=1)
  return params_tensor


#######################################################################################################

def sort( pointcloud, 
          num_points_gof,
          sort_params,   
          min_block_size, 
          bitdepth_xyz, 
          bitdepth_opacity, 
          bitdepth_scale, 
          bitdepth_rotate, 
          bitdepth_dc, 
          bitdepth_sh, 
          trans_position,
          device, 
          verbose=False): 

  lock = FileLock()
  lock.acquire() 

  resize(pointcloud, num_points_gof, min_block_size, verbose)
  params = prepare_tensor(pointcloud,
                          sort_params, 
                          bitdepth_xyz, 
                          bitdepth_opacity, 
                          bitdepth_scale, 
                          bitdepth_rotate, 
                          bitdepth_dc, 
                          bitdepth_sh,
                          trans_position,
                          device, 
                          verbose) 
  params_torch_grid = params.permute(1, 0).reshape(-1, pointcloud.sidelen, pointcloud.sidelen)
  _, sorted_grid_indices = sort_with_plas(params_torch_grid, min_block_size, improvement_break=1e-4, verbose=False)
  sorted_indices = sorted_grid_indices.flatten().cpu().numpy()
  pointcloud.df = pointcloud.df.iloc[sorted_indices]
  
  lock.release()

#######################################################################################################
