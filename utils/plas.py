import numpy as np
import torch
from plas import sort_with_plas 
from utils.common import make_path, log_transform, linear_normalize
from utils.pointcloud import Pointcloud

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

def resize( pointcloud, num_points_gof, min_block_size, verbose=False ):
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
      norm_values = linear_normalize( values, bitdepth_dc)
      # norm_values = np.clip(dc_vals * C0 + 0.5, 0, 1) * coords_scale_dc  # C0  = 0.28209479177387814 
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
  resize(pointcloud, num_points_gof, min_block_size, verbose)
  params = prepare_tensor( pointcloud,
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
  sorted_coords, sorted_grid_indices = sort_with_plas(params_torch_grid, 
                                                      min_block_size,
                                                      improvement_break=1e-4, 
                                                      verbose=verbose)
  sorted_indices = sorted_grid_indices.flatten().cpu().numpy()
  pointcloud.df = pointcloud.df.iloc[sorted_indices]

#######################################################################################################
