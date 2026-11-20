# CLAUDE.md – ESP32 Climate Controller

Guidance for Claude Code (and humans) working in this repo. Read this first, then `PLAN.md`.

## What this is

A temperature and humidity controller for a small AC/climate unit, built from two ESP32 boards joined by a wired serial link:

- **Mainboard** – ESP32 NodeMCU WROOM-32 DevKit. Runs the control rules. Reads an **AHT20 + BMP280** sensor board (I2C), switches a **4-relay board** (fan, heater, humidifier, compressor), sets the fan speed through a **PWM to 0-10 V converter**, and reads the fan's **tach output** (open collector, 1 pulse per revolution, sinks max 10 mA, SELV). Keeps the settings in flash.
- **Controller** – ESP32-C3 SuperMini. The user interface: a **DST-013 OLED** display and **two rotary encoders** with push switches (one concentric dual encoder in the final version). Set points, mode and configuration are changed on the encoders and sent to the Mainboard as commands. It shows temperature, humidity, what is running, and fault messages (sensor fault, fan fault, link lost).

There is **no web page in the current scope**. Everything is configured on the Controller.

- `PLAN.md` has the hardware and pin plan, the link protocol, the control rules, phases with checkboxes, the test list and the open questions. It is the project plan. Keep its checkboxes up to date when you finish something.
- The current status is in `PLAN.md` section 3. Phase 1 (control logic + simulated sensor, on an ESP8266 with a web page) is done. The firmware for both new boards (Phases 2 and 3) is written and builds, but **has not been run on hardware yet**. Next: bench-test both boards, then Phase 4 (safety and alarms) and Phase 5 (final hardware).

## Repo map

```
platformio.ini                 Build envs: mainboard (esp32dev), controller (esp32-c3-devkitm-1)
include/link_protocol.h        Link framing, message structs and the item table. Shared by both firmwares
src/mainboard/main.cpp         Mainboard: relays, fan output order, link, USB serial commands
src/mainboard/climate_control.{h,cpp}  Control rules + FanMonitor. Plain C++, no Arduino calls (keep it that way: unit-testable)
src/mainboard/sensor.{h,cpp}   AHT20 + BMP280: read every 2 s, average, 30 s fault timeout, I2C bus recovery
src/mainboard/fan.{h,cpp}      LEDC PWM to the 0-10 V converter, tach interrupt and RPM
src/mainboard/storage.{h,cpp}  Settings saved to NVS
src/mainboard/sim_room.h       Simulated sensor + "room reacts" model (for testing)
src/mainboard/config.h         Mainboard pins and timings
src/controller/main.cpp        Controller: OLED screens, menu, pending changes, link
src/controller/input.h         Encoder (interrupt quadrature decode) and Button (debounce, long press)
src/controller/config.h        Controller pins and timings
tools/host-test/               g++ tests of the control rules, FanMonitor and link framing
tools/make_bench_diagram.py    Writes docs/bench-wiring.svg (breadboard wiring). Pins must match both config.h files
docs/BENCH_SETUP.md            Bench wiring checklist, Windows 11 flashing steps, first checks
hardware/                      KiCad 10 project for the Phase 1 ESP8266 relay carrier PCB (on hold)
hardware/gen/                  Python generator: design.py is the single source of truth for the PCB
hardware/sim/                  ngspice simulations of the PCB (SIM_REPORT.md)
hardware/case/                 CadQuery enclosure + fit check (CASE.md)
```

The Phase 1 ESP8266 firmware (web page, WiFi, OTA, `tools/test-control.ps1`) was removed. The last commit with it is `65d825e`.

## Setting up on a new machine

The original setup is Windows 11 with PowerShell. Paths below assume that; adjust on macOS/Linux.

1. **Firmware:** install VS Code + the PlatformIO IDE extension. The CLI is at `%USERPROFILE%\.platformio\penv\Scripts\pio.exe`. The first build downloads the ESP32 toolchains (Xtensa and RISC-V), which takes a few minutes. No secrets file is needed any more.
2. **Hardware (optional):** install KiCad 10 (scripts expect `C:\Program Files\KiCad\10.0`). The generators run on KiCad's bundled Python (`C:\Program Files\KiCad\10.0\bin\python.exe`), which has `pcbnew` and numpy.
3. **Simulation (optional):** `cd hardware\sim`, then `py -3.12 -m venv .venv` and `.venv\Scripts\pip install numpy matplotlib`. Run `.venv\Scripts\python run_sim.py`. It drives KiCad's `ngspice.dll` through ctypes, so it needs KiCad 10 installed too.
4. **Case (optional):** `cd hardware\case`, then `py -3.12 -m venv .venv` and `.venv\Scripts\pip install cadquery`. Run `hardware\build.ps1 -Fab` first, because `fit_check.py` needs the board STEP. `.venv\Scripts\python case.py` rebuilds the parts, and `.venv\Scripts\python fit_check.py` must report `"PASS": true`. See `CASE.md`.
5. USB drivers: the WROOM-32 DevKit usually needs CP210x (Silicon Labs) or CH340, depending on the board. The ESP32-C3 SuperMini uses the chip's built-in USB and normally needs no driver.

## Firmware

| Command | What |
|---|---|
| `pio run` | Builds both |
| `pio run -e mainboard -t upload` | Flash the Mainboard (ESP32 WROOM-32 DevKit) |
| `pio run -e controller -t upload` | Flash the Controller (ESP32-C3 SuperMini). If it won't connect: hold BOOT, tap RESET, release BOOT |
| `--upload-port COM5` / `--monitor-port` | Pick the board when both are plugged in |
| `pio device monitor -e mainboard` | Mainboard serial at 115200. `help` lists the commands (`status`, `mode`, `sensor real/sim`, `temp`, `hum`, `relay`, `set <name> <value>`, ...) |
| `g++ -std=c++17 -Isrc/mainboard -Iinclude tools/host-test/test_control.cpp src/mainboard/climate_control.cpp -o test_control && ./test_control` | Host tests, no board needed |

- **Mainboard pins (`src/mainboard/config.h`):** relays Fan 26, Heater 27, Humidifier 32, Compressor 33 (relay board active LOW by default: `RELAY_ACTIVE_LOW`). I2C SDA 21, SCL 22. Fan PWM 25. Fan tach 34 (input only: external pull-up to 3.3 V, never 5 V). Link UART2 TX 17, RX 16, RS-485 DE 4. Avoid strapping pins 0, 2, 5, 12, 15 for outputs, and 6 to 11 (flash).
- **Controller pins (`src/controller/config.h`):** OLED SDA 8, SCK 9 (1.3" I2C, SH1106 by default, `OLED_SSD1306` to switch). Encoder 1 A/B/push 0/1/3. Encoder 2 A/B/push 4/5/10. Link UART1 TX 21, RX 20, RS-485 DE 7. USB is on 18/19. GPIO 2, 8, 9 are strapping pins.
- If you change a pin, change `config.h`, `PLAN.md` section 1, `README.md`, `docs/BENCH_SETUP.md` and `tools/make_bench_diagram.py` (then run it) together.
- **Link (`include/link_protocol.h`):** UART 115200 8N1 now; MAX485 RS-485 modules later for ~10 m (DE pins already driven; the MAX485's 5 V RO output needs a divider, or use a 3.3 V MAX3485). Frames: `0xA5, type, len, payload, CRC-16`. The Mainboard sends STATUS every 0.5 s and nothing else unasked. The Controller may send ONE frame right after each STATUS (GET_SETTINGS or SET); the Mainboard answers with SETTINGS or ACK. Keep that rule: it is what makes half-duplex RS-485 work. Values are `LinkItem`s as scaled `int16` (x10 for °C/%RH). **Bump `LINK_PROTOCOL_VERSION` when a payload struct changes**, and keep `linkItemInfo()` in step with `sanitize()`.
- The Mainboard owns all settings and makes all control decisions. The Controller only displays and sends changes. A change is shown as pending (inverted) until the Mainboard's ACK.
- Control rules (bands, reheat while dehumidifying, fan run-on, compressor min off/on times, sensor-fault and fan-fault shutdown) live in `src/mainboard/climate_control.cpp`. They are specified in `PLAN.md` section 2. If you change behaviour, update `PLAN.md`, the test list and `tools/host-test/`, and run the host tests.
- **The 0-10 V command follows the fan relay**: `updateOutputs()` in `src/mainboard/main.cpp` sets it to 0 before opening the relay and to the speed setting after closing it.
- `Settings` is saved as a raw struct. **Bump `SETTINGS_VERSION` in `src/mainboard/storage.cpp` whenever `Settings` changes** (now 2), otherwise old flash data is misread.
- The simulated-sensor choice, sim values and manual switches are never saved: the Mainboard always boots on the real sensor with everything off.
- Before committing firmware changes, `pio run` (both envs) must build and the host tests must pass.

### Bench-test notes (next job)

- **Sensor:** AHT20 at 0x38, BMP280 at 0x76 or 0x77 (pressure only shown if found). I2C at 100 kHz. Library calls are in `sensor.cpp` (`adafruit/Adafruit AHTX0`, `adafruit/Adafruit BMP280 Library`).
- **Fan:** check the converter responds to a 3.3 V, 1 kHz PWM (many want 5 V or more: add a level shifter if not), then calibrate `FAN_PWM_DUTY_AT_0V/10V`. Tach: 10 kΩ pull-up to 3V3, 1 kΩ series, 10 nF to GND. Fan fault defaults: below 200 RPM for 15 s after 10 s spin-up; `fanfaultrpm 0` turns it off for bench work without a fan.
- **Controller:** check `ENC_STEPS_PER_DETENT` and `ENC1/2_REVERSE` against the real encoders, and the display driver.

## Hardware (KiCad)

The PCB in `hardware/` is the **Phase 1 ESP8266 design** (plug-in NodeMCU v2, SHT31-D connector). It does not fit the WROOM-32 Mainboard, and its `nodemcuv2-pcb` firmware env is gone (commit `65d825e` has it). Whether to rework it or use an off-the-shelf relay board is an open item in `PLAN.md` Phase 5. The rules below apply to any work on it.

- **Never hand-edit `hardware/*.kicad_sch` / `*.kicad_pcb` and expect it to stick.** They are generated. Change `hardware/gen/design.py` (parts, values, nets, placement), or the generator scripts, then run:
  ```
  powershell -ExecutionPolicy Bypass -File hardware\build.ps1        # regenerate + ERC + DRC + renders
  powershell -ExecutionPolicy Bypass -File hardware\build.ps1 -Fab   # + Gerbers, drill, BOM, PDFs, STEP
  ```
  It exits 0 only if ERC and DRC have 0 errors, 0 unconnected items and 0 schematic/PCB differences. It must exit 0 before you commit. The ~90 DRC warnings are silkscreen cosmetics. Outputs go to `hardware/build/` (git-ignored).
- **Pipeline:**
  1. `make_pro.py` writes the project file, net classes and `.kicad_dru` rules.
  2. `make_sch.py` writes the schematic by copying symbols from KiCad's libraries.
  3. `kicad-cli sch upgrade` and ERC run.
  4. `make_pcb.py` places parts, using nets from KiCad's own netlist export so parity always holds. It hand-routes the mains traces on both layers, auto-routes the rest with `router.py` (a small A* grid router), and pours GND.
  5. DRC runs.
- If you hand-edit in KiCad anyway (e.g. to polish routing), you're leaving the generator behind. Say so in the commit and stop using `build.ps1` for that file.
- **Mains safety rules are enforced by DRC.** Netclass `Mains` covers the `*_COM/_NO/_NC` nets. Mains to low voltage needs ≥ 3.0 mm clearance and ≥ 4.0 mm creepage; mains to mains ≥ 2.0 mm; mains to screw holes ≥ 3.0 mm. Currently measured: 3.70 / 4.83 / 2.78 / 5.12 mm. Routed U-slots around each relay's COM pin provide the creepage. Don't weaken these rules to make DRC pass. Any new low-voltage connectors (0-10 V, tach, link) count as low voltage.
- **Gotchas found the hard way:**
  - KiCad DRC silently ignores a condition like `!B.hasNetclass('Mains')`. Use `B.NetClass != 'Mains'`. To prove a rule is active, set it to an absurd value (20 mm) on a scratch copy and confirm DRC fails.
  - On the horizontal Phoenix MKDS terminal footprints, the wire entry is on the footprint's **+Y** face. This was checked in the STEP model; the terminals are rotated 180° so the entry faces the board edge.
  - KiCad 3D-model z-rotation is the opposite sign to what you'd expect. The socket models use `-90`.
  - In PowerShell, `$fab` and a `-Fab` switch are the same variable (case-insensitive).
  - Never put `\"` at the end of a native argument (`-o "dir\"`), because it escapes the quote. Use `dir/`.
  - Running downloaded executables (e.g. the Freerouting CLI) was blocked by the permission policy on the original machine. That's why routing is done by `router.py`.
- The NodeMCU footprint assumes a **v2 "Amica" board with 22.86 mm row spacing** (CP2102). The LoLin v3 (27.9 mm) does not fit. **The PCB's relays are active HIGH** (`RELAY_ACTIVE_LOW = false`).

## Safety (keep these in docs and designs)

- Relay contacts can carry mains. 5 A max per channel on the project PCB; check the rating of any relay board used instead. The compressor (and any heater over ~1 kW) goes through a contactor. Heaters need an independent thermal cut-out. Mains wiring must be done by a competent person.
- The fan's 0-10 V input and tach output must be SELV. Confirm it in the fan's datasheet before connecting them. Keep sensor, link, 0-10 V and tach wiring away from mains wiring.
- The firmware must fail safe. On a sensor fault or a fan fault, the heater, humidifier and compressor stop. In Off mode, before a firmware update, after a crash and at boot, every load is off and the 0-10 V command is 0. Compressor protection (minimum off time, also after reboot) must stay.
- Losing the Controller link must never stop safety functions on the Mainboard. The Mainboard keeps controlling with its saved settings.

## Working conventions

- Keep docs in plain, direct English. When behaviour changes, update `README.md`, `PLAN.md`, `hardware/README.md`, or `CASE.md`, whichever applies.
- Small, focused commits. Run the relevant checks first: firmware builds, `build.ps1`, `run_sim.py`, `fit_check.py`.
- Don't commit secrets, `.pio/`, `hardware/build/`, any `.venv/` or host-test binaries.
- Licences: firmware, scripts and docs are MIT (`LICENSE`); everything in `hardware/` is CERN-OHL-P-2.0 (`hardware/LICENSE`). Don't add code or models with incompatible terms (e.g. copied without permission or under a non-commercial licence).

## Open questions for the project owner (from PLAN.md section 5)

1. Have the dehumidify reheat rule and the "too hot + too dry" behaviour been read correctly?
2. Should the unit start in Off after a power cut, instead of resuming the last mode?
3. Does the fan need to run whenever the heater is on? (It does now.)
4. Fan speed: one fixed setting, or different per demand? Is there a minimum speed?
5. Is the fan-fault behaviour right, and what is the fan's full-speed RPM?
6. Bring WiFi back on the Mainboard just for OTA updates, or stay USB-only?
7. Is the encoder layout right?
