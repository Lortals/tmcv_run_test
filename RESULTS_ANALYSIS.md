# TMCV CTC 综合结果分析报告

> 本文档对 TMCV 在 CTC（公共测试条件）下、综合 **1F（单帧）** 和 **NF（多帧，N=32）** 两种配置所得到的所有结果进行全面分析，指出数据合理性、异常情况及改进建议。

---

## 一、数据概览

### 1.1 测试矩阵

| 维度 | 内容 |
|------|------|
| 场景类别 | Forward Facing（前向场景）× 11 序列；Object-Centric（目标中心）× 12 序列 |
| 帧数配置 | 1F（单帧）、NF（N=32 帧） |
| 码率点 | RP1 ~ RP5，共 5 个 |
| 理论行数 | (11 + 12) × 2 配置 × 5 码率点 = **230 行** |
| 实际有效行数 | 约 **79 行**（其中 trio / makeup / musical 三个序列完全空缺，library 等部分序列仅有 1F 结果） |

> **重要缺口**：实际有效数据仅约 79 行，远低于理论 230 行，覆盖率约 34%。

---

### 1.2 序列覆盖情况

#### Forward Facing（前向场景，1920×1080）

| 序列 | 相机数 | 帧数配置 | 数据状态 |
|------|--------|----------|----------|
| bartender_semitracked | 21 | 1F + NF | ✅ 有数据 |
| cinema_semitracked | 21 | 1F + NF | ✅ 有数据 |
| breakfast_semitracked | 21 | 1F + NF | ✅ 有数据 |
| breakfast_untracked | 15 | 1F + NF | ✅ 有数据 |
| breakdance_untracked | 35 | 1F + NF | ✅ 有数据 |
| bartender_tracked | 21 | 1F + NF | ✅ 有数据 |
| cinema_tracked | 21 | 1F + NF | ✅ 有数据 |
| breakfast_tracked | 15 | 1F + NF | ✅ 有数据 |
| **trio** | 21 | 1F + NF | ❌ **完全缺失** |
| **makeup** | 21 | 1F + NF | ❌ **完全缺失** |
| **musical** | 21 | 1F + NF | ❌ **完全缺失** |

#### Object-Centric（目标中心）

| 序列 | 相机数 | 分辨率 | 起始帧 | 数据状态 |
|------|--------|--------|--------|----------|
| manwithfruit_tracked | 21 | 3840×2160 | 81 | ✅ 有数据 |
| lego_ferrari | 128 | 4594×5514 | 0 | ✅ 有数据 |
| lego_bugatti | 132 | 3852×2868 | 0 | ✅ 有数据 |
| cricket_player | 46 | 4520×2540 | 0 | ✅ 有数据 |
| plant | 66 | 2954×3968 | 0 | ✅ 有数据 |
| solo_tango_female | 41 | 4534×2542 | 0 | ✅ 有数据 |
| solo_tango_male | 41 | 4528×2544 | 0 | ✅ 有数据 |
| tango_duo | 41 | 4522×2538 | 0 | ✅ 有数据 |
| tennis_player | 62 | 4518×2540 | 0 | ✅ 有数据 |
| **library** | 100 | 3780×2131 | 0 | ⚠️ 仅 1F，未在 `tmcv_run_ctc.py` SEQUENCES 列表中 |
| flowerdance | 21 | 2456×2054 | 0 | ✅ 有数据 |
| gymnast | 64 | 2456×2054 | **200** | ✅ 有数据（起始帧特殊） |

---

## 二、码率分析

### 2.1 总体码率范围

在 5 个码率点的设计下，各序列的码率分布应呈单调递增趋势（RP1 最高质量/最高码率 → RP5 最低）：

| 场景类别 | 典型码率范围（kbps，NF=32帧） | 说明 |
|----------|-------------------------------|------|
| Forward Facing 1920×1080 | ~5,000 – ~200,000 kbps | 取决于场景复杂度和 Gaussian 数量 |
| Object-Centric 3840×2160+ | ~20,000 – ~800,000 kbps | 分辨率更高，相机数更多，码率显著更大 |

> **合理性判断**：码率数量级与序列分辨率和 Gaussian 数量（通常数十万至数百万点）相匹配，总体合理。

### 2.2 典型单帧（1F）码率

单帧编码场景中，码率 = 文件总字节数 × 8 / (1帧/30fps) = 总比特 × 30（kbps，除以1000）。
表格中可见的"bit rate"列数值（如 171,447,338），若以 **bits** 计，则对应约 171 Mbit/帧，换算为码率约 5.1 Gbps（@30fps）——这对单个 3DGS 帧编码是不寻常的高值。

**可能原因与建议检查项**：
- ⚠️ **确认 bit rate 单位**：是 bits、bytes 还是 kbps？若列值为 bytes，则 171,447,338 bytes ≈ 163 MB/帧；乘以 8 再乘以 30fps 得约 39 Gbps，远超合理范围，说明该列表示的是多帧总量而非单帧码率。建议在 `collect_results.py` 中明确标注单位并统一转换。
- ✅ 若"bit rate"列为 **总字节数（bytes）**，其中包含了所有 NF=32 帧的总码量，则 163 MB / 32帧 ≈ 5.1 MB/帧，较高但对高分辨率序列有一定合理性。
- 建议在表格列头标注：`bit rate (bytes, NF total)` 或 `bit rate (kbps)`，避免歧义。推荐统一转换公式：
  ```
  kbps = (file_bytes × 8 × fps) / (num_frames × 1000)
  ```

### 2.3 码率点间单调性检查

正常情况下每个序列的各码率点应满足：
```
总码量（RP1）> 总码量（RP2）> 总码量（RP3）> 总码量（RP4）> 总码量（RP5）
```
如果出现码率点间数值不单调（如 RP3 > RP2），需排查：
- `--bd_pos` 参数是否正确传递（见 CTC_CONDITIONS.md §六）
- `--format_2 yuv420/yuv444` 是否随码率点正确切换

---

## 三、质量指标（Average Objective Quality）分析

### 3.1 指标含义

表格中的质量指标来自 `mpeg-gsc-metrics` 工具，列含义如下：

| 列 | 含义 | 正常范围 |
|----|------|----------|
| Y-PSNR | 亮度（Y 通道）PSNR，dB | 25 – 50 dB |
| UV-PSNR | 色度（UV 通道）PSNR，dB | 25 – 50 dB |
| RGB-PSNR | RGB 综合 PSNR，dB | 25 – 50 dB |
| YUV-SSIM | YUV 结构相似度 | 0.85 – 0.9999 |

### 3.2 质量指标合理性评估

**合理范围判断**：
- RP1（最高质量）：PSNR 应在 40~50 dB，SSIM 应在 0.990~0.9999
- RP5（最低质量）：PSNR 应在 25~35 dB，SSIM 应在 0.85~0.95
- 若 PSNR < 20 dB：渲染质量极差，可能存在解码错误或参数错误
- 若 PSNR > 55 dB：异常高，可能存在质量评估的 bug（如解码文件与参考文件完全相同）

**表中可见的极端值观察**：
- ✅ 大多数 PSNR 值在 30–50 dB 范围内，属于合理范围
- ✅ SSIM 值接近 0.999 的出现在高码率（RP1）时，对无损几何编码合理
- ⚠️ 需关注 **manwithfruit_tracked** 序列的质量指标：根据 m74517 文档该序列与 Video 锚点存在"No overlap"问题，且 G-PCC 对比中出现 `#VALUE!` 错误（CTC_CONDITIONS.md §3.2），说明其率失真曲线范围与锚点不重叠，BD-rate 无法计算

### 3.3 质量指标异常情况

| 异常 | 序列/情况 | 可能原因 |
|------|----------|----------|
| PSNR 为 0 或缺失 | trio / makeup / musical | 序列未被处理，metrics 工具未运行 |
| SSIM 异常接近 1.0 | 高码率 RP1，1F | 单帧无损编码，质量极高，属正常现象 |
| PSNR 无单调性 | 如某序列 RP3 质量高于 RP2 | 编码参数配置异常，需复查 |
| G-PCC 对比 #VALUE! | manwithfruit_tracked | 率失真曲线范围不重叠，无法计算 BD-rate |

---

## 四、时间与内存分析

### 4.1 编码时间（Encoding Time）

| 场景 | 典型 1F 编码时间 | 典型 NF(32帧) 编码时间 |
|------|----------------|-----------------------|
| Forward Facing 1920×1080 | 20 – 120 秒 | 200 – 2000 秒 |
| Object-Centric 3840×2160+ | 60 – 300 秒/帧 | 数小时 |

**合理性判断**：
- 编码时间与场景中 Gaussian 点数（数十万~数百万）成正比
- HM 编码器对高分辨率视频编码耗时较长，Object-Centric 场景的编码时间远大于 Forward Facing 是正常的
- 若编码时间极短（< 1 秒），可能是编码失败后提前退出

**需要关注的问题**：
- ⚠️ `parse_time_memory()` 同时使用 stdout 和 stderr 解析时间，但实际上 `/usr/bin/time -v` 输出到 stderr，`encode.py` 的"Time: x secondes"输出到 stdout。当 log 文件同时包含两路输出（`stderr=subprocess.STDOUT`）时，两种解析均从同一文件读取，可能存在优先级冲突导致部分序列时间记录不准确。

### 4.2 解码时间（Decoding Time）

解码时间应远小于编码时间（通常为编码时间的 1/10~1/20）。

| 观察项 | 说明 |
|--------|------|
| 解码时间与编码时间之比 > 50% | 异常，可能存在解码 bug |
| 解码时间 = 0 | 解码日志解析失败，需检查 `dec_log` 文件 |
| 解码时间远大于编码时间 | 异常，需排查 |

### 4.3 渲染时间（Rendering Time）

表格中可见的渲染时间约为 **0.07 – 0.10 秒**，这是 `mpeg-3d-renderer` 对单帧视角渲染的时间。对于 1M~5M Gaussian 点的场景，单视角渲染 0.07~0.10 秒属于合理范围（~10 fps）。

**异常检查**：
- 渲染时间 = 0：metrics 工具未运行成功（可能是 camera info 缺失）
- 渲染时间 >> 1 秒：Gaussian 数量异常多或渲染环境问题

### 4.4 最大内存用量（Max RSS）

代码中 `Max RSS` 以 MB 为单位（从 `/usr/bin/time -v` 的 kbytes 值除以 1024）。

| 场景 | 典型值 |
|------|--------|
| Forward Facing（NF=32 帧） | 300 – 800 MB |
| Object-Centric（高分辨率） | 800 – 4000 MB |

**合理性判断**：内存使用主要由 Gaussian 点数 × 每点属性大小决定，加上 HM 编码器的内部缓存。300MB~4000MB 对应数百万高斯点的处理是合理的。

**异常情况**：
- ⚠️ 若 Max RSS 记录值异常大（如超过 100GB），检查 `/usr/bin/time -v` 的输出格式是否被正确解析（有些系统报告单位不同）
- Max RSS = 0：`/usr/bin/time -v` 不可用或日志解析失败

---

## 五、特殊情况与已知异常

### 5.1 【严重】trio / makeup / musical 三序列完全缺失

**现象**：表格中这三个 Forward Facing 序列（各 21 相机，1920×1080）的行为空行，无任何数据。

**可能原因**：
1. `anchor_run/tmcv_run_ctc.py` 的 `SEQUENCES` 列表中 **没有** 这三个序列（已确认），说明 CTC 运行脚本遗漏了这三个序列
2. 数据集目录中对应的 PLY 文件不存在（`input_ply % start_frame` 检查失败，任务被跳过）
3. 序列在测试计划中但尚未采集/处理

**影响**：这三个序列均为 Forward Facing 类别，缺失会造成该类别的覆盖不完整，无法对前向场景做完整的 BD-rate 评估。

**修复建议**：
```python
# anchor_run/tmcv_run_ctc.py 第 32 行
SEQUENCES = [
    "bartender_semitracked", "cinema_semitracked", "breakfast_semitracked",
    "breakfast_untracked", "breakdance_untracked",
    "bartender_tracked", "cinema_tracked", "breakfast_tracked",
    "manwithfruit_tracked",
    # 需要补充以下三个序列（确认数据集路径存在后添加）:
    "trio",
    "makeup",
    "musical",
]
```

---

### 5.2 【注意】library 序列未在 SEQUENCES 列表中

**现象**：表格中 Object-Centric 部分出现 `library`（100 相机，3780×2131），但 `anchor_run/tmcv_run_ctc.py` 的 `SEQUENCES` 和 `SEQ_RES` 中均无该序列记录。

**可能原因**：该序列是在 `tmcv_run_ctc.py` 之外、通过其他脚本或手动命令单独测试的，结果被合并进了汇总表。

**建议**：若 library 是正式 CTC 序列，应将其添加到 `SEQUENCES` 和 `SEQ_RES` 中：
```python
"library": (3780, 2131, 0),
```
如果是临时序列，应在表格中注明"非 CTC 标准序列"以避免误解。

---

### 5.3 【注意】gymnast 起始帧 = 200

`gymnast` 序列的 `start_frame = 200`（`SEQ_RES` 中已配置），与大多数从第 0 帧开始的序列不同。这是因为该序列的有效动作从第 200 帧才开始，前 200 帧属于无效/静态帧。

**合理性**：这是数据集设计决定的，属于正常现象，无需修改。只需确保：
1. `--first_frame 200` 参数正确传入 encode.py
2. metrics 工具使用与编码相同的起始帧范围（`--startFrame=200`）

---

### 5.4 【注意】lego_ferrari 和 lego_bugatti 的纵向分辨率

- `lego_ferrari`：4594 × **5514**（纵向比横向更大，竖幅格式）
- `lego_bugatti`：3852 × 2868（正常横幅格式）

纵向分辨率 5514 > 横向 4594 说明 `lego_ferrari` 是一个竖幅采集的场景。这对 PLAS 排序的网格尺寸计算可能有影响（`sidelen_w` 和 `sidelen_h` 的计算涉及 `sidelen_w = sidelen_h` 假设）。

**建议检查**：在 `rectangular_sort=True` 的配置下验证 lego_ferrari 的排序网格是否正确。

---

### 5.5 【注意】manwithfruit_tracked 的率失真曲线问题

根据 m74517 文档（CTC_CONDITIONS.md §3.1/3.2）：
- 与 Video 锚点对比：**No overlap**（曲线范围不重叠，BD-rate 无法计算）
- 与 G-PCC 对比：**#VALUE!**（Excel 计算错误）

**分析**：manwithfruit_tracked 分辨率为 3840×2160（4K），Gaussian 数量远超 Forward Facing 序列，导致 TMCV 码率范围与锚点码率范围不在同一区间。这是典型的"超出比较范围"问题。

**改进建议**：
1. 调整该序列的 Gaussian 数量上限（通过 `--num_points` 参数）以降低码率
2. 或将 Object-Centric 序列单独与适合的锚点进行比较，而非与 Forward Facing 的锚点混合

---

### 5.6 1F vs NF 结果对比的合理性

**预期规律**：
- NF（32帧）的**总**码量应约为 1F 的 10~25 倍（不是 32 倍，因为视频编码利用帧间冗余）
- NF 的**质量指标**应与 1F 相当或略有不同（帧间参考影响）
- NF 的**编码时间**约为 1F 的 25~40 倍（帧数增加，但有部分固定开销）

如果 NF 总码量接近 1F × 32，说明帧间压缩未生效（可能是 SH 视频的 `temporal` 打包未正确使用帧间参考）。

---

## 六、Object-Centric vs Forward Facing 比较

| 维度 | Forward Facing | Object-Centric | 差异分析 |
|------|---------------|----------------|----------|
| 分辨率 | 1920×1080（固定） | 2456×2054 ~ 4594×5514（可变） | OC 分辨率差异极大（最大/最小比 ≈ 5×） |
| 相机数量 | 15 – 35 | 21 – 132 | OC 相机数量更多，质量评估计算量更大 |
| 编码器配置 | 相同 CTC 配置 | 相同 CTC 配置 | 无差异，但 OC 的高分辨率导致编码时间差异 |
| 典型码率 | 相对低 | 相对高（分辨率/点数更多） | OC 码率可达 FF 的 5~10× |
| 质量指标 | PSNR 通常 30~45 dB | PSNR 预期类似范围 | 应分类别单独评估，不应混合对比 |

---

## 七、数据合理性总结

| 项目 | 评估 | 说明 |
|------|------|------|
| 码率单调性（RP1 > RP5） | ✅ 预期合理 | 需逐序列验证 |
| PSNR 范围（25~50 dB） | ✅ 总体合理 | 极端值需排查 |
| SSIM 范围（0.85~0.9999） | ✅ 总体合理 | 高码率接近 1.0 是正常的 |
| 编码时间量级 | ✅ 合理 | OC 序列耗时显著更长 |
| 内存使用量级 | ✅ 合理 | 与 Gaussian 数量相关 |
| 数据覆盖率 | ❌ 不足 | trio/makeup/musical 完全缺失 |
| unit 标注一致性 | ⚠️ 待确认 | bit rate 列单位不明确 |
| library 归属 | ⚠️ 需说明 | 不在标准 SEQUENCES 列表中 |
| manwithfruit BD-rate | ⚠️ 已知异常 | 曲线范围与锚点不重叠 |

---

## 八、改进建议（按优先级排序）

### P0（必须修复）

1. **补充 trio / makeup / musical 三个序列的测试**
   - 确认数据集路径存在，并将三个序列加入 `anchor_run/tmcv_run_ctc.py` 的 `SEQUENCES` 列表
   - 目前 CTC 结果中 Forward Facing 类别仅有 8/11 个序列，不完整

2. **明确 bit rate 列的单位**
   - 在 `collect_results.py` 和结果表格中统一注明 `kbps`、`Mbps` 还是 `bytes`
   - 添加标准转换（fps=30，NF=32帧时）：`kbps = (file_bytes × 8 × fps) / (num_frames × 1000)`

### P1（应尽快处理）

3. **library 序列归属说明**
   - 若为正式 CTC 序列：加入 `SEQUENCES` 和 `SEQ_RES`，补充 NF 结果
   - 若为额外序列：在表格中注明"非标准 CTC 序列，仅供参考"

4. **manwithfruit_tracked 的率失真曲线问题**
   - 分析该序列的 Gaussian 数量，评估是否需要通过 `--num_points` 限制高斯点数以使码率落入与锚点重叠的范围
   - 或单独为 Object-Centric 序列建立参考基线

5. **验证 1F vs NF 帧间压缩有效性**
   - 检查 NF 总码量是否 ≤ 1F × 20（帧间有效压缩）
   - 若 NF ≈ 1F × 32，说明帧间压缩未生效，需排查 Video 2 的 `lowdelay` 配置是否正确传入编码器

### P2（后续优化）

6. **Object-Centric 序列编码超时风险**
   - lego_ferrari（128 相机，4594×5514）和 lego_bugatti（132 相机，3852×2868）的 NF 编码时间可能达到数小时
   - 建议监控并记录每个任务的实际耗时，为服务器资源规划提供依据

7. **gymnast 起始帧 200 的 metrics 对齐确认**
   - 确认 `mpeg-gsc-metrics` 工具使用 `--startFrame=200 --frameCount=32`（NF=32，与编码参数一致）
   - 避免因帧号偏移导致质量评估结果偏低

8. **lego_ferrari 竖幅分辨率的排序网格检查**
   - 当 height > width 时，`rectangular_sort` 的网格计算（`sidelen_h = num_points // sidelen_w`）应进行专项验证

9. **结果表格增加 BD-rate 汇总列**
   - 当前表格仅显示原始数值，建议增加 BD-rate（相对 G-PCC 和 Video 锚点）列，便于直接比较
   - 对无法计算 BD-rate 的序列（如 manwithfruit），明确标注原因

---

## 九、参考：CTC 各码率点参数

| RP | bd_pos (MSB,LSB) | qp_1 | qp_2 | format_2 | 总几何精度 |
|----|-----------------|------|------|----------|-----------|
| 1 | 10, 9 | -8 | 0 | yuv444 | 19 位 |
| 2 | 10, 6 | -4 | 4 | yuv444 | 16 位 |
| 3 | 9, 6 | 4 | 12 | yuv444 | 15 位 |
| 4 | 9, 6 | 8 | 16 | yuv420 | 15 位 |
| 5 | 8, 6 | 16 | 24 | yuv420 | 14 位 |

> MSB/LSB 含义详见 `CTC_CONDITIONS.md §六`。
