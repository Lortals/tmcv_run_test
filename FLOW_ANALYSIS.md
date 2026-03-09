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
  → GroupOfFrames.encode()          # 分三路视频编码（详见 §十）
      ├─ Video 0: HM-RExt, qp=0 + lossless.cfg, bd_0=bd0, 几何坐标（x/y/z MSB+LSB），近无损
      ├─ Video 1: HM-RExt, qp=qp1, bd=10（固定），几何属性（opacity/scale/rotation），有损帧内
      └─ Video 2: HM-RExt, qp=qp2, bd=10（固定），颜色+SH（f_dc+f_rest），有损帧间
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

---

## 十、`encode.py` 三路视频的 `qp` 与 `bd` 参数详解

### 10.1 参数来源

`tmcv_run_ctc.py` 调用 `encode.py` 时传入的关键参数为：

```bash
encode.py
  --bd_0   {bd0}          # Video 0 的 bit depth（随码率点变化）
  --bd_pos {bd0},{bd1}    # 几何坐标 MSB,LSB 精度（bd_pos[0]=bd0, bd_pos[1]=bd1）
  --qp_1   {qp1}          # Video 1 的量化参数（随码率点变化）
  --qp_2   {qp2}          # Video 2 的量化参数（随码率点变化）
  # Video 0 的 qp 由 cfg_3_videos.cfg 指定为 0（配合 lossless.cfg）
  # Video 1/2 的 bd 由 cfg_3_videos.cfg 固定为 10
```

`cfg/hm/ctc/cfg_3_videos.cfg` 定义了三路视频各自的**组件分配、编码器类型、格式、打包方式**，而 `tmcv_run_ctc.py` 只覆盖 `qp_1`、`qp_2`、`bd_0`、`bd_pos`。

---

### 10.2 `bd`（位深，Bit Depth）的双重角色

`bd` 在 TMCV 管线中同时扮演**两个不同但相关**的角色：

#### 角色 1：TMCV 应用层量化精度（`VideoData._quantize_linear`）

每个高斯点的浮点属性（如 opacity、scale、f_dc_0 等）在打包进视频前，需先经过**线性量化**映射到整数：

```
normed    = (value - min_val) / (max_val - min_val)   # 归一化到 [0,1]
quantized = round(normed × 2^bd)                       # 映射到 [0, 2^bd - 1] 整数
```

`bd` 越大 → 量化区间越细 → **TMCV 应用层引入的量化误差越小**。

| Video | 包含的属性 | `bd` 控制的量化精度 |
|-------|-----------|-------------------|
| Video 0 | x, y, z 几何坐标 | 由 `--bd_pos bd0,bd1` 控制（MSB 用 `bd0` 位，LSB 用 `bd1` 位，合计 `bd0+bd1` 位精度） |
| Video 1 | opacity, scale(×3), rotation(×4) | `bd=10`（固定，10 位精度） |
| Video 2 | f_dc(×3), f_rest(×45) 颜色/SH | `bd=10`（固定，10 位精度） |

#### 角色 2：HM-RExt 编码器的输入/内部位深（`encode_hm` → `--InputBitDepth`）

量化后的整数数据以 `bd` 位的 YUV 视频帧写入磁盘，再送给 HM-RExt 编码：

```python
# video_codec.py encode_hm()
cmd += [
    '--InputBitDepth='    + str(max(video.bits, 8)),   # video.bits == bd
    '--InternalBitDepth=' + str(max(video.bits, 8)),
    '--OutputBitDepth='   + str(max(video.bits, 8)),
]
```

**`bd` 决定了 HM-RExt 处理的样本范围上限**：`bd=10` 时样本值域为 `[0, 1023]`，`bd=8` 时为 `[0, 255]`。这同时影响了 HM-RExt 内部的 `QpBdOffset`（见 §10.4）。

---

### 10.3 各码率点的 `bd` 取值设计

| RP | bd0 (Video 0 MSB) | bd1 (Video 0 LSB) | Video 1 bd | Video 2 bd | 几何总精度 |
|----|-------------------|-------------------|------------|------------|-----------|
| 1  | 10                | 9                 | 10（固定）  | 10（固定）  | 19 位     |
| 2  | 10                | 6                 | 10（固定）  | 10（固定）  | 16 位     |
| 3  | 9                 | 6                 | 10（固定）  | 10（固定）  | 15 位     |
| 4  | 9                 | 6                 | 10（固定）  | 10（固定）  | 15 位     |
| 5  | 8                 | 6                 | 10（固定）  | 10（固定）  | 14 位     |

**设计逻辑**：
- **RP1（最高码率）**：`bd0=10, bd1=9` → 几何坐标总精度 19 位，几乎接近浮点精度。
- **RP5（最低码率）**：`bd0=8, bd1=6` → 几何坐标总精度 14 位，量化更粗，码率更低。
- **Video 1/2 的 bd 恒为 10**：属性和颜色精度不跟码率点走，仅由视频 QP（qp1/qp2）控制质量。

---

### 10.4 `qp`（量化参数，Quantization Parameter）的含义

`qp` 是传给 HM-RExt (`--QP=`) 的**视频编码量化参数**，直接控制视频帧的有损压缩程度：

```
QP 越大  →  量化步长越大  →  压缩损失越大  →  码率越低、质量越差
QP 越小  →  量化步长越小  →  压缩损失越小  →  码率越高、质量越好
```

#### HM-RExt 的 QpBdOffset 机制（负 QP 的由来）

H.265/HEVC 规范定义：

```
QpBdOffset = 6 × (bitDepth − 8)
```

对于 `bd=10`（Video 1/2 的固定位深）：

```
QpBdOffset = 6 × (10 − 8) = 12
```

HM-RExt 实际量化使用的是**内部有效 QP**：

```
QP_effective = QP_external + QpBdOffset
```

因此，当 `QP_external = -8` 时：`QP_effective = -8 + 12 = 4`（接近无损）。

这就是为什么 RP1/RP2 的 `qp1` 为**负数**：它是为了在 10 位编码下获得比 `QP_external=0`（有效 QP=12）更精细的量化质量。HM-RExt 对 10 位输入允许 `QP_external ∈ [-12, 51]`，负值完全合法。

---

### 10.5 三路视频的 `qp` 设计决策

#### Video 0：几何坐标（x, y, z, x_add, y_add, z_add）

```
qp_0  = 0（来自 cfg_3_videos.cfg）
config = encoder_intra_main_rext.cfg + lossless/lossless.cfg
bd_0  = bd0（随码率点变化：10/10/9/9/8）
```

| 参数 | 值 | 原因 |
|------|-----|------|
| `qp=0` | 固定 | `lossless.cfg` 将 HM 切换到**无损模式**，QP 值在无损模式下不生效，本质上 qp=0 仅作占位 |
| `lossless.cfg` | 强制启用 | 几何坐标（x/y/z）是高斯点位置的精确描述，任何有损压缩都会导致点云几何失真，进而严重影响 3DGS 渲染质量 |
| `bd_0` 随码率变化 | 10→8 | 通过减少量化位数来降低几何精度和码率，是 RP1→RP5 码率控制的主要手段之一 |
| `format=yuv400` | 仅亮度 | 几何坐标是标量，无需色度通道；单通道节省 2/3 空间 |
| `packing=planar` | 平面打包 | x/y/z/x_add/y_add/z_add 共 6 个分量各自独占一个通道平面，帧间无时序依赖 |
| `config=intra_main_rext` | 帧内编码 | 几何分量帧间相关性弱（不同帧高斯点数量和排列不同），帧内编码更稳定 |

#### Video 1：几何属性（opacity, scale×3, rotation×4）

```
qp_1  = qp1（来自 RATE_POINTS，随码率点变化）
bd_1  = 10（固定，来自 cfg_3_videos.cfg）
config = encoder_intra_main_rext.cfg（帧内，无 lossless）
format = yuv400，packing = planar
```

| RP | qp1 | QP_effective（10-bit） | 质量倾向 |
|----|-----|-----------------------|---------|
| 1  | -8  | 4                     | 近无损   |
| 2  | -4  | 8                     | 高质量   |
| 3  | 4   | 16                    | 中等     |
| 4  | 8   | 20                    | 中低     |
| 5  | 16  | 28                    | 低质量   |

**为什么不使用无损模式**：属性参数（opacity、scale、rotation）对渲染有影响但容错性高于几何坐标；有损压缩可以大幅降低码率，且视觉质量下降可控。

**为什么 bd 固定为 10**：属性量化精度独立于码率点；用 QP 调控属性质量比用 bd 更灵活（QP 可以连续调节）。

#### Video 2：颜色 + 球谐系数（f_dc×3, f_rest×45）

```
qp_2  = qp2（来自 RATE_POINTS，随码率点变化）
bd_2  = 10（固定，来自 cfg_3_videos.cfg）
config = encoder_lowdelay_main_rext.cfg（低延迟帧间编码）
format = yuv444（RP1/2/3）或 yuv420（RP4/5）
packing = temporal（时序打包）
```

| RP | qp2 | fmt2   | 颜色/SH 质量 |
|----|-----|--------|------------|
| 1  | 0   | yuv444 | 最高（有效 QP=12） |
| 2  | 4   | yuv444 | 较高（有效 QP=16） |
| 3  | 12  | yuv444 | 中等（有效 QP=24） |
| 4  | 16  | yuv420 | 中低（+色度降采样） |
| 5  | 24  | yuv420 | 低（有效 QP=36）   |

**为什么使用 `encoder_lowdelay`（帧间低延迟模式）**：颜色和球谐系数在相邻帧之间往往高度相关（3DGS 场景动态变化小），帧间预测可以显著降低码率。与 Video 0/1 使用帧内模式不同。

**为什么 `temporal` 打包**：48 个颜色/SH 分量（f_dc×3 + f_rest×45）被时序打包到一个视频流中（在时间轴上堆叠），充分利用帧间预测；而 planar 打包会为每个分量单独创建一帧，帧间相关性更弱。

**为什么 `yuv444` vs `yuv420`**：SH 系数通过 BT.601 RGB→YUV 转换处理（`sh_conversion=601`），yuv444 保留了全分辨率色度，质量更高但码率也更高；低码率点切换 yuv420 以牺牲色度精度换取码率节省。

---

### 10.6 三路视频参数汇总对比

| 属性 | Video 0（几何坐标） | Video 1（几何属性） | Video 2（颜色/SH） |
|------|-------------------|-------------------|------------------|
| `comp` | x,y,z,x_add,y_add,z_add | opacity,rot_3,zero,scale_0~2,rot_0~2 | f_dc_0~2, f_rest_0~44 |
| `bd` | bd0（8/9/10，随 RP 变化） | **10（固定）** | **10（固定）** |
| `qp` | **0（固定）** | qp1（-8/-4/4/8/16，随 RP 变化） | qp2（0/4/12/16/24，随 RP 变化） |
| `format` | yuv400 | yuv400 | yuv444（RP1-3）/ yuv420（RP4-5） |
| `packing` | planar | planar | temporal |
| `codec_config` | intra + lossless | intra（有损） | lowdelay（帧间） |
| **码率控制手段** | **bd 精度** | **QP 量化** | **QP + 格式降采样** |
| **设计原因** | 几何必须近无损 | 属性容忍适度有损 | 颜色/SH 利用帧间相关性 |

---

## 十一、为什么 Object-Centric 的编解码时间普遍小于 Forward Facing？

### 11.1 表面悖论：更高分辨率的相机，更短的编解码时间？

从测试序列的基本参数来看，Object-Centric（OC）序列的**输入相机分辨率**显著高于 Forward Facing（FF）序列：

| 类别 | 典型相机分辨率 | 典型相机数量 | 典型编解码时间 (NF=32, RP3) |
|------|-------------|------------|--------------------------|
| Forward Facing | 1920×1080 | 15 – 35 | **相对较长** |
| Object-Centric | 2456×2054 – 4594×5514 | 21 – 132 | **相对较短** |

这看起来违反直觉——相机分辨率更高、相机数更多的 OC 序列，为什么编解码反而更快？

**根本原因：TMCV 的编解码时间取决于高斯点数量，而非输入相机分辨率。**

---

### 11.2 关键事实：输入是 PLY 文件，不是相机图像

TMCV 的编码器（`encode.py`）接收的输入是已经训练好的 **3DGS 高斯点云（.ply 文件）**，而不是原始相机图像。

```
encode.py -i frame_%04d.ply   ← 高斯点云，不是相机图像
```

3DGS 训练（在 TMCV 流程之外）决定了每帧的高斯点数量 N。相机分辨率只影响 3DGS 训练质量，不直接参与 TMCV 编解码。

**TMCV 的编解码时间主要由 `N`（有效高斯点数量）决定。**

---

### 11.3 PLAS 排序网格尺寸：编解码时间的根本决定因素

在编码开始之前，高斯点需要通过 PLAS 排序映射到二维网格上（`utils/plas.py → resize()`）：

```python
# utils/plas.py resize()
n = int(np.sqrt(num_points_gof))          # GoF 中最少帧的高斯点数
sidelen_w = n // min_block_size * min_block_size   # 向下取整到 16 的倍数
sidelen_h = sidelen_w                              # 正方形网格 (非矩形排序时)
prune_gaussians(pointcloud, sidelen_w * sidelen_h) # 裁剪到 sidelen²
```

`sidelen` 决定了**所有三路视频的帧尺寸**：

| 视频 | 打包方式 | 每帧尺寸 | 帧数 (NF=32) |
|------|---------|---------|-------------|
| Video 0（几何） | planar，6分量，网格 3×2 | `sidelen × 3` × `sidelen × 2` | 32 |
| Video 1（属性） | planar，9分量，网格 3×3 | `sidelen × 3` × `sidelen × 3` | 32 |
| Video 2（颜色/SH） | temporal，48分量 | `sidelen × 1` × `sidelen × 1` | **32 × 48 = 1536** |

**三路视频总像素数约正比于 `sidelen²`，而 `sidelen ∝ sqrt(N)`，因此编解码总像素数 ∝ N。**

具体数值对比：

| 高斯点数 N | sidelen | 三路总像素数 (NF=32) | 相对编码时间 |
|-----------|---------|---------------------|-----------|
| 300,000   | 544     | ~6.0 亿像素          | 1× (基准) |
| 500,000   | 704     | ~10.0 亿像素         | ~1.7×    |
| 1,000,000 | 992     | ~19.8 亿像素         | ~3.3×    |
| 2,000,000 | 1408    | ~40.0 亿像素         | ~6.7×    |
| 3,000,000 | 1728    | ~60.2 亿像素         | ~10×     |

HM 编码器的时间复杂度近似为 O(总像素数) ，因此高斯点数量是编解码时间的主导因素。

---

### 11.4 为什么 OC 序列的高斯点数更少？

3DGS 重建 **单个物体**（Object-Centric）所需的高斯点数，通常**显著少于**重建一个**完整室内/室外场景**（Forward Facing）：

#### Forward Facing 序列的典型特征

| 序列 | 场景描述 | 典型高斯点数估算 |
|------|---------|---------------|
| `bartender_semitracked` | 酒吧场景，多人+复杂背景 | **1M – 3M** |
| `cinema_semitracked` | 影院场景，大空间+多人 | **1M – 3M** |
| `breakfast_semitracked` | 餐桌场景，桌面+多人+背景 | **0.8M – 2M** |
| `breakdance_untracked` | 舞蹈场景，较大空间 | **1M – 3M** |

**原因**：FF 序列的相机面朝一个大型场景（如餐厅、影院），3DGS 需要用大量高斯点覆盖前景人物、桌椅、墙壁、地板等复杂背景，导致点数多、网格大。

#### Object-Centric 序列的典型特征

| 序列 | 场景描述 | 典型高斯点数估算 |
|------|---------|---------------|
| `gymnast` | 单人体操，2456×2054 相机 | **0.3M – 0.8M** |
| `flowerdance` | 单人舞蹈，2456×2054 相机 | **0.3M – 0.8M** |
| `plant` | 单个植物，2954×3968 相机 | **0.2M – 0.6M** |
| `cricket_player` | 单人运动，4520×2540 相机 | **0.4M – 1M** |
| `solo_tango_female` | 单人舞蹈，4534×2542 相机 | **0.4M – 1M** |
| `lego_ferrari` | 单个乐高模型，4594×5514 相机 | **0.5M – 1.5M** |

**原因**：OC 序列的相机围绕**单个有界物体**（人、车模、植物）环绕拍摄，3DGS 只需重建该物体本身（通常有干净背景或背景遮罩），高斯点数量因此远少于 FF 序列。相机分辨率高是为了提高**单物体的重建细节**，而不会导致高斯点数量成比例增加。

> **关键区别**：一个人站在前景（OC）vs 一整个酒吧场景（FF）——前者的高斯点数量可以是后者的 1/5 到 1/10。

---

### 11.5 `min_num_gaussian_in_gof` 的放大效应

对于 NF=32 帧的编码，`encode.py` 使用 GoF 中**最少帧**的高斯点数来确定 `sidelen`：

```python
# encode.py
min_num_gaussian = pcs.get_min_num_gaussian_in_gof()  # 取 32 帧中点数最少的那帧
sort(..., num_points_gof=min_num_gaussian, ...)        # 所有帧都裁剪到这个数
```

对于动态 OC 序列（如 `gymnast`、`tango_duo`、`flowerdance`），每帧 3DGS 训练独立，帧间高斯点数差异可能较大（某帧动态模糊或遮挡可能导致高斯点骤降）。这会进一步降低有效高斯点数，从而加速编码。

---

### 11.6 例外情况：哪些 OC 序列编码时间不短？

不是所有 OC 序列都比 FF 快，以下情况是例外：

| 序列 | 原因 |
|------|------|
| `manwithfruit_tracked` | 被追踪的完整人物（带手持水果），3840×2160 高分辨率，且作为 NF=32 的**多帧**，高斯点数可能与部分 FF 序列相当 |
| `lego_ferrari`（128 相机） | 极高相机密度（128 个视角）可能导致 3DGS 过度填充细节，产生较多高斯点 |
| `lego_bugatti`（132 相机） | 同上 |

这些序列尽管也是 OC，但由于场景重建精度要求或相机数量导致高斯点较多，编码时间与 FF 序列相近或更长。

---

### 11.7 总结：编解码时间的决定因素层次

```
编解码时间 ∝ 总像素数 ∝ sidelen² × (各视频帧数)
                ↑
         sidelen = floor(sqrt(N)/16) × 16
                ↑
         N = min_num_gaussian_in_gof (GoF 中最少高斯点数)
                ↑
      N 由 3DGS 重建质量和场景复杂度决定：
      - Object-Centric (单物体) → 通常 N 较小 (0.3M–1.5M)
      - Forward Facing (完整场景) → 通常 N 较大 (1M–3M)
```

**输入相机分辨率、相机数量对 TMCV 编解码时间几乎没有直接影响**（它们只影响 3DGS 训练质量，而 3DGS 训练在 TMCV 流程之外完成）。

因此，**几乎所有 OC 序列的编解码时间小于 FF 序列，是因为 OC 单物体场景的 3DGS 高斯点数量通常显著少于 FF 完整场景——更小的高斯点网格意味着更小的视频帧，从而大幅缩短 HM 编码时间**。
