#!/usr/bin/env python3
import argparse
from pathlib import Path

import matplotlib.pyplot as plt

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
    parser.add_argument("--outdir", type=Path, default=Path("plots"), help="Directory to save plots .")
    parser.add_argument("--show", action="store_true", help="Show plots interactively.")
    parser.add_argument("--ad", default=None, help="Filter results to only include this AD length.")
    parser.add_argument("--enc-only", action="store_true", help="Only process encryption results.")
    parser.add_argument("--dec-only", action="store_true", help="Only process decryption results.")
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

    if args.ad is not None:
        allowed = {int(x.strip()) for x in args.ad.split(",") if x.strip()}
        df_ok = df_ok[df_ok["ad_len"].isin(allowed)].copy()
    
    plot_enc = not args.dec_only
    plot_dec = not args.enc_only

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

    args.outdir.mkdir(parents=True, exist_ok=True)
    agg_keys = ["algorithm", "implementation", "board", "msg_len", "ad_len"]

    agg = (
        df_ok.groupby(agg_keys)
        .agg(
            enc_mean=("enc_time_us_per_op", "mean"),
            dec_mean=("dec_time_us_per_op", "mean"),
            enc_std=("enc_time_us_per_op", "std"),
            dec_std=("dec_time_us_per_op", "std"),
        )
        .reset_index()
    )

    plt.figure()
    if plot_enc:
        for ad_len, group in agg.groupby("ad_len"):
            group = group.sort_values("msg_len")
            plt.errorbar(group["msg_len"], group["enc_mean"], yerr=group["enc_std"].fillna(0.0), marker='o', capsize=3, label=f'enc ad={ad_len}')

    if plot_dec:
        for ad_len, group in agg.groupby("ad_len"):
            group = group.sort_values("msg_len")
            plt.errorbar(group["msg_len"], group["dec_mean"], yerr=group["dec_std"].fillna(0.0), marker='x', linestyle='--', capsize=3, label=f'dec ad={ad_len}')

    title = f"{df_ok.iloc[0]['algorithm']} ({df_ok.iloc[0]['implementation']}) - {df_ok.iloc[0]['board']}"
    plt.title(title)
    plt.xlabel("Message Length (bytes)")
    plt.ylabel("Time per Operation (us/op)")
    plt.xscale("log", base=2)
    plt.grid(True)
    plt.legend()

    plot_path = args.outdir / "time_per_op_vs_msg_len.png"
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    print(f"\nPlot saved to: {plot_path}")
    if args.show:
        plt.show()
    plt.close()

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