import os
import subprocess
import sys
import shutil
import platform
from dataclasses import dataclass

BUILD_DIR = "build"

BOARDS = {
    "1": {"name": "PC (Simulation)", "id": "pc", "arch": "x86_64"},
    "2": {"name": "Indus Board (RISC-V)", "id": "indus", "arch": "riscv32"},
    "3": {"name": "STM32 Nucleo (ARM)", "id": "stm32", "arch": "armv7e-m"},
}

ALGORITHMS = {
    "1": {"name": "ASCON AEAD-128", "cmake_algo": "ascon_aead128", "cmake_impl": "ref"},
    "2": {"name": "AES-GCM", "cmake_algo": "aes_gcm", "cmake_impl": "ref"},
    "3": {"name": "ASCON-80PQ", "cmake_algo": "ascon_aead80pq", "cmake_impl": "ref"},
}

OPTIMIZATIONS = {
    "1": "-O0 (Debug/None)",
    "2": "-O2 (Default)",
    "3": "-O3 (Aggressive)",
    "4": "-Os (Size Optimized)",
}

IMPL_ROOT = "impl"

def ask(options, prompt):
    print(f"\n--- {prompt} ---")
    for key, value in options.items():
        if isinstance(value, dict):
            print(f"[{key}] {value['name']}")
        else:
            print(f"[{key}] {value}")
    
    while True:
        choice = input("Enter your choice: ").strip()
        if choice in options:
            return options[choice]
        else:
            print("Invalid choice. Please try again.")

def run_command(cmd):
    print(f"[EXEC] {cmd}")
    ret = subprocess.call(cmd, shell=True)
    if ret != 0:
        print("Error executing command.")
        sys.exit(1)

def prompt_default(prompt, default):
    response = input(f"{prompt} [default: {default}]: ").strip()
    return response if response else default

def yes_no(prompt, default=False):
    default_str = "Y/n" if default else "y/N"
    response = input(f"{prompt} ({default_str}): ").strip().lower()
    if not response:
        return default
    return response in ['y', 'yes', 'true', '1']

def list_impl_targets():
    targets = []
    if not os.path.isdir(IMPL_ROOT):
        print(f"Implementation root directory '{IMPL_ROOT}' does not exist.")
        sys.exit(1)

    for name in sorted(os.listdir(IMPL_ROOT)):
        full_path = os.path.join(IMPL_ROOT, name)
        if not os.path.isdir(full_path):
            continue
        if "_" not in name:
            continue
        algo, impl = name.rsplit("_", 1)
        targets.append({"folder": name, "algo": algo, "impl": impl, "name": f"{algo} ({impl})"})
    return targets

def choose_target():
    targets = list_impl_targets()
    if not targets:
        print("Error: No implementation folders found under ./impl.")
        print("Expected folders like: impl/<algo>_<impl>/")
        sys.exit(1)

    options = {}
    for idx, target in enumerate(targets, start=1):
        options[str(idx)] = target
    
    chosen = ask(options, "Select Algorithm/Implementation Target")
    return chosen

def build_exe_name(algo, impl):
    exe = f"bench_{algo}_{impl}"
    if platform.system() == "Windows":
        exe += ".exe"
    return exe

def resolve_exe_path(exe_name):
    exe_path = os.path.join(BUILD_DIR, exe_name)
    if platform.system() == "Windows" and not os.path.exists(exe_path):
        possible_path = os.path.join(BUILD_DIR, "Release", exe_name)
        if os.path.exists(possible_path):
            exe_path = possible_path
    return exe_path

def main():
    print("=== Benchmark Manager ===")
    target = choose_target()
    board = ask(BOARDS, "Select Target Board")
    optimization = ask(OPTIMIZATIONS, "Select Optimization Level")

    version = input("\nEnter version identifier (e.g., v1.0): ").strip() or "default"

    msg_lens = prompt_default('Message lengths for -l (comma list, e.g. "16,64,1024")', "16,32,64,128,256,512,1024,4096,16384")
    ad_lens  = prompt_default('AD lengths for -a (comma list, e.g. "0,32")', "0,32,128")
    iter_s   = prompt_default("Iterations for small messages (-i)", "20000")
    iter_L   = prompt_default("Iterations for large messages (-I)", "2000")
    try:
        repeats = int(prompt_default("Number of times to repeat each measurement", "1"))
    except ValueError:
        print("Invalid input for repeats. Using default value 1.")
        repeats = 1

    out_path = prompt_default("Output CSV file path", os.path.join("results", f"{target['algo']}_{target['impl']}.csv"))
    append = yes_no("Append to output file (will drop the repeated header line)?", default=False)
    clean_build = yes_no("Clean build directory before building?", default=True)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    if clean_build and os.path.exists(BUILD_DIR):
        print(f"\n>>> Cleaning existing build directory '{BUILD_DIR}'...")
        try:
            shutil.rmtree(BUILD_DIR)
        except Exception as e:
            print(f"Warning: Could not remove build directory: {e}")
    os.makedirs(BUILD_DIR, exist_ok=True)

    opt_flag = optimization.split(" ")[0]

    print(f"\n>>> Configuring for {board['name']} with {opt_flag}...")
    cmake_cmd = (
        f"cmake -S . -B {BUILD_DIR} "
        f"-DBOARD={board['id']} "
        f"-DUSER_VERSION=\"{version}\" "
        f"-DCMAKE_C_FLAGS=\"{opt_flag}\" "
        f"-DALGO_SELECTED={target['algo']} "
        f"-DIMPL_SELECTED={target['impl']}"
    )
    run_command(cmake_cmd)

    print("\n>>> Compiling...")
    run_command(f"cmake --build {BUILD_DIR} --config Release")
    
    exe_name = build_exe_name(target["algo"], target["impl"])
    exe_path = resolve_exe_path(exe_name)
    
    print("\n>>> Running Benchmark...")
    if not os.path.exists(exe_path):
        print(f"Error: Could not find executable at {exe_path}")
        print("Check the build output above for errors.")
        sys.exit(1)
    
    cmd = [exe_path, "-l", msg_lens, "-a", ad_lens, "-i", str(iter_s), "-I", str(iter_L)]
    print("[EXEC]", " ".join(f"\"{c}\"" if " " in c else c for c in cmd))

    for r in range(1, repeats + 1):
        print(f">>> Run {r}/{repeats}...")

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr)
            print("Error: Benchmark execution failed.")
            sys.exit(proc.returncode)
        
        csv_text = proc.stdout

        append_run = append or (r > 1)

        if append_run and os.path.exists(out_path):
            csv_lines = csv_text.splitlines(True)
            if csv_lines:
                csv_text = "".join(csv_lines[1:])
        
        mode = "a" if append_run else "w"
        with open(out_path, mode, newline="") as f:
            f.write(csv_text)
    
    print(f"\n>>> Results written to {out_path}")

if __name__ == "__main__":
    main()