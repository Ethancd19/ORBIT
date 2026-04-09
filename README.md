# ORBIT

**Open-Source Reference Benchmark for IoT Cryptography**

ORBIT is a portable bare-metal C benchmarking framework for evaluating NIST-standardized lightweight and post-quantum cryptographic algorithms on constrained IoT microcontrollers. It measures performance (cycles/byte), energy consumption ($\mu$J/operation), and memory footprint across multiple embedded architectures under identical, reproducible conditions.

Developed as a part of an M.Eng. Project & Report in Computer Engineering at Virginia Polytechnic Institute and State University, 2026.

---

## Algorithms

| Algorithm   | Type | Standard          | Notes                                 |
| ----------- | ---- | ----------------- | ------------------------------------- |
| Ascon-128   | AEAD | NIST SP 800-232   | Primary LWC standard                  |
| Ascon-80pq  | AEAD | NIST SP 800-232   | Quantum-hardened symmetric hedge      |
| GIFT-COFB   | AEAD | NIST LWC Finalist | SPN-based, compact hardware footprint |
| AES-128-GCM | AEAD | NIST SP 800-38D   | Baseline - industry standard          |
| ML-KEM-512  | KEM  | FIPS 203          | Post-quantum key encapsulation        |

All algorithms use publicly available reference C implementations. Hardware acceleration is explicitly disabled on all platforms for cross-architecture comparability.

---

## Hardware Platforms

| Board                      | MCU       | Architecture    | Clock   | RAM    | Flash  |
| -------------------------- | --------- | --------------- | ------- | ------ | ------ |
| Raspberry Pi Pico          | RP2040    | ARM Cortex-M0+  | 125 MHz | 264 KB | 2 MB   |
| STM32 Nucleo F446RE        | STM32F446 | ARM Cortex-M4F  | 180 MHz | 128 KB | 512 KB |
| Nordic nRF52832 (PCA10040) | nRF52832  | ARM Cortex-M4F  | 64 MHz  | 64 KB  | 512 KB |
| ESP32-C6 (DevKitC-1)       | ESP32-C6  | RISC-V RV32IMAC | 160 MHz | 512 KB | 4 MB   |
| Raspberry Pi 5             | BCM2712   | ARM Cortex-A76  | 2.4 GHz | 8 GB   | -      |

---

## Repository Structure

```text
ORBIT/
├── algorithms/
│   ├── ascon_aead128/      # Ascon-128 reference (NIST SP 800-232)
│   ├── ascon_aead80pq/     # Ascon-80pq reference
│   ├── gift_cofb/          # GIFT-COFB opt32 (NIST LWC finalist)
│   ├── aes_128_gcm/        # AES-128-GCM (cifra library, software-only)
│   └── ml_kem_512/         # ML-KEM-512 (PQClean reference, FIPS 203)
├── bench/
│   ├── main.c              # Benchmark loop, KAT correctness checks
│   ├── util.c / util.h     # CSV output, statistics, timing utilities
│   └── platform.h          # Resolved from platforms/<board>/platform.h
├── platforms/
│   ├── pico/platform.h     # RP2040: SysTick + time_us_64 cycle counter
│   ├── stm32/platform.h    # STM32F446: DWT CYCCNT cycle counter
│   ├── nrf52/platform.h    # nRF52832: DWT CYCCNT cycle counter
│   ├── esp32c6/platform.h  # ESP32-C6: RISC-V CSR cycle register
│   └── rpi5/platform.h     # RPi5: clock_gettime(CLOCK_MONOTONIC)
├── results/
│   ├── archived/           # Preliminary single-run data (superseded)
│   └── *.csv               # Final 5-run benchmark datasets
├── scripts/
│   └── attach_pico.ps1     # Windows: auto-attach Pico to WSL2 via usbipd
├── tools/
│   ├── orbit.py            # Benchmark orchestration and serial capture
│   └── plot_results.py     # Result visualization
├── include/
│   └── crypto_aead.h       # Shared AEAD interface
├── CMakeLists.txt          # Pico SDK build (ARM targets)
├── setup.sh                # One-shot environment setup script
└── requirements.txt        # Python dependencies
```

---

## Host Environment Setup

> **These instructions target Windows 11 + WSL2 (Ubuntu 24.04 LTS).**
> Native Linux users can skip the WSL2 and uspipd sections.
> See the [Native Linux Notes](#native-linux-notes) section at the bottom.

### Requirements

- Windows 11 with WSL2 enabled
- Ubuntu 24.04 LTS under WSL2
- Python 3.12+
- USB port for board connection

---

### Step 1: Install usbipd-win (Windows side, once only)

usbipd-win forwards USB devices from Windows into WSL2.

Download and install from: **https://github.com/dorssel/usbipd-win/releases**

Then allow running local Powershell scripts (run PowerShell as Administrator, once only):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

### Step 2: Run the automated setup script (WSL2 side)

```bash
git clone https://github.com/ethancd19/ORBIT.git
cd ORBIT
chmod +x setup.sh
./setup.sh
```

This handles everything automatically:

- System dependencies (`cmake`, `gcc-arm-none-eabi`, `build-essential`, `libusb`, etc.)
- Pico SDK clone and submodule init at `~/pico-sdk` with `PICO_SDK_PATH` added to `~/.bashrc`
- picotool build, install, and udev rules (enables automatic BOOTSEL reboot for runs 2–5)
- Python virtual environment at `.venv/` with all dependencies installed
- Passwordless sudo rule for `mount`/`umount` at `/etc/sudoers.d/orbit`
- `/mnt/pico` mount point

---

### Step 3: Activate the virtual environment

```bash
source .venv/bin/activate
```

To activate automatically on every terminal session, add to `~/.bashrc`:

```bash
echo 'cd ~/projects/ORBIT && source .venv/bin/activate' >> ~/.bashrc
```

---

### Step 4: Verify

```bash
python3 --version           # 3.12.x
cmake --version             # 3.16+
arm-none-eabi-gcc --version
picotool version
```

---

## Building

### Pico (ARM Cortex-M0+, Pico SDK)

```bash
source .venv/bin/activate

cmake -S . -B build \
    -DBOARD=pico \
    -DALGO_SELECTED=ascon_aead128

cmake --build build -- -j4
```

Output: `build/ORBIT_ascon_aead128_pico.uf2`

Use `--clean` flag in orbit.py or delete `build/` manually when switching algorithms or boards.

**BOARD values:** `pico`, `stm32`, `nrf52`

**ALGO_SELECTED values:** `ascon_aead128`, `ascon_aead80pq`, `gift_cofb`, `aes_128_gcm`, `ml_kem_512`

### STM32 Nucleo F446RE (ARM Cortex-M4F)

> Requires STM32CubeMX HAL or bare-metal CMSIS headers.
> **TODO: in progress.**

### nRF52832 PCA10040 (ARM Cortex-M4F)

> Requires nRF5 SDK. Set `NRF5_SDK_PATH` environment variable.
> **TODO: in progress.**

### ESP32-C6 DevKitC-1 (RISC-V RV32IMAC)

> Requires ESP-IDF v5.x. ESP32-C6 uses a separate build system.
> **TODO: ESP-IDF project under `platforms/esp32c6/` — in progress.**

### Raspberry Pi 5 (Linux, native GCC)

> Compile and run natively on the Pi. No cross-compilation needed.
> Requires `libgpiod-dev`: `sudo apt install libgpiod-dev`
> **TODO: native CMake target — in progress.**

---

## Running Benchmarks

### Automated mode (recommended)

```bash
source .venv/bin/activate

python3 tools/orbit.py \
  --board pico \
  --algo ascon_aead128 \
  --runs 5 \
  --flash
```

Results save to `results/pico_ascon_aead128.csv`.

### Available flags

| Flag                | Description                                                |
| ------------------- | ---------------------------------------------------------- |
| `--board`           | Target board (`pico`, `stm32`, `nrf52`, `esp32c6`, `rpi5`) |
| `--algo`            | Algorithm to benchmark                                     |
| `--runs`            | Independent runs (default: 5)                              |
| `--flash`           | Auto-flash firmware after build                            |
| `--clean`           | Clean build directory first                                |
| `--output`          | Custom output CSV path                                     |
| `--port`            | Serial port override (default: auto-detect)                |
| `--postprocess CSV` | Fix epoch timestamps in an existing CSV                    |

### Per-run workflow (Pico + WSL2)

**Run 1 — manual BOOTSEL entry required (no firmware on board yet):**

1. Hold the BOOTSEL button
2. Unplug the USB cable
3. Plug the USB cable back in
4. Release BOOTSEL — the RPI-RP2 drive should appear in Windows
5. In PowerShell: `usbipd attach --wsl --busid <busid>`
   (find busid with `usbipd list`: look for "RP2 Boot", VID:PID `2e8a:0003`)
6. Press Enter in the WSL2 terminal

**Runs 2–5 — fully automatic:**

- orbit.py reboots the Pico into BOOTSEL via picotool
- Runs `scripts/attach_pico.ps1` via `powershell.exe` from WSL2 automatically
- Scans for the device, mounts it, and copies the UF2
- Just press Enter when prompted

### Fixing timestamps on existing CSVs

```bash
python3 tools/orbit.py --postprocess results/pico_ascon_aead128.csv
```

Uses the file modification time as a proxy for the actual run timestamp.

### Interactive mode

```bash
python3 tools/orbit.py
```

This will prompt you through the available boards and algorithms you can run.

---

## Energy Measurement

### Hardware required

- INA226 power monitor breakout module
- 0.1Ω 1% tolerance shunt resistor
- Analog Discovery 3
- Breadboard and jumper wires

> Recommended to set up one dedicated breadboard per board.

### Wiring overview

The shunt resistor is placed in series on the 3.3V rail, load side of the onboard regulator. THis isolates the MCU current draw from USB supply noise and regulates quiescent current.

```text
USB 5V → [onboard regulator] → [0.1Ω shunt] → board 3.3V pin → MCU
                                     ↑
                                  INA226 IN+/IN-
                                  INA226 SDA/SCL → MCU I2C pins
                                  INA226 analog out → AD3 scope ch1
                                  MCU GPIO trigger → AD3 DIO ch0
```

### Pin assignments

| Board               | Trigger | SDA   | SCL   |
| ------------------- | ------- | ----- | ----- |
| Raspberry Pi Pico   | GP15    | GP4   | GP5   |
| STM32 Nucleo F446RE | PA8     | PB9   | PB8   |
| nRF52832 PCA10040   | P0.17   | P0.26 | P0.27 |
| ESP32-C6 DevKitC-1  | GPIO15  | GPIO6 | GPIO7 |
| Raspberry Pi 5      | GPIO23  | GPIO2 | GPIO3 |

### INA226 configuration

| Parameter             | Value        |
| --------------------- | ------------ |
| Shunt resistance      | 0.1Ω 1%      |
| Conversion time       | 140 µs       |
| Averaging             | 4 samples    |
| Effective sample rate | 1 per 560 µs |
| ADC resolution        | 16-bit       |

### Collection workflow

1. Wire up the board on its dedicated breadboard
2. Take an idle baseline current reading before each algorithm configuration
3. Run the same firmware binary used for cycle benchmarking
4. AEAD: one GPIO window per full iteration loop (divide total energy by iteration count)
5. ML-KEM: one GPIO window per individual operation
6. For ML-KEM on Pico (operations >130ms): use WaveForms Record mode
7. Export AD3 trace from WaveForms
8. Post-process trace against timing CSV using GPIO trigger timestamps for alignment

---

## Output Format

One CSV row per (algorithm, platform, message size) per run, prefixed with a `run` index.

| Field                 | Description                                     |
| --------------------- | ----------------------------------------------- |
| `run`                 | Independent run index (1-5)                     |
| `timestamp_iso`       | UTC timestamp injected from host clock          |
| `algorithm`           | Algorithm name                                  |
| `board`               | Target platform identifier                      |
| `arch`                | Instruction set architecture                    |
| `freq_hz`             | Core clock frequency (Hz)                       |
| `msg_len`             | Plaintext length (bytes)                        |
| `iterations`          | Iterations for this configuration               |
| `enc_cycles_total`    | Total cycles across all iterations (encryption) |
| `enc_cycles_per_byte` | Cycles per plaintext byte (primary metric)      |
| `enc_time_us_per_op`  | Microseconds per encryption operation           |
| `energy_uJ_enc_total` | Total energy: encryption window (INA226)        |
| `avg_power_mW_enc`    | Average power draw during encryption            |
| `ok`                  | 1 = KAT passed, 0 = KAT failed                  |

---

## Results

Final 5-run datasets: `results/<board>_<algo>.csv`

Preliminary single-run data (collected before 5-run protocol): `results/archived/`

---

## Cycle Counting

| Platform            | Method                         | Resolution |
| ------------------- | ------------------------------ | ---------- |
| RP2040 (Pico)       | SysTick + time_us_64()         | 1 cycle    |
| STM32F446 (Nucleo)  | DWT CYCCNT                     | 1 cycle    |
| nRF52832 (PCA10040) | DWT CYCCNT                     | 1 cycle    |
| ESP32-C6            | RISC-V CSR `cycle`             | 1 cycle    |
| BCM2712 (RPi5)      | clock_gettime(CLOCK_MONOTONIC) | ~1 ns      |

> The RP2040 Cortex-M0+ does not implement DWT CYCCNT. ORBIT uses SysTick combined with the RP2040 hardware timer for equivalent single-cycle resolution within each microsecond tick.

---

## Native Linux Notes

Running on native Linux (Ubuntu, Debian, etc.) without WSL2:

- Skip Step 1 entirely (usbipd-win is not needed)
- USB devices are directly accessible as `/dev/ttyACM0` etc.
- The Pico BOOTSEL drive mounts automatically on most distros
- `scripts/attach_pico.ps1` is not used. The PowerShell call in `orbit.py`'s `flash_pico()` will silently fail but the manual mount fallback will still work
- picotool BOOTSEL reboot works identically
- Everything else is the same

---

## Citation

```
Duval, E.C. (2026). Cross-Architecture Benchmarking of Lightweight and
Post-Quantum Cryptography on Constrained IoT Microcontrollers.
M.Eng. Project & Report, Virginia Polyechnic Institute and State University
```

---

## License

MIT License - see [LICENSE](LICENSE)
