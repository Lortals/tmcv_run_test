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
| `format_0` | `yuv400`（单通道灰度，与文档一致）|
| `packing_0` | `planar`（平铺打包） |

> **说明**：几何视频采用 HM-Rext 的帧内无损模式，确保位置坐标无损保存。`x_add, y_add, z_add` 是位置坐标的低有效位（LSB），位深通过 `--bd_pos MSB,LSB` 参数控制，随码率点独立变化。

---

#### 视频 1：几何属性（Opacity / Scale / Rotation）

| 参数 | 值 |
|------|----|
| `bd_1` | 10（位深，**固定不变**，不随码率点调整） |
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
1. **几何位深**：MSB（`bd_0` 中的 `x,y,z` 主位）与 LSB（`x_add,y_add,z_add` 补充位）的位深组合（详见 §六）
2. **QP_1 / QP_2**：视频 1（几何属性）与视频 2（颜色/SH）的量化参数
3. **颜色/SH 视频格式**：高质量用 YUV444，低码率用 YUV420

| 码率点 | MSB 位深 | LSB 位深 | 颜色/SH 格式 | QP_1 | QP_2 |
|--------|----------|----------|--------------|------|------|
| **RP1**（最高质量） | 10 | 9 | YUV444 | -8 | 0 |
| **RP2** | 10 | 6 | YUV444 | -4 | 4 |
| **RP3** | 9 | 6 | YUV444 | 4 | 12 |
| **RP4** | 9 | 6 | YUV420 | 8 | 16 |
| **RP5**（最低质量） | 8 | 6 | YUV420 | 16 | 24 |

> 上表直接对应 m74517 文档 Table 1，代码经修复后已与本表完全一致（见第八节合规性审计）。

**设计原则**：
- 码率范围与 G-PCC 锚点保持一致（便于公平比较）
- 几何信息优先（QP_0 始终为 0，无损编码）
- 高质量时用 YUV444（保留完整色度）；低码率时降为 YUV420（色度下采样）
- QP 值说明：负 QP 是 HM-RExt 高位深编码的合法值（详见 §1.3）

---

### 1.3 为什么 QP_1 会出现负值？

这是 **HM-RExt（HEVC 参考软件的 Range Extension 变体）对高位深内容的标准处理机制**，并非错误。

#### 根本原因：QpBdOffset 机制

H.265/HEVC 规范引入了一个随位深变化的偏移量 **QpBdOffset**，其定义为：

```
QpBdOffset = 6 × (bitDepth − 8)
```

对于 10 位（`bd_1 = 10`，视频 1 的**固定**位深——注意：`bd_1` 在所有五个码率点中均固定为 10，不随码率点变化；只有 `bd_0`（Video 0 几何坐标）随码率点在 8/9/10 之间变化）：

```
QpBdOffset = 6 × (10 − 8) = 12
```

HM 编码器在实际量化时，使用的是"内部有效 QP"（Internal Effective QP）：

```
QP_effective = QP_external + QpBdOffset
             = QP_external + 12      （10-bit 时）
```

因此，HM-RExt 在 10 位模式下将 QP 的**最小合法值**设为 `−QpBdOffset = −12`，  
对应的量化步长与 8 位时 QP=0 的步长完全相同（即最精细的有损压缩边界）。

#### 具体数值解读

| RP | QP_1（外部参数） | QP_effective（内部有效 QP） | 量化精度 |
|----|----------------|---------------------------|---------|
| 1 | **−8** | −8 + 12 = **4** | 极精细，接近无损 |
| 2 | **−4** | −4 + 12 = **8** | 非常精细 |
| 3 | 4 | 4 + 12 = **16** | 中等 |
| 4 | 8 | 8 + 12 = **20** | 中低质量 |
| 5 | 16 | 16 + 12 = **28** | 低质量 |

> **关键结论**：如果在 10 位模式下直接将 QP_external 设为 0，则内部有效 QP = 12，量化步长已经相当粗糙（损失明显）。  
> 为了在高码率点（RP1、RP2）获得**接近无损的几何属性质量**，必须将外部 QP 设为负值，  
> 通过负值来抵消 QpBdOffset 的影响，使有效量化步长趋近于最精细水平。

#### 代码层面的映射

`utils/video_codec.py` 的 `encode_hm()` 函数直接将 `qp` 参数传入 HM 编码器的 `--QP=` 选项：

```python
'--QP=' + str(qp),                       # 可以为负值，HM-RExt 合法接受
'--InternalBitDepth=' + str(max(video.bits, 8)),   # 编码 Video 1（bd_1=10）时 video.bits=10，QpBdOffset=12
```

> **注意**：`video.bits` 的值取决于当前被编码的视频。当编码 **Video 1**（几何属性，`bd_1=10`，所有码率点固定不变）时，`video.bits=10`，因此 `QpBdOffset=12`，`--QP=-8` 和 `--QP=-4` 均为合法值。当编码 Video 0（几何坐标，`bd_0` 随码率点变化为 8/9/10）时，`QP=0` 固定，不涉及负 QP 问题。

负 QP 值由 `anchor_run/tmcv_run_ctc.py` 中的 `RATE_POINTS` 列表传入，经 `encode.py` → `group_of_frames.py` → `video_codec.py` 完整链路到达 HM 编码器，属于正常流程。

#### 有效 QP 范围

| 视频位深 | QpBdOffset | 外部 QP 合法范围 | 内部有效 QP 范围 |
|--------|-----------|----------------|----------------|
| 8 bit | 0 | [0, 51] | [0, 51] |
| 9 bit | 6 | [−6, 51] | [0, 57] |
| **10 bit** | **12** | **[−12, 51]** | **[0, 63]** |
| 12 bit | 24 | [−24, 51] | [0, 75] |

CTC 中使用的 −8 和 −4 均在 10 位的合法范围 [−12, 51] 内，完全符合标准。

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
| **高精度位置分拆** | MSB+LSB 组合，总精度 14~19 位，远高于常规视频编码（详见 §六） |
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

## 六、几何坐标 MSB / LSB 机制详解

> **本节回答：在 CTC 码率点表格中，"MSB 位深" 和 "LSB 位深" 具体代表什么？它们是怎么工作的？**

---

### 6.1 背景：3DGS 几何坐标的精度需求

3D Gaussian Splatting（3DGS）场景中，每个 Gaussian 的空间位置由浮点坐标 `(x, y, z)` 描述。这些坐标覆盖的空间范围差异极大（从厘米级到几百米均有），直接用普通视频编码器编码存在两个挑战：

1. **动态范围大**：视频编码器的像素值是固定位深的整数（如 8~16 位），无法直接容纳任意范围的浮点数。
2. **精度要求高**：位置坐标直接影响渲染质量，需要更精细的量化精度（超出普通视频编码的 8~10 位）。

TMCV 的解决方案是：**用两路视频通道联合表示一个坐标**，合并精度达到 MSB+LSB 位。

---

### 6.2 完整编码流程（以 x 坐标为例）

```
原始浮点 x
    │
    ▼  [Step 1] Signed-log 变换（trans_position=1）
    │  x' = sign(x) × ln(1 + |x|)    # 即 sign(x) × log1p(|x|)，自然对数
    │  → 压缩大数值的动态范围，放大小数值附近的分辨率
    │
    ▼  [Step 2] 线性归一化 + 量化到 (MSB+LSB) 位整数
    │  total_bits = MSB位深 + LSB位深
    │  quantized ∈ [0, 2^total_bits - 1]    （无符号整数）
    │
    ▼  [Step 3] 整数拆分
    │  msb_value = quantized >> LSB位深      （取高 MSB 位）
    │  lsb_value = quantized & (2^LSB位深-1)  （取低 LSB 位）
    │
    ├──▶ msb_value → 存入 Video 0 的 "x"   通道（主坐标，MSB位深位）
    └──▶ lsb_value → 存入 Video 0 的 "x_add" 通道（补充低位，LSB位深位）
```

**解码时（逆过程）**：

```
msb_value（来自 "x"    通道）
lsb_value（来自 "x_add" 通道）
    │
    ▼  重组
    │  quantized = (msb_value << LSB位深) | lsb_value
    │
    ▼  线性反归一化 → 浮点 x'
    │
    ▼  逆 signed-log 变换
    │  x = sign(x') × (exp(|x'|) - 1)   # 即 sign(x') × expm1(|x'|)
    │
    └──▶ 重建的浮点 x 坐标
```

代码来源（`utils/group_of_frames.py`，`quantize()` 方法）：

```python
msb = (block >> bits_add) & msb_mask   # block 是 total_bits 位整数
lsb = block & lsb_mask
video_xyz.set_block('x', frame_index, msb, ...)    # 主通道存 MSB
video_add.set_block('x_add', frame_index, lsb, ...) # 附加通道存 LSB
```

---

### 6.3 CTC 五码率点的位深含义

| 码率点 | MSB 位深 | LSB 位深 | 总精度 | 量化级数 | 典型应用场景 |
|--------|----------|----------|--------|----------|----------|
| RP1 | 10 | 9 | **19 位** | 524,288 级 | 最高质量，近乎无损几何 |
| RP2 | 10 | 6 | **16 位** | 65,536 级 | 高质量 |
| RP3 | 9 | 6 | **15 位** | 32,768 级 | 中质量 |
| RP4 | 9 | 6 | **15 位** | 32,768 级 | 中低质量 |
| RP5 | 8 | 6 | **14 位** | 16,384 级 | 低码率 |

> **对比**：标准 HD 视频 = 8 位 = 256 级；标准 10-bit 视频 = 1024 级。TMCV 几何坐标的精度（14~19 位）远高于普通视频。

---

### 6.4 为什么要拆成 MSB + LSB 两路？

#### 原因 1：视频编码器的位深限制

HM-Rext 等视频编码器支持最多 16 位输入（`yuv400` 单通道时约为 16 位）。而几何坐标需要高达 19 位的总精度，**超出了单路视频的承载能力**。通过将 19 位拆成两路（10 + 9），每路都在编码器支持范围内。

#### 原因 2：压缩效率优化

- **MSB 通道（x, y, z）**：包含几何轮廓信息，变化相对平滑，空间预测效率高 → 适合帧内编码，QP=0 无损。
- **LSB 通道（x_add, y_add, z_add）**：仅包含低位残差，数值较小，近似随机噪声 → 压缩效率相对较低。

通过为两部分分配不同的编码策略（都无损，但可以通过 LSB 位深降低来减少低位的信息量），实现**几何精度与码率的精细权衡**。

#### 原因 3：码率控制粒度

码率点 RP1→RP5 降低 LSB 位深（9→6→6→6→6），直接减少低位通道的信息量，达到降码率的目的，同时 MSB 层面的几何轮廓精度（10 或 9 位）相对保持。

---

### 6.5 与 `--bd_pos` 参数的对应关系

`encode.py` 通过 `--bd_pos MSB,LSB` 参数传入这两个值：

```
--bd_pos 10,9   → MSB=10位 (x,y,z通道), LSB=9位 (x_add,y_add,z_add通道), 总精度=19位
--bd_pos 10,6   → MSB=10位, LSB=6位, 总精度=16位
--bd_pos  9,6   → MSB= 9位, LSB=6位, 总精度=15位
--bd_pos  8,6   → MSB= 8位, LSB=6位, 总精度=14位
```

`--bd_0` 参数（Video 0 的视频编码位深）**必须 ≥ MSB 位深**，用于设置 HM 编码器的输入视频像素位深。

---

### 6.6 Signed-log 变换的作用（trans_position=1）

在量化前，坐标先经过 **signed-log 变换**（代码：`utils/common.py`）：

```python
def log_transform(x):
    return np.sign(x) * np.log1p(np.abs(x))   # log1p(x) = ln(1+x)，自然对数
```

**逆变换**（`utils/common.py` 中的 `inverse_log_transform`）：

```python
def inverse_log_transform(x):
    return np.sign(x) * np.expm1(np.abs(x))   # expm1(x) = exp(x) - 1
```

**效果**：将坐标动态范围从线性压缩为对数尺度。

| 原始坐标值 | 变换后 | 说明 |
|-----------|--------|------|
| 0.001 | ≈ 0.001 | 小值基本不变 |
| 1.0 | ≈ 0.693 | 中等值压缩 |
| 10.0 | ≈ 2.398 | 大值被强烈压缩 |
| 100.0 | ≈ 4.615 | 极大值压缩明显 |

这意味着量化精度被**自动分配给绝对值小的坐标区域**（精度更密集），而大坐标范围用更少的量化级数表示。这与人眼感知（近处精度要求高）以及 3DGS 场景的分布（大量高斯分布在近处）一致。

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
  --qp_1 <QP_1>            # 视频1（几何属性）QP，随码率点变化
  --qp_2 <QP_2>            # 视频2（颜色/SH）QP，随码率点变化
  --format_2 <fmt>         # yuv444 或 yuv420，随码率点变化
  --bd_0 <MSB位深>         # 视频0（几何主坐标 x,y,z）编码位深
  --bd_pos <MSB位深>,<LSB位深>  # 几何坐标 MSB/LSB 精度拆分
  --verbose
```

> **注意**：`--bd_0` 设置视频 0 的编码位深（影响 x,y,z 的视频编码质量），`--bd_pos {MSB},{LSB}` 明确指定几何坐标的高低位精度拆分。视频 1（几何属性）和视频 2（颜色/SH）的位深由配置文件中的 `bd_1: 10` / `bd_2: 10` 决定，不在命令行中覆盖。

解码命令：

```bash
python decode.py \
  -b <码流文件>.bin \
  -d <解码输出>_dec_%04d.ply \
  --first_frame <起始帧> \
  --verbose
```

### 五码率点完整参数对照（修正后）

| 码率点 | `--bd_0` (MSB) | `--bd_pos` | `--format_2` | `--qp_1` | `--qp_2` |
|--------|----------------|------------|--------------|----------|----------|
| RP1 | 10 | 10,9 | yuv444 | -8 | 0 |
| RP2 | 10 | 10,6 | yuv444 | -4 | 4 |
| RP3 | 9 | 9,6 | yuv444 | 4 | 12 |
| RP4 | 9 | 9,6 | yuv420 | 8 | 16 |
| RP5 | 8 | 8,6 | yuv420 | 16 | 24 |


| 文档内容 | 仓库文件 |
|----------|---------|
| CTC 三路视频配置文件 | `cfg/hm/ctc/cfg_3_videos.cfg` |
| CTC 无旋转版配置 | `cfg/hm/ctc/cfg_3_videos_nr.cfg` |
| HM-Rext 配置参考路径 | `dependencies/HM-18.0-Rext/cfg/` |
| 码率点参数（RP1~RP5） | `anchor_run/tmcv_run_ctc.py` 中 `RATE_POINTS` 列表 |
| 编码入口 | `encode.py` |
| 解码入口 | `decode.py` |

---

## 八、合规性审计结果（与 m74517 CTC 配置对比）

> 版本：本节记录了对 `anchor_run/tmcv_run_ctc.py` 和 `cfg/hm/ctc/cfg_3_videos.cfg` 的合规性审计及已修复的问题。

### 8.1 已修复的问题

#### Bug 1：几何坐标 LSB 位深从未生效（所有码率点均受影响）

**原因**：`encode.py` 的 `--bd_pos` 参数若未在命令行显式指定，则通过 `find_video_bitdepth()` 自动推断：
- `x, y, z` 所在视频：Video 0，位深 = `bd_0`
- `x_add, y_add, z_add` 所在视频：**同样是 Video 0**，位深 = `bd_0`
- 因此 `bd_pos = (bd_0, bd_0)`，MSB == LSB，LSB 精度被忽略。

**现象**：所有5个码率点的实际几何精度均等于 MSB 位深，不符合文档规定。

**修复**：在编码命令中显式加入 `--bd_pos {bd0},{bd1}`，确保 MSB 和 LSB 位深独立生效。

#### Bug 2：RP1 / RP2 的 LSB 位深值错误

| 码率点 | 文档 LSB BD | 原代码 bd1 | 修复后 bd1 |
|--------|------------|-----------|-----------|
| RP1 | 9 | **10（错误）** | 9 ✓ |
| RP2 | 6 | **10（错误）** | 6 ✓ |
| RP3 | 6 | 6 ✓ | 6 ✓ |
| RP4 | 6 | 6 ✓ | 6 ✓ |
| RP5 | 6 | 6 ✓ | 6 ✓ |

#### Bug 3：视频 1 和视频 2 的位深被错误地随码率点变化（RP3-RP5）

**原命令**（错误）：
```
--bd_1 {bd1} --bd_2 {bd1}
```
对于 RP3/RP4/RP5，这将 Video 1（几何属性）和 Video 2（颜色/SH）的编码位深降至 **6 bits**，而文档规定 `bd_1: 10`、`bd_2: 10`（固定不变）。

**修复**：移除 `--bd_1 {bd1} --bd_2 {bd1}`，改为 `--bd_pos {bd0},{bd1}`（仅影响几何坐标精度，不影响属性/SH 视频位深）。

#### Bug 4：cfg_3_videos.cfg 中 format_0 / format_1 不符合文档规定

| 参数 | 文档规定 | 原配置 | 修复后 |
|------|---------|--------|--------|
| `format_0`（几何视频）| `yuv400` | **yuv444** | `yuv400` ✓ |
| `format_1`（属性视频）| `yuv400` | **yuv444** | `yuv400` ✓ |

几何和属性数据均为纯灰度标量，应使用 `yuv400`（单通道）。使用 `yuv444` 会让 HM 编码器以 4:4:4 三通道模式处理，与文档规定不符。

### 8.2 无需修改的正确项

| 项目 | 文档规定 | 代码/配置 | 状态 |
|------|---------|-----------|------|
| 配置文件路径 | `cfg_3_videos.cfg` | `cfg/hm/ctc/cfg_3_videos.cfg` | ✓ |
| QP 值（RP1-RP5）| {-8,-4,4,8,16} / {0,4,12,16,24} | 相同 | ✓ |
| format_2（YUV444/420）| 随码率点 | 相同 | ✓ |
| MSB 位深（bd_0）| {10,10,9,9,8} | 相同 | ✓ |
| Video 0 编码配置 | intra + lossless | 相同 | ✓ |
| Video 1 编码配置 | intra | 相同 | ✓ |
| Video 2 编码配置 | lowdelay | 相同 | ✓ |
| 所有 codec | `hmr` | `hmr` | ✓ |
| comp_0/comp_1/comp_2 | 见文档 | 相同 | ✓ |
| sh_conversion | 601 | 默认值=601 | ✓ |
| trans_position | 1 | 默认值=1 | ✓ |
| min_block_size | 16 | 默认值=16 | ✓ |
| cov_norm | 未指定（默认 0）| 默认值=0 | ✓ |
| Video 0 QP | qp_0=0（无损）| qp_0=0 | ✓ |

### 8.3 文档内部不一致（不修改代码）

- **RP5 QP_1**：正文 bullet 写 "QP_1={-8,-4,4,8,**12**}"，但表格 RP5 行为 **16**。代码使用表格值（16），表格优先级更高，不作修改。
