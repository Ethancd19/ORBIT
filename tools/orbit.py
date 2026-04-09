#!/usr/bin/env python3
"""
ORBIT - Open-Source Reference Benchmark for IoT Cryptography
Benchmark Manager Script.

Usage:
    python3 tools/orbit.py --board pico --algo ascon_aead128 --runs 5
    python3 tools/orbit.py --board pico --algo ascon_aead128 --runs 5 --output results/run1.csv
    python3 tools/orbit.py --board pico --algo ascon_aead128 --runs 5 --flash
"""

import argparse
import csv
import io
import os
import subprocess
import sys
import time
import re
import shutil
import glob
from datetime import datetime, timezone

import serial
import serial.tools.list_ports

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
ALGORITHMS = [
    "ascon_aead128",
    "ascon_aead80pq",
    "gift_cofb",
    "aes_128_gcm",
    "ml_kem_512",
]

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")

TIMESTAMP_COL = "timestamp_iso"
RUN_ID_COL = "run_id"

FLASH_FUNCS = {
    "pico": lambda binary: flash_pico(binary),
    # "stm32":   lambda binary: flash_stm32(binary),
    # "nrf52":   lambda binary: flash_nrf52(binary),
    # "esp32c6": lambda binary: flash_esp32c6(binary),
    # "rpi5":    lambda binary: flash_rpi5(binary),
}

# ----- Logging -----
def log(msg):
    print(f"[ORBIT] {msg}")

# ----- Timestamp Formatting -----
def host_timestamp_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _compact_ts(iso: str) -> str:
    return re.sub(r"[-:]", "", iso).replace("Z", "Z")

def make_run_id(ts_iso: str, algorithm: str, board: str, arch: str) -> str:
    compact = _compact_ts(ts_iso)
    def slug(s):
        return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return f"{compact}_{slug(algorithm)}_{slug(board)}_{slug(arch)}"

def postprocess_csv(input_path: str, output_path: str | None = None) -> None:
    if output_path is None:
        output_path = input_path

    mtime = os.path.getmtime(input_path)
    file_ts = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    log(f"Post-processing CSV: {input_path}")
    log(f"File timestamp (UTC): {file_ts}")

    with open(input_path, newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            log("Error: CSV file has no header")
            sys.exit(1)

        rows = list(reader)
    
    epoch_pattern = re.compile(r"^1970-")
    fixed = 0

    for row in rows:
        if epoch_pattern.match(row.get(TIMESTAMP_COL, "")):
            row[TIMESTAMP_COL] = file_ts
            row[RUN_ID_COL] = make_run_id(file_ts, row.get("algorithm", "unknown"), row.get("board", "unknown"), row.get("arch", "unknown"))
            fixed += 1
    
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    with open(output_path, "w", newline="", encoding="utf-8") as outfile:
        outfile.write(buf.getvalue())

    log(f"Fixed {fixed} timestamp(s) in CSV. Written to: {output_path}")

# ----- Build and Flashing -----

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

    target_name = f"ORBIT_{algo}_{board}"
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

def _attach_pico_wsl():
    """
    Call the powershell attach script from WSL2 to reattach the Pico
    after a BOOTSEL replug. powershell.exe is accessible from WSL2.
    """
    ps_script = os.path.join(PROJECT_ROOT, "scripts", "attach_pico.ps1")
        
    if not os.path.exists(ps_script):
        log("attach_pico.ps1 not found, trying inline usbipd command...")
        cmd = (
            'powershell.exe -Command "'
            '$d = usbipd list | Select-String \\"2e8a:0003\\"; '
            'if ($d) { $b = ($d[0].Line -split \\"\\\\s+\\")[0].Trim(); '
            'usbipd attach --wsl --busid $b; '
            'Write-Host \\"Attached $b\\" }"'
        )
        ret = subprocess.call(cmd, shell=True)
        return ret == 0

    # Copy script to Windows temp directory (accessible to powershell.exe)
    win_temp = "/mnt/c/Windows/Temp/attach_pico.ps1"
    try:
        shutil.copy(ps_script, win_temp)
    except Exception as e:
        log(f"Could not copy script to Windows temp: {e}")
        return False

    log("Running attach_pico.ps1 via powershell.exe...")
    ret = subprocess.call(
        'powershell.exe -ExecutionPolicy RemoteSigned -File "C:\\Windows\\Temp\\attach_pico.ps1"',
        shell=True
    )
    return ret == 0

def flash_pico(binary_path):
    uid = os.getuid()
    gid = os.getgid()
    mount_point = None

    log("Attempting picotool reboot into BOOTSEL mode...")
    ret = subprocess.call(
        "picotool reboot -f -u",
        shell=True,
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL
    )

    if ret == 0:
        log("Picotool reboot successful.")
        time.sleep(3)
    else:
        log("Picotool reboot failed: Pico may already be in BOOTSEL or unpowered.")

    log("Reattaching Pico to WSL2 via usbipd...")
    _attach_pico_wsl()
    time.sleep(2)

    # Check if already mounted from a manual mount
    if os.path.exists("/mnt/pico/INFO_UF2.TXT"):
        mount_point = "/mnt/pico"
        log("Found Pico at /mnt/pico (already mounted)")
    else:
        # Try to find and mount automatically
        try:
            result = subprocess.run(
                ["lsblk", "-o", "NAME,SIZE,RM,TYPE", "--noheadings"],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[3] == "part" and parts[2] == "1" and "128M" in parts[1]:
                    clean_name = re.sub(r'[^a-zA-Z0-9]', '', parts[0])
                    device = f"/dev/{clean_name}"
                    os.makedirs("/mnt/pico", exist_ok=True)
                    mount_cmd = f"sudo mount -o rw,uid={uid},gid={gid} {device} /mnt/pico"
                    log(f"Attempting: {mount_cmd}")
                    ret = subprocess.call(mount_cmd, shell=True)
                    log(f"Mount return code: {ret}")
                    time.sleep(1)
                    if os.path.exists("/mnt/pico/INFO_UF2.TXT"):
                        mount_point = "/mnt/pico"
                        log(f"Auto-mounted {device} at /mnt/pico")
                    else:
                        log(f"Mount succeeded (rc={ret}) but INFO_UF2.TXT not found")
                        log(f"Contents of /mnt/pico: {os.listdir('/mnt/pico') if os.path.exists('/mnt/pico') else 'directory missing'}")
                    break
        except Exception as e:
            log(f"Auto-mount scan failed: {e}")

    # Fall back to asking user
    if not mount_point:
        log("Auto-mount failed. Please mount manually in another terminal:")
        log("  lsblk  then  sudo mount -o rw,uid=$(id -u),gid=$(id -g) /dev/sdX1 /mnt/pico")
        input("Press Enter once /mnt/pico shows INFO_UF2.TXT ...")
        mount_point = "/mnt/pico"

    log(f"Copying {os.path.basename(binary_path)} -> {mount_point} ...")
    shutil.copy(binary_path, mount_point)
    log("Flash complete. Pico rebooting...")

    subprocess.call("sudo umount /mnt/pico", shell=True, stderr=subprocess.DEVNULL)
    log("Unmounted /mnt/pico.")

    log("Waiting for Pico to reboot into firmware mode...")
    time.sleep(8)

    log("Reattaching Pico serial device to WSL2...")
    _attach_pico_wsl()
    time.sleep(3)
# ----- Serial Capture and Result Processing -----

def find_serial_port(baud=115200, timeout=30):
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
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                print(f"    {line}")
                lines.append(line)
                if "ORBIT benchmark completed" in line:
                    log("Benchmark complete signal received")
                    break
    except serial.SerialException as e:
        log(f"Error reading serial port: {e}")
        sys.exit(1)
    return lines

def save_results(lines, output_path, run_index, total_runs, board, algo):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    ts_now = host_timestamp_iso()

    header = None
    data_rows = []
    for line in lines:
        if line.startswith("timestamp_iso"):
            header = line
        elif line.startswith("1970") or (line[:4].isdigit() and line[4] == "-"):
            try:
                parsed = next(csv.reader([line]))
            except StopIteration:
                continue
            
            if len(parsed) < 2:
                continue
            
            parsed[0] = ts_now
            parsed[1] = make_run_id(ts_now, algo, board, parsed[6] if len(parsed) > 6 else "unknown")

            buf = io.StringIO()
            csv.writer(buf).writerow(parsed)
            data_rows.append(f"{run_index},{buf.getvalue().strip()}")
    
    if not data_rows:
        log("Warning: No data rows found in serial output.")
        return
    
    write_header = (run_index == 1) and not os.path.exists(output_path)

    with open(output_path, "a", encoding="utf-8", newline="") as f:
        if write_header and header:
            f.write(f"run,{header}\n")
        for row in data_rows:
            f.write(f"{row}\n")
    
    log(f"Run {run_index}/{total_runs} results saved to {output_path}")

# ----- Main -----
def main():
    parser = argparse.ArgumentParser(
        description="ORBIT Benchmark Orchestration Tool", 
        formatter_class=argparse.RawDescriptionHelpFormatter,         
        epilog="""
Examples:
  # Interactive mode (prompts for board and algo):
  python3 tools/orbit.py
 
  # Explicit run with auto-flash:
  python3 tools/orbit.py --board pico --algo ascon_aead128 --runs 5 --flash
 
  # Fix timestamps in an existing CSV produced without host-side injection:
  python3 tools/orbit.py --postprocess results/pico_ascon_aead128.csv
        """,
    )
    parser.add_argument("--board", required=False, choices=BOARDS.keys(), help="Target board")
    parser.add_argument("--algo", required=False, choices=ALGORITHMS, help="Algorithm to benchmark")
    parser.add_argument("--runs", type=int, default=5, help="Number of independent runs (default: 5)")
    parser.add_argument("--output", default=None, help="Output CSV file path (default: results/<board>_<algo>.csv)")
    parser.add_argument("--flash", action="store_true", help="Automatically flash the firmware after building")
    parser.add_argument("--clean", action="store_true", help="Clean build directory before building")
    parser.add_argument("--port", default=None, help="Serial port to use for capturing results (default: auto-detect)")
    parser.add_argument("--postprocess", metavar="CSV", help="Post-process an existing CSV file to fix timestamps and run IDs")
    args = parser.parse_args()

    if args.postprocess:
        postprocess_csv(args.postprocess)
        return

    if not args.board or not args.algo:
        print("\n=== ORBIT Interactive Mode ===")

        if not args.board:
            print("Available boards:")
            for i, (key, val) in enumerate(BOARDS.items(), 1):
                print(f"  [{i}] {key} - {val['name']}")
            while True:
                choice = input("Select a board: ").strip()
                board_keys = list(BOARDS.keys())
                if choice.isdigit() and 1 <= int(choice) <= len(BOARDS):
                    args.board = board_keys[int(choice) - 1]
                    break
                elif choice in BOARDS:
                    args.board = choice
                    break
                print("Invalid choice, please try again.")

        if not args.algo:
            print("\nAvailable algorithms:")
            for i, algo in enumerate(ALGORITHMS, 1):
                print(f"  [{i}] {algo}")
            while True:
                choice = input("Select an algorithm: ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(ALGORITHMS):
                    args.algo = ALGORITHMS[int(choice) - 1]
                    break
                elif choice in ALGORITHMS:
                    args.algo = choice
                    break
                print("Invalid choice, please try again.")
        
        if args.runs == 5:
            runs_input = input("\nEnter number of runs (default 5): ").strip()
            if runs_input.isdigit():
                args.runs = int(runs_input)

    board_info = BOARDS[args.board]
    if args.output is None:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        args.output = os.path.join(RESULTS_DIR, f"{args.board}_{args.algo}.csv")

    log(f"Board:      {board_info['name']}")
    log(f"Algorithm:  {args.algo}")
    log(f"Runs:       {args.runs}")
    log(f"Output CSV: {args.output}")

    binary = build(args.board, args.algo, clean=args.clean)

    slow_algos = {"aes_128_gcm", "ml_kem_512"}
    serial_timeout = 3600 if args.algo in slow_algos else 300

    for run in range(1, args.runs + 1):
        log(f"=== Starting run {run}/{args.runs} ===")

        if args.flash:
            if args.board == "pico":
                if run == 1:
                    log("Run 1 requires manual BOOTSEL entry (no firmware to reboot from):")
                    log("  1. Hold BOOTSEL button")
                    log("  2. Unplug USB")
                    log("  3. Plug USB back in")
                    log("  4. Release BOOTSEL")
                    input("Press Enter once Pico is in BOOTSEL mode ...")
                else:
                    log(f"Run {run}: picotool will reboot Pico into BOOTSEL automatically...")
                FLASH_FUNCS[args.board](binary)
            else:
                log(f"Auto-flash not yet implemented for {BOARDS[args.board]['name']}")
                log(f"Please flash manually: {binary}")
                input("Press Enter when the board is running the new firmware ...")
        else:
            if run == 1:
                log("Manual flash mode - please flash the board now")
                log(f"Binary to flash: {binary}")
                log("Flash the binary now, then come back here.")
            else:
                log("Reflash the board for the next run:")
                log("  Pico: hold BOOTSEL, re-plug USB, copy the UF2 to RPI-RP2")
                log(f"  UF2: {binary}") 
                input("Press Enter when the board is flashed and ready...")

        port = args.port or find_serial_port(timeout=20)
        if port is None:
            log("ERROR: Could not find serial port - exiting")
            sys.exit(1)

        lines = capture_serial(port, baud=BOARDS[args.board]["baud"], timeout=serial_timeout)
        save_results(lines, args.output, run, args.runs, args.board, args.algo)
    
    log(f"\nAll {args.runs} runs complete:")
    log(f"Results saved to: {args.output}")

    postprocess_csv(args.output)

    
if __name__ == "__main__":
    main()