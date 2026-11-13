# Climate Controller â€“ Relay Carrier PCB

A 2-layer, 90 Ã— 86 mm through-hole carrier board for the climate controller. It has:

- 4 Ã— SRD-05VDC-SL-C relays: fan, humidifier, compressor and heater.
- A plug-in NodeMCU v2 (ESP8266), so you keep USB programming and the existing firmware pins.
- A JST connector for the SHT31-D sensor.
- 5 V DC input with a resettable fuse and reverse-polarity protection.

Everything here is generated from **`gen/design.py`**: parts, values, connections and placement. Change the design there and rebuild. Don't hand-edit the `.kicad_sch` / `.kicad_pcb` and then rebuild, because the rebuild overwrites them. You can still open and inspect them in KiCad 10.

| File | What it is |
|---|---|
| `climate-controller.kicad_pro/.kicad_sch/.kicad_pcb` | The KiCad 10 project. Open the `.kicad_pro` in KiCad |
| `climate-controller.kicad_dru` | Custom DRC rules: mains clearance and creepage |
| `lib/` | Project symbol and footprint for the NodeMCU, plus a simple 3D model |
| `gen/` | Generator: `design.py` (single source), `make_sch.py`, `make_pcb.py`, `router.py`, `make_pro.py` |
| `build.ps1` | Rebuilds everything and runs ERC/DRC. `-Fab` also writes manufacturing files |
| `sim/` | SPICE simulations (ngspice): `SIM_REPORT.md`, plots, `run_sim.py` |
| `case/` | 3D-printable enclosure (CadQuery): see `case/CASE.md` |
| `build/` | Generated: renders, ERC/DRC reports, `fab/` (Gerbers, drill, BOM, PDFs, STEP). Not in git |

## Rebuild and check

```
powershell -ExecutionPolicy Bypass -File hardware\build.ps1 -Fab
```

This takes about 1 minute and needs KiCad 10 in `C:\Program Files\KiCad\10.0`. It writes the schematic, runs ERC, places and routes the PCB, pours ground, runs DRC with the schematic-parity check, renders images, and exports the manufacturing files.

Results of the current design:

| Check | Result |
|---|---|
| ERC | 0 errors, 0 warnings |
| DRC | 0 errors, 0 unconnected items, 0 schematic/PCB differences. The 91 warnings are silkscreen cosmetics, such as text overlapping outlines |
| Mains â†’ low-voltage clearance (rule â‰¥ 3.0 mm) | **3.70 mm** minimum |
| Mains â†’ low-voltage creepage (rule â‰¥ 4.0 mm) | **4.83 mm** minimum, using routed slots around each relay's COM pin |
| Mains â†’ mains, between COM/NO/NC (rule â‰¥ 2.0 mm) | 2.78 mm minimum. This is set by the 5.08 mm terminal pitch |
| Mains â†’ mounting screws (rule â‰¥ 3.0 mm) | 5.12 mm minimum |

Each minimum was measured with KiCad's DRC engine. I also checked that the rules really are enforced: setting them to 20 mm on a scratch copy produced hundreds of violations. KiCad silently ignores a rule condition written as `!B.hasNetclass('Mains')`, so `gen/make_pro.py` uses `B.NetClass != 'Mains'`.

## Circuit

- **Relay driver (Ã—4):** GPIO â†’ 1 kÎ© â†’ BC337-40, with 4.7 kÎ© base-to-emitter so the relay stays off while the ESP8266 boots. The coil runs from +5 V with a 1N4148 flyback diode. A red LED + 1 kÎ© across the coil shows when the relay is on. **The relays are active HIGH**, so build the firmware with `pio run -e nodemcuv2-pcb`. That sets `RELAY_ACTIVE_LOW = false`.
- **Channels, left to right:** 1 FAN (D0), 2 HUMIDIFIER (D5), 3 COMPRESSOR (D6), 4 HEATER (D7). These match the firmware pins. The order follows the NodeMCU pin order so the traces don't cross.
- **Outputs:** each relay has a 3-way screw terminal, NC / COM / NO from left to right.
- **Power:** J1 5 V DC â†’ F1 PTC fuse â†’ D5 1N5819 (reverse protection) â†’ +5V â†’ relays and NodeMCU VIN. **Use a 5.1â€“5.25 V, â‰¥ 1 A supply.** The fuse and diode drop about 0.45 V, and the NodeMCU's 3.3 V regulator needs about 4.4 V in. The simulation shows a bare 5.00 V supply leaves only 70 mV of headroom on the regulator input.
- **Sensor:** J6 (JST-XH 4-pin) is wired 3V3, GND, SCL, SDA, matching most SHT31-D breakouts. R14/R15 are 4.7 kÎ© pull-ups. J7 is a spare I2C header. Run I2C at 100 kHz.
- **USB:** with the NodeMCU on USB and no 5 V supply, the relays still work, powered through the NodeMCU's own diode. D5 stops that power flowing back into J1. With all 4 relays on, peaks reach about 0.57 A, which is over a USB 2.0 port's 500 mA. Use the 5 V supply for anything more than a quick test.

## Simulation summary (`sim/SIM_REPORT.md`)

These were run in ngspice with manufacturer SPICE models. A coil inductance of 50â€“500 mH was swept, and the results don't depend on it.

| Check | Result |
|---|---|
| GPIO current | 2.4 mA (limit 12 mA) |
| Transistor Vce(sat) | 55 mV worst case |
| Coil voltage at 4.5 V supply | 4.45 V (must-operate 3.75 V) |
| Turn-off spike | 5.8 V with the flyback diode (about 50 V and avalanche without it) |
| Relay held off during boot | Yes, with the 4.7 kÎ© pull-downs, even with a 30 kÎ© internal pull-up enabled (10 kÎ© failed that case) |
| +5 V rail at 5.0 V input | â‰¥ 4.47 V (typical diode). With a 4.75 V input the 3.3 V regulator is short of headroom, hence the 5.1â€“5.25 V supply |
| I2C rise time | 0.4â€“0.8 Âµs at 100â€“200 pF (passes 100 kHz). For a long sensor cable (â‰ˆ400 pF), fit 2.2 kÎ© pull-ups |
| Relay contact traces | 2 mm on both layers: about 5 Â°C rise at 5 A, 16 Â°C at 8 A. **This board is rated 5 A per channel** |

## Ordering the PCB

Upload `build/fab/climate-controller-gerbers.zip` to any PCB maker (for example JLCPCB, PCBWay or Aisler) with these settings:

- 2 layers, FR4, 1.6 mm, 1 oz copper (2 oz is optional), HASL or ENIG, any colour.
- **Board outline includes routed slots.** Four U-shaped 1 mm slots around the relay COM pins are on the Edge.Cuts layer. Most makers mill these at no extra cost; check that they appear in the maker's Gerber preview.

## Parts (BOM)

The full BOM is in `build/fab/climate-controller-bom.csv`.

| Refs | Qty | Part | Notes |
|---|---|---|---|
| K1â€“K4 | 4 | Songle SRD-05VDC-SL-C | 5 V coil, 10 A contacts. **5 A max on this board** |
| Q1â€“Q4 | 4 | BC337-40, TO-92 | Pinout C-B-E |
| D1â€“D4 | 4 | 1N4148 | Flyback, cathode band to +5V |
| D5 | 1 | 1N5819 | Reverse protection |
| D6â€“D9 / D10 | 4 / 1 | 3 mm LED, red / green | Relay on / power |
| R1â€“R4, R9â€“R13 | 9 | 1 kÎ© Â¼ W | |
| R5â€“R8, R14, R15 | 6 | 4.7 kÎ© Â¼ W | |
| C1 | 1 | 470 ÂµF 10 V electrolytic, 8 mm, 3.5 mm pitch | |
| C2, C3 | 2 | 100 nF ceramic, 5 mm pitch | |
| F1 | 1 | Bourns MF-RHT100 PTC (about 1 A hold) | Check the hold current on the datasheet before ordering. Any radial PTC of about 1 A hold, â‰¥ 6 V, with 5.1 mm pitch fits |
| J1 | 1 | Phoenix MKDS 1,5/2-5,08 (or any 5.08 mm 2-way screw terminal) | |
| J2â€“J5 | 4 | Phoenix MKDS 1,5/3-5,08 (or any 5.08 mm 3-way screw terminal) | Wire entry faces the board edge |
| J6 | 1 | JST B4B-XH-A + housing XHP-4 + crimps | Sensor cable |
| J7 | 1 | 1Ã—4 2.54 mm pin header | Optional |
| U1 | 2 | 1Ã—15 2.54 mm female header | The NodeMCU v2 plugs in here |
| â€“ | 4 | M3 screws | Mounting |

## Assembly

1. **Check your NodeMCU first.** This board is for the v2 "Amica" (CP2102 USB chip) with **22.86 mm (0.9 in) between the pin rows**. The wider "LoLin v3" (27.9 mm) will not fit.
2. Solder the lowest parts first: resistors, diodes, then LEDs and transistors (flat face as on the silkscreen), C2/C3, the sockets, C1, F1, the terminals and JST connector, and finally the relays.
3. **Bring-up, without the NodeMCU:**
   - Apply 5.1 V to J1. The green LED should light.
   - Check about 4.6â€“4.7 V between the +5V and GND pins of the sockets (U1 pin 15 VIN and pin 14 GND).
   - Touch a 1 kÎ© resistor from 3.3 V to each relay's base resistor (R1â€“R4, GPIO side). The relay should click and its red LED light.
4. Plug in the NodeMCU with the USB end at the board edge. Flash with `pio run -e nodemcuv2-pcb -t upload`.
5. Test each relay in the web page's **Manual** mode before connecting any load.

## Safety

- The relay contact area (top of the board, "DANGER MAINS") can be at mains voltage. Mains wiring must be done by a competent person, in an earthed or double-insulated enclosure, with suitable fusing on each load.
- 5 A per channel. Drive the **compressor through a contactor** (AC-3 rated), and do the same for any heater over about 1 kW. Fit the heater's own thermal cut-out.
- A 3D-printed case is fine for development. For a permanent mains installation, use a flame-retardant (UL94 V-0) material or a commercial enclosure.

## License

The hardware design in this folder is licensed under the [CERN Open Hardware Licence Version 2 – Permissive](LICENSE) (CERN-OHL-P-2.0). Copyright (c) 2026 Josh-Dell-Marketing and contributors.

Third-party material used in the design keeps its own terms:
- Symbols, footprints and 3D models from the KiCad libraries (embedded in the `.kicad_sch` / `.kicad_pcb` and referenced by the STEP export) are from the KiCad Libraries Team, under CC-BY-SA 4.0 with an exception that allows them to be used in designs under any licence.
- The SPICE models in `sim/models/` come from the manufacturers' published models (NXP/Nexperia BC337-40, onsemi 1N4148 and 1N5819), as noted in each file. They are included for simulation only.
