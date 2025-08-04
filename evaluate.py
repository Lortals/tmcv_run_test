#!/usr/bin/env python3
import subprocess
import os
import re
import csv
import argparse
import matplotlib.pyplot as plt
from utils.common import to_bash_path, handler_ctrl_c

#######################################################################################################

METRIC_PATH = r"C:\Users\ricar\dev\mpeg-gsc-metric_mpeg\build\Release\bin\Release\mpeg-gsc-metrics.exe"

#######################################################################################################

def extract_psnr_rgb(log_path):
    pattern = re.compile(r"PSNR RGB =\s*([0-9]+\.[0-9]+)\s+([0-9]+\.[0-9]+)\s+([0-9]+\.[0-9]+)")
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            m = pattern.search(line)
            if m:
                return tuple(map(float, m.groups()))
    raise ValueError(f"Aucune ligne 'PSNR RGB =' trouvée dans {log_path}")

#######################################################################################################

def extract_compression_stats(log_path): 
    pattern = re.compile(
        r"bits\s*=\s*(\d+)\s*/\s*(\d+).*?([0-9]+\.[0-9]+)\s*$"
    )
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            m = pattern.search(line)
            if m:
                bits_orig = int(m.group(1))
                bits_comp = int(m.group(2))
                ratio     = float(m.group(3))
                return bits_orig, bits_comp, ratio
    raise ValueError(f"Can't find compression ratio information in: {log_path}")

#######################################################################################################

def load_parameters_from_csv(csv_file):
    """Load parameter sets from a CSV file."""
    parameter_sets = []
    with open(csv_file, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Convert the parameters to the appropriate types (integers, floats, etc.)
            param_set = {key: int(value) if value.isdigit() else float(value) for key, value in row.items()}
            parameter_sets.append(param_set)
    return parameter_sets

#######################################################################################################

def make_suffix(p):
    """Build test name """
    bd = p
    suffix = (
      f"bd"
      f"{bd['bd_0']:02d}_"
      f"{bd['bd_1']:02d}_"
      f"{bd['bd_2']:02d}_"
      f"{bd['bd_3']:02d}_"
      f"{bd['bd_4']:02d}_"
      f"{bd['bd_5']:02d}_"
      f"{bd['bd_6']:02d}_"
      f"qp"
      f"{bd['qp_0']:02d}_"
      f"{bd['qp_1']:02d}_"
      f"{bd['qp_2']:02d}_"
      f"{bd['qp_3']:02d}_"
      f"{bd['qp_4']:02d}_"
      f"{bd['qp_5']:02d}_"
      f"{bd['qp_6']:02d}_"
      f"c{bd['force_comp']:02d}"
    )
    return suffix

#######################################################################################################

def run(cmd):
    print("RUN:", " ".join(cmd))
    subprocess.run(cmd, check=True)

#######################################################################################################

def main():
  # Initialize
  handler_ctrl_c()

  # Set up argparse for reading parameters from the command line
  parser = argparse.ArgumentParser(description="Test different configurations for 3D Gaussian Splatting encoding and decoding.")    
  main = parser.add_argument_group('Inputs')    
  main.add_argument('-c','--csv_file',    help="Path to the CSV file.",     default='',                         type=str, required=True)
  main.add_argument('-i,', '--input',     help='Input ply path',            default= "test/ply/QQ21-3DGS.ply",  type=str )
  main.add_argument('-n','--num_frames',  help='Number of frames',          default=1,                          type=int )
  main.add_argument('--first_frame',      help='Index of the first frame',  default=0,                          type=int )
  main = parser.add_argument_group('Options')    
  main.add_argument('-v','--verbose',     help='Verbose',                   default=False, action='store_true')
  main.add_argument('-p', '--plot',       help='Plot RD graphs',            default=False, action='store_true')
  args = parser.parse_args()

  parameter_sets = load_parameters_from_csv(args.csv_file)
  base_name = to_bash_path( os.path.splitext(args.input)[0] )
  print("number of test = %d " % ( len(parameter_sets)))
  bitrate_list = []
  cr_list = []
  psnr_avg_list = []
  for i, params in enumerate(parameter_sets):
    suffix     = make_suffix(params)
    output_dir = f"{base_name}_{suffix}"
    os.makedirs(output_dir, exist_ok=True)
    bin_name   = to_bash_path( os.path.join( output_dir, output_dir + '.v3c' ) )
    dec_ply    = to_bash_path( os.path.join( output_dir, f"{output_dir}_0000_dec.ply" ) )
    enc_log    = to_bash_path( os.path.join( output_dir, f"{output_dir}_encoder.log" ) )
    dec_log    = to_bash_path( os.path.join( output_dir, f"{output_dir}_decoder.log" ) )
    met_log    = to_bash_path( os.path.join( output_dir, f"{output_dir}_metrics.log" ) )
    
    # 1) Encode
    if not os.path.exists(bin_name):      
      encode_cmd = [
        "python",       "encode.py",
        "-i",            args.input,
        "-b",            bin_name,
        "-n",            str(args.num_frames),
        "--first_frame", str(args.first_frame),
      ]
      for key, val in params.items():
          encode_cmd.append(f"--{key}={val}")
      encode_cmd += ["--verbose"] if args.verbose else []
      result = subprocess.run(
          encode_cmd,
          stdout=subprocess.PIPE,
          stderr=subprocess.STDOUT,
          text=True
      )
      with open(enc_log, 'w', encoding='utf-8') as log_f:
          log_f.write(result.stdout)
      if result.returncode != 0:
          print(f"[ERROR] encode.py failed (code {result.returncode}), see {enc_log}")

    # 2) Decode
    if not os.path.exists(dec_ply):
      decode_cmd = [ "python", "decode.py", "-b", bin_name, "-d", dec_ply ]
      decode_cmd += ["--verbose"] if args.verbose else []
      result = subprocess.run(
        decode_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
      )
      with open(dec_log, 'w', encoding='utf-8') as log_f:
        log_f.write(result.stdout)
      if result.returncode != 0:
        print(f"[ERROR] decoder.py failed (code {result.returncode}), see {dec_log}")

    # 3) Metrics
    if not os.path.exists(met_log):
      metrics_cmd = [
        METRIC_PATH,
        "-a", args.input,
        "-b", dec_ply,
        "-s", "1", 
        "-v", "1", 
        "-f", str(args.num_frames), 
        "-n", "16"
      ]
      with open(met_log, 'w', encoding='utf-8') as log_f:
          subprocess.run(
              metrics_cmd,
              stdout=log_f,
              stderr=subprocess.STDOUT,
              check=True,
              text=True
          )

    # Stat
    bits_orig, bits_comp, cr = extract_compression_stats(enc_log)      
    psnr_r, psnr_g, psnr_b   = extract_psnr_rgb(met_log)
    print("%3d / %3d: %-30s: src_bits = %10d enc_bits = %10d cr = %8.4f psnr = %8.4f %8.4f %8.4f  " % 
          ( i, len(parameter_sets),output_dir, bits_orig, bits_comp, cr, psnr_r, psnr_g, psnr_b ))
   
    # Collecting data for plotting
    bitrate_list.append((bits_comp / args.num_frames) * 30 / 1e6)   
    cr_list.append(cr)
    psnr_avg_list.append((psnr_r + psnr_g + psnr_b) / 3.0)

  # Plotting
  if args.plot:
    
    plt.figure()
    plt.scatter(cr_list, psnr_avg_list)
    plt.xlabel("Compression Ratio")
    plt.ylabel("Average PSNR (dB)")
    plt.title("Compression ratio vs. average PSNR")
    plt.grid(True)

    plt.figure()
    bitrate_list = [1.0 / cr for cr in cr_list]
    plt.scatter(bitrate_list, psnr_avg_list)
    plt.xlabel("Bitrate (Mbps)")
    plt.ylabel("Average PSNR (dB)")
    plt.title("Bitrate vs. average PSNR")
    plt.grid(True)

    plt.show()
      
if __name__ == "__main__":
    main()
