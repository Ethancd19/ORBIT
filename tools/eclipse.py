#!/usr/bin/env python3
"""
ECLIPSE - Embedded Cryptography Lightweight and Post-quantum IoT Performance Evaluation
Benchmark Manager Script.

Usage:
    python3 tools/eclipse.py --board pico --algo ascon_aead128 --runs 5
    python3 tools/eclipse.py --board pico --algo ascon_aead128 --runs 5 --output results/run1.csv
    python3 tools/eclipse.py --board pico --algo ascon_aead128 --runs 5 --flash
"""

import argparse
import os
import subprocess
import sys
import time
import serial
import serial.tools.list_ports
import shutil

# ----- Board Definitions -----

BOARDS = {
    "pico": {
        "name": "Raspberry Pi Pico (RP2040)",
        "arch": "armv6-m",
        "flash_method": "uf2",
        "baud": 115200,
    },
    "nrf52": {
        "name": "Nordic nRF52840",
        "arch": "armv7e-m",
        "flash_method": "nrfjprog",
        "baud": 115200,
    },
    "stm32": {
        "name": "STM32 Nucleo F446RE",
        "arch": "armv7e-m",
        "flash_method": "openocd",
        "baud": 115200,
    },
    "esp32c6": {
        "name": "ESP32-C6",
        "arch": "riscv32",
        "flash_method": "esptool",
        "baud": 115200,
    },
    "rpi5": {
        "name": "Raspberry Pi 5",
        "arch": "aarch64",
        "flash_method": "ssh",
        "baud": None,
    },
}

# ----- Algorithm Definitions -----
ALGORITHMS = {
    "ascon_aead128",
    "ascon_aead80pq",
    "gift_cofb",
    "aes_gcm_128",
    "ml-kem_512",
}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

def log(msg):
    print(f"[ECLIPSE] {msg}")

def run_command(cmd, cwd=None):
    print(f"Running: {cmd}")
    ret = subprocess.call(cmd, shell=True, cwd=cwd)
    if ret != 0:
        print(f"Command failed with exit code {ret}")
        sys.exit(1)

def build(board, algo, clean=False):
    if clean and os.path.exists(BUILD_DIR):
        log(f"Cleaning build directory '{BUILD_DIR}'...")
        shutil.rmtree(BUILD_DIR)

    os.makedirs(BUILD_DIR, exist_ok=True)

    log(f"Configuring for {board} with algorithm {algo}...")
    run_command(
        f"cmake -S {PROJECT_ROOT} -B {BUILD_DIR} "
        f"-DBOARD={board} "
        f"-DALGO_SELECTED={algo}",
    )

    log("Building...")
    run_command(f"cmake --build {BUILD_DIR} --config Release -- -j4")

    target_name = f"ECLIPSE_{algo}_{board}"
    uf2 = os.path.join(BUILD_DIR, f"{target_name}.uf2")
    elf = os.path.join(BUILD_DIR, f"{target_name}.elf")

    if os.path.exists(uf2):
        log(f"Build successful. UF2 file located at: {uf2}")
        return uf2
    elif os.path.exists(elf):
        log(f"Build successful. ELF file located at: {elf}")
        return elf
    else:
        log("Build failed: No output file found.")
        sys.exit(1)

def flash_pico(binary_path):
    mount_candidates = ["/mnt/pico", "/media/pico", "/mnt/d", "/mnt/e"]
    mount_point = None
    
    for candidate in mount_candidates:
        if os.path.ismount(candidate):
            info_file = os.path.join(candidate, "INFO_UF2.TXT")
            if os.path.exists(info_file):
                mount_point = candidate
                break
    
    if not mount_point:
        log("Pico not found at known mount points.")
        log("Please mount it manually:")
        log("  sudo mount -o rw,uid=$(id -u),gid=$(id -g) /dev/sde1 /mnt/pico")
        mount_point = input("Enter mount point path: ").strip()
    
    log(f"Flashing {binary_path} to Pico at {mount_point}...")
    shutil.copy(binary_path, mount_point)
    log("Flash complete. Pico will reboot with the new firmware.")
    time.sleep(3)

def find_serial_port(baud=115200, timeout=15):
    log(f"Waiting for serial port (timeout {timeout}s)...")
    start = time.time()
    while time.time() - start < timeout:
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "ttyACM" in port.device or "ttyUSB" in port.device:
                log(f"Found serial port: {port.device}")
                return port.device
        time.sleep(0.5)
    log("No serial port found within timeout.")
    return None

def capture_serial(port, baud=115200, timeout=300):
    log(f"Opening {port} at {baud} baud...")
    lines = []

    try:
        with serial.Serial(port, baudrate=baud, timeout=1) as ser:
            ser.flushInput()
            start = time.time()
            while time.time() - start < timeout:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                print(f"    {line}")
                lines.append(line)
                if "ECLIPSE benchmark completed" in line:
                    log("Benchmark complete signal received")
                    break
    except serial.SerialException as e:
        log(f"Error reading serial port: {e}")
        sys.exit(1)
    return lines

def save_results(lines, output_path, run_index, total_runs):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    header = None
    data_rows = []
    for line in lines:
        if line.startswith("timestamp_iso"):
            header = line
        elif line.startswith("1970") or line.startswith("20"):
            data_rows.append(f"{run_index},{line}")
    
    if not data_rows:
        log("Warning: No data rows found in serial output.")
        return
    
    write_header = (run_index == 1) and not os.path.exists(output_path)

    with open(output_path, "a") as f:
        if write_header and header:
            f.write(f"run,{header}\n")
        for row in data_rows:
            f.write(f"{row}\n")
    
    log(f"Run {run_index}/{total_runs} results saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="ECLIPSE Benchmark Orchestration Tool")
    parser.add_argument("--board", required=True, choices=BOARDS.keys(), help="Target board")
    parser.add_argument("--algo", required=True, choices=ALGORITHMS, help="Algorithm to benchmark")
    parser.add_argument("--runs", type=int, default=5, help="Number of independent runs (default: 5)")
    parser.add_argument("--output", default=None, help="Output CSV file path (default: results/<board>_<algo>.csv)")
    parser.add_argument("--flash", action="store_true", help="Automatically flash the firmware after building")
    parser.add_argument("--clean", action="store_true", help="Clean build directory before building")
    parser.add_argument("--port", default=None, help="Serial port to use for capturing results (default: auto-detect)")
    args = parser.parse_args()

    board_info = BOARDS[args.board]
    log(f"Board:     {board_info['name']}")
    log(f"Algorithm: {args.algo}")
    log(f"Runs:      {args.runs}")

    if args.output is None:
        args.output = os.path.join(RESULTS_DIR, f"{args.board}_{args.algo}.csv")
    log(f"Output CSV: {args.output}")

    binary = build(args.board, args.algo, clean=args.clean)

    for run in range(1, args.runs + 1):
        log(f"=== Starting run {run}/{args.runs} ===")

        if args.flash:
            if args.board == "pico":
                flash_pico(binary)
            else:
                log(f"Auto-flash not yet implemented for {BOARDS[args.board]['name']}")
                log("Please flash manually and press Enter when ready")
                input()
        else:
            if run == 1:
                log("Manual flash mode - please flash the board now")
                log(f"Binary to flash: {binary}")
                input("Press Enter when the board is flashed and ready...")

        port = args.port
        if port is None:
            port = find_serial_port(timeout=15)
        if port is None:
            log("could not find serial port - exiting")
            sys.exit(1)

        lines = capture_serial(port, baud=BOARDS[args.board]["baud"], timeout=300)
        save_results(lines, args.output, run, args.runs)

        if not args.flash and run < args.runs:
            log("Please re-flash the board for the next run and press Enter when ready")
            input()
    
    log(f"\nAll {args.runs} runs complete:")
    log(f"Results saved to: {args.output}")

    
if __name__ == "__main__":
    main()