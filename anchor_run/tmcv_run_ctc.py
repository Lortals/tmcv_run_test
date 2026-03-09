import os
import subprocess
import re
import csv
import sys
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# 1. 核心并发与显卡配置 (榨干服务器性能的关键)
# ==========================================
# 分配可用的 GPU 列表。假设 0 号卡被占用，我们使用剩下的 7 张卡
AVAILABLE_GPUS = [3, 4, 5, 6, 7] 

# 每张 GPU 同时承载的任务数。
# 3090 有 24G 显存，TMCV 的 GPU 占用较小，这里设为 8。
# 总并发数 = 5 * 8 = 40 个并行任务 (远小于您的 128 个 CPU 核心，非常安全高效)
TASKS_PER_GPU = 8 
NUM_FRAMES = 32

# ==========================================
# 2. 测试序列与码率点配置
# ==========================================
SEQUENCES = [
    "bartender_semitracked", "cinema_semitracked", "breakfast_semitracked",
    "breakfast_untracked", "breakdance_untracked",
    "bartender_tracked", "cinema_tracked", "breakfast_tracked",
    "manwithfruit_tracked"
]

RATE_POINTS = [
    # bd0 = MSB bit depth (geometry x,y,z)   bd1 = LSB bit depth (geometry x_add,y_add,z_add)
    # Passed to encode.py as: --bd_0 bd0 --bd_pos bd0,bd1
    # Source: m74517 Table 1 (MSB BD / LSB BD columns)
    {"rp": 1, "qp1": -8, "qp2": 0,  "fmt2": "yuv444", "bd0": 10, "bd1": 9},
    {"rp": 2, "qp1": -4, "qp2": 4,  "fmt2": "yuv444", "bd0": 10, "bd1": 6},
    {"rp": 3, "qp1": 4,  "qp2": 12, "fmt2": "yuv444", "bd0": 9,  "bd1": 6},
    {"rp": 4, "qp1": 8,  "qp2": 16, "fmt2": "yuv420", "bd0": 9,  "bd1": 6},
    {"rp": 5, "qp1": 16, "qp2": 24, "fmt2": "yuv420", "bd0": 8,  "bd1": 6}
]

# ==========================================
# 3. 路径与全局锁初始化
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR) # mpeg-gsc-tmcv root
DATASET_DIR = "/home/data/datasets/mpeg_gsdata/CTC"
OUTPUT_DIR = os.path.join(ROOT_DIR, "output_nf", "tmcv_ctc_results")
CONFIG_FILE = os.path.join(ROOT_DIR, "cfg", "hm", "ctc", "cfg_3_videos.cfg")

METRICS_TOOL = "/home/zhongdalv/mpeg-gsc-metrics/build/clang/Release/bin/mpeg-gsc-metrics"
ADD_CAMERA_POS_EXE = "/home/zhongdalv/mpeg-gsc-tools/gsTools/build/msvc/Release/bin/cameraPosition"
PYTHON_EXE = "/home/zhongdalv/anaconda3/envs/v3c_gsc_cloned/bin/python"

# Format: (width, height, start_frame)
SEQ_RES = {
    # Forward Facing
    "bartender_semitracked": (1920, 1080, 0),
    "cinema_semitracked": (1920, 1080, 0),
    "breakfast_semitracked": (1920, 1080, 0),
    "breakfast_untracked": (1920, 1080, 0),
    "breakdance_untracked": (1920, 1080, 0),
    "bartender_tracked": (1920, 1080, 0),
    "cinema_tracked": (1920, 1080, 0),
    "breakfast_tracked": (1920, 1080, 0),

    # Object Centric
    "manwithfruit_tracked": (3840, 2160, 81),
    "lego_ferrari": (4594, 5514, 0),
    "lego_bugatti": (3852, 2868, 0),
    "cricket_player": (4520, 2540, 0),
    "plant": (2954, 3968, 0),
    "solo_tango_female": (4534, 2542, 0),
    "solo_tango_male": (4528, 2544, 0),
    "tango_duo": (4522, 2538, 0),
    "tennis_player": (4518, 2540, 0),
    "flowerdance": (2456, 2054, 0),
    "gymnast": (2456, 2054, 200)
}

# 初始化 GPU 动态调度队列
gpu_queue = queue.Queue()
for gpu in AVAILABLE_GPUS:
    for _ in range(TASKS_PER_GPU):
        gpu_queue.put(gpu)

# 线程锁：确保多线程写入 CSV 和打印日志时不会互相覆盖、错行
csv_lock = threading.Lock()
print_lock = threading.Lock()

def safe_print(msg):
    with print_lock:
        print(msg)

# ==========================================
# 4. 核心功能函数
# ==========================================
def has_camera_info(ply_path):
    """检查PLY文件是否已经包含相机视角信息"""
    try:
        if not os.path.exists(ply_path): return False
        with open(ply_path, 'rb') as f:
            # 读取前2KB检查头部注释
            header = f.read(2048).decode('utf-8', errors='ignore')
            return "camera_position" in header
    except:
        return False

def run_command(cmd, log_file, env):
    """带环境变量支持的命令执行，提取时间和内存"""
    log_file = os.path.abspath(log_file)
    full_cmd = f"/usr/bin/time -v {cmd}"
    
    with open(log_file, "w") as f:
        # 传入 env 环境变量以实现 CUDA_VISIBLE_DEVICES 隔离
        process = subprocess.Popen(full_cmd, shell=True, env=env, stdout=f, stderr=subprocess.STDOUT)
        process.wait()
        
    with open(log_file, "r", errors='ignore') as f:
        content = f.read()

    return process.returncode, content, content

def parse_time_memory(stdout, stderr):
    """从日志中解析 EncT/DecT 和 MaxRSS"""
    metrics = {"Total Time": 0.0, "Max RSS": 0.0, "Geo Time": 0.0, "Attr Time": 0.0}
    
    # 1. 解析 Max RSS (来自 /usr/bin/time -v stderr)
    rss_match = re.search(r"Maximum resident set size \(kbytes\): (\d+)", stderr)
    if rss_match:
        metrics["Max RSS"] = float(rss_match.group(1)) / 1024.0 
    
    # 2. 解析 Total Time (来自 /usr/bin/time -v stderr 或 encode.py 输出)
    # 优先使用 encode.py/decode.py 输出的 "Time: x.xxxx secondes"
    py_time_match = re.search(r"Time:\s+([\d\.]+)\s+secondes", stdout)
    if py_time_match:
        metrics["Total Time"] = float(py_time_match.group(1))
    else:
        # 否则回退到 /usr/bin/time -v
        wall_match = re.search(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): ([\d:\.]+)", stderr)
        if wall_match:
            t_str = wall_match.group(1)
            parts = t_str.split(':')
            if len(parts) == 3:
                val = float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
            elif len(parts) == 2:
                val = float(parts[0])*60 + float(parts[1])
            else:
                val = float(parts[0])
            metrics["Total Time"] = val

    # 3. 解析 Geometry / Attributes 时间 (来自 encode.py/decode.py 的自定义打印)
    # EncT Geometry: 12.3400 / DecT Geometry: 1.2300
    geo_match = re.search(r"(?:EncT|DecT)\s+Geometry:\s+([\d\.]+)", stdout)
    if geo_match:
        metrics["Geo Time"] = float(geo_match.group(1))

    # EncT Attributes: 5.6700 / DecT Attributes: 0.4500
    attr_match = re.search(r"(?:EncT|DecT)\s+Attributes:\s+([\d\.]+)", stdout)
    if attr_match:
        metrics["Attr Time"] = float(attr_match.group(1))
            
    return metrics

def parse_metrics(log_file):
    """从 mpeg-gsc-metrics 日志中提取 PSNR/SSIM"""
    metrics = {"RGB-PSNR": 0.0, "YUV-PSNR": 0.0, "YUV-SSIM": 0.0}
    if not os.path.exists(log_file):
        return metrics
    
    with open(log_file, "r", errors='ignore') as f:
        content = f.read()
    
    # 根据 gscodec 的 collect_results_gscodec.py 逻辑匹配
    # Psnr RGB (avg)       =   33.1234
    rgb_match = re.search(r"Psnr RGB \(avg\)\s+=\s+([\d\.]+)", content)
    if rgb_match: metrics["RGB-PSNR"] = float(rgb_match.group(1))
    
    # Psnr YUV (avg)       =   35.6789
    yuv_match = re.search(r"Psnr YUV \(avg\)\s+=\s+([\d\.]+)", content)
    if yuv_match: metrics["YUV-PSNR"] = float(yuv_match.group(1))
    
    # SSIM (avg)           =   0.9876
    ssim_match = re.search(r"SSIM \(avg\)\s+=\s+([\d\.]+)", content)
    if ssim_match: metrics["YUV-SSIM"] = float(ssim_match.group(1))
    
    return metrics

def process_single_task(seq, rp, results_csv, csv_headers, existing_records):
    """单个序列+码率点的完整端到端测试任务"""
    rp_id = rp["rp"]
    
    # 0. 检查是否已在 CSV 中记录 (避免重复写入)
    if (seq, str(rp_id)) in existing_records:
        safe_print(f"[SKIP] Already found in CSV: {seq} RP{rp_id}")
        return

    # 阻塞式获取一个空闲的 GPU 槽位
    gpu_id = gpu_queue.get()
    
    # 设定当前任务独占的环境变量
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    
    try:
        base_name = f"{seq}_r{rp_id}"
        # 修改：为每个 RP 创建独立的子目录，避免中间文件(如02_dcsh_enc.log)冲突和覆盖
        rp_dir = os.path.join(OUTPUT_DIR, seq, f"r{rp_id}")
        os.makedirs(rp_dir, exist_ok=True)
        
        # 解包 SEQ_RES 中的 (width, height, start_frame) 3-tuple
        width, height, start_frame = SEQ_RES.get(seq, (1920, 1080, 0))
        
        input_ply = os.path.join(DATASET_DIR, seq, "plys", "frame_%04d.ply")
        if not os.path.exists(input_ply % start_frame):
            safe_print(f"[SKIP] Input file not found: {input_ply % start_frame}")
            return
            
        bin_file = os.path.abspath(os.path.join(rp_dir, f"{base_name}.bin"))
        rec_file = os.path.abspath(os.path.join(rp_dir, f"{base_name}.ply"))
        enc_log = os.path.abspath(os.path.join(rp_dir, f"{base_name}_enc.log"))
        dec_log = os.path.abspath(os.path.join(rp_dir, f"{base_name}_dec.log"))
        
        # 防重复运行机制 (断点续传) - 检查是否已完成编码和解码
        skip_enc_dec = False
        if os.path.exists(rec_file) and os.path.getsize(rec_file) > 0 and \
           os.path.exists(enc_log) and os.path.exists(dec_log):
             skip_enc_dec = True
             safe_print(f"[RESUME] Found existing output for {seq} RP{rp_id}, skipping encode/decode.")

        # --- 1. Encoding & 2. Decoding ---
        enc_metrics = {"Total Time": 0.0, "Max RSS": 0.0, "Geo Time": 0.0, "Attr Time": 0.0}
        dec_metrics = {"Total Time": 0.0, "Max RSS": 0.0, "Geo Time": 0.0, "Attr Time": 0.0}

        if not skip_enc_dec:
            safe_print(f"[START] Seq: {seq} | RP: {rp_id} | Using GPU: {gpu_id}")
            
            # --- 1. Encoding ---
            enc_cmd = (
                f"{PYTHON_EXE} encode.py -c {CONFIG_FILE} -i {input_ply} -n {NUM_FRAMES} --first_frame {start_frame} "
                f"-b {bin_file} -r {rec_file} --qp_1 {rp['qp1']} --qp_2 {rp['qp2']} "
                f"--format_2 {rp['fmt2']} --bd_0 {rp['bd0']} --bd_pos {rp['bd0']},{rp['bd1']} --verbose"
            )
            ret_enc, stdout_enc, stderr_enc = run_command(enc_cmd, enc_log, env)
            
            if ret_enc != 0 or not os.path.exists(bin_file):
                safe_print(f"    [ERROR] Encoding failed: {seq} RP{rp_id}. Check log: {enc_log}")
                return
                
            enc_metrics = parse_time_memory(stdout_enc, stderr_enc)
            
            # --- 2. Decoding ---
            dec_output_ply = os.path.abspath(os.path.join(rp_dir, f'{base_name}_dec_%04d.ply'))
            dec_cmd = f"{PYTHON_EXE} decode.py -b {bin_file} -d {dec_output_ply} --first_frame {start_frame} --verbose"
            
            ret_dec, stdout_dec, stderr_dec = run_command(dec_cmd, dec_log, env)
            if ret_dec != 0:
                safe_print(f"    [ERROR] Decoding failed: {seq} RP{rp_id}. Check log: {dec_log}")
                return
                 
            dec_metrics = parse_time_memory(stdout_dec, stderr_dec)

        else:
            # Parse existing logs for time/memory
            if os.path.exists(enc_log):
                with open(enc_log, 'r', errors='ignore') as f: content_enc = f.read()
                enc_metrics = parse_time_memory(content_enc, content_enc)
            
            if os.path.exists(dec_log):
                with open(dec_log, 'r', errors='ignore') as f: content_dec = f.read()
                dec_metrics = parse_time_memory(content_dec, content_dec)

        # --- 3. Quality Metrics ---
        dec_output_ply = os.path.abspath(os.path.join(rp_dir, f'{base_name}_dec_%04d.ply'))

        # --- Add Camera Position (Moved here to ensure it runs even if resumed) ---
        # safe_print(f"    [INFO] Checking camera position for {seq} RP{rp_id}...")
        for i in range(start_frame, start_frame + NUM_FRAMES):
            current_ply = dec_output_ply % i
            if os.path.exists(current_ply):
                if has_camera_info(current_ply):
                    continue
                
                colmap_dir = os.path.join(DATASET_DIR, seq, "colmap_data", f"frame_{i:04d}", "sparse")
                cam_bin = os.path.join(colmap_dir, "cameras.bin")
                img_bin = os.path.join(colmap_dir, "images.bin")
                
                if os.path.exists(cam_bin) and os.path.exists(img_bin):
                    temp_ply = current_ply.replace(".ply", "_cam.ply")
                    add_cam_cmd = (
                        f"{ADD_CAMERA_POS_EXE} --input={current_ply} --output={temp_ply} "
                        f"--camera={cam_bin} --image={img_bin}"
                    )
                    try:
                        subprocess.run(add_cam_cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if os.path.exists(temp_ply):
                            os.replace(temp_ply, current_ply)
                    except Exception as e:
                        safe_print(f"    [WARN] Failed to add camera info to {current_ply}: {e}")

        metrics_log = os.path.abspath(os.path.join(rp_dir, f"{base_name}_metrics.log"))
        
        # 确定 Anchor 模板
        anchor_pattern_cam = os.path.join(DATASET_DIR, seq, "plys", "frame_%04d.camerapos.ply")
        anchor_pattern_ply = os.path.join(DATASET_DIR, seq, "plys", "frame_%04d.ply")
        
        use_camera_pos = 1
        anchor_pattern = anchor_pattern_cam
        
        # 1. 优先检查 .camerapos.ply 是否存在
        if not os.path.exists(anchor_pattern_cam % start_frame):
            # 2. 如果不存在，使用普通 .ply
            anchor_pattern = anchor_pattern_ply
            
            # 3. 检查普通 .ply 是否包含相机信息
            try:
                ply_file = anchor_pattern % start_frame
                if os.path.exists(ply_file):
                    with open(ply_file, 'rb') as f:
                        # 读取前 4KB header
                        header_bytes = f.read(4096)
                        header_str = header_bytes.decode('utf-8', errors='ignore')
                        if "camera_position" not in header_str:
                             use_camera_pos = 0
                             safe_print(f"[INFO] No camera info in source {seq}, checking decoded...")
                else:
                    use_camera_pos = 0
            except Exception as e:
                safe_print(f"[WARN] Failed to check PLY header for {seq}: {e}")
                use_camera_pos = 0

        # 4. 如果源文件没有相机信息，检查解码文件是否有（可能通过 gsTools 添加了）
        if use_camera_pos == 0:
            try:
                dec_ply_first = dec_output_ply % start_frame
                if os.path.exists(dec_ply_first) and has_camera_info(dec_ply_first):
                    use_camera_pos = 1
                    safe_print(f"[INFO] Found camera info in decoded file for {seq}, enabling useCameraPosition.")
            except Exception as e:
                pass

        # Metrics 命令 (直接使用模板作为参数)
        # Limit threads to avoid OOM/CPU overload (128 cores / 40 tasks ~= 3 threads)
        metrics_cmd = (
            f"{METRICS_TOOL} -a {anchor_pattern} -b {dec_output_ply} "
            f"--frameCount={NUM_FRAMES} --startFrame={start_frame} --width={width} --height={height} "
            f"--verbose=1 --cpu=1 --useCameraPosition={use_camera_pos} --threads=3 > {metrics_log} 2>&1"
        )
        
        # 执行 metrics
        subprocess.run(metrics_cmd, shell=True)
        qual_metrics = parse_metrics(metrics_log)
        
        # --- 4. Write to CSV ---
        row = {
            "Sequence": seq, "RP": rp_id,
            "EncT Total": enc_metrics["Total Time"], "DecT Total": dec_metrics["Total Time"],
            "EncT Geo": enc_metrics["Geo Time"], "DecT Geo": dec_metrics["Geo Time"],
            "EncT Attr": enc_metrics["Attr Time"], "DecT Attr": dec_metrics["Attr Time"],
            "MaxRSS Enc": enc_metrics["Max RSS"], "MaxRSS Dec": dec_metrics["Max RSS"],
            "RGB-PSNR": qual_metrics["RGB-PSNR"], "YUV-PSNR": qual_metrics["YUV-PSNR"], "YUV-SSIM": qual_metrics["YUV-SSIM"],
            "Bin File": bin_file, "Rec File": rec_file
        }
        
        with csv_lock:
            with open(results_csv, "a", newline="") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
                writer.writerow(row)
                
        safe_print(f"[SUCCESS] Finished: {seq} | RP: {rp_id}")
        
    except Exception as e:
        safe_print(f"[EXCEPTION] Task failed for {seq} RP{rp_id}: {str(e)}")
    finally:
        # 无论成功或失败，都必须将 GPU 槽位归还给调度队列
        gpu_queue.put(gpu_id)

# ==========================================
# 5. 主程序与线程池调度
# ==========================================
def main():
    os.chdir(ROOT_DIR)
    print(f"Working directory: {os.getcwd()}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
        
    results_csv = os.path.join(OUTPUT_DIR, "ctc_summary.csv")
    csv_headers = ["Sequence", "RP", "EncT Total", "DecT Total", "EncT Geo", "DecT Geo", "EncT Attr", "DecT Attr", "MaxRSS Enc", "MaxRSS Dec", "RGB-PSNR", "YUV-PSNR", "YUV-SSIM", "Bin File", "Rec File"]
    
    # 写入 CSV 表头
    existing_records = set()
    if not os.path.exists(results_csv):
        with open(results_csv, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writeheader()
    else:
        # 读取已存在的记录，防止重复运行
        try:
            with open(results_csv, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if "Sequence" in row and "RP" in row:
                        # Check if YUV-PSNR is valid (> 0.1)
                        try:
                            psnr = float(row.get("YUV-PSNR", 0.0))
                            if psnr > 0.1:
                                existing_records.add((row["Sequence"], row["RP"]))
                        except ValueError:
                            pass
        except Exception as e:
            print(f"[WARN] Failed to parse existing CSV: {e}")
            
    # 打包所有待执行的任务
    tasks = []
    for seq in SEQUENCES:
        for rp in RATE_POINTS:
            tasks.append((seq, rp))
            
    total_tasks = len(tasks)
    max_workers = len(AVAILABLE_GPUS) * TASKS_PER_GPU
    print(f"=====================================================")
    print(f" Total Tasks       : {total_tasks} (Sequences x Rate Points)")
    print(f" Completed Tasks   : {len(existing_records)} (Found in CSV)")
    print(f" Available GPUs    : {len(AVAILABLE_GPUS)}")
    print(f" Max Concurrency   : {max_workers} tasks")
    print(f" CPU Threads Avail : 128 (AMD EPYC 7502)")
    print(f"=====================================================")

    # 启动线程池并发执行
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_single_task, t[0], t[1], results_csv, csv_headers, existing_records) for t in tasks]
        # 等待所有任务完成
        for future in as_completed(futures):
            future.result() 

    print(f"\n[ALL DONE] Performance metrics saved to {results_csv}")

if __name__ == "__main__":
    main()