import math
import numpy as np
import torch
from torch import Tensor
from typing import Tuple
from typing_extensions import Literal

from .cuda._wrapper import (
    fully_fused_projection,
    isect_offset_encode,
    isect_tiles,
    rasterize_to_pixels
)

#######################################################################################################

def calculate_importance_score(pc, cams):
  device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

  means = torch.tensor(pc.df[['x', 'y', 'z']].values, dtype=torch.float32, device=device)
  quats = torch.tensor(pc.df[['rot_0', 'rot_1', 'rot_2', 'rot_3']].values, dtype=torch.float32, device=device)
  scales = torch.exp(torch.tensor(pc.df[['scale_0', 'scale_1', 'scale_2']].values, dtype=torch.float32, device=device))
  opacities = torch.sigmoid(torch.tensor(pc.df['opacity'].values, dtype=torch.float32, device=device))

  total_importance = torch.zeros(len(means), device=device)

  for cam_idx, cam2world in enumerate(cams.camtoworlds):
    world2cam = torch.tensor(np.linalg.inv(cam2world[None, ...]), dtype=torch.float32, device=device)
    cam_id = list(cams.Ks_dict.keys())[min(cam_idx, len(cams.Ks_dict) - 1)]
    K = torch.tensor(cams.Ks_dict[cam_id], dtype=torch.float32, device=device).unsqueeze(0)
    width, height = cams.image_sizes[cam_id]

    weights, _, _ = rasterize_gaussians(means, quats, scales, opacities, world2cam, K, width, height)
    total_importance += weights

  return total_importance.cpu().numpy()


#######################################################################################################

def prune_by_cdf_threshold(pc, cdf_thr, verbose=False):
  scores = pc.df['importance_score'].values
  device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

  if cdf_thr < 1.0:
    scores_tensor = torch.tensor(scores, dtype=torch.float32, device=device)
    sorted_vals, _ = torch.sort(scores_tensor.flatten() + 1e-6)
    cum_sum = torch.cumsum(sorted_vals, dim=0)
    thr_idx = ((cum_sum / sorted_vals.sum()) > (1 - cdf_thr)).nonzero().min()
    mask = (scores_tensor > sorted_vals[thr_idx]).cpu().numpy()
  else:
    mask = np.ones(len(scores), dtype=bool)

  num_before = len(scores)
  num_after = mask.sum()
  num_pruned = num_before - num_after
  prune_pct = (num_pruned / num_before * 100) if num_before > 0 else 0

  if verbose:
    print("[Pruning] %d / %d gaussians pruned (%.1f%%)" % (num_pruned, num_before, prune_pct))

  pc.df = pc.df[mask].reset_index(drop=True)
  pc.df['importance_score'] = scores[mask]

#######################################################################################################

def rasterize_gaussians(
  means: Tensor,
  quats: Tensor,
  scales: Tensor,
  opacities: Tensor,
  viewmats: Tensor,
  Ks: Tensor,
  width: int,
  height: int,
  near_plane: float = 0.01,
  far_plane: float = 1e10,
  radius_clip: float = 0.0,
  eps2d: float = 0.3,
  tile_size: int = 16,
  camera_model: Literal["pinhole", "ortho", "fisheye"] = "pinhole",
) -> Tuple[Tensor, Tensor, Tensor]:

  N = means.shape[0]
  C = viewmats.shape[0]

  assert means.shape == (N, 3), means.shape
  assert quats.shape == (N, 4), quats.shape
  assert scales.shape == (N, 3), scales.shape
  assert opacities.shape == (N,), opacities.shape
  assert viewmats.shape == (C, 4, 4), viewmats.shape
  assert Ks.shape == (C, 3, 3), Ks.shape

  radii, means2d, depths, conics = fully_fused_projection(
    means,
    quats,
    scales,
    viewmats,
    Ks,
    width,
    height,
    eps2d=eps2d,
    near_plane=near_plane,
    far_plane=far_plane,
    radius_clip=radius_clip,
    camera_model=camera_model,
  )

  opacities = opacities.repeat(C, 1)

  tile_w = math.ceil(width / float(tile_size))
  tile_h = math.ceil(height / float(tile_size))

  _, isect_ids, flat_ids = isect_tiles(means2d, radii, depths, tile_size, tile_w, tile_h)

  isect_offsets = isect_offset_encode(isect_ids, C, tile_w, tile_h)

  weights, px_counts, dom_counts = rasterize_to_pixels(
    means2d,
    conics,
    opacities,
    width,
    height,
    tile_size,
    isect_offsets,
    flat_ids
  )

  return weights, px_counts, dom_counts

#######################################################################################################
