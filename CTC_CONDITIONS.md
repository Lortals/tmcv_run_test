# m74517 文档解读：TMCV 性能与 CTC 公共测试条件

## 文档基本信息

| 项目 | 内容 |
|------|------|
| 文档编号 | ISO/IEC JTC 1/SC 29/WG 4 **m74517** |
| 标题 | [GSC][JEE6.7] TMCV performances and common test conditions |
| 作者 | Julien Ricard, Gilles Teniou, Stephen Wenger |
| 会议 | October 2025, Geneva（MPEG 第152次会议）|

---

## 摘要

该文档展示了 TMCV（Test Model Candidate Video）的编码性能，并提出了一套可用于未来 **公共测试条件（Common Test Conditions，CTC）** 的编码配置方案，与 G-PCC 锚点和 Video 锚点进行了比对评估。

---

## 一、CTC 编码配置

### 1.1 三路视频基础配置

CTC 方案基于三路视频配置文件（对应 TMCV 的 `cfg/hm/ctc/cfg_3_videos.cfg`）：

---

#### 视频 0：几何位置（Geometry）

| 参数 | 值 |
|------|----|
| `bd_0` | 10（位深，随码率点变化，见 §1.2） |
| `qp_0` | **0**（固定无损/近无损）|
| `codec_0` | `hmr`（HM-18.0-Rext，支持高位深） |
| `config_0` | `encoder_intra_main_rext.cfg` + `lossless/lossless.cfg`（帧内+无损模式）|
| `comp_0` | `x, y, z, x_add, y_add, z_add`（坐标主位 + 补充低位，实现高精度位置编码） |
| `format_0` | `yuv400`（文档描述）/ `yuv444`（实际配置文件） |
| `packing_0` | `planar`（平铺打包） |

> **说明**：几何视频采用 HM-Rext 的帧内无损模式，确保位置坐标无损保存。`x_add, y_add, z_add` 是位置坐标的低有效位（LSB），位深随码率点变化（见下表）。
> **注**：文档原文中描述的格式为 `yuv400`，但仓库中实际的配置文件 `cfg/hm/ctc/cfg_3_videos.cfg` 使用的是 `yuv444`。几何分量（x,y,z）本质上是灰度量，使用 `yuv444` 时三个通道写入相同数据，未造成实质差异；实际执行时以配置文件内容为准。

---

#### 视频 1：几何属性（Opacity / Scale / Rotation）

| 参数 | 值 |
|------|----|
| `bd_1` | 10（位深，随 `QP_1` 码率点调整） |
| `qp_1` | **可变**（随码率点，见 §1.2） |
| `codec_1` | `hmr`（HM-18.0-Rext） |
| `config_1` | `encoder_intra_main_rext.cfg`（帧内模式） |
| `comp_1` | `opacity, rot_3, zero, scale_0, scale_1, scale_2, rot_0, rot_1, rot_2` |
| `format_1` | `yuv400`（灰度） |
| `packing_1` | `planar`（平铺打包） |

> **说明**：`rot_3` 对应四元数的 `rot_w`（w 分量），`rot_0,rot_1,rot_2` 对应 `rot_x,rot_y,rot_z`。`zero` 是填充零通道，用于对齐视频宽高至块大小的整数倍。

---

#### 视频 2：颜色与球谐系数（Color and Spherical Harmonics）

| 参数 | 值 |
|------|----|
| `bd_2` | 10 |
| `qp_2` | **可变**（随码率点，见 §1.2） |
| `codec_2` | `hmr`（HM-18.0-Rext） |
| `config_2` | `encoder_lowdelay_main_rext.cfg`（低延迟模式，对时序相关的SH帧间编码效率更高） |
| `comp_2` | `f_dc_0,f_dc_1,f_dc_2` + 全部 45 个 `f_rest_*`（RGB 顺序交错排列）|
| `format_2` | `yuv444` 或 `yuv420`（随码率点变化，见 §1.2） |
| `packing_2` | `temporal`（时序打包，每个属性分量独立占一帧） |

> **说明**：球谐系数排列方式为 R/G/B 交错：`f_rest_0,f_rest_15,f_rest_30 | f_rest_1,f_rest_16,f_rest_31 | ...`，形成自然的 YUV 三通道组合，与 `sh_conversion: 601` 配合做 BT.601 色彩空间转换。视频 2 使用低延迟模式来利用球谐系数的帧间相关性。

---

#### 全局设置

| 参数 | 值 | 说明 |
|------|----|----|
| `min_block_size` | 16 | PLAS 排序的最小块大小（高斯点网格对齐粒度） |
| `sh_conversion` | 601 | 球谐 RGB → YUV 颜色空间转换（BT.601 标准） |
| `trans_position` | 1 | 坐标值做 signed log 变换，压缩动态范围 |

---

### 1.2 五个码率点（Rate Points）

不同码率点通过调整以下三个维度实现：
1. **几何位深**：MSB（`bd_0` 中的 `x,y,z` 主位）与 LSB（`x_add,y_add,z_add` 补充位）的位深组合
2. **QP_1 / QP_2**：视频 1（几何属性）与视频 2（颜色/SH）的量化参数
3. **颜色/SH 视频格式**：高质量用 YUV444，低码率用 YUV420

| 码率点 | MSB 位深 | LSB 位深（文档） | 颜色/SH 格式 | QP_1 | QP_2 |
|--------|----------|------------------|--------------|------|------|
| **RP1**（最高质量） | 10 | 9 | YUV444 | -8 | 0 |
| **RP2** | 10 | 6 | YUV444 | -4 | 4 |
| **RP3** | 9 | 6 | YUV444 | 4 | 12 |
| **RP4** | 9 | 6 | YUV420 | 8 | 16 |
| **RP5**（最低质量） | 8 | 6 | YUV420 | 16 | 24 |

> **说明**：上表中"LSB 位深"列来自 m74517 文档原文。而仓库中 `anchor_run/tmcv_run_ctc.py` 的实现里，RP1 和 RP2 的 `bd1`（同时用于视频1位深和 LSB 位深参数）均设为 **10**，与文档存在差异。具体参见第七节的完整参数对照表。

**设计原则**：
- 码率范围与 G-PCC 锚点保持一致（便于公平比较）
- 几何信息优先（QP_0 始终为 0，无损编码）
- 高质量时用 YUV444（保留完整色度）；低码率时降为 YUV420（色度下采样）
- QP 值说明：负 QP 相当于对 `bd_1=10` 的基础进行额外精度保留，正 QP 为有损压缩

---

## 二、测试序列

根据实验结果章节，CTC 测试序列包括：

| 序列名 | 类别 | 备注 |
|--------|------|------|
| `cinema_track` | 前向场景（Forward Facing） | |
| `bartender_track` | 前向场景 | |
| `breakfast_track` | 前向场景 | |
| `ManWithFruit` | 目标中心场景（Object Centric）| 结果存在异常，需进一步研究 |

---

## 三、实验结果

### 3.1 与 Video 锚点（Video Anchor）相比的 BD-rate

| 序列 | RGB-PSNR | YUV-PSNR | YUV-SSIM |
|------|----------|----------|----------|
| bartender_track | **-25.0%** | **-41.6%** | **-42.2%** |
| breakfast_track | **-36.8%** | **-50.4%** | **-51.4%** |
| cinema_track | **-32.2%** | **-47.3%** | **-39.5%** |
| **平均** | **-31.3%** | **-46.4%** | **-44.3%** |
| ManWithFruit | No overlap | +45.7% | +1.8% |

> **解读**：在三个主要序列上，TMCV 相比 Video 锚点的 BD-rate 节省 **31%～51%**（负值表示在相同质量下码率更低），性能大幅领先。ManWithFruit 序列出现 "No overlap"，说明两条率失真曲线不在同一范围内，数据点无法形成有效的 BD-rate 计算区间。

### 3.2 与 G-PCC 锚点（G-PCC Anchor）相比的 BD-rate

| 序列 | RGB-PSNR | YUV-PSNR | YUV-SSIM |
|------|----------|----------|----------|
| bartender_track | **-15.4%** | **-14.2%** | +2.9% |
| breakfast_track | **-31.6%** | **-25.5%** | -1.1% |
| cinema_track | **-21.4%** | **-17.4%** | +7.5% |
| **平均** | **-22.8%** | **-19.0%** | +3.1% |
| ManWithFruit | #VALUE! | #VALUE! | #VALUE! |

> **解读**：在 PSNR 指标上，TMCV 相比 G-PCC 锚点节省约 **15%～32%** 的码率（负值）。SSIM 指标略有不稳定，平均略高于 G-PCC（+3.1%），原因可能在于 SSIM 对某些失真类型的敏感性与 PSNR 不同。ManWithFruit 存在计算错误，需进一步排查。

---

## 四、关键技术要点总结

| 技术特点 | 描述 |
|----------|------|
| **三视频流设计** | 几何、几何属性、颜色+SH 分开编码，各用最优参数 |
| **几何无损** | 位置坐标（`x,y,z` + `x_add,y_add,z_add`）始终 QP=0 无损编码 |
| **高精度位置分拆** | MSB+LSB 组合，总精度 19~20 位，远高于常规视频编码 |
| **SH 色彩转换** | BT.601 RGB→YUV，提升球谐系数在 YUV 编码器中的压缩效率 |
| **Signed-log 坐标变换** | 压缩坐标动态范围，提升量化精度 |
| **Temporal 打包用于 SH** | SH 系数数量多（48个），temporal 模式将每个分量展开为独立帧，更好利用帧间相关性 |
| **低延迟配置用于 SH** | `encoder_lowdelay_main_rext.cfg` 允许帧间参考，进一步压缩 SH 帧间冗余 |
| **与 GPCC 同码率范围** | 通过 5 个码率点的设计，确保与 G-PCC 锚点在同一码率区间内可做公平比较 |

---

## 五、结论与建议

文档结论：

> 根据实验结果，建议将上述定义的配置方案正式作为未来 CTC（公共测试条件）使用。

即将文档中的三路视频配置 + 五个码率点参数体系，作为 MPEG GSC 标准化过程中所有提案方进行性能比较的统一基准。

---

## 七、CTC 实际执行命令

`anchor_run/tmcv_run_ctc.py` 中对每个序列和码率点生成的完整编码命令如下：

```bash
python encode.py \
  -c cfg/hm/ctc/cfg_3_videos.cfg \
  -i <数据集路径>/<序列名>/plys/frame_%04d.ply \
  -n 32 \
  --first_frame <起始帧> \
  -b <输出>.bin \
  -r <重建>.ply \
  --qp_1 <QP_1>     # 视频1（几何属性）QP，随码率点变化
  --qp_2 <QP_2>     # 视频2（颜色/SH）QP，随码率点变化
  --format_2 <fmt>  # yuv444 或 yuv420，随码率点变化
  --bd_0 <MSB位深>  # 视频0（几何主坐标 x,y,z）
  --bd_1 <LSB位深>  # 视频1（几何属性）位深
  --bd_2 <LSB位深>  # 视频2（颜色/SH）位深（与 bd_1 相同）
  --verbose
```

> **注意**：`--bd_0` 对应 MSB 位深（视频 0 中 `x,y,z` 的编码位深），`--bd_1`/`--bd_2` 对应 LSB 位深（由 `bd_pos` 参数控制的低位部分）。配置文件中的 `bd_0` 和 `bd_1` 分别被命令行参数 `--bd_0` 和 `--bd_1` 覆盖。

解码命令：

```bash
python decode.py \
  -b <码流文件>.bin \
  -d <解码输出>_dec_%04d.ply \
  --first_frame <起始帧> \
  --verbose
```

### 五码率点完整参数对照

| 码率点 | `--bd_0` (MSB) | `--bd_1`/`--bd_2` (LSB) | `--format_2` | `--qp_1` | `--qp_2` |
|--------|----------------|--------------------------|--------------|----------|----------|
| RP1 | 10 | 10 | yuv444 | -8 | 0 |
| RP2 | 10 | 10 | yuv444 | -4 | 4 |
| RP3 | 9 | 6 | yuv444 | 4 | 12 |
| RP4 | 9 | 6 | yuv420 | 8 | 16 |
| RP5 | 8 | 6 | yuv420 | 16 | 24 |

> **与文档表格的差异**：`anchor_run/tmcv_run_ctc.py` 中 RP1 和 RP2 的 `bd1` 值均设为 **10**，而文档原文中分别为 9 和 6（见 §1.2 表格）。即代码实现中前两个码率点的 LSB 均采用更高精度（10 位），以代码实现为准。


| 文档内容 | 仓库文件 |
|----------|---------|
| CTC 三路视频配置文件 | `cfg/hm/ctc/cfg_3_videos.cfg` |
| CTC 无旋转版配置 | `cfg/hm/ctc/cfg_3_videos_nr.cfg` |
| HM-Rext 配置参考路径 | `dependencies/HM-18.0-Rext/cfg/` |
| 码率点参数（RP1~RP5） | `anchor_run/tmcv_run_ctc.py` 中 `RATE_POINTS` 列表 |
| 编码入口 | `encode.py` |
| 解码入口 | `decode.py` |
