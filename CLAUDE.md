# CLAUDE.md – ESP32 Climate Controller

Guidance for Claude Code (and humans) working in this repo. Read this first, then `PLAN.md`.

## What this is

A temperature and humidity controller for a small AC/climate unit, built from two ESP32 boards joined by a wired serial link:

- **Mainboard** – ESP32 NodeMCU WROOM-32 DevKit. Runs the control rules. Reads an **AHT20 + BMP280** sensor board (I2C), switches a **4-relay board** (fan, heater, humidifier, compressor), sets the fan speed through a **PWM to 0-10 V converter**, and reads the fan's **tach output** (open collector, 1 pulse per revolution, sinks max 10 mA, SELV). Keeps the settings in flash.
- **Controller** – ESP32-C3 SuperMini. The user interface: a **DST-013 OLED** display and **two rotary encoders** with push switches (one concentric dual encoder in the final version). Set points, mode and configuration are changed on the encoders and sent to the Mainboard as commands. It shows temperature, humidity, what is running, and fault messages (sensor fault, fan fault, link lost).

There is **no web page in the current scope**. Everything is configured on the Controller.

- `PLAN.md` has the hardware and pin plan, the link protocol, the control rules, phases with checkboxes, the test list and the open questions. It is the project plan. Keep its checkboxes up to date when you finish something.
- The current status is in `PLAN.md` section 3. Phase 1 (control logic + simulated sensor, built on an ESP8266 with a web page) is done. **Next up is Phase 2: the Mainboard firmware on the ESP32** (sensor, fan speed and tach, fan fault, link). Then Phase 3 (Controller firmware), Phase 4 (safety and alarms) and Phase 5 (final hardware).

## Repo map

What is in the repo today. Most of it is from Phase 1 (ESP8266 + web page) and is the starting point for the Mainboard firmware.

```
platformio.ini            Firmware build envs (see below)
src/main.cpp              Relays, web server, WiFi/AP fallback, OTA, serial commands (Phase 1)
src/controller.{h,cpp}    Control rules. Plain C++, no Arduino calls (keep it that way: unit-testable)
src/sim_room.h            Simulated sensor + "room reacts" model (keep for testing)
src/storage.{h,cpp}       Settings saved to flash (LittleFS on ESP8266, NVS on ESP32)
include/config.h          Pins, active-low/high, network names
include/web_ui.h          The Phase 1 web page (to be removed or put behind a build flag)
include/secrets.example.h Copy to include/secrets.h (git-ignored) and fill in WiFi + passwords
tools/test-control.ps1    Phase 1 control-rule tests over HTTP (to be replaced by a serial test)
hardware/                 KiCad 10 project for the ESP8266 relay carrier PCB (see hardware/README.md)
hardware/gen/             Python generator: design.py is the single source of truth for the PCB
hardware/sim/             ngspice simulations of the PCB (SIM_REPORT.md)
hardware/case/            CadQuery enclosure + fit check (CASE.md)
```

Planned (not there yet): a separate build for the Controller firmware, and one shared header for the link messages that both firmwares include. Keep `controller.{h,cpp}` on the Mainboard side only; the Controller never makes control decisions.

## Setting up on a new machine

The original setup is Windows 11 with PowerShell. Paths below assume that; adjust on macOS/Linux.

1. **Firmware:** install VS Code + the PlatformIO IDE extension. The CLI is at `%USERPROFILE%\.platformio\penv\Scripts\pio.exe`. The first build downloads the toolchain, which takes a few minutes.
2. `copy include\secrets.example.h include\secrets.h` and fill in WiFi (needed while the Phase 1 web/WiFi code is still in the build). Never commit `secrets.h`.
3. **Hardware (optional):** install KiCad 10 (scripts expect `C:\Program Files\KiCad\10.0`). The generators run on KiCad's bundled Python (`C:\Program Files\KiCad\10.0\bin\python.exe`), which has `pcbnew` and numpy.
4. **Simulation (optional):** `cd hardware\sim`, then `py -3.12 -m venv .venv` and `.venv\Scripts\pip install numpy matplotlib`. Run `.venv\Scripts\python run_sim.py`. It drives KiCad's `ngspice.dll` through ctypes, so it needs KiCad 10 installed too.
5. **Case (optional):** `cd hardware\case`, then `py -3.12 -m venv .venv` and `.venv\Scripts\pip install cadquery`. Run `hardware\build.ps1 -Fab` first, because `fit_check.py` needs the board STEP. `.venv\Scripts\python case.py` rebuilds the parts, and `.venv\Scripts\python fit_check.py` must report `"PASS": true`. See `CASE.md`.
6. USB drivers: the WROOM-32 DevKit usually needs CP210x (Silicon Labs) or CH340, depending on the board. The ESP32-C3 SuperMini uses the chip's built-in USB and normally needs no driver.

## Firmware

| Command | What |
|---|---|
| `pio run -e esp32dev` | ESP32 WROOM-32 DevKit: the **Mainboard** (pins in `config.h`) |
| `pio run -e nodemcuv2` | Phase 1: NodeMCU (ESP8266) + a relay **module** (relays active LOW) |
| `pio run -e nodemcuv2-pcb` | Phase 1: NodeMCU on the ESP8266 PCB (relays active HIGH, `-DCLIMATE_PCB`) |
| `pio run -e <env> -t upload` | Flash over USB |
| `pio device monitor` | Serial at 115200. Commands: `status`, `mode off/auto/manual`, `temp 23.5`, `hum 60` |

A Controller env (ESP32-C3 SuperMini) is to be added in Phase 3. The ESP8266 envs, the `ota` env and the web/WiFi code are Phase 1 leftovers; remove them only as part of the Phase 2 checklist.

- **Mainboard pins (proposed, see `PLAN.md` section 1):** relays Fan 26, Heater 27, Humidifier 32, Compressor 33. I2C SDA 21, SCL 22 (sensor). Fan speed PWM 25. Fan tach 34 (input only: needs an external pull-up to 3.3 V, never 5 V). Link UART2 TX 17, RX 16. Avoid strapping pins 0, 2, 5, 12, 15 for outputs, and 6 to 11 (flash).
- **Controller pins (proposed):** OLED SDA 8, SCL 9. Encoder 1 A/B/push 0/1/3. Encoder 2 A/B/push 4/5/10. Link UART1 TX 21, RX 20. USB is on 18/19. GPIO 2, 8, 9 are strapping pins.
- If you change a pin, change `config.h` and `PLAN.md` together. The ESP8266 PCB's `CHANNELS` in `hardware/gen/design.py` only matches the Phase 1 NodeMCU pins.
- **Link:** UART 115200 8N1 (RS-485 if the cable is long). Framed messages with a CRC. The Mainboard owns the settings and sends status every 1 s; the Controller sends commands and waits for accept/reject. The Controller shows "NO LINK TO MAINBOARD" after 5 s without status. The Mainboard keeps controlling if the link is lost. Details in `PLAN.md` section 1.
- Control rules (bands, reheat while dehumidifying, fan run-on, compressor min off/on times, sensor-fault and fan-fault shutdown) live in `src/controller.cpp`. They are specified in `PLAN.md` section 2. If you change behaviour, update `PLAN.md` and the test list, and run the tests.
- `Settings` is saved as a raw struct. **Bump `SETTINGS_VERSION` in `src/storage.cpp` whenever `Settings` changes**, otherwise old flash data is misread.
- Before committing firmware changes, every env in `platformio.ini` must build.

### Phase 2 notes (next job: Mainboard)

- **Sensor:** AHT20 (temp + RH, I2C 0x38) and BMP280 (pressure + temp, 0x76 or 0x77) on one board, I2C at 100 kHz. Control uses the AHT20. Read every 2 s and average a few readings. Raise a sensor fault after 30 s with no valid reading. There is a `Reading` struct with a `valid` flag, and `Controller` already handles faults. Libraries: `adafruit/Adafruit AHTX0` and `adafruit/Adafruit BMP280 Library` via `lib_deps`.
- **Fan speed:** LEDC PWM into the PWM to 0-10 V converter. The 0-10 V command follows the fan relay: 0 V whenever the relay is off, the speed setting whenever it is on (command to 0 before the relay opens). Check the converter's PWM frequency and input level (many want 5 V or more), and calibrate its output.
- **Fan tach:** pull-up to 3.3 V (4.7-10 kΩ) plus a small RC filter. Count with PCNT. RPM = pulses/s × 60. **Fan fault:** fan relay on and speed above minimum, but RPM below the threshold (proposed 200) for 15 s after a 10 s spin-up allowance. It stops the heater, humidifier and compressor, keeps the fan on, and is latched until cleared from the Controller.
- Keep the simulated sensor, selectable from the Controller menu and the serial commands.

## Hardware (KiCad)

The PCB in `hardware/` is the **Phase 1 ESP8266 design** (plug-in NodeMCU v2, SHT31-D connector). It does not fit the WROOM-32 Mainboard. Whether to rework it or use an off-the-shelf relay board is an open item in `PLAN.md` Phase 5. The rules below apply to any work on it.

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
- The NodeMCU footprint assumes a **v2 "Amica" board with 22.86 mm row spacing** (CP2102). The LoLin v3 (27.9 mm) does not fit. **The PCB's relays are active HIGH** (`nodemcuv2-pcb`).

## Safety (keep these in docs and designs)

- Relay contacts can carry mains. 5 A max per channel on the project PCB; check the rating of any relay board used instead. The compressor (and any heater over ~1 kW) goes through a contactor. Heaters need an independent thermal cut-out. Mains wiring must be done by a competent person.
- The fan's 0-10 V input and tach output must be SELV. Confirm it in the fan's datasheet before connecting them. Keep sensor, link, 0-10 V and tach wiring away from mains wiring.
- The firmware must fail safe. On a sensor fault or a fan fault, the heater, humidifier and compressor stop. In Off mode, before a firmware update, after a crash and at boot, every load is off and the 0-10 V command is 0. Compressor protection (minimum off time, also after reboot) must stay.
- Losing the Controller link must never stop safety functions on the Mainboard. The Mainboard keeps controlling with its saved settings.

## Working conventions

- Keep docs in plain, direct English. When behaviour changes, update `README.md`, `PLAN.md`, `hardware/README.md`, or `CASE.md`, whichever applies.
- Small, focused commits. Run the relevant checks first: firmware builds, `build.ps1`, `run_sim.py`, `fit_check.py`.
- Don't commit secrets, `.pio/`, `hardware/build/` or any `.venv/`.
- Licences: firmware, scripts and docs are MIT (`LICENSE`); everything in `hardware/` is CERN-OHL-P-2.0 (`hardware/LICENSE`). Don't add code or models with incompatible terms (e.g. copied without permission or under a non-commercial licence).

## Open questions for the project owner (from PLAN.md section 5)

1. Have the dehumidify reheat rule and the "too hot + too dry" behaviour been read correctly?
2. Should the unit start in Off after a power cut, instead of resuming the last mode?
3. Fan speed: one fixed setting, or different per demand? Is there a minimum speed?
4. Is the proposed fan-fault behaviour right, and what is the fan's full-speed RPM?
5. Which driver does the DST-013 OLED use (SH1106 or SSD1306)?
6. How long is the Controller–Mainboard cable (UART or RS-485)?
7. Keep WiFi on the Mainboard just for OTA updates, or USB-only?
8. Is the proposed encoder layout right?
