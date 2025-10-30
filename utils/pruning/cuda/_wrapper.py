from typing import Callable, Optional, Tuple, Any
from typing_extensions import Literal

import torch
from torch import Tensor


def _make_lazy_cuda_func(name: str) -> Callable:
  def call_cuda(*args, **kwargs):
    from ._backend import _C
    return getattr(_C, name)(*args, **kwargs)
  return call_cuda

def _make_lazy_cuda_obj(name: str) -> Any:
  from ._backend import _C
  obj = _C
  for attr in name.split("."):
    obj = getattr(obj, attr)
  return obj

def fully_fused_projection(
  means: Tensor,
  quats: Optional[Tensor],
  scales: Optional[Tensor],
  viewmats: Tensor,
  Ks: Tensor,
  width: int,
  height: int,
  eps2d: float = 0.3,
  near_plane: float = 0.01,
  far_plane: float = 1e10,
  radius_clip: float = 0.0,
  camera_model: Literal["pinhole", "ortho", "fisheye"] = "pinhole",
) -> Tuple[Tensor, Tensor, Tensor, Tensor]:

  C = viewmats.size(0)
  N = means.size(0)
  assert means.size() == (N, 3), means.size()
  assert viewmats.size() == (C, 4, 4), viewmats.size()
  assert Ks.size() == (C, 3, 3), Ks.size()
  means = means.contiguous()

  assert quats is not None, "covars or quats is required"
  assert scales is not None, "covars or scales is required"
  assert quats.size() == (N, 4), quats.size()
  assert scales.size() == (N, 3), scales.size()
  quats = quats.contiguous()
  scales = scales.contiguous()

  viewmats = viewmats.contiguous()
  Ks = Ks.contiguous()

  camera_model_type = _make_lazy_cuda_obj(
    f"CameraModelType.{camera_model.upper()}"
  )

  return _make_lazy_cuda_func("fully_fused_projection_fwd")(
    means,
    quats,
    scales,
    viewmats,
    Ks,
    width,
    height,
    eps2d,
    near_plane,
    far_plane,
    radius_clip,
    camera_model_type,
  )

@torch.no_grad()
def isect_tiles(
  means2d: Tensor,
  radii: Tensor,
  depths: Tensor,
  tile_size: int,
  tile_width: int,
  tile_height: int,
  sort: bool = True,
) -> Tuple[Tensor, Tensor, Tensor]:

  C, N, _ = means2d.shape
  assert means2d.shape == (C, N, 2), means2d.size()
  assert radii.shape == (C, N), radii.size()
  assert depths.shape == (C, N), depths.size()

  tiles_per_gauss, isect_ids, flatten_ids = _make_lazy_cuda_func("isect_tiles")(
    means2d.contiguous(),
    radii.contiguous(),
    depths.contiguous(),
    C,
    tile_size,
    tile_width,
    tile_height,
    sort,
    True,
  )
  return tiles_per_gauss, isect_ids, flatten_ids

@torch.no_grad()
def isect_offset_encode(
  isect_ids: Tensor, n_cameras: int, tile_width: int, tile_height: int
) -> Tensor:
  return _make_lazy_cuda_func("isect_offset_encode")(
    isect_ids.contiguous(), n_cameras, tile_width, tile_height
  )

def rasterize_to_pixels(
  means2d: Tensor,
  conics: Tensor,
  opacities: Tensor,
  image_width: int,
  image_height: int,
  tile_size: int,
  isect_offsets: Tensor,
  flatten_ids: Tensor,
) -> Tuple[Tensor, Tensor, Tensor]:
  C = isect_offsets.size(0)
  N = means2d.size(1)
  assert means2d.shape == (C, N, 2), means2d.shape
  assert conics.shape == (C, N, 3), conics.shape
  assert opacities.shape == (C, N), opacities.shape

  tile_height, tile_width = isect_offsets.shape[1:3]
  assert (
    tile_height * tile_size >= image_height
  ), f"Assert Failed: {tile_height} * {tile_size} >= {image_height}"
  assert (
    tile_width * tile_size >= image_width
  ), f"Assert Failed: {tile_width} * {tile_size} >= {image_width}"

  total_gaussians = C * N
  accum_weight_sum = torch.zeros(total_gaussians, dtype=torch.float32, device=means2d.device)
  accum_pixel_count = torch.zeros(total_gaussians, dtype=torch.int32, device=means2d.device)
  accum_dominant_count = torch.zeros(total_gaussians, dtype=torch.int32, device=means2d.device)

  accum_weight_sum, accum_pixel_count, accum_dominant_count = _make_lazy_cuda_func(
    "rasterize_to_pixels_fwd"
  )(
    means2d.contiguous(),
    conics.contiguous(),
    opacities.contiguous(),
    image_width,
    image_height,
    tile_size,
    isect_offsets.contiguous(),
    flatten_ids.contiguous(),
    accum_weight_sum,
    accum_pixel_count,
    accum_dominant_count
  )

  return accum_weight_sum, accum_pixel_count, accum_dominant_count