# CLAUDE.md â€“ ESP32/ESP8266 Climate Controller

Guidance for Claude Code (and humans) working in this repo. Read this first, then `PLAN.md`.

## What this is

A temperature and humidity controller for a small AC/climate unit. An ESP8266 (NodeMCU v2) switches 4 relays (fan, heater, humidifier, compressor) to hold a temperature set point and a humidity set point. It has a web page and JSON API, a simulated sensor for development, a custom relay carrier PCB (KiCad 10), SPICE simulations of that PCB, and a 3D-printable case.

- `PLAN.md` has the control rules, phases with checkboxes, the test list and the open questions. It is the project plan. Keep its checkboxes up to date when you finish something.
- The current status is in `PLAN.md` section 3. Phases 1 (control logic + simulated sensor) and 5 (PCB and case design) are done. **Next up is Phase 2: the real SHT31-D sensor.** After that come Phase 3 (safety and alarms) and Phase 4 (history and remote access).

## Repo map

```
platformio.ini            Firmware build envs (see below)
src/main.cpp              Relays, web server, WiFi/AP fallback, OTA, serial commands
src/controller.{h,cpp}    Control rules. Plain C++, no Arduino calls (keep it that way: unit-testable)
src/sim_room.h            Simulated sensor + "room reacts" model (stand-in until the SHT31-D is fitted)
src/storage.{h,cpp}       Settings saved to flash (LittleFS on ESP8266, NVS on ESP32)
include/config.h          Pins, active-low/high, network names
include/web_ui.h          The web page (HTML/JS in a raw string)
include/secrets.example.h Copy to include/secrets.h (git-ignored) and fill in WiFi + passwords
tools/test-control.ps1    Runs the PLAN.md control-rule test list against a live board over HTTP
hardware/                 KiCad 10 project for the relay carrier PCB (see hardware/README.md)
hardware/gen/             Python generator: design.py is the single source of truth for the PCB
hardware/sim/             ngspice simulations of the PCB (SIM_REPORT.md)
hardware/case/            CadQuery enclosure + fit check (CASE.md)
```

## Setting up on a new machine

The original setup is Windows 11 with PowerShell. Paths below assume that; adjust on macOS/Linux.

1. **Firmware:** install VS Code + the PlatformIO IDE extension. The CLI is at `%USERPROFILE%\.platformio\penv\Scripts\pio.exe`. The first build downloads the ESP8266 toolchain, which takes a few minutes.
2. `copy include\secrets.example.h include\secrets.h` and fill in WiFi. Never commit `secrets.h`.
3. **Hardware (optional):** install KiCad 10 (scripts expect `C:\Program Files\KiCad\10.0`). The generators run on KiCad's bundled Python (`C:\Program Files\KiCad\10.0\bin\python.exe`), which has `pcbnew` and numpy.
4. **Simulation (optional):** `cd hardware\sim`, then `py -3.12 -m venv .venv` and `.venv\Scripts\pip install numpy matplotlib`. Run `.venv\Scripts\python run_sim.py`. It drives KiCad's `ngspice.dll` through ctypes, so it needs KiCad 10 installed too.
5. **Case (optional):** `cd hardware\case`, then `py -3.12 -m venv .venv` and `.venv\Scripts\pip install cadquery`. See `CASE.md` for the scripts.
6. A USB-serial driver may be needed for the NodeMCU: CP210x from Silicon Labs, or CH340 depending on the board.

## Firmware

| Command | What |
|---|---|
| `pio run -e nodemcuv2` | NodeMCU + a cheap relay **module** (relays active LOW) |
| `pio run -e nodemcuv2-pcb` | NodeMCU on **this project's PCB** (relays active HIGH, `-DCLIMATE_PCB`) |
| `pio run -e esp32dev` | ESP32 DevKit (different pins, see `config.h`) |
| `pio run -e <env> -t upload` | Flash over USB. `pio run -e ota -t upload` flashes over WiFi (`climate.local`) |
| `pio device monitor` | Serial at 115200. Commands: `status`, `mode off/auto/manual`, `temp 23.5`, `hum 60` |
| `powershell -ExecutionPolicy Bypass -File tools\test-control.ps1 -Base http://<board-ip>` | Control-rule tests (32 checks) against a running board. Takes ~40 s, clicks relays, and leaves it in Off with default settings |

- **Pins:** Fan D0 (GPIO16), Heater D7 (GPIO13), Humidifier D5 (GPIO14), Compressor D6 (GPIO12). I2C is SCL D1 (GPIO5) and SDA D2 (GPIO4), kept free for the sensor. **These must match `CHANNELS` in `hardware/gen/design.py`.** Change both together or not at all.
- Don't use D3/D4/D8 for outputs (boot strapping pins).
- The web page is `http://climate.local` or the board's IP. Its API is `GET /api/state`, plus `POST /api/settings`, `/api/sim` and `/api/manual` (documented at the top of `src/main.cpp` and in `README.md`).
- Control rules (bands, reheat while dehumidifying, fan run-on, compressor min off/on times, sensor-fault shutdown) live in `src/controller.cpp`. They are specified in `PLAN.md` section 2. If you change behaviour, update `PLAN.md` and the test list, and run `tools/test-control.ps1`.
- `Settings` is saved as a raw struct. **Bump `SETTINGS_VERSION` in `src/storage.cpp` whenever `Settings` changes**, otherwise old flash data is misread.
- Always run `pio run -e nodemcuv2 -e nodemcuv2-pcb` (both must build) before committing firmware changes.

### Phase 2 notes (next job: real sensor)

- Use an SHT31-D at I2C address 0x44, at 100 kHz. Read every 2 s and average a few readings. Raise a sensor fault after 30 s with no valid reading. There is a `Reading` struct with a `valid` flag, and `Controller` already handles faults.
- Keep the simulated sensor selectable from the web page for testing (see the PLAN.md Phase 2 checklist).
- A library such as `adafruit/Adafruit SHT31 Library` works on both ESP8266 and ESP32. Add it via `lib_deps` in `platformio.ini`.

## Hardware (KiCad)

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
- **Mains safety rules are enforced by DRC.** Netclass `Mains` covers the `*_COM/_NO/_NC` nets. Mains to low voltage needs â‰¥ 3.0 mm clearance and â‰¥ 4.0 mm creepage; mains to mains â‰¥ 2.0 mm; mains to screw holes â‰¥ 3.0 mm. Currently measured: 3.70 / 4.83 / 2.78 / 5.12 mm. Routed U-slots around each relay's COM pin provide the creepage. Don't weaken these rules to make DRC pass.
- **Gotchas found the hard way:**
  - KiCad DRC silently ignores a condition like `!B.hasNetclass('Mains')`. Use `B.NetClass != 'Mains'`. To prove a rule is active, set it to an absurd value (20 mm) on a scratch copy and confirm DRC fails.
  - On the horizontal Phoenix MKDS terminal footprints, the wire entry is on the footprint's **+Y** face. This was checked in the STEP model; the terminals are rotated 180Â° so the entry faces the board edge.
  - KiCad 3D-model z-rotation is the opposite sign to what you'd expect. The socket models use `-90`.
  - In PowerShell, `$fab` and a `-Fab` switch are the same variable (case-insensitive).
  - Never put `\"` at the end of a native argument (`-o "dir\"`), because it escapes the quote. Use `dir/`.
  - Running downloaded executables (e.g. the Freerouting CLI) was blocked by the permission policy on the original machine. That's why routing is done by `router.py`.
- The NodeMCU footprint assumes a **v2 "Amica" board with 22.86 mm row spacing** (CP2102). The LoLin v3 (27.9 mm) does not fit.
- **The PCB's relays are active HIGH.** Flash `nodemcuv2-pcb`.

## Safety (keep these in docs and designs)

- Relay contacts can carry mains. 5 A max per channel on this PCB. The compressor (and any heater over ~1 kW) goes through a contactor. Heaters need an independent thermal cut-out. Mains wiring must be done by a competent person.
- The firmware must fail safe. On a sensor fault, in Off mode, before an OTA update and at boot, every load is off. Compressor protection (minimum off time, also after reboot) must stay.

## Working conventions

- Keep docs in plain, direct English. When behaviour changes, update `README.md`, `PLAN.md`, `hardware/README.md`, or `CASE.md`, whichever applies.
- Small, focused commits. Run the relevant checks first: firmware builds, `build.ps1`, `run_sim.py`, `fit_check.py`.
- Don't commit secrets, `.pio/`, `hardware/build/` or any `.venv/`.
- Licences: firmware, scripts and docs are MIT (`LICENSE`); everything in `hardware/` is CERN-OHL-P-2.0 (`hardware/LICENSE`). Don't add code or models with incompatible terms (e.g. copied without permission or under a non-commercial licence).

## Open questions for the project owner (from PLAN.md section 5)

1. Have the dehumidify reheat rule and the "too hot + too dry" behaviour been read correctly?
2. Should the unit start in Off after a power cut, instead of resuming the last mode?
3. Will the final unit stay on the ESP8266 or move to an ESP32?
