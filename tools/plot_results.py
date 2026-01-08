#!/usr/bin/env python3
import argparse
from pathlib import Path
import re

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

def _slug(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s)
    s = s.strip('_')
    return s

def make_plot_filename(outdir: Path, df: pd.DataFrame, metric: str, args) -> Path:
    op = "enc" if args.enc_only else "dec" if args.dec_only else "both"
    ad_tag = f"ad{args.ad.replace(',', '-')}" if args.ad else "multi_ad"

    boards = sorted(set(df["board"].astype(str)))
    board_tag = _slug(boards[0]) if len(boards) == 1 else "multi_board"

    algos = sorted(set(df["algorithm"].astype(str)))
    algo_tag = _slug(algos[0]) if len(algos) == 1 else "compare_" + _slug("-".join(algos))

    impls = sorted(set(df["implementation"].astype(str)))
    impl_tag = _slug(impls[0]) if len(impls) == 1 else "compare_" + _slug("-".join(impls))

    filename = f"{algo_tag}_{impl_tag}_{board_tag}_{ad_tag}_{op}_{metric}.png"
    return outdir / filename

def main():
    parser = argparse.ArgumentParser(description="Load benchmark results and compute derived metrics.")
    parser.add_argument("input_csv", nargs="+", type=Path, help="Path to input CSV file(s) with benchmark results.")
    parser.add_argument("--outdir", type=Path, default=Path("plots"), help="Directory to save plots .")
    parser.add_argument("--show", action="store_true", help="Show plots interactively.")
    parser.add_argument("--ad", default=None, help="Filter results to only include this AD length.")
    parser.add_argument("--enc-only", action="store_true", help="Only process encryption results.")
    parser.add_argument("--dec-only", action="store_true", help="Only process decryption results.")
    parser.add_argument("--compare", choices=["none","algorithm", "implementation", "board"], default="none", help="Fields to compare in plots.")
    args = parser.parse_args()
    
    dfs = []
    for csv_path in args.input_csv:
        if not csv_path.exists():
            raise SystemExit(f"Error: Input CSV file '{csv_path}' does not exist.")
        dfs.append(pd.read_csv(csv_path))
    df = pd.concat(dfs, ignore_index=True)

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
    
    if args.compare == "none":
        if df_ok["algorithm"].nunique() != 1 or df_ok["implementation"].nunique() != 1 or df_ok["board"].nunique() != 1:
            raise SystemExit(
                "Error: Multiple algorithms/implementations/boards detected.\n"
                "For 'one algorithm, many ADs' plots, pass a single CSV (or filter your inputs),\n"
                "or use --compare algorithm|implementation|board."
            )
    
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
            enc_MBps_mean=("enc_MBps", "mean"),
            dec_MBps_mean=("dec_MBps", "mean"),
            enc_MBps_std=("enc_MBps", "std"),
            dec_MBps_std=("dec_MBps", "std"),
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
    algos = sorted(set(df_ok["algorithm"].astype(str)))
    impls = sorted(set(df_ok["implementation"].astype(str)))
    boards = sorted(set(df_ok["board"].astype(str)))

    if len(algos) == 1 and len(impls) == 1 and len(boards) == 1:
        title = f"{algos[0]} ({impls[0]}) - {boards[0]}"
    else:
        title = f"Comparison: {', '.join(algos)}"
    plt.title(title)
    plt.xlabel("Message Length (bytes)")
    plt.ylabel("Time per Operation (us/op)")
    plt.xscale("log", base=2)
    plt.grid(True)
    plt.legend()

    plot_path = make_plot_filename(args.outdir, df_ok, "time_per_op", args)
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    print(f"\nPlot saved to: {plot_path}")
    if args.show:
        plt.show()
    plt.close()

    plt.figure()
    if plot_enc:
        for ad_len, group in agg.groupby("ad_len"):
            group = group.sort_values("msg_len")
            plt.errorbar(group["msg_len"], group["enc_MBps_mean"], yerr=group["enc_MBps_std"].fillna(0.0), marker='o', capsize=3, label=f'enc ad={ad_len}')

    if plot_dec:
        for ad_len, group in agg.groupby("ad_len"):
            group = group.sort_values("msg_len")
            plt.errorbar(group["msg_len"], group["dec_MBps_mean"], yerr=group["dec_MBps_std"].fillna(0.0), marker='x', linestyle='--', capsize=3, label=f'dec ad={ad_len}')

    plt.title(title)
    plt.xlabel("Message Length (bytes)")
    plt.ylabel("Throughput (MB/s)")
    plt.xscale("log", base=2)
    plt.grid(True)
    plt.legend()

    plot_path = make_plot_filename(args.outdir, df_ok, "throughput_MBps", args)
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