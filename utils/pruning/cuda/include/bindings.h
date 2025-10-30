#ifndef GSPLAT_CUDA_BINDINGS_H
#define GSPLAT_CUDA_BINDINGS_H

#include <c10/cuda/CUDAGuard.h>
#include <torch/extension.h>
#include <tuple>

#define GSPLAT_N_THREADS 256

#define GSPLAT_CHECK_CUDA(x)                                                   \
    TORCH_CHECK(x.is_cuda(), #x " must be a CUDA tensor")
#define GSPLAT_CHECK_CONTIGUOUS(x)                                             \
    TORCH_CHECK(x.is_contiguous(), #x " must be contiguous")
#define GSPLAT_CHECK_INPUT(x)                                                  \
    GSPLAT_CHECK_CUDA(x);                                                      \
    GSPLAT_CHECK_CONTIGUOUS(x)
#define GSPLAT_DEVICE_GUARD(_ten)                                              \
    const at::cuda::OptionalCUDAGuard device_guard(device_of(_ten));

#define GSPLAT_PRAGMA_UNROLL _Pragma("unroll")

// https://github.com/pytorch/pytorch/blob/233305a852e1cd7f319b15b5137074c9eac455f6/aten/src/ATen/cuda/cub.cuh#L38-L46
#define GSPLAT_CUB_WRAPPER(func, ...)                                          \
    do {                                                                       \
        size_t temp_storage_bytes = 0;                                         \
        func(nullptr, temp_storage_bytes, __VA_ARGS__);                        \
        auto &caching_allocator = *::c10::cuda::CUDACachingAllocator::get();   \
        auto temp_storage = caching_allocator.allocate(temp_storage_bytes);    \
        func(temp_storage.get(), temp_storage_bytes, __VA_ARGS__);             \
    } while (false)

namespace pruning {

enum CameraModelType
{
    PINHOLE = 0,
    ORTHO = 1,
    FISHEYE = 2,
};


std::tuple<
    torch::Tensor,
    torch::Tensor,
    torch::Tensor,
    torch::Tensor>
fully_fused_projection_fwd_tensor(
    const torch::Tensor &means,
    const torch::Tensor &quats,
    const torch::Tensor &scales,
    const torch::Tensor &viewmats,
    const torch::Tensor &Ks,
    const uint32_t image_width,
    const uint32_t image_height,
    const float eps2d,
    const float near_plane,
    const float far_plane,
    const float radius_clip,
    const CameraModelType camera_model
);

std::tuple<torch::Tensor, torch::Tensor, torch::Tensor> isect_tiles_tensor(
    const torch::Tensor &means2d,
    const torch::Tensor &radii,
    const torch::Tensor &depths,
    const uint32_t C,
    const uint32_t tile_size,
    const uint32_t tile_width,
    const uint32_t tile_height,
    const bool sort,
    const bool double_buffer
);

torch::Tensor isect_offset_encode_tensor(
    const torch::Tensor &isect_ids,
    const uint32_t C,
    const uint32_t tile_width,
    const uint32_t tile_height
);

std::tuple<torch::Tensor, torch::Tensor, torch::Tensor>
rasterize_to_pixels_fwd_tensor(
    const torch::Tensor &means2d,
    const torch::Tensor &conics,
    const torch::Tensor &opacities,
    
    const uint32_t image_width,
    const uint32_t image_height,
    const uint32_t tile_size,

    const torch::Tensor &tile_offsets,
    const torch::Tensor &flatten_ids,

    const torch::Tensor &accum_weight_sum,
    const torch::Tensor &accum_pixel_count,
    const torch::Tensor &accum_dominant_count
);
}

#endif
