"""
ORBIT Benchmark Plotter
Generates publication-quality charts from ORBIT CSV result files.
 
Usage:
    python3 tools/plot_results.py --results_dir results/ --board pico
    python3 tools/plot_results.py --results_dir results/ --board pico --output_dir plots/
"""

import argparse
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

ALGORITHM_COLORS = {
    "ascon_aead128":  "#185FA5",
    "ascon_aead80pq": "#0F6E56",
    "gift_cofb":      "#993C1D",
    "aes_128_gcm":    "#888780",
    "ml_kem_512":     "#534AB7",
}

ALGORITHM_LABELS = {
    "ascon_aead128":  "Ascon-128",
    "ascon_aead80pq": "Ascon-80pq",
    "gift_cofb":      "GIFT-COFB",
    "aes_128_gcm":    "AES-128-GCM",
    "ml_kem_512":     "ML-KEM-512",
}

AEAD_ALGORITHMS = [k for k in ALGORITHM_LABELS if k != "ml_kem_512"]
MSG_SIZES = [16, 64, 256, 1024, 4096, 16384]
MSG_LABELS = ["16B", "64B", "256B", "1KB", "4KB", "16KB"]

def load_results(results_dir, board=None):
    files = glob.glob(os.path.join(results_dir, "*.csv"))
    dfs = []
    for file in files:
        try:
            dfs.append(pd.read_csv(file))
        except Exception as e:
            print(f"Warning: Could not read {file}: {e}")
    if not dfs:
        raise ValueError(f"No valid CSV files found in {results_dir}")
        return pd.DataFrame() 
    df = pd.concat(dfs, ignore_index=True)
    return df[df["board"] == board] if board else df

def apply_style():
    plt.rcParams.update({
        "font.family":        "sans-serif",
        "font.size":          11,
        "axes.titlesize":     13,
        "axes.titleweight":   "normal",
        "axes.labelsize":     11,
        "axes.spines.top":    False,
        "axes.spines.right":  False,
        "axes.grid":          True,
        "grid.alpha":         0.3,
        "grid.linestyle":     "--",
        "legend.frameon":     False,
        "legend.fontsize":    10,
        "figure.dpi":         150,
        "savefig.dpi":        300,
        "savefig.bbox":       "tight",
    })

def us_formatter(x, _):
    return f"{x/1000:.1f}" if x >= 1000 else f"{int(x)}us"

def cbp_formatter(x, _):
    return f"{int(x/1000)}K" if x >= 1000 else str(int(x))

def save_figure(fig, output_path, filename):
    path = os.path.join(output_path, filename)
    fig.savefig(path)
    plt.close(fig)
    print(f"Saved: {path}")

def mean_for(df, algo, col, msg_len=None, note=None):
    mask = df["algorithm"] == algo
    if msg_len is not None:
        mask &= df["msg_len"] == msg_len
    if note is not None:
        mask &= df["notes"] == note
    subset = df[mask]
    return subset[col].mean() if not subset.empty else None

def plot_cycles_per_byte(df, output_path, board):
    fig, ax = plt.subplots(figsize=(8, 5))

    for algo in AEAD_ALGORITHMS:
        points = [mean_for(df, algo, "enc_cycles_per_byte", m) for m in MSG_SIZES]

        if all(v is None for v in points):
            continue
        ax.plot(
            range(len(MSG_SIZES)),
            points,
            label=ALGORITHM_LABELS[algo],
            color=ALGORITHM_COLORS[algo],
            linewidth=2,
            linestyle = "--" if algo == "aes_128_gcm" else "-",
            marker="o",
            markersize=5,
        )
    ax.set_yscale("log")
    ax.set_xticks(range(len(MSG_SIZES)))
    ax.set_xticklabels(MSG_LABELS)
    ax.set_xlabel("Message Size")
    ax.set_ylabel("Average Cycles/Byte (log scale)")
    ax.set_title(f"cycles per byte: AEAD algorithms\n{board} @ 125 MHz, -O2, reference implementations")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{int(x/1000)}K" if x >= 1000 else f"{int(x)}"))
    ax.legend()
    plt.tight_layout()
    save_figure(fig, output_path, f"{board}_cycles_per_byte.png")

def plot_lwc_only(df, output_dir, board):
    fig, ax = plt.subplots(figsize=(8, 5))
    for algo in [a for a in AEAD_ALGORITHMS if a != "aes_128_gcm"]:
        points = [mean_for(df, algo, "enc_cycles_per_byte", m) for m in MSG_SIZES]
        if all(v is None for v in points):
            continue
        ax.plot(range(len(MSG_SIZES)), points,
                label=ALGORITHM_LABELS[algo], color=ALGORITHM_COLORS[algo],
                linewidth=2, marker="o", markersize=5)
    ax.set_xticks(range(len(MSG_SIZES)))
    ax.set_xticklabels(MSG_LABELS)
    ax.set_xlabel("message size")
    ax.set_ylabel("cycles per byte")
    ax.set_title(f"cycles per byte — LWC algorithms (linear scale)\n{board} @ 125 MHz, -O2")
    ax.legend()
    plt.tight_layout()
    save_figure(fig, output_dir, f"{board}_lwc_cycles_per_byte.png")


def plot_latency_comparison(df, output_dir, board):
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    for ax, msg_size in zip(axes, [16, 1024]):
        labels, values, colors = [], [], []
        for algo in AEAD_ALGORITHMS:
            v = mean_for(df, algo, "enc_time_us_per_op", msg_size)
            if v is not None:
                labels.append(ALGORITHM_LABELS[algo])
                values.append(v)
                colors.append(ALGORITHM_COLORS[algo])
        v = mean_for(df, "ml_kem_512", "enc_time_us_per_op", note="keygen")
        if v is not None:
            labels.append("ML-KEM-512\n(KeyGen)")
            values.append(v)
            colors.append(ALGORITHM_COLORS["ml_kem_512"])
        bars = ax.bar(range(len(labels)), values, color=colors,
                      width=0.6, edgecolor="none", zorder=3)
        ax.set_yscale("log")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontsize=9, rotation=15, ha="right")
        ax.set_ylabel("us per operation (log scale)")
        size_label = f"{msg_size}B" if msg_size < 1024 else f"{msg_size//1024}KB"
        ax.set_title(f"latency @ {size_label} payload")
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(us_formatter))
        for bar, val in zip(bars, values):
            label = f"{val/1000:.1f}ms" if val >= 1000 else f"{int(val)}us"
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.1, label,
                    ha="center", va="bottom", fontsize=8, color="#444")
    fig.suptitle(f"per-operation latency — {board} @ 125 MHz", y=1.02)
    plt.tight_layout()
    save_figure(fig, output_dir, f"{board}_latency_comparison.png")
 
 
def plot_mlkem_operations(df, output_dir, board):
    ops = [("keygen", "KeyGen"), ("encap", "Encapsulate"), ("decap", "Decapsulate")]
    values = [mean_for(df, "ml_kem_512", "enc_time_us_per_op", note=op) or 0
              for op, _ in ops]
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar([lbl for _, lbl in ops], values,
                  color=ALGORITHM_COLORS["ml_kem_512"], width=0.5, edgecolor="none", zorder=3)
    ref = mean_for(df, "ascon_aead128", "enc_time_us_per_op", msg_len=64)
    if ref:
        ax.axhline(ref, color=ALGORITHM_COLORS["ascon_aead128"],
                   linestyle="--", linewidth=1.5,
                   label=f"Ascon-128 @ 64B ({ref:.0f}us)")
        ax.legend()
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 200,
                f"{val/1000:.1f}ms", ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("us per operation")
    ax.set_title(f"ML-KEM-512 operation latency\n{board} @ 125 MHz, -O2")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(us_formatter))
    plt.tight_layout()
    save_figure(fig, output_dir, f"{board}_mlkem_operations.png")
 
 
def plot_80pq_overhead(df, output_dir, board):
    overheads = []
    for m in MSG_SIZES:
        base = mean_for(df, "ascon_aead128",  "enc_cycles_per_byte", m)
        pq   = mean_for(df, "ascon_aead80pq", "enc_cycles_per_byte", m)
        overheads.append(((pq - base) / base * 100) if base and pq else 0)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(MSG_LABELS, overheads, color=ALGORITHM_COLORS["ascon_aead80pq"],
           width=0.5, edgecolor="none", zorder=3)
    ax.set_xlabel("message size")
    ax.set_ylabel("overhead vs Ascon-128 (%)")
    ax.set_title(f"Ascon-80pq overhead over Ascon-128\n{board} @ 125 MHz")
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    plt.tight_layout()
    save_figure(fig, output_dir, f"{board}_ascon80pq_overhead.png")
 
 
def print_summary(df, board):
    print(f"\n{'='*65}")
    print(f"ORBIT summary — {board}")
    print(f"{'='*65}")
    print(f"{'Algorithm':<20} {'16B':>8} {'256B':>8} {'1KB':>8} {'16KB':>8}  cpb")
    print(f"{'-'*55}")
    for algo in AEAD_ALGORITHMS:
        vals = [mean_for(df, algo, "enc_cycles_per_byte", m)
                for m in [16, 256, 1024, 16384]]
        row = "  ".join(f"{v:>8,.0f}" if v else f"{'--':>8}" for v in vals)
        print(f"{ALGORITHM_LABELS[algo]:<20} {row}")
    print(f"\n{'Algorithm':<20} {'KeyGen':>10} {'Encap':>10} {'Decap':>10}  ms")
    print(f"{'-'*55}")
    vals = [mean_for(df, "ml_kem_512", "enc_time_us_per_op", note=op)
            for op in ["keygen", "encap", "decap"]]
    row = "  ".join(f"{v/1000:>10.2f}" if v else f"{'--':>10}" for v in vals)
    print(f"{'ML-KEM-512':<20} {row}")
    print(f"{'='*65}\n")
 
 
def main():
    parser = argparse.ArgumentParser(description="ORBIT benchmark plotter")
    parser.add_argument("--results_dir", default="results")
    parser.add_argument("--output_dir",  default="plots")
    parser.add_argument("--board",       default="pico")
    args = parser.parse_args()
 
    os.makedirs(args.output_dir, exist_ok=True)
    apply_style()
 
    df = load_results(args.results_dir, board=args.board)
    if df.empty:
        print("No data loaded. Check your results directory and board name.")
        return
 
    print(f"Loaded {len(df)} rows -- algorithms: {df['algorithm'].unique().tolist()}")
 
    plot_cycles_per_byte(df, args.output_dir, args.board)
    plot_lwc_only(df, args.output_dir, args.board)
    plot_latency_comparison(df, args.output_dir, args.board)
    plot_mlkem_operations(df, args.output_dir, args.board)
    plot_80pq_overhead(df, args.output_dir, args.board)
    print_summary(df, args.board)
 
    print(f"All plots saved to {args.output_dir}/")
 
 
if __name__ == "__main__":
    main()