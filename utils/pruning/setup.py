import os
import pathlib
from setuptools import setup

if "TORCH_CUDA_ARCH_LIST" not in os.environ:
  os.environ["TORCH_CUDA_ARCH_LIST"] = "6.0;6.1;7.0;7.5;8.0;8.6;8.9;9.0"

BUILD_NO_CUDA = os.getenv("BUILD_NO_CUDA", "0") == "1"


def get_extensions():
  try:
    from torch.utils.cpp_extension import CUDAExtension
  except ImportError:
    return []

  this_dir = pathlib.Path(__file__).parent.resolve()
  cuda_dir = this_dir / "cuda"

  sources = list(cuda_dir.glob("csrc/*.cu")) + list(cuda_dir.glob("csrc/*.cpp"))
  sources = [str(s.relative_to(this_dir)) for s in sources if "hip" not in str(s)]

  if not sources:
    return []

  include_dirs = [
    str(cuda_dir / "csrc" / "third_party" / "glm"),
    str(cuda_dir / "include"),
    str(cuda_dir / "csrc"),
  ]

  return [CUDAExtension(
    name="pruning.csrc",
    sources=sources,
    include_dirs=include_dirs,
    extra_compile_args={
      "cxx": ["-O3"],
      "nvcc": ["-O3", "--use_fast_math", "--expt-relaxed-constexpr"]
    },
  )]


def get_cmdclass():
  if BUILD_NO_CUDA:
    return {}
  try:
    from torch.utils.cpp_extension import BuildExtension
    return {"build_ext": BuildExtension.with_options(no_python_abi_suffix=True, use_ninja=True)}
  except ImportError:
    return {}


setup(
  name="pruning",
  version="0.1.0",
  description="CUDA pruning operations for gaussian splatting",
  python_requires=">=3.7",
  install_requires=["torch", "ninja", "rich"],
  ext_modules=get_extensions() if not BUILD_NO_CUDA else [],
  cmdclass=get_cmdclass(),
  packages=["pruning", "pruning.cuda"],
  package_dir={"pruning": ".", "pruning.cuda": "cuda"},
  package_data={"pruning": ["*.so", "*.pyd"], "pruning.cuda": ["*.so", "*.pyd"]},
  include_package_data=True,
  zip_safe=False,
)
