import os
import re
import sys
import glob

def get_time_from_file(file_path):
    """
    Reads a log file and looks for 'Total Time: <float> sec.'
    """
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            # Match " Total Time:        9.059 sec."
            match = re.search(r"Total Time:\s+([\d\.]+)\s+sec", content)
            if match:
                return float(match.group(1))
    except Exception as e:
        pass
    return 0.0

def collect_results(root_dir):
    # Print header
    print(f"{'Sequence':<40}\t{'EncT Total':<10}\t{'DecT Total':<10}\t{'EncT Geometry':<13}\t{'DecT Geometry':<13}\t{'EncT Attributes':<15}\t{'DecT Attributes':<15}")
    
    if not os.path.exists(root_dir):
        print(f"Error: Directory {root_dir} does not exist.")
        return

    sequences = sorted([d for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d))])
    
    for seq in sequences:
        seq_path = os.path.join(root_dir, seq)
        rates = sorted([d for d in os.listdir(seq_path) if os.path.isdir(os.path.join(seq_path, d))])
        
        for rate in rates:
            rate_path = os.path.join(seq_path, rate)
            
            # Find files
            # Geometry logs start with 00_
            geo_enc_files = glob.glob(os.path.join(rate_path, "00_*_enc.log"))
            geo_dec_files = glob.glob(os.path.join(rate_path, "00_*_dec.log"))
            
            enc_geo = 0.0
            if geo_enc_files:
                enc_geo = get_time_from_file(geo_enc_files[0])
                
            dec_geo = 0.0
            if geo_dec_files:
                dec_geo = get_time_from_file(geo_dec_files[0])
            
            # Attribute logs: 01_*, 02_*, etc.
            # Using simple pattern matching
            all_enc_logs = glob.glob(os.path.join(rate_path, "*_enc.log"))
            all_dec_logs = glob.glob(os.path.join(rate_path, "*_dec.log"))
            
            enc_attr = 0.0
            for f in all_enc_logs:
                fname = os.path.basename(f)
                if fname.startswith("00_"): continue
                # Skip main log (e.g. cinema_semitracked_r4_enc.log) which likely doesn't start with digit
                if not fname[0].isdigit(): continue
                enc_attr += get_time_from_file(f)

            dec_attr = 0.0
            for f in all_dec_logs:
                fname = os.path.basename(f)
                if fname.startswith("00_"): continue
                if not fname[0].isdigit(): continue
                dec_attr += get_time_from_file(f)
            
            enc_total = enc_geo + enc_attr
            dec_total = dec_geo + dec_attr
            
            row_label = f"{seq}_{rate}"
            print(f"{row_label:<40}\t{enc_total:<10.4f}\t{dec_total:<10.4f}\t{enc_geo:<13.4f}\t{dec_geo:<13.4f}\t{enc_attr:<15.4f}\t{dec_attr:<15.4f}")

if __name__ == "__main__":
    root = "/home/zhongdalv/mpeg-gsc-tmcv/output/tmcv_ctc_results"
    collect_results(root)
