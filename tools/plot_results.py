#!/usr/bin/env python3
import argparse
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = [
    "timestamp_iso",
    "run_id",
    "algorithm",
    "implementation",
    "version",
    "board",
    "arch",
    "compiler",
    "compiler_version",
    "cflags",
    "msg_len",
    "ad_len",
    "iterations",
    "enc_time_us_total",
    "dec_time_us_total",
    "enc_time_us_per_op",
    "dec_time_us_per_op",
    "ok",
]

def compute_derived(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = [
        "msg_len",
        "ad_len",
        "iterations",
        "enc_time_us_total",
        "dec_time_us_total",
        "enc_time_us_per_op",
        "dec_time_us_per_op",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[
        (df["msg_len"] > 0) &
        (df["iterations"] > 0) &
        (df["enc_time_us_total"] > 0) &
        (df["dec_time_us_total"] > 0)
    ].copy()
    
    # df["enc_cycles_per_byte"] = df["enc_time_us_total"] / df["msg_len"] * df["iterations"]
    # df["dec_cycles_per_byte"] = df["dec_time_us_total"] / df["msg_len"] * df["iterations"]
    df["enc_us_per_byte"] = df["enc_time_us_total"] / (df["msg_len"] * df["iterations"])
    df["dec_us_per_byte"] = df["dec_time_us_total"] / (df["msg_len"] * df["iterations"])

    df["enc_MBps"] = (df["msg_len"] * df["iterations"]) / (df["enc_time_us_total"] * 1e-6) / 1e6
    df["dec_MBps"] = (df["msg_len"] * df["iterations"]) / (df["dec_time_us_total"] * 1e-6) / 1e6
    return df

def main():
    parser = argparse.ArgumentParser(description="Load benchmark results and compute derived metrics.")
    parser.add_argument("input_csv", type=Path, help="Path to input CSV file with benchmark results.")
    args = parser.parse_args()

    csv_path = Path(args.input_csv)
    if not csv_path.exists():
        raise SystemExit(f"Error: Input CSV file '{csv_path}' does not exist.")
    
    df = pd.read_csv(csv_path)

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise SystemExit(f"Error: Input CSV file is missing required columns:\n" + "\n".join(f"  - {c}" for c in missing_cols))
    
    df_ok = df[df["ok"] == 1].copy()
    if df_ok.empty:
        raise SystemExit("Error: No successful benchmark runs (ok == 1) found in the input CSV.")
    
    bad = df_ok[
        (df_ok["msg_len"] <= 0) |
        (df_ok["iterations"] <= 0) |
        (df_ok["enc_time_us_total"] <= 0) |
        (df_ok["dec_time_us_total"] <= 0)
    ]
    if not bad.empty:
        print("\nWarning: Some rows have non-positive values for msg_len, iterations, or times. These will be excluded from derived metrics.")
        print(bad[["algorithm", "implementation", "msg_len", "iterations", "enc_time_us_total", "dec_time_us_total"]])

    df_ok = compute_derived(df_ok)

    group_cols = ["algorithm", "implementation", "board", "compiler", "cflags", "ad_len"]
    summary = (
        df_ok.groupby(group_cols)
        .agg(
            rows=("run_id", "count"),
            msg_min=("msg_len", "min"),
            msg_max=("msg_len", "max"),
            enc_us_op_mean=("enc_time_us_per_op", "mean"),
            dec_us_op_mean=("dec_time_us_per_op", "mean"),
            enc_MBps_mean=("enc_MBps", "mean"),
            dec_MBps_mean=("dec_MBps", "mean"),
        )
        .reset_index()
        .sort_values(group_cols)
    )

    print("\n=== Benchmark Summary ===")
    print(summary.to_string(index=False))

    print("\n=== First 5 Rows with Derived Metrics ===")
    cols = [
        "timestamp_iso", "algorithm", "implementation", "board",
        "msg_len", "ad_len", "iterations",
        "enc_time_us_per_op", "dec_time_us_per_op",
        "enc_us_per_byte", "dec_us_per_byte",
        "enc_MBps", "dec_MBps",
    ]

    missing_cols = [col for col in cols if col not in df_ok.columns]
    if missing_cols:
        raise SystemExit(f"Error: Missing expected columns for display:\n" + "\n".join(f"  - {c}" for c in missing_cols))
    else:
        print(df_ok[cols].head(5).to_string(index=False))

if __name__ == "__main__":
    main()