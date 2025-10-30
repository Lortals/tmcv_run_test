#include "bindings.h"
#include "types.cuh"
#include <cooperative_groups.h>
#include <cub/cub.cuh>
#include <cuda_runtime.h>

namespace pruning {

namespace cg = cooperative_groups;

/****************************************************************************
 * Rasterization to Pixels Forward Pass
 ****************************************************************************/

__global__ void rasterize_to_pixels_fwd_kernel(
    const uint32_t C,
    const uint32_t N,
    const uint32_t n_isects,
    const vec2<float> *__restrict__ means2d, // [C, N, 2]
    const vec3<float> *__restrict__ conics,  // [C, N, 3]
    const float *__restrict__ opacities,     // [C, N]
    const uint32_t image_width,
    const uint32_t image_height,
    const uint32_t tile_size,
    const uint32_t tile_width,
    const uint32_t tile_height,
    const int32_t *__restrict__ tile_offsets, // [C, tile_height, tile_width]
    const int32_t *__restrict__ flatten_ids,  // [n_isects]
    float* __restrict__ accum_weight_sum,
    int* __restrict__ accum_pixel_count, 
    int* __restrict__ accum_dominant_count
) {
    // Each thread processes one pixel and shares Gaussian loading

    auto block = cg::this_thread_block();
    int32_t camera_id = block.group_index().x;
    int32_t tile_id =
        block.group_index().y * tile_width + block.group_index().z;
    uint32_t i = block.group_index().y * tile_size + block.thread_index().y;
    uint32_t j = block.group_index().z * tile_size + block.thread_index().x;

    tile_offsets += camera_id * tile_height * tile_width;

    float px = (float)j + 0.5f;
    float py = (float)i + 0.5f;

    // Check if pixel is within image bounds
    bool inside = (i < image_height && j < image_width);
    bool done = !inside;

    // Process Gaussians in batches for this tile
    int32_t range_start = tile_offsets[tile_id];
    int32_t range_end =
        (camera_id == C - 1) && (tile_id == tile_width * tile_height - 1)
            ? n_isects
            : tile_offsets[tile_id + 1];
    const uint32_t block_size = block.size();
    uint32_t num_batches =
        (range_end - range_start + block_size - 1) / block_size;

    extern __shared__ int s[];
    int32_t *id_batch = (int32_t *)s; // [block_size]
    vec3<float> *xy_opacity_batch =
        reinterpret_cast<vec3<float> *>(&id_batch[block_size]); // [block_size]
    vec3<float> *conic_batch =
        reinterpret_cast<vec3<float> *>(&xy_opacity_batch[block_size]
        ); // [block_size]

    float T = 1.0f;

    // Process Gaussians in batches
    uint32_t tr = block.thread_rank();

    float max_vis = 0.f;
    int32_t strong_gaussian = -1;
    for (uint32_t b = 0; b < num_batches; ++b) {
        // Early exit if entire tile is done
        if (__syncthreads_count(done) >= block_size) {
            break;
        }

        // Load Gaussian data for this batch
        uint32_t batch_start = range_start + block_size * b;
        uint32_t idx = batch_start + tr;
        if (idx < range_end) {
            int32_t g = flatten_ids[idx];
            id_batch[tr] = g;
            const vec2<float> xy = means2d[g];
            const float opac = opacities[g];
            xy_opacity_batch[tr] = {xy.x, xy.y, opac};
            conic_batch[tr] = conics[g];
        }

        // Wait for all threads to load Gaussian data
        block.sync();

        // Process each Gaussian in the batch
        uint32_t batch_size = min(block_size, range_end - batch_start);
        for (uint32_t t = 0; (t < batch_size) && !done; ++t) {
            const vec3<float> conic = conic_batch[t];
            const vec3<float> xy_opac = xy_opacity_batch[t];
            const float opac = xy_opac.z;
            const vec2<float> delta = {xy_opac.x - px, xy_opac.y - py};
            const float sigma = 0.5f * (conic.x * delta.x * delta.x +
                                    conic.z * delta.y * delta.y) +
                            conic.y * delta.x * delta.y;
            float alpha = min(0.999f, opac * __expf(-sigma));
            if (sigma < 0.f || alpha < 1.f / 255.f) {
                continue;
            }

            const float next_T = T * (1.0f - alpha);
            if (next_T <= 1e-4) { // pixel saturated
                done = true;
                break;
            }

            int32_t g = id_batch[t];
            const float vis = alpha * T;

            if (inside) {
                atomicAdd(&accum_weight_sum[g], vis);
                atomicAdd(&accum_pixel_count[g], 1);
            }
            
            if (vis > max_vis) {
                max_vis = vis;
                strong_gaussian = g;
            }

            T = next_T;
        }
        
    }

    if (inside) {
        if (strong_gaussian >= 0) {
            atomicAdd(&accum_dominant_count[strong_gaussian], 1);
        }
    }

}

std::tuple<torch::Tensor, torch::Tensor, torch::Tensor> call_kernel_with_dim(
    // Gaussian parameters
    const torch::Tensor &means2d,   // [C, N, 2]
    const torch::Tensor &conics,    // [C, N, 3]
    const torch::Tensor &opacities, // [C, N]
    // image size
    const uint32_t image_width,
    const uint32_t image_height,
    const uint32_t tile_size,
    // intersections
    const torch::Tensor &tile_offsets, // [C, tile_height, tile_width]
    const torch::Tensor &flatten_ids,   // [n_isects]

    const torch::Tensor &accum_weight_sum,
    const torch::Tensor &accum_pixel_count,
    const torch::Tensor &accum_dominant_count
) {
    GSPLAT_DEVICE_GUARD(means2d);
    GSPLAT_CHECK_INPUT(means2d);
    GSPLAT_CHECK_INPUT(conics);
    GSPLAT_CHECK_INPUT(opacities);
    GSPLAT_CHECK_INPUT(tile_offsets);
    GSPLAT_CHECK_INPUT(flatten_ids);
    uint32_t C = tile_offsets.size(0);         // number of cameras
    uint32_t N = means2d.size(1); // number of gaussians
    uint32_t tile_height = tile_offsets.size(1);
    uint32_t tile_width = tile_offsets.size(2);
    uint32_t n_isects = flatten_ids.size(0);

    // Each block covers a tile on the image. In total there are
    // C * tile_height * tile_width blocks.
    dim3 threads = {tile_size, tile_size, 1};
    dim3 blocks = {C, tile_height, tile_width};

    at::cuda::CUDAStream stream = at::cuda::getCurrentCUDAStream();
    const uint32_t shared_mem =
        tile_size * tile_size *
        (sizeof(int32_t) + sizeof(vec3<float>) + sizeof(vec3<float>));

    if (cudaFuncSetAttribute(
            rasterize_to_pixels_fwd_kernel,
            cudaFuncAttributeMaxDynamicSharedMemorySize,
            shared_mem
        ) != cudaSuccess) {
        AT_ERROR(
            "Failed to set maximum shared memory size (requested ",
            shared_mem,
            " bytes), try lowering tile_size."
        );
    }
    rasterize_to_pixels_fwd_kernel
        <<<blocks, threads, shared_mem, stream>>>(
            C,
            N,
            n_isects,
            reinterpret_cast<vec2<float> *>(means2d.data_ptr<float>()),
            reinterpret_cast<vec3<float> *>(conics.data_ptr<float>()),
            opacities.data_ptr<float>(),
            image_width,
            image_height,
            tile_size,
            tile_width,
            tile_height,
            tile_offsets.data_ptr<int32_t>(),
            flatten_ids.data_ptr<int32_t>(),
            accum_weight_sum.data_ptr<float>(),
            accum_pixel_count.data_ptr<int>(),
            accum_dominant_count.data_ptr<int>()
        );

    return std::make_tuple(accum_weight_sum, accum_pixel_count, accum_dominant_count);
}

std::tuple<torch::Tensor, torch::Tensor, torch::Tensor>
rasterize_to_pixels_fwd_tensor(
    // Gaussian parameters
    const torch::Tensor &means2d,   // [C, N, 2]
    const torch::Tensor &conics,    // [C, N, 3]
    const torch::Tensor &opacities, // [C, N]
    // image size
    const uint32_t image_width,
    const uint32_t image_height,
    const uint32_t tile_size,
    // intersections
    const torch::Tensor &tile_offsets, // [C, tile_height, tile_width]
    const torch::Tensor &flatten_ids,   // [n_isects]

    const torch::Tensor &accum_weight_sum,
    const torch::Tensor &accum_pixel_count,
    const torch::Tensor &accum_dominant_count
) {
    return call_kernel_with_dim(
        means2d,
        conics,
        opacities,
        image_width,
        image_height,
        tile_size,
        tile_offsets,
        flatten_ids,
        accum_weight_sum,
        accum_pixel_count,
        accum_dominant_count
    );
}

} // namespace gsplat