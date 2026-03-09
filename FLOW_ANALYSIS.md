# `anchor_run/tmcv_run_ctc.py` 完整执行流程梳理

本文档对 `anchor_run/tmcv_run_ctc.py` 的整个运行流程进行逐层梳理，覆盖：全局配置、并发调度、单任务生命周期、数据流向、日志/CSV 汇总。

---

## 一、总体数据流（鸟瞰图）

```
原始 PLY 序列
  │
  │  [Step 1] encode.py → 视频编码 (HM-RExt ×3路) + 打包
  ▼
.bin 码流文件
  │
  │  [Step 2] decode.py → 视频解码 (HM-RExt ×3路) + 还原高斯点
  ▼
解码 PLY 序列 (*_dec_%04d.ply)
  │
  │  [Step 3] gsTools/cameraPosition → 向每帧写入相机位姿 (可选)
  ▼
带相机信息的解码 PLY
  │
  │  [Step 4] mpeg-gsc-metrics → 与原始 PLY 对比，计算 PSNR/SSIM
  ▼
质量指标 (*_metrics.log)
  │
  │  [Step 5] 汇总写入 CSV
  ▼
output_nf/tmcv_ctc_results/ctc_summary.csv
```

对 **23 个序列 × 5 个码率点 = 115 个任务**，上述流程以最多 `5 GPU × 8 并发槽 = 40 并发任务` 同时运行。

---

## 二、模块级常量与初始化（脚本加载时执行）

```
脚本被 Python 解释器加载
        │
        ├─ AVAILABLE_GPUS = [3,4,5,6,7]    # 可用 GPU 编号列表
        ├─ TASKS_PER_GPU  = 8               # 每张 GPU 的并发任务数
        ├─ NUM_FRAMES     = 32              # 每个序列编码的帧数
        │
        ├─ SEQUENCES = [23 个序列名]        # Forward Facing + Object Centric
        ├─ RATE_POINTS = [5 个码率点配置]   # RP1~RP5：qp1, qp2, fmt2, bd0, bd1
        ├─ SEQ_RES     = {序列名: (width, height, start_frame)} # 23 条
        │
        ├─ DATASET_DIR  = "/home/data/datasets/mpeg_gsdata/CTC"
        ├─ OUTPUT_DIR   = "<root>/output_nf/tmcv_ctc_results"
        ├─ CONFIG_FILE  = "<root>/cfg/hm/ctc/cfg_3_videos.cfg"
        │
        ├─ gpu_queue   = Queue()   # 预先填入 5×8=40 个 GPU 槽位 (int)
        ├─ csv_lock    = Lock()    # 保护 CSV 写入
        └─ print_lock  = Lock()    # 保护 print 输出不错行
```

### RATE_POINTS 详解

| RP | qp1 | qp2 | fmt2 | bd0 (MSB) | bd1 (LSB) |
|----|-----|-----|------|-----------|-----------|
| 1  | -8  | 0   | yuv444 | 10 | 9 |
| 2  | -4  | 4   | yuv444 | 10 | 6 |
| 3  | 4   | 12  | yuv444 | 9  | 6 |
| 4  | 8   | 16  | yuv420 | 9  | 6 |
| 5  | 16  | 24  | yuv420 | 8  | 6 |

> qp1 负值原因详见 `CTC_CONDITIONS.md §1.3`（HM-RExt QpBdOffset 机制）。

---

## 三、`main()` 启动序列

```
main()
  │
  ├─ os.chdir(ROOT_DIR)          # 切换工作目录到 mpeg-gsc-tmcv 根目录
  ├─ os.makedirs(OUTPUT_DIR)     # 创建输出根目录（如已存在则跳过）
  │
  ├─ results_csv = ".../ctc_summary.csv"
  ├─ csv_headers = [15 列名]
  │
  ├─ 断点续传读取 ──────────────────────────────────────────────────────┐
  │   if CSV 不存在:                                                    │
  │       写入表头                                                       │
  │   else:                                                             │
  │       逐行读取 CSV                                                   │
  │       for each row:                                                 │
  │           if YUV-PSNR > 0.1:                                       │
  │               existing_records.add((seq, str(rp_id)))              │
  │       # 已完成的记录不会被重复执行                                   │
  └─────────────────────────────────────────────────────────────────────┘
  │
  ├─ 任务打包
  │   tasks = [(seq, rp) for seq in SEQUENCES for rp in RATE_POINTS]
  │   # 共 23 × 5 = 115 个任务
  │
  ├─ 打印统计摘要 (总任务数 / 已完成数 / GPU数 / 最大并发数)
  │
  └─ ThreadPoolExecutor(max_workers=40)
       for each task: executor.submit(process_single_task, seq, rp, ...)
       for future in as_completed(futures): future.result()  # 等待全部完成
       
       打印 "[ALL DONE] Performance metrics saved to ..."
```

---

## 四、`process_single_task(seq, rp, ...)` 单任务完整生命周期

每次调用对应 **一个 (序列, 码率点) 组合**，在一个独立线程中执行。

### 4.0 前置检查

```
process_single_task(seq="bartender_semitracked", rp={"rp":1, ...}, ...)
  │
  ├─ if (seq, str(rp_id)) in existing_records:
  │       safe_print("[SKIP] Already found in CSV")
  │       return   ← 提前退出，跳过本任务
  │
  ├─ gpu_id = gpu_queue.get()   # 阻塞直到有空闲槽位（令牌桶限速）
  │
  └─ env = os.environ.copy()
       env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
       env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
```

### 4.1 路径构建

```
base_name = f"{seq}_r{rp_id}"            # 例: "bartender_semitracked_r1"
rp_dir    = OUTPUT_DIR/{seq}/r{rp_id}/   # 例: .../bartender_semitracked/r1/

os.makedirs(rp_dir, exist_ok=True)

width, height, start_frame = SEQ_RES[seq]   # 例: (1920, 1080, 0)

input_ply  = DATASET_DIR/{seq}/plys/frame_%04d.ply
bin_file   = rp_dir/{base_name}.bin
rec_file   = rp_dir/{base_name}.ply          # 编码器直接重建输出（非解码输出）
enc_log    = rp_dir/{base_name}_enc.log
dec_log    = rp_dir/{base_name}_dec.log
```

如果 `input_ply % start_frame` 不存在：打印 `[SKIP]` 并 `return`。

### 4.2 断点续传检查

```
skip_enc_dec = False
if rec_file 存在 AND rec_file > 0 bytes
   AND enc_log 存在 AND dec_log 存在:
       skip_enc_dec = True
       safe_print("[RESUME] Found existing output, skipping encode/decode.")
```

### 4.3 Step 1：编码（`encode.py`）

> 仅在 `skip_enc_dec == False` 时执行

```
enc_cmd = """
  {PYTHON_EXE} encode.py
    -c {CONFIG_FILE}          # cfg/hm/ctc/cfg_3_videos.cfg
    -i {input_ply}            # .../plys/frame_%04d.ply（帧模板）
    -n {NUM_FRAMES}           # 32
    --first_frame {start_frame}
    -b {bin_file}             # 输出码流
    -r {rec_file}             # 编码器重建 PLY（用于调试，非最终解码结果）
    --qp_1  {rp['qp1']}       # Video 1（几何属性）QP，可为负
    --qp_2  {rp['qp2']}       # Video 2（颜色/SH）QP
    --format_2 {rp['fmt2']}   # yuv444 或 yuv420
    --bd_0  {rp['bd0']}       # Video 0（几何主坐标）编码位深
    --bd_pos {bd0},{bd1}      # 几何坐标 MSB,LSB 精度拆分
    --verbose
"""

run_command(enc_cmd, enc_log, env)
    # 内部用 /usr/bin/time -v 包装，记录挂钟时间和 MaxRSS
    # stdout + stderr 合并写入 enc_log
    # 返回 (returncode, full_log_content, full_log_content)

if returncode != 0 OR bin_file 不存在:
    safe_print("[ERROR] Encoding failed")
    return                         ← 提前退出

enc_metrics = parse_time_memory(stdout_enc, stderr_enc)
    # 提取 Total Time / Max RSS / Geo Time / Attr Time
```

**`encode.py` 内部调用链（简化）**：

```
encode.py
  → preprocess_args_with_config()   # 合并 cfg 文件与命令行参数
  → GroupOfPointclouds.load()       # 读入 32 帧 PLY
  → GroupOfFrames.encode()          # 分三路视频编码
      ├─ Video 0: HM-RExt, qp=0, bd_0=bd0, 几何坐标 MSB
      ├─ Video 1: HM-RExt, qp=qp1, bd=10, 几何属性
      └─ Video 2: HM-RExt, qp=qp2, bd=10, 颜色+SH
  → 打包为 .bin 码流
  → 打印 "Time: x.xxxx secondes"
```

### 4.4 Step 2：解码（`decode.py`）

> 仅在 `skip_enc_dec == False` 时执行

```
dec_output_ply = rp_dir/{base_name}_dec_%04d.ply   # 帧模板

dec_cmd = """
  {PYTHON_EXE} decode.py
    -b {bin_file}             # 输入码流
    -d {dec_output_ply}       # 输出帧模板（带 %04d 占位符）
    --first_frame {start_frame}
    --verbose
"""

run_command(dec_cmd, dec_log, env)

if returncode != 0:
    safe_print("[ERROR] Decoding failed")
    return

dec_metrics = parse_time_memory(stdout_dec, stderr_dec)
```

**`decode.py` 内部调用链（简化）**：

```
decode.py
  → 读取 .bin 码流，解析 V3C 容器
  → GroupOfFrames.decode()
      ├─ 解码 Video 0 → 几何坐标 MSB
      ├─ 解码 Video 1 → 几何属性 (opacity / scale / rotation)
      └─ 解码 Video 2 → 颜色 + SH
  → 合并重建 → 输出 {base_name}_dec_%04d.ply (32 帧)
  → 打印 "Time: x.xxxx secondes"
```

### 4.5 Step 3：注入相机位姿（`gsTools/cameraPosition`）

> 无论是否 skip_enc_dec，此步骤都会执行（断点续传也会检查）

```
for i in range(start_frame, start_frame + NUM_FRAMES):
    current_ply = dec_output_ply % i

    if current_ply 不存在: continue
    if has_camera_info(current_ply): continue   # 已有相机信息则跳过

    colmap_dir = DATASET_DIR/{seq}/colmap_data/frame_{i:04d}/sparse/
    cam_bin = colmap_dir/cameras.bin
    img_bin = colmap_dir/images.bin

    if cam_bin 存在 AND img_bin 存在:
        temp_ply = current_ply.replace(".ply", "_cam.ply")
        
        add_cam_cmd = """
          cameraPosition
            --input={current_ply}
            --output={temp_ply}
            --camera={cam_bin}
            --image={img_bin}
        """
        subprocess.run(add_cam_cmd)
        
        if temp_ply 存在:
            os.replace(temp_ply, current_ply)   # 原地替换（更新 PLY 头部）
```

**作用**：将 COLMAP 稀疏重建中的相机内外参写入解码 PLY 的头部注释，使 `mpeg-gsc-metrics` 能以正确视点渲染评估。

### 4.6 Step 4：质量评估（`mpeg-gsc-metrics`）

```
# 确定 anchor（参考帧）路径
anchor_pattern_cam = DATASET_DIR/{seq}/plys/frame_%04d.camerapos.ply
anchor_pattern_ply = DATASET_DIR/{seq}/plys/frame_%04d.ply

# 优先级：
#  1. 如果 .camerapos.ply 存在 → use_camera_pos=1, anchor=camerapos.ply
#  2. 否则检查普通 .ply 的 PLY 头部是否含 "camera_position"
#  3. 若仍无相机信息，再检查 dec PLY 是否含相机信息

metrics_cmd = """
  mpeg-gsc-metrics
    -a {anchor_pattern}          # 参考帧（原始 PLY）模板
    -b {dec_output_ply}          # 解码帧模板
    --frameCount={NUM_FRAMES}    # 32
    --startFrame={start_frame}
    --width={width}
    --height={height}
    --verbose=1
    --cpu=1                      # 使用 CPU 渲染（避免 GPU 争用）
    --useCameraPosition={0|1}    # 是否使用 PLY 头部的相机位姿
    --threads=3                  # 限制线程数（128核/40任务 ≈ 3线程/任务）
  > {metrics_log} 2>&1
"""

subprocess.run(metrics_cmd, shell=True)

qual_metrics = parse_metrics(metrics_log)
    # 提取 RGB-PSNR / YUV-PSNR / YUV-SSIM
```

### 4.7 Step 5：写入 CSV

```
row = {
    "Sequence":  seq,
    "RP":        rp_id,
    "EncT Total": enc_metrics["Total Time"],     # 编码总耗时 (秒)
    "DecT Total": dec_metrics["Total Time"],     # 解码总耗时 (秒)
    "EncT Geo":   enc_metrics["Geo Time"],       # 编码 几何时间
    "DecT Geo":   dec_metrics["Geo Time"],       # 解码 几何时间
    "EncT Attr":  enc_metrics["Attr Time"],      # 编码 属性时间
    "DecT Attr":  dec_metrics["Attr Time"],      # 解码 属性时间
    "MaxRSS Enc": enc_metrics["Max RSS"],        # 编码 峰值内存 (MB)
    "MaxRSS Dec": dec_metrics["Max RSS"],        # 解码 峰值内存 (MB)
    "RGB-PSNR":   qual_metrics["RGB-PSNR"],
    "YUV-PSNR":   qual_metrics["YUV-PSNR"],
    "YUV-SSIM":   qual_metrics["YUV-SSIM"],
    "Bin File":   bin_file,                      # 码流文件绝对路径
    "Rec File":   rec_file                       # 编码器重建 PLY 绝对路径
}

with csv_lock:                     # 线程安全写入
    csv.DictWriter.writerow(row)   # 追加到 ctc_summary.csv
    
safe_print("[SUCCESS] Finished: {seq} | RP: {rp_id}")
```

### 4.8 异常处理与 GPU 槽归还

```
except Exception as e:
    safe_print(f"[EXCEPTION] Task failed for {seq} RP{rp_id}: {str(e)}")
finally:
    gpu_queue.put(gpu_id)   # 无论成功/失败/异常，必须归还 GPU 槽位
                             # 否则后续任务会永久阻塞在 gpu_queue.get()
```

---

## 五、并发调度模型

### GPU 令牌桶（Token Bucket）

```
初始化：gpu_queue = Queue()
        [3,3,3,3,3,3,3,3, 4,4,4,4,4,4,4,4, 5,5,..., 7,7,7,7,7,7,7,7]
         ↑── 每张 GPU 重复 8 次 ───────────────────────────────────────↑
         # 共 5 × 8 = 40 个令牌

任务开始时: gpu_id = gpu_queue.get()   # 阻塞等待，限制并发上限
任务结束时: gpu_queue.put(gpu_id)      # 归还令牌，允许新任务开始
```

### ThreadPoolExecutor 调度

```
ThreadPoolExecutor(max_workers=40)
  ├─ 最多 40 个工作线程同时活跃（对应 5 GPU × 8 并发槽）
  ├─ 每个线程执行一个 process_single_task()
  ├─ 线程内部通过 gpu_queue.get() 进一步限流（令牌桶）
  └─ as_completed(futures) 收集所有结果（顺序不定）
```

### 线程安全机制

| 资源 | 保护方式 | 说明 |
|------|---------|------|
| CSV 文件 | `csv_lock` (threading.Lock) | 防止多线程同时写入导致行错乱 |
| stdout 输出 | `print_lock` (threading.Lock) | 防止多线程 print 交错混乱 |
| GPU 资源 | `gpu_queue` (Queue) | 令牌桶限速，防止 GPU OOM |
| 文件系统 | `os.makedirs(exist_ok=True)` | 防止并发创建目录时竞争 |

---

## 六、辅助函数说明

### `run_command(cmd, log_file, env)`

```
输入: shell 命令字符串、日志文件路径、环境变量 dict
处理:
  1. 用 /usr/bin/time -v 包装命令，统计系统级时间和内存
  2. 将 stdout + stderr 合并写入 log_file
  3. process.wait() 等待完成
输出: (returncode, log_content, log_content)
     # stdout 和 stderr 返回值相同（均为 log 全文），
     # parse_time_memory 分别处理 encode.py 打印和 time -v 输出
```

### `parse_time_memory(stdout, stderr)`

```
解析优先级：
  1. Total Time: 优先匹配 "Time: x.xxxx secondes"（encode.py/decode.py 打印）
                 其次 "Elapsed (wall clock) time ... h:mm:ss"（/usr/bin/time -v）
  2. Max RSS:    匹配 "Maximum resident set size (kbytes): N"（/usr/bin/time -v）
                 转换为 MB（÷1024）
  3. Geo Time:   匹配 "EncT|DecT Geometry: x.xxxx"
  4. Attr Time:  匹配 "EncT|DecT Attributes: x.xxxx"

返回: {"Total Time", "Max RSS", "Geo Time", "Attr Time"}
```

### `parse_metrics(log_file)`

```
从 mpeg-gsc-metrics 输出日志中提取：
  "Psnr RGB (avg)    = x.xxxx"  → RGB-PSNR
  "Psnr YUV (avg)    = x.xxxx"  → YUV-PSNR
  "SSIM (avg)        = x.xxxx"  → YUV-SSIM
  
若文件不存在：返回全零 dict
```

### `has_camera_info(ply_path)`

```
读取 PLY 文件前 2KB（ASCII 头部区域）
检查是否包含字符串 "camera_position"
返回 True/False
（用于决定是否跳过相机注入步骤）
```

---

## 七、输出文件结构

```
output_nf/tmcv_ctc_results/
├── ctc_summary.csv                      # 汇总表：所有序列×码率点的指标
│
├── bartender_semitracked/
│   ├── r1/
│   │   ├── bartender_semitracked_r1.bin          # 码流
│   │   ├── bartender_semitracked_r1.ply          # 编码器重建 PLY（32帧合并）
│   │   ├── bartender_semitracked_r1_dec_%04d.ply # 解码 PLY（每帧独立）
│   │   ├── bartender_semitracked_r1_enc.log      # 编码日志（含 time -v）
│   │   ├── bartender_semitracked_r1_dec.log      # 解码日志（含 time -v）
│   │   └── bartender_semitracked_r1_metrics.log  # metrics 工具输出
│   ├── r2/ ... r5/
│
├── cinema_semitracked/ ...
...（共 23 个序列，每序列 5 个 rN 子目录）
```

### `ctc_summary.csv` 列定义

| 列名 | 含义 | 单位 |
|------|------|------|
| Sequence | 序列名 | — |
| RP | 码率点编号 (1~5) | — |
| EncT Total | 编码总耗时 | 秒 |
| DecT Total | 解码总耗时 | 秒 |
| EncT Geo | 编码几何时间 | 秒 |
| DecT Geo | 解码几何时间 | 秒 |
| EncT Attr | 编码属性时间 | 秒 |
| DecT Attr | 解码属性时间 | 秒 |
| MaxRSS Enc | 编码峰值内存 | MB |
| MaxRSS Dec | 解码峰值内存 | MB |
| RGB-PSNR | RGB 平均 PSNR | dB |
| YUV-PSNR | YUV 平均 PSNR | dB |
| YUV-SSIM | YUV 平均 SSIM | 0~1 |
| Bin File | 码流文件绝对路径 | — |
| Rec File | 编码器重建 PLY 绝对路径 | — |

---

## 八、完整执行序列（时序伪代码）

```
python anchor_run/tmcv_run_ctc.py
│
├─ [模块加载] 常量初始化、gpu_queue 填充 40 个令牌
│
└─ main()
    ├─ chdir(ROOT_DIR)
    ├─ makedirs(OUTPUT_DIR)
    ├─ 读取/创建 ctc_summary.csv，构建 existing_records
    ├─ 构建 tasks 列表（115 个 (seq, rp) 元组）
    ├─ 打印统计摘要
    │
    └─ ThreadPoolExecutor(40 workers)
        │
        ├─ [Thread-01] process_single_task("bartender_semitracked", RP1)
        │    ├─ [0] 检查 existing_records → 未完成，继续
        │    ├─ [0] gpu_queue.get() → gpu_id=3
        │    ├─ [1] encode.py ... --qp_1 -8 ... → .bin (编码 ~60s)
        │    ├─ [2] decode.py ... → _dec_%04d.ply (解码 ~5s)
        │    ├─ [3] cameraPosition × 32帧 → 注入相机信息
        │    ├─ [4] mpeg-gsc-metrics → RGB/YUV-PSNR, SSIM (~30s)
        │    ├─ [5] csv_lock → 写入 CSV 一行
        │    └─ [F] gpu_queue.put(3) → 归还令牌
        │
        ├─ [Thread-02] process_single_task("bartender_semitracked", RP2)
        │    └─ ... (同上，gpu_id=3，与 Thread-01 并发)
        │
        ├─ ... (最多 40 个线程同时运行)
        │
        └─ as_completed → 等待全部 115 个任务完成
    
    └─ print("[ALL DONE] ... ctc_summary.csv")
```

---

## 九、关键设计决策说明

| 设计 | 原因 |
|------|------|
| 每 RP 独立子目录（`r1/`, `r2/`...）| 避免多线程并发时同一序列不同 RP 的中间文件（如 `02_dcsh_enc.log`）互相覆盖 |
| GPU 令牌桶 | 5张 GPU 各最多 8 个并发，防止 GPU 显存溢出（OOM）|
| `--threads=3` in metrics | 最多 40 任务并发，每任务 3 个 metrics 线程，理论最大值 120 ≤ 128 CPU 核心，充分利用但不过载（实际同时运行的任务受 GPU 令牌桶限制） |
| `YUV-PSNR > 0.1` 判定完成 | 过滤编码/解码成功但 metrics 失败（PSNR=0）的行，强制重新评估 |
| `/usr/bin/time -v` 包装 | 获取真实系统级时间和内存，比 Python 内部计时更准确 |
| `CUDA_VISIBLE_DEVICES` per-task | 隔离 GPU 使用，防止不同任务的 PyTorch/CUDA 操作互相干扰 |
| `os.replace(temp, current)` | 原子性文件替换，防止相机注入中途崩溃导致原始文件损坏 |
