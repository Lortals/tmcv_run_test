#!/usr/bin/env python3

import csv
import re
from pathlib import Path


ROOT_DIR = Path("/home/zhongdalv/mpeg-gsc-tmcv")
CTC_DIR = ROOT_DIR / "output_nf" / "tmcv_ctc_results"
CTC_CSV = CTC_DIR / "ctc_summary_old_wrong_metrics.csv"
OUTPUT_TEMPLATE_CSV = CTC_DIR / "ctc_template_filled_1f_old_metrics.csv"
OUTPUT_ANNOTATED_CSV = CTC_DIR / "ctc_template_filled_1f_annotated_old_metrics.csv"

FPS = 30
FRAME_COUNT_1F = 1
RATE_POINTS = [1, 2, 3, 4, 5]


SEQUENCE_LAYOUT = [
    ("Forward facing", "1F", "bartender_semitracked", 21, "1920x1080", 0, 1),
    ("Forward facing", "1F", "cinema_semitracked", 21, "1920x1080", 0, 1),
    ("Forward facing", "1F", "breakfast_semitracked", 15, "1920x1080", 0, 1),
    ("Forward facing", "1F", "breakfast_untracked", 15, "1920x1080", 0, 1),
    ("Forward facing", "1F", "breakdance_untracked", 33, "1920x1080", 0, 1),
    ("Forward facing", "1F", "bartender_tracked", 21, "1920x1080", 0, 1),
    ("Forward facing", "1F", "cinema_tracked", 21, "1920x1080", 0, 1),
    ("Forward facing", "1F", "breakfast_tracked", 15, "1920x1080", 0, 1),
    ("Forward facing", "1F", "trio", 21, "1920x1080", 0, 1),
    ("Forward facing", "1F", "makeup", 21, "1920x1080", 0, 1),
    ("Forward facing", "1F", "musical", 21, "1920x1080", 0, 1),
    ("Object centric", "1F", "manwithfruit_tracked", 24, "3840x2160", 81, 1),
    ("Object centric", "1F", "lego_ferrari", 128, "4594x5514", 0, 1),
    ("Object centric", "1F", "lego_bugatti", 132, "3852x2868", 0, 1),
    ("Object centric", "1F", "cricket_player", 60, "4520x2540", 0, 1),
    ("Object centric", "1F", "plant", 66, "2954x3968", 0, 1),
    ("Object centric", "1F", "solo_tango_female", 44, "4534x2542", 0, 1),
    ("Object centric", "1F", "solo_tango_male", 44, "4528x2544", 0, 1),
    ("Object centric", "1F", "tango_duo", 44, "4522x2538", 0, 1),
    ("Object centric", "1F", "tennis_player", 60, "4518x2540", 0, 1),
    ("Object centric", "1F", "library", 100, "3793x2131", 0, 1),
    ("Object centric", "1F", "flowerdance", 64, "2456x2054", 0, 1),
    ("Object centric", "1F", "gymnast", 64, "2456x2054", 200, 1),
]


TEMPLATE_HEADERS = [
    "Category",
    "Experiment",
    "Sequence",
    "View Count",
    "Frame Size",
    "Start Frame",
    "Frame Count",
    "RP",
    "bit rate [kbps]",
    "Total [bytes]",
    "position [bytes]",
    "sh0 [bytes]",
    "sh1 [bytes]",
    "sh2 [bytes]",
    "sh3 [bytes]",
    "rotation [bytes]",
    "scaling [bytes]",
    "opacity [bytes]",
    "RGB-PSNR",
    "YUV-PSNR",
    "YUV-SSIM",
    "Custom A",
    "Custom B",
    "Min RGB-PSNR",
    "Min YUV-PSNR",
    "Min YUV-SSIM",
    "Max RGB-PSNR",
    "Max YUV-PSNR",
    "Max YUV-SSIM",
    "Encoding time total [s]",
    "Encoding time geometry [s]",
    "Encoding time attributes [s]",
    "Decoding time total [s]",
    "Decoding time geometry [s]",
    "Decoding time attributes [s]",
    "Max RSS encoder [MB]",
    "Max RSS decoder [MB]",
]


ANNOTATED_EXTRA_HEADERS = [
    "position stream exact [bytes]",
    "aux stream exact [bytes]",
    "sh stream exact [bytes]",
    "container overhead [bytes]",
    "Notes",
]


def parse_float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def format_number(value, digits=None):
    if value is None:
        return ""
    if digits is None:
        if isinstance(value, int):
            return str(value)
        if float(value).is_integer():
            return str(int(value))
        return str(value)
    return f"{value:.{digits}f}"


def load_summary_rows():
    rows = {}
    with CTC_CSV.open("r", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows[(row["Sequence"].strip(), int(row["RP"]))] = row
    return rows


def safe_size(path):
    return path.stat().st_size if path.exists() else None


def parse_bytes_from_log(log_path):
    if not log_path.exists():
        return None
    content = log_path.read_text(errors="ignore")
    match = re.search(r"Bytes written to file:\s+(\d+)", content)
    return int(match.group(1)) if match else None


def get_stream_sizes(base_dir):
    pos_size = safe_size(base_dir / "00_xyzxayaza_enc.hm")
    aux_size = safe_size(base_dir / "01_or3-s0s1s2r0r1r2_enc.hm")
    sh_size = safe_size(base_dir / "02_dcsh_enc.hm")

    if pos_size is None:
        pos_size = parse_bytes_from_log(base_dir / "00_xyzxayaza_enc.log")
    if aux_size is None:
        aux_size = parse_bytes_from_log(base_dir / "01_or3-s0s1s2r0r1r2_enc.log")
    if sh_size is None:
        sh_size = parse_bytes_from_log(base_dir / "02_dcsh_enc.log")

    return pos_size, aux_size, sh_size


def compute_bitrate_kbps(total_bytes):
    if total_bytes is None:
        return None
    return total_bytes * 8 * FPS / 1000.0 / FRAME_COUNT_1F


def base_row(category, experiment, sequence, view_count, frame_size, start_frame, frame_count, rp):
    row = {header: "" for header in TEMPLATE_HEADERS}
    row.update(
        {
            "Category": category,
            "Experiment": experiment,
            "Sequence": sequence,
            "View Count": view_count,
            "Frame Size": frame_size,
            "Start Frame": start_frame,
            "Frame Count": frame_count,
            "RP": rp,
        }
    )
    return row


def build_rows():
    summary_rows = load_summary_rows()
    template_rows = []
    annotated_rows = []

    for category, experiment, sequence, view_count, frame_size, start_frame, frame_count in SEQUENCE_LAYOUT:
        for rp in RATE_POINTS:
            row = base_row(category, experiment, sequence, view_count, frame_size, start_frame, frame_count, rp)
            annotated = dict(row)
            annotated.update({header: "" for header in ANNOTATED_EXTRA_HEADERS})

            summary = summary_rows.get((sequence, rp))
            if summary is None:
                annotated["Notes"] = "No tmcv result found for this sequence/RP."
                template_rows.append(row)
                annotated_rows.append(annotated)
                continue

            bin_path = Path(summary["Bin File"])
            base_dir = bin_path.parent
            total_size = safe_size(bin_path)
            pos_size, aux_size, sh_size = get_stream_sizes(base_dir)

            known_payload = sum(value for value in (pos_size, aux_size, sh_size) if value is not None)
            overhead = total_size - known_payload if total_size is not None else None

            rgb_psnr = parse_float(summary.get("RGB-PSNR"))
            yuv_psnr = parse_float(summary.get("YUV-PSNR"))
            yuv_ssim = parse_float(summary.get("YUV-SSIM"))

            row.update(
                {
                    "bit rate [kbps]": format_number(compute_bitrate_kbps(total_size), 3),
                    "Total [bytes]": format_number(total_size),
                    "position [bytes]": format_number(pos_size),
                    "sh0 [bytes]": format_number(sh_size),
                    "rotation [bytes]": format_number(aux_size),
                    "RGB-PSNR": format_number(rgb_psnr, 12) if rgb_psnr is not None else "",
                    "YUV-PSNR": format_number(yuv_psnr, 12) if yuv_psnr is not None else "",
                    "YUV-SSIM": format_number(yuv_ssim, 12) if yuv_ssim is not None else "",
                    "Min RGB-PSNR": format_number(rgb_psnr, 12) if rgb_psnr is not None else "",
                    "Min YUV-PSNR": format_number(yuv_psnr, 12) if yuv_psnr is not None else "",
                    "Min YUV-SSIM": format_number(yuv_ssim, 12) if yuv_ssim is not None else "",
                    "Max RGB-PSNR": format_number(rgb_psnr, 12) if rgb_psnr is not None else "",
                    "Max YUV-PSNR": format_number(yuv_psnr, 12) if yuv_psnr is not None else "",
                    "Max YUV-SSIM": format_number(yuv_ssim, 12) if yuv_ssim is not None else "",
                    "Encoding time total [s]": summary.get("EncT Total", ""),
                    "Encoding time geometry [s]": summary.get("EncT Geo", ""),
                    "Encoding time attributes [s]": summary.get("EncT Attr", ""),
                    "Decoding time total [s]": summary.get("DecT Total", ""),
                    "Decoding time geometry [s]": summary.get("DecT Geo", ""),
                    "Decoding time attributes [s]": summary.get("DecT Attr", ""),
                    "Max RSS encoder [MB]": summary.get("MaxRSS Enc", ""),
                    "Max RSS decoder [MB]": summary.get("MaxRSS Dec", ""),
                }
            )

            annotated.update(row)
            annotated.update(
                {
                    "position stream exact [bytes]": format_number(pos_size),
                    "aux stream exact [bytes]": format_number(aux_size),
                    "sh stream exact [bytes]": format_number(sh_size),
                    "container overhead [bytes]": format_number(overhead),
                    "Notes": (
                        "position is exact from 00_xyzxayaza; "
                        "sh0 stores the combined SH stream from 02_dcsh because logs do not split sh0-sh3; "
                        "rotation stores the combined auxiliary stream from 01_or3-s0s1s2r0r1r2 because logs do not split rotation/scaling/opacity."
                    ),
                }
            )

            template_rows.append(row)
            annotated_rows.append(annotated)

    return template_rows, annotated_rows


def write_csv(path, headers, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not CTC_CSV.exists():
        raise FileNotFoundError(f"Missing summary CSV: {CTC_CSV}")

    template_rows, annotated_rows = build_rows()
    write_csv(OUTPUT_TEMPLATE_CSV, TEMPLATE_HEADERS, template_rows)
    write_csv(OUTPUT_ANNOTATED_CSV, TEMPLATE_HEADERS + ANNOTATED_EXTRA_HEADERS, annotated_rows)

    print(f"Wrote template CSV: {OUTPUT_TEMPLATE_CSV}")
    print(f"Wrote annotated CSV: {OUTPUT_ANNOTATED_CSV}")
    print(f"Rows written: {len(template_rows)}")


if __name__ == "__main__":
    main()
