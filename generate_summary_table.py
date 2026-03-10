#!/usr/bin/env python3
"""
Generate performance summary table from ctc_summary.csv.
Maps tmcv results to the expected format with timing, bitrate, and memory metrics.
"""
import os
import pandas as pd
import numpy as np
from collections import defaultdict

def calculate_bitrate(file_path, frame_num=1, fps=30):
    """Calculate bitrate from bin file size in kbps."""
    if not os.path.exists(file_path):
        return np.nan
    try:
        file_size_bytes = os.path.getsize(file_path)
        bits = file_size_bytes * 8
        seconds = frame_num / fps
        if seconds == 0:
            return np.nan
        kbps = bits / 1000.0 / seconds
        return round(kbps, 3)
    except Exception as e:
        print(f"Error calculating bitrate for {file_path}: {e}")
        return np.nan

def main():
    csv_path = "output/tmcv_ctc_results/ctc_summary.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found")
        return
    
    # Read tmcv results
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from {csv_path}")
    
    # Group by Sequence to get aggregate metrics (avg across all RPs)
    results = []
    for seq_name in df['Sequence'].unique():
        seq_data = df[df['Sequence'] == seq_name]
        
        # Calculate average metrics across rate points
        avg_enc_total = seq_data['EncT Total'].mean()
        avg_dec_total = seq_data['DecT Total'].mean()
        avg_enc_geo = seq_data['EncT Geo'].mean()
        avg_dec_geo = seq_data['DecT Geo'].mean()
        avg_enc_attr = seq_data['EncT Attr'].mean()
        avg_dec_attr = seq_data['DecT Attr'].mean()
        avg_maxrss_enc = seq_data['MaxRSS Enc'].mean()
        avg_maxrss_dec = seq_data['MaxRSS Dec'].mean()
        
        # Calculate average bitrate (also avg across RPs)
        bitrates = []
        for _, row in seq_data.iterrows():
            br = calculate_bitrate(row['Bin File'], frame_num=1, fps=30)
            if not np.isnan(br):
                bitrates.append(br)
        avg_bitrate = np.mean(bitrates) if bitrates else np.nan
        
        # Calculate average PSNR/SSIM
        avg_rgb_psnr = seq_data['RGB-PSNR'].mean() if 'RGB-PSNR' in seq_data.columns else np.nan
        avg_yuv_psnr = seq_data['YUV-PSNR'].mean() if 'YUV-PSNR' in seq_data.columns else np.nan
        avg_yuv_ssim = seq_data['YUV-SSIM'].mean() if 'YUV-SSIM' in seq_data.columns else np.nan

        row = {
            'Sequence': seq_name,
            'BB-rate (kbps)': round(avg_bitrate, 3) if not np.isnan(avg_bitrate) else 'N/A',
            'RGB-PSNR (dB)': round(avg_rgb_psnr, 2) if not np.isnan(avg_rgb_psnr) and avg_rgb_psnr > 0 else 'N/A',
            'YUV-PSNR (dB)': round(avg_yuv_psnr, 2) if not np.isnan(avg_yuv_psnr) and avg_yuv_psnr > 0 else 'N/A',
            'YUV-SSIM': round(avg_yuv_ssim, 4) if not np.isnan(avg_yuv_ssim) and avg_yuv_ssim > 0 else 'N/A',
            'EncT Total (s)': round(avg_enc_total, 2),
            'DecT Total (s)': round(avg_dec_total, 2),
            'EncT Geometry (s)': round(avg_enc_geo, 2),
            'DecT Geometry (s)': round(avg_dec_geo, 2),
            'EncT Attributes (s)': round(avg_enc_attr, 2),
            'DecT Attributes (s)': round(avg_dec_attr, 2),
            'MaxRSS Encoder (MB)': round(avg_maxrss_enc, 2),
            'MaxRSS Decoder (MB)': round(avg_maxrss_dec, 2),
        }
        results.append(row)
    
    # Create DataFrame
    summary_df = pd.DataFrame(results)
    
    # Add sequences that are not in tmcv results as placeholders
    expected_seqs = [
        # Forward Facing
        'bartender_semitracked',
        'cinema_semitracked',
        'breakfast_semitracked',
        'breakfast_untracked',
        'breakdance_untracked',
        'bartender_tracked',
        'cinema_tracked',
        'breakfast_tracked',
        'trio',
        'makeup',
        'musical',
        # Object Centric
        'manwithfruit_tracked',
        'lego_ferrari',
        'lego_bugatti',
        'cricket_player',
        'plant',
        'solo_tango_female',
        'solo_tango_male',
        'tango_duo',
        'tennis_player',
        'library',
        'flowerdance',
        'gymnast',
    ]
    
    existing_seqs = set(summary_df['Sequence'].values)
    for seq in expected_seqs:
        if seq not in existing_seqs:
            placeholder = {
                'Sequence': seq,
                'BB-rate (kbps)': 'N/A',
                'RGB-PSNR (dB)': 'N/A',
                'YUV-PSNR (dB)': 'N/A',
                'YUV-SSIM': 'N/A',
                'EncT Total (s)': 'N/A',
                'DecT Total (s)': 'N/A',
                'EncT Geometry (s)': 'N/A',
                'DecT Geometry (s)': 'N/A',
                'EncT Attributes (s)': 'N/A',
                'DecT Attributes (s)': 'N/A',
                'MaxRSS Encoder (MB)': 'N/A',
                'MaxRSS Decoder (MB)': 'N/A',
            }
            summary_df = pd.concat([summary_df, pd.DataFrame([placeholder])], ignore_index=True)
    
    # Reorder to match expected order
    seq_order = {seq: i for i, seq in enumerate(expected_seqs)}
    summary_df['_order'] = summary_df['Sequence'].map(lambda x: seq_order.get(x, len(expected_seqs)))
    summary_df = summary_df.sort_values('_order').drop('_order', axis=1).reset_index(drop=True)
    
    # Save to Excel
    output_excel = "output/tmcv_ctc_results/performance_summary.xlsx"
    summary_df.to_excel(output_excel, index=False, engine='openpyxl')
    print(f"\n✓ Saved to {output_excel}")
    
    # Also save as CSV for easy viewing
    output_csv = "output/tmcv_ctc_results/performance_summary.csv"
    summary_df.to_csv(output_csv, index=False)
    print(f"✓ Saved to {output_csv}")
    
    # Print preview
    print("\n" + "="*100)
    print("Summary Table Preview:")
    print("="*100)
    print(summary_df.to_string(index=False))
    print("="*100)
    
    # Print notes
    print("\nNotes:")
    print("- BB-rate, RGB-PSNR, YUV-PSNR, YUV-SSIM: Not available in tmcv results (marked as N/A)")
    print("- EncT/DecT Geometry/Attributes: All 0 in current tmcv results (pending fix)")
    print("- For quality metrics (PSNR/SSIM), run mpeg-gsc-metrics tool on decoded results")
    print("- For sub-stage timing, enhance encode.py/decode.py to log geometry/attribute times separately")

if __name__ == "__main__":
    os.chdir("/home/zhongdalv/mpeg-gsc-tmcv")
    main()
