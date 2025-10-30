#include "bindings.h"

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    py::enum_<pruning::CameraModelType>(m, "CameraModelType")
        .value("PINHOLE", pruning::CameraModelType::PINHOLE)
        .value("ORTHO", pruning::CameraModelType::ORTHO)
        .value("FISHEYE", pruning::CameraModelType::FISHEYE)
        .export_values();
    

    m.def(
        "fully_fused_projection_fwd", &pruning::fully_fused_projection_fwd_tensor
    );
    
    m.def("isect_tiles", &pruning::isect_tiles_tensor);
    m.def("isect_offset_encode", &pruning::isect_offset_encode_tensor);

    m.def("rasterize_to_pixels_fwd", &pruning::rasterize_to_pixels_fwd_tensor);
    
}
