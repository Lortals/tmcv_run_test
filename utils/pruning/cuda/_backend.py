import glob
import json
import os
import shutil
from subprocess import DEVNULL, call

from rich.console import Console
from torch.utils.cpp_extension import (
  _get_build_directory,
  _import_module_from_library,
  load,
)

PATH = os.path.dirname(os.path.abspath(__file__))
NO_FAST_MATH = os.getenv("NO_FAST_MATH", "0") == "1"
need_to_unset_max_jobs = not os.getenv("MAX_JOBS")
if need_to_unset_max_jobs:
  os.environ["MAX_JOBS"] = "10"


def load_extension(name, sources, extra_cflags=None, extra_cuda_cflags=None,
                   extra_ldflags=None, extra_include_paths=None, build_directory=None):
  if build_directory:
    os.makedirs(build_directory, exist_ok=True)

  try:
    return load(name, sources, extra_cflags=extra_cflags,
                extra_cuda_cflags=extra_cuda_cflags, extra_ldflags=extra_ldflags,
                extra_include_paths=extra_include_paths, build_directory=build_directory)
  except OSError:
    return _import_module_from_library(name, build_directory, True)


def cuda_toolkit_available():
  try:
    call(["nvcc"], stdout=DEVNULL, stderr=DEVNULL)
    return True
  except FileNotFoundError:
    return False


def cuda_toolkit_version():
  cuda_home = os.path.join(os.path.dirname(shutil.which("nvcc")), "..")
  version_txt = os.path.join(cuda_home, "version.txt")
  version_json = os.path.join(cuda_home, "version.json")

  if os.path.exists(version_txt):
    with open(version_txt) as f:
      return f.read().strip().split()[-1]
  elif os.path.exists(version_json):
    with open(version_json) as f:
      return json.load(f)["cuda"]["version"]
  else:
    raise RuntimeError("Cannot find the cuda version.")


_C = None

try:
  from pruning import csrc as _C
except ImportError:
  if cuda_toolkit_available():
    name = "pruning_cuda"
    build_dir = _get_build_directory(name, verbose=False)
    glm_path = os.path.join(PATH, "csrc", "third_party", "glm")

    extra_include_paths = [os.path.join(PATH, "include/"), glm_path]
    extra_cflags = ["-O3"]
    extra_cuda_cflags = ["-O3"] if NO_FAST_MATH else ["-O3", "--use_fast_math"]
    sources = glob.glob(os.path.join(PATH, "csrc/*.cu")) + glob.glob(os.path.join(PATH, "csrc/*.cpp"))

    try:
      os.remove(os.path.join(build_dir, "lock"))
    except OSError:
      pass

    build_exists = os.path.exists(os.path.join(build_dir, "pruning_cuda.so")) or \
                   os.path.exists(os.path.join(build_dir, "pruning_cuda.lib"))

    if not build_exists:
      shutil.rmtree(build_dir, ignore_errors=True)
      with Console().status(
        f"[bold yellow]pruning: Setting up CUDA with MAX_JOBS={os.environ['MAX_JOBS']} (This may take a few minutes the first time)",
        spinner="bouncingBall",
      ):
        _C = load_extension(name, sources, extra_cflags, extra_cuda_cflags,
                           extra_include_paths=extra_include_paths, build_directory=build_dir)
    else:
      _C = load_extension(name, sources, extra_cflags, extra_cuda_cflags,
                         extra_include_paths=extra_include_paths, build_directory=build_dir)
  else:
    Console().print("[yellow]pruning: No CUDA toolkit found. pruning will be disabled.[/yellow]")

if need_to_unset_max_jobs:
  os.environ.pop("MAX_JOBS")


__all__ = ["_C"]
