# 项目详细分析报告：MPEG GSC Test Model Candidate Video (TMCV)

## 1. 项目概述

本项目是 **MPEG GSC (Gaussian Splatting Compression) 测试模型**的 Python 实现，版本号 v2.0（MPEG 152）。核心目标是将 **3D Gaussian Splatting（3DGS）** 点云文件（`.ply` 格式）编码进 **V3C（Video-based 3D Compression）** 码流，并支持解码还原。

> 3DGS 是一种新兴的三维场景表示方法，使用数百万个三维高斯椭球体来重建真实场景。本项目将高斯点云的各属性映射为视频帧，借助成熟的视频编解码标准（HEVC/HM、VVC/VTM、H.264/x264）进行压缩。

---

## 2. 项目目录结构

```
tmcv_run_test/
├── encode.py                    # 编码入口（主程序）
├── decode.py                    # 解码入口（主程序）
├── collect_results.py           # 结果收集脚本
├── generate_summary_table.py    # 生成摘要表格
├── version.txt                  # 版本说明
├── requirements.txt             # Python 依赖
├── environment.yml              # Conda 环境配置
├── LICENCE                      # 许可证
├── README.md                    # 使用文档
│
├── cfg/                         # 编码配置文件目录
│   ├── ffmpeg/                  # FFMPEG 编码器配置
│   ├── hm/                      # HM (HEVC) 编码器配置
│   │   └── ctc/                 # CTC 测试配置
│   └── vtm/                     # VTM (VVC) 编码器配置
│
├── scripts/                     # 辅助脚本
│   ├── install_dependencies.sh  # 安装 HM/VTM 编码器
│   ├── test_float.sh            # 浮点精度测试
│   └── test_quantize.sh         # 量化精度测试
│
├── anchor_run/
│   └── tmcv_run_ctc.py          # CTC 基准测试运行脚本（多 GPU 并行）
│
└── utils/                       # 核心工具模块
    ├── common.py                # 通用工具函数
    ├── pointcloud.py            # 点云数据结构与操作
    ├── group_of_pointclouds.py  # 多帧点云分组管理
    ├── group_of_frames.py       # 核心编解码逻辑（帧组）
    ├── video_data.py            # 单路视频数据管理
    ├── video.py                 # 底层 YUV 视频 I/O
    ├── video_codec.py           # 视频编解码器接口（HM/VTM/FFMPEG）
    ├── bitstream.py             # 码流读写（基于 bitarray）
    ├── cameras.py               # COLMAP 相机参数读取
    ├── stat.py                  # 码流统计与日志
    ├── plas.py                  # PLAS 空间排序封装
    ├── generate_detailed_summary.py
    │
    ├── v3c/                     # V3C 码流格式实现
    │   ├── type.py              # 枚举类型定义
    │   ├── v3c_unit.py          # V3C 单元结构
    │   ├── v3c_parameter_set.py # VPS 参数集
    │   ├── sample_stream_v3c_unit.py
    │   ├── atlas_sub_bitstream.py
    │   ├── video_sub_bitstream.py
    │   ├── nal_unit.py
    │   ├── profile_level_tier.py
    │   ├── vps_extension.py     # VPS GSC 扩展
    │   ├── vps_gsc_extension.py
    │   └── sei/                 # SEI 消息（参数元数据）
    │       ├── sei.py
    │       ├── sei_rbsp.py
    │       ├── sei_message.py
    │       ├── component_codec_mapping.py  # 视频-组件映射
    │       ├── gsc_registered.py           # GSC 量化参数
    │       ├── dequantization_mapping_registered.py
    │       ├── video_type_mapping_registered.py
    │       ├── input_camera_information.py
    │       └── trans_sh_ac_registered.py   # SH AC 变换参数
    │
    └── pruning/                 # CUDA 高斯剪枝模块
        ├── pruning.py           # 重要度计算 + CDF 剪枝
        ├── setup.py             # CUDA 扩展编译
        └── cuda/
            ├── _backend.py
            ├── _wrapper.py
            └── csrc/            # CUDA C++ 源码（高斯光栅化）
                ├── ext.cpp
                ├── fully_fused_projection_fwd.cu
                ├── isect_tiles.cu
                └── rasterize_to_pixels_fwd.cu
```

---

## 3. 核心数据类型

### 3.1 3DGS 点云属性

每个高斯点（Gaussian）包含以下属性，全部存储在 `Pointcloud.df`（pandas DataFrame）中：

| 属性名 | 维度 | 含义 |
|--------|------|------|
| `x, y, z` | 3 | 空间位置（坐标） |
| `nx, ny, nz` | 3 | 法向量（通常为零，保留用） |
| `opacity` | 1 | 不透明度（sigmoid 激活前） |
| `scale_0, scale_1, scale_2` | 3 | 各轴缩放（log 空间） |
| `rot_0, rot_1, rot_2, rot_3` | 4 | 四元数旋转（w, x, y, z） |
| `f_dc_0, f_dc_1, f_dc_2` | 3 | 球谐函数 DC 项（颜色） |
| `f_rest_0` … `f_rest_44` | 45 | 球谐函数 AC 高阶项 |

总计：**59 个浮点属性**（3DGS 标准格式）

### 3.2 V3C 单元类型（`V3CUnitType`）

- `V3C_VPS`：序列参数集（全局配置）
- `V3C_AD`：图集子码流（含 SEI 消息）
- `V3C_GSC_0` … `V3C_GSC_20`：21 路 GSC 视频数据流，每路对应一组高斯属性

---

## 4. 编码流程（encode.py）

```
输入：多帧 .ply 文件

 ┌─────────────────────────────────────────────────┐
 │  第一步：读取点云 (GroupOfPointclouds)              │
 │  - 逐帧读取 .ply 文件（trimesh 解析）              │
 │  - 可选：从 COLMAP 读取相机参数                    │
 └────────────────────┬────────────────────────────┘
                      ↓
 ┌─────────────────────────────────────────────────┐
 │  第二步：预处理                                   │
 │  a. 高斯剪枝（可选 --gaussian_pruning）           │
 │     - 利用 CUDA 光栅化计算每个高斯的重要度         │
 │     - 按 CDF 阈值过滤低重要度高斯                  │
 │  b. 协方差归一化（可选 --cov_norm=1）              │
 │     - 对 scale/rotation 进行排序归一化             │
 │  c. YUV 颜色转换（可选 --src_sh_conversion）      │
 │     - 将球谐 RGB 转为 YUV（BT.601/709/2020）      │
 │  d. SH AC PCA 变换（可选 --trans_sh_ac=pca）      │
 │     - 对 f_rest_* 做 PCA 降维                     │
 └────────────────────┬────────────────────────────┘
                      ↓
 ┌─────────────────────────────────────────────────┐
 │  第三步：PLAS 空间排序 (sort)                      │
 │  - 将高斯点裁剪至最小块大小的整数倍（sidelen²）    │
 │  - 使用 PLAS 算法按属性相似性排列点云              │
 │  - 目的：提升 2D 视频编码效率（相邻像素相关性）    │
 └────────────────────┬────────────────────────────┘
                      ↓
 ┌─────────────────────────────────────────────────┐
 │  第四步：量化 (quantize)                          │
 │  - Linear 量化：线性拉伸到 [0, 2^bitdepth-1]      │
 │  - Gaussian 量化：按高斯分布归一化                  │
 │  - 位置属性高精度分拆：MSB（x,y,z）+ LSB（x_add）  │
 │  - 位置坐标可选 signed log 变换                    │
 └────────────────────┬────────────────────────────┘
                      ↓
 ┌─────────────────────────────────────────────────┐
 │  第五步：打包为视频帧 (pack_one_frame)             │
 │  - Planar 模式：各属性占据不同行，一次性写成图像   │
 │  - Temporal 模式：各属性分配为独立视频帧            │
 │  - 支持 YUV400（灰度）、YUV420、YUV444 格式        │
 └────────────────────┬────────────────────────────┘
                      ↓
 ┌─────────────────────────────────────────────────┐
 │  第六步：视频编码（多线程并行）                   │
 │  - HM（HEVC 参考软件）                            │
 │  - VTM（VVC 参考软件，可选高位深 VTM-Rext）        │
 │  - FFMPEG（x264/x265）                            │
 │  每路视频独立编码，读取 .bin 码流                  │
 └────────────────────┬────────────────────────────┘
                      ↓
 ┌─────────────────────────────────────────────────┐
 │  第七步：写入 V3C 码流 (.v3c)                     │
 │  - 写入 VPS（含 GSC 扩展、量化映射 SEI 等）       │
 │  - 写入各路 V3C_GSC_* 单元                        │
 │  - 写入 V3C_AD（含 SEI 消息：组件映射、去量化）   │
 └────────────────────┬────────────────────────────┘
                      ↓
输出：.v3c 码流文件，_rec.ply 重建文件
```

---

## 5. 解码流程（decode.py）

```
输入：.v3c 码流文件

 ┌─────────────────────────────────────────────────┐
 │  第一步：读取 V3C 码流 (GroupOfFrames.read)        │
 │  - 解析 VPS、GSC 扩展参数                         │
 │  - 解析 SEI 消息（量化参数、组件映射等）           │
 │  - 提取各路视频压缩码流                            │
 └────────────────────┬────────────────────────────┘
                      ↓
 ┌─────────────────────────────────────────────────┐
 │  第二步：视频解码（多线程并行）                   │
 │  - 调用对应解码器（HM/VTM/FFMPEG）                │
 │  - 将压缩视频还原为 YUV 格式                      │
 └────────────────────┬────────────────────────────┘
                      ↓
 ┌─────────────────────────────────────────────────┐
 │  第三步：色度上采样（YUV420 → YUV444，如适用）    │
 └────────────────────┬────────────────────────────┘
                      ↓
 ┌─────────────────────────────────────────────────┐
 │  第四步：后处理                                   │
 │  a. YUV → RGB 球谐反变换                         │
 │  b. 去量化（dequantize）：还原浮点属性值           │
 │  c. SH AC PCA 逆变换（若编码时启用）               │
 │  d. 色彩空间反转换（若编码时启用 src_sh_conversion）│
 │  e. 四元数重建（w（rot_0）设为 √2/2 初始值，归一化）  │
 └────────────────────┬────────────────────────────┘
                      ↓
 ┌─────────────────────────────────────────────────┐
 │  第五步：写出 .ply 文件                           │
 │  - 保留相机位置注释（若原始文件包含）              │
 └────────────────────┬────────────────────────────┘
                      ↓
输出：_dec.ply 解码文件
```

---

## 6. 关键模块详解

### 6.1 `Pointcloud`（`utils/pointcloud.py`）

**职责**：单帧 3DGS 点云的读写、属性变换。

**主要方法**：

| 方法 | 说明 |
|------|------|
| `read(path, index)` | 读取 PLY 文件（trimesh 解析），支持 `%04d` 格式路径 |
| `write(path, index, ascii)` | 写出 PLY 文件，保留相机位置注释 |
| `rgb2yuv / yuv2rgb` | 球谐系数 RGB↔YUV 颜色空间转换（浮点和 uint16） |
| `normalize_scale_rotation` | 对 scale 排序 + 相应旋转补偿 + 四元数 w=√2/2 归一化 |
| `reconstruct_quat` | 解码时从 x,y,z 三分量重建完整四元数 |
| `trans_sh_ac` | 对 f_rest 球谐系数做 PCA 降维 |
| `inv_trans_sh_ac` | PCA 逆变换还原球谐系数 |
| `prune_by_importance` | 按重要度分数剪枝高斯 |

**相机位置**：从 PLY 文件头部的 `comment camera_position` 行读取并缓存于 `camera_df`。

### 6.2 `GroupOfFrames`（`utils/group_of_frames.py`）

**职责**：管理一组帧的视频编解码状态，负责编解码全流程的数据流转。

**核心功能**：
- 创建和管理多路 `VideoData` 对象（对应不同属性组）
- `set_video`：将点云属性打包进视频帧
- `quantize / dequantize`：量化和反量化（含 MSB/LSB 位置分拆）
- `yuv2rgb`：YUV 到 RGB 转换
- `upsample`：YUV420 色度上采样
- `write / read`：V3C 码流的序列化与反序列化
- `get_pointcloud`：从视频帧提取重建点云

### 6.3 `VideoData`（`utils/video_data.py`）

**职责**：单路视频的属性配置、数据存储、量化/反量化逻辑。

**四个视频缓冲区**：
- `video_src`：原始浮点值
- `video_uint`：量化后整数值（送入编码器）
- `video_dec`：解码器输出的重建整数值
- `video_res`：反量化后浮点值

**打包模式（Packing）**：
- **Planar**：每个属性各占一行（或网格的一格），所有属性放在同一帧中
- **Temporal**：每个属性占一个独立视频帧（按时间轴展开）

### 6.4 V3C 码流层（`utils/v3c/`）

实现了 ISO/IEC 23090-5（V3C）标准的码流格式的子集，扩展了 GSC 相关的自定义单元类型和 SEI 消息：

**SEI 消息**：
- `component_codec_mapping`：记录各视频编码器类型（HM/VTM/FFMPEG）
- `gsc_registered`：GSC 量化参数（min/max/center/sigma）
- `dequantization_mapping_registered`：去量化映射
- `video_type_mapping_registered`：视频类型到属性的映射
- `trans_sh_ac_registered`：PCA 变换参数（basis、mean、std）
- `input_camera_information`：相机位置信息

**码流结构**（`write` 方法写出顺序）：
```
SampleStreamV3CUnit:
  [V3C_VPS]     ← 全局参数（帧数、fps、block_size、编码器列表、GSC扩展）
  [V3C_AD]      ← SEI 消息（量化参数、组件映射等元数据）
  [V3C_GSC_0]   ← 第 0 路视频码流
  [V3C_GSC_1]   ← 第 1 路视频码流
  ...
  [V3C_GSC_N]   ← 第 N 路视频码流
```

### 6.5 视频编解码接口（`utils/video_codec.py`）

**支持的编解码器**：

| 标识符 | 编码器 | 特点 |
|--------|--------|------|
| `hm`   | HM（HEVC 参考软件） | 高压缩效率，速度较慢 |
| `hmr`  | HM-Rext 变体 | 支持高位深 RExt |
| `hmd`  | HM 另一变体 | |
| `vtm`  | VTM（VVC 参考软件） | 最高压缩效率 |
| `vtr`  | VTM-Rext | 高位深支持 VVC |
| `x264` | FFmpeg libx264 | 速度快，编码质量略低 |
| `x265` | FFmpeg libx265 | 速度中等 |

编解码器二进制路径通过 `dependencies/binary_path.json` 配置（由 `install_dependencies.sh` 生成）。

### 6.6 PLAS 排序（`utils/plas.py`）

**PLAS**（Parallel Local Assignment Sort，来自 Fraunhofer HHI）将高斯点以2D网格排列，使空间相近的点在视频帧中也相邻，大幅提升视频编码的压缩率。

**流程**：
1. 按 GoF 最小帧数裁剪，使点数为 `min_block_size` 的倍数的平方
2. 将选定属性（位置、颜色等）归一化为张量
3. 调用 `sort_with_plas` 得到排序索引
4. 重排点云 DataFrame

**文件锁**（`FileLock`）：防止多进程同时使用同一 GPU 进行 PLAS 排序时冲突。

### 6.7 高斯剪枝模块（`utils/pruning/`）

使用自定义 CUDA 内核实现高斯光栅化，计算每个高斯对所有相机视角的渲染贡献（重要度分数），然后按 CDF 阈值剪枝低重要度的高斯。

**CUDA 内核**：
- `fully_fused_projection_fwd.cu`：高斯投影到 2D
- `isect_tiles.cu`：高斯与图像瓦片的求交
- `rasterize_to_pixels_fwd.cu`：alpha 合成渲染

---

## 7. 配置文件系统

配置文件采用简单的 `key: value` 格式，通过 `-c` 参数传入，会展开为命令行参数。

### 典型配置（以 `cfg/hm/ctc/cfg_3_videos.cfg` 为代表）

一套编码通常将属性分配到 2～8 路视频：

| 视频路 | 典型属性 | 说明 |
|--------|----------|------|
| Video 0 | `x, y, z` + `x_add, y_add, z_add` | 位置（高精度分拆） |
| Video 1 | `opacity, scale_0..2, rot_1..3` | 几何属性 |
| Video 2 | `f_dc_0..2, f_rest_0..44` | 颜色和球谐 |

### 视频参数一览

| 参数 | 含义 | 典型值 |
|------|------|--------|
| `--bd_N` | 第 N 路视频位深 | 8, 9, 10 |
| `--qp_N` | 量化参数 | 0（无损）~32 |
| `--format_N` | 色彩格式 | `yuv400`, `yuv420`, `yuv444` |
| `--packing_N` | 打包方式 | `planar`, `temporal` |
| `--codec_N` | 编码器 | `hm`, `vtm`, `x264`, `x265` |
| `--comp_N` | 属性列表 | `x,y,z` 等 |

---

## 8. CTC 基准测试运行脚本（`anchor_run/tmcv_run_ctc.py`）

该脚本用于大规模并行 CTC（Common Test Conditions）测试，特点：

- **多 GPU 调度**：使用队列动态分配 GPU（可配置 GPU 列表和每 GPU 并发任务数）
- **测试序列**：支持 9 类场景（bartender、cinema、breakfast 等）
- **5 个码率点（RP1~RP5）**：覆盖高码率（无损近似）到低码率的压缩范围
- **自动化流程**：编码 → 解码 → 质量评估（mpeg-gsc-metrics）
- **断点续跑**：通过检查日志文件末尾是否有 `Time:` 行判断是否已完成
- **CSV 日志**：将各测试结果写入 CSV 文件

---

## 9. 版本历史与主要功能（`version.txt`）

### MPEG 152（v2.0）主要新增功能

| 贡献编号 | 功能描述 |
|----------|----------|
| m74520 | 色度下采样（YUV 420）、YUV 颜色转换、可配置 MSB/LSB 位深 |
| m74046 | 矩形排序（`--rectangular_sorting`） |
| m74048 | 基于重要度的高斯剪枝（`--gaussian_pruning`） |
| m74049 | PCA 降维（基础实现） |
| m74243 | SH AC 系数低秩近似（`--trans_sh_ac=pca`） |

### MPEG 151（v1.0）
- 首个版本

---

## 10. 依赖关系

### Python 依赖（`requirements.txt`）

| 库 | 版本 | 用途 |
|----|------|------|
| `numpy` | 1.26 | 数值计算 |
| `pandas` | 2.2 | 点云属性 DataFrame |
| `torch` | 2.4.0 | PLAS 排序、CUDA 剪枝 |
| `torchvision` | 0.19 | 图像处理辅助 |
| `plyfile` | 1.1 | PLY 文件写出 |
| `trimesh` | - | PLY 文件读取 |
| `ffmpeg-python` | - | FFMPEG 接口 |
| `bitarray` | - | 码流位操作 |
| `scipy` | 1.14 | 科学计算 |
| `plas` | - | PLAS 排序算法（GitHub 安装） |

### 外部软件依赖

| 软件 | 用途 |
|------|------|
| `HM` | HEVC 参考编解码器 |
| `VTM` | VVC 参考编解码器（含 RExt 高位深变体） |
| `FFmpeg` | x264/x265 编解码 |
| `mpeg-gsc-metrics` | 质量评估（PSNR 等指标） |
| `mpeg-3d-renderer` | 3DGS 渲染可视化 |
| `mpeg-gsc-tools` | 相机位置添加等预处理工具 |

---

## 11. 关键算法总结

### 11.1 坐标变换

位置坐标（`x, y, z`）可进行 signed-log 变换：
```python
y = sign(x) * log(1 + |x|)   # 编码时
x = sign(y) * (exp(|y|) - 1)  # 解码时
```
目的：压缩动态范围，使大值和小值都得到较精确的量化。

### 11.2 四元数归一化（`normalize_scale_rotation`）

将 scale 按大小排序（s0 ≥ s1 ≥ s2），同时对旋转四元数做相应的旋转补偿；
然后从 4 种等价四元数表示中选择 `|w|` 最大的那种，再按比例缩放使 `w = √2/2`（约 0.707）并 clip x, y, z 分量至 [-1, 1]，仅存储 x, y, z 三个分量（`rot_1, rot_2, rot_3`）。

这样每个高斯的旋转仅需 3 个值（代替原来 4 个），节省约 25% 旋转带宽。

### 11.3 高精度位置分拆

当同时配置 `x, y, z` 和 `x_add, y_add, z_add` 时：
- `x, y, z` 存储位置坐标的高位部分（MSB，`bits_main` 位）
- `x_add, y_add, z_add` 存储低位部分（LSB，`bits_add` 位）
- 总精度为 `bits_main + bits_add` 位

### 11.4 PCA SH AC 降维

对 45 个球谐 AC 系数（`f_rest_0`~`f_rest_44`）：
1. 可选地减去均值、除以标准差（白化）
2. SVD 分解，取累计方差达到阈值（如 99%）的主成分
3. 编码降维后的系数和基矩阵（存于 SEI）
4. 解码时逆变换还原

---

## 12. 使用示例

### 编码

```bash
python encode.py \
  -c cfg/ffmpeg/temporal_7_videos.cfg \
  -i /path/to/frame%03d.ply \
  -b output/test.v3c \
  -r output/test_rec_%04d.ply \
  -n 2 \
  -v
```

### 解码

```bash
python decode.py \
  -b output/test.v3c \
  -d output/test_dec_%04d.ply \
  -v
```

### 无损编码（FFmpeg x264）

```bash
python encode.py \
  -c cfg/ffmpeg/temporal_7_videos.cfg \
  -i frame%03d.ply \
  -b test.v3c \
  --qp_0 0 --qp_1 0 --qp_2 0 \
  -n 1
```

---

## 13. 潜在改进方向

1. **单元测试缺失**：目前没有单元测试框架（如 pytest），各模块缺乏自动化测试
2. **Windows 路径兼容性**：`fixpath` 等函数的跨平台处理在部分边界情况下可能存在问题
3. **`encode_vtm` 返回值缺失**：`encode_vtm` 函数在 verbose=False 时没有 `return` 语句，可能导致编码结果丢失
4. **大量全局状态**：`parser` 被声明为全局变量，在模块被多次导入时可能出现问题
5. **硬编码路径**：`anchor_run/tmcv_run_ctc.py` 中有多处硬编码路径（数据集路径、工具路径等），需要用户手动修改
