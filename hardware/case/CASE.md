# Climate-controller enclosure (3D-printed)

> **Status: Phase 1, on hold.** This case fits the ESP8266 relay carrier PCB in `hardware/`, which does not fit the current ESP32 Mainboard. A Controller enclosure (display and encoders on the front) is still to be designed. See PLAN.md Phase 5.

Two-part case (base tray + lid) for the 90 x 86 mm relay-controller board, modelled in CadQuery.
Every dimension is a parameter at the top of `case.py`. The fit was proved with real boolean
intersections against the KiCad STEP of the populated board (`../build/fab/climate-controller.step`).
That STEP is generated, not stored in git: run `powershell -ExecutionPolicy Bypass -File hardware\build.ps1 -Fab` once before `fit_check.py`. `fit_check.py` also regenerates `assembly.step` (git-ignored, ~13 MB).

## Overall size

| | |
|---|---|
| Outer footprint | **100.0 x 100.0 mm**, vertical corners R4 |
| Total height (base + lid) | **29.5 mm** (base 27.5 + lid 2.0; lid screws are countersunk flush) |
| Walls / floor / lid | 2.0 / 2.0 / 2.0 mm |
| Outside the box | Gland domes stick out: M16 about 18 mm from the top wall, M12 about 15 mm from the left and right walls. The USB plug sticks out of the right wall. |

### Coordinate frame (used in the scripts and in `assembly.step`)
X = board x (0 = left edge). Y = -board y (0 = board top edge; +Y points at the top wall). Z = height above the case's outer bottom face.
STEP -> assembly: X = Xs - 50, Y = Ys + 50, Z = Zs + 7.0. The fit check confirms this frame from the STEP itself: PCB bbox x 50..140, y -136..-50, z 0..1.51. KiCad exports only the 1.51 mm dielectric; the parts sit on z = 1.6.

### Board position in the case
| Gap | Value |
|---|---|
| PCB bottom -> floor top | 5.0 mm (lowest lead tip is 3.1 mm above the floor) |
| PCB left edge -> left wall | 5.0 mm (J1 wire openings -> wall 5.7 mm) |
| PCB right edge -> right wall | 1.0 mm (the micro-USB socket's 0.6 mm overhang sits inside the USB opening) |
| PCB top edge -> top wall | 8.0 mm (**terminal openings -> top wall 8.7 mm**) |
| PCB bottom edge -> bottom wall | 2.0 mm |
| Board top -> lid underside | 18.9 mm (relays 15.6 mm high -> 3.3 mm clear) |

## Openings: where they are and why

| Opening | Wall | Position (board coords / height) | Why there |
|---|---|---|---|
| M16 gland A, 16.4 mm hole | top | board x 25.0, centre 14.75 above case bottom | Mains cables for K1/K2 (J2, J3). The gland axis points straight at the terminal openings, which face the top wall. The locknut (22 AC x 5) and thread (6 mm inside) fit in the 8 mm top gap. Clearances: 1.75 mm to the floor, 1.0 mm to the lid, 2.0 mm thread -> PCB edge. |
| M16 gland B, 16.4 mm hole | top | board x 65.0, same height | Mains cables for K3/K4 (J4, J5). Same as A. |
| M12 gland "5 V in", 12.4 mm hole | left | board y 46.0, centre 18.2 (9.6 above board top) | J1 is on the left edge and its openings face the left wall, so the 5 V cable must come in through the left wall. Only the low-voltage stretch between the relays (y < 33.3) and J1 (y 60.4) has room for a nut. The nut is placed above the board top (1.19 mm clear), because the 5 mm left gap cannot take a 5 mm nut beside the board. The wires run about 20 mm down the left gap into J1. |
| M12 gland "sensor", 12.4 mm hole | right | board y 44.0, centre 18.2 | The bottom wall cannot take a gland: it is 2 mm from the board, and J6, J7, the bottom mounting screw and the NodeMCU block any nut position above the board. The left wall's low-voltage stretch already holds the 5 V gland. The right edge between the K4 standoff (y 27) and the NodeMCU (y 59) is clear. The nut overhangs the board edge 1.19 mm above it. **The sensor cable runs about 85 mm across the low-voltage area** (between the relay row and the NodeMCU, over parts at most 9 mm high, about 10 mm under the lid) to J6. |
| USB opening 13.5 x 9.0 mm, corner R1.5 | right | centred on the socket: board y 71.9, z 20.1 (11.5 above board top) | It is a notch from the wall top down to the slot bottom (no bridge to print). A tab on the lid closes the notch above the slot. A 12 x 7 mm plug body has 0.75 / 1.0 mm clearance and a straight insertion path (checked with a 40 mm sweep). |
| Vents | bottom wall | 10 slots 1.8 x 10 mm, x 46..86, z 11..21, 45° pointed tops | Low-voltage half only (below the NodeMCU). |
| Vents | lid | 8 slots 1.6 x 18 mm over the NodeMCU, board x 50..78, y 63..81 | Low-voltage half only. |
| LED windows | lid | 5 x Ø5 pockets from the inside, leaving a 0.6 mm skin, over D6-D9 (y 43.5) and D10 (power) | The lid stays closed above the relay area. Set `LED_WINDOW = "hole"` for open Ø2 holes. |
| Wall mounting | floor | 2 x Ø4.5 holes with a countersink from inside (for 4 mm countersunk screws, head ≤ 8.5 mm), on Ø12 x 1.5 pads, at board (18, 52) and (72, 52) | In the low-voltage area, so the screw heads are 3.1 mm below the low-voltage lead tips, not the mains leads. |
| "DANGER 230V" | lid top | debossed 0.6 mm, 8 mm bold, over the relays | |

## Fixing scheme
- **PCB:** 4 x M3 male-female hex standoffs (5.5 AF, 18 mm body + 6 mm male thread). They screw through the PCB mounting holes into heat-set inserts in 4 floor bosses. A boss is Ø6.4 (the 3.2 mm keep-out radius) with a Ø10.4 foot that rises at 45° to z 4.0, below the lead tips.
- **Lid:** 6 x M3 x 8 countersunk screws. 4 go into the tops of the standoffs: the lid has 0.7 mm pads that stop 0.2 mm above the standoff tops. 2 go into full-height corner columns (Ø7) with inserts in the two **top** corners, which are on the mains side.
  Why not 4 corner bosses: the bottom gap is 2 mm and the right gap is 1 mm, so there is no room for an insert boss at the bottom or right corners without cutting the PCB. The standoffs also hold the middle of the lid.
- A 1.2 x 2.0 mm locating lip runs inside the walls with a 0.3 mm gap. It is cut back 1 mm around the gland nuts, the standoffs and the corner columns.
- `INSERT_MODE = "selftap"` changes all 6 insert holes to Ø2.5 pilots: the standoffs' male M3 threads and the corner screws then cut their own thread.

## Hardware list
| Qty | Part |
|---|---|
| 6 | M3 heat-set insert, M3 x 5.7 mm (hole Ø4.1, depth 6.2 / 7.0). Alternative: self-tapping, see above |
| 4 | M3 male-female hex standoff, **nylon PA66** (it sits in the mains area), 5.5 mm AF, 18 mm body, 6 mm male thread, female thread ≥ 5.5 mm deep |
| 6 | M3 x 8 countersunk, ISO 10642 / DIN 7991, A2 stainless (lid) |
| 2 | M16 x 1.5 **nylon** cable gland, IP68, with locknut ≤ 22 mm AC x 5 mm, thread length ≤ 8 mm (cable OD about 4.5-10 mm) |
| 2 | M12 x 1.5 nylon cable gland, IP68, with locknut ≤ 17 mm AC x 5 mm, thread length ≤ 8 mm (cable OD about 3-6.5 mm) |
| 2 | 4 mm countersunk wood/plug screws, head ≤ 8.5 mm (wall mounting, optional) |
| - | Ferrules for the mains conductors; cable ties |

## Printing
- **Material:** PETG or ASA. 4 perimeters (a solid 2 mm wall), 5 top and 5 bottom layers, 25-30 % gyroid infill, 0.2 mm layers. No supports.
- **Base:** floor down, as exported.
- **Lid:** top face down. `case_lid.stl` is already flipped: lip, tab and pads point up, and Y is mirrored relative to the assembly. Use a light or natural colour if you want the LEDs to show through the 0.6 mm windows.
- **Overhangs** (`printability.py`, exact B-rep normals, print orientation): nothing is steeper than 45° except these deliberate short bridges:
  - base: the flat tops of the truncated-teardrop gland holes. These are 3.8 mm wide (M16) and 2.1 mm wide (M12), and the gland washers cover them.
  - lid: the floors of the debossed letters (stroke width about 1-1.5 mm).
  Countersinks and boss feet are exactly 45°.
- **Mains safety:** PETG and ASA are not flame-retardant. Mains-switching relays should be in a **UL94 V-0** material: a flame-retardant PC or ABS filament, or a commercial ABS/PC box. Treat this printed case as a prototype or for indoor dry use. Only nylon glands and standoffs touch the mains area. The vents are only in the low-voltage half. The lid needs a tool to open.
- Heat-set inserts: soldering iron at about 230-245 °C for PETG (about 250 °C for ASA). Press them in square and flush.

## Assembly
1. Fit the 6 inserts. Fit the glands: M16 in the top wall, M12 in the left and right walls. Tighten the locknuts inside; any nut rotation is fine, because the check models each nut as its across-corners cylinder.
2. (Wall mount) Screw the base to the wall now. The screw heads end up under the PCB.
3. Pass the cables through the glands. The 5 V pair goes through the left M12 and the sensor cable through the right M12. Crimp the JST-XH contacts after threading the cable. The mains cables go through the two M16 glands.
4. Connect the 5 V wires to J1 **before** you seat the board, and leave a little slack. The openings are only 5.7 mm from the wall: use flexible ≤ 0.75 mm² wire with ferrules.
5. Seat the board on the bosses. Screw the 4 nylon standoffs through the mounting holes into the inserts, finger-tight plus a little.
6. Insert the mains wires into J2-J5 (the screws are on top). There is 8.7 mm between the wire openings and the top wall. Plug the sensor into J6 and route its cable over the low-voltage area to the right wall. Tie it down away from the relays.
7. Tighten the gland domes.
8. Put the lid on. The tab drops into the USB notch and the lip locates inside the walls. Fit 6 x M3 x 8 countersunk screws.
9. The USB cable plugs in from the right with the lid on.

## Fit-check results (`fit_check.py`, full output in `fit_check_results.json`)
1051 solid pairs checked: the base, lid, gland nuts and threads, and standoffs against all 50 STEP solids (PCB + 46 parts by reference; some parts have 2 solids), the 4 NodeMCU solids, the USB plug and keep-outs. Each pair is a real `BRepAlgoAPI_Common` volume when the bounding boxes overlap. The check is sensitive: an earlier version found a **0.06 mm³** overlap between the lid lip and the K4 standoff, which was fixed.

| Intersection | Volume (mm³) |
|---|---|
| base x board, parts, NodeMCU, USB plug, keep-outs | **0.0** |
| lid x board, parts, NodeMCU, USB plug, keep-outs | **0.0** |
| base x lid | **0.0** |
| gland locknuts + threads x board, plug, lid, base, standoffs | **0.0** |
| gland outside bodies x base and lid | **0.0** |
| PCB standoffs x board parts (incl. PCB), lid, base | **0.0** |
| USB plug straight insertion path (40 mm sweep) x base and lid | **0.0** |
| NodeMCU solids x STEP parts (information only) | 0.0 |
| **Outer dims** | **100.0 x 100.0 x 29.5 mm (limit 100 x 100 x 30) - PASS** |

| Minimum gap | mm |
|---|---|
| PCB edge -> left / right / top / bottom wall (measured) | 4.99 / 1.00 / 7.99 / 1.99 |
| Terminal block openings (J2-J5) -> top wall | **8.70** |
| J1 openings -> left wall | 5.70 |
| Tallest part (K1-K4 relays, 15.6 above board) -> lid underside | **3.31** |
| Lid (incl. lip, pads, USB tab) -> nearest part | 2.66 (K1/K4 under the standoff pads) |
| NodeMCU micro-USB socket -> lid tab | 3.16 |
| USB plug -> base / lid | 0.60 / 1.00 (plug face = socket face) |
| M16 locknut -> PCB / floor / lid | 3.00 / 1.75 / 1.00 |
| M16 thread -> PCB edge | 2.00 |
| M12 locknut -> PCB top / lid | 1.19 / 0.80 |
| M12 thread -> PCB | 3.69 |
| Standoff hex -> nearest part | 0.63 (K1, K4), 0.98 (J6), 0.83 (NodeMCU PCB) |
| Nearest part -> base (excl. PCB/sockets) | 1.20 (NodeMCU PCB -> bottom wall) |
| Estimated mated JST-XH plug on J6 -> lid | 6.11 |
| Lowest lead tip -> floor | 3.10 |

## Compromises and assumptions
- **The M12 locknut size is assumed** to be 17 mm AC x 5 mm, with an 8 mm thread. The M16 values come from the brief. Check the glands you buy: a larger M12 nut reduces the 0.8 mm clearance to the lid.
- **NodeMCU:** added as the boxes from the brief, plus a conservative 3.5 mm envelope for the buttons and USB-UART chip between the ESP-12 and the USB socket. These are not from a real model.
- **J6 mated plug** is an estimated envelope (11 mm above the board).
- The **sensor cable crosses the board** (about 85 mm) because there is no better wall position (see above). The 5 V wires need a tight bend in the 5.7 mm left gap.
- **Lid fixing uses PCB standoffs plus 2 corner columns**, not 4 corner bosses, because there is no room at the bottom and right corners.
- Glands, wall screws and the USB plug stick out beyond the 100 x 100 footprint. The 100 x 100 x 29.5 envelope is the printed case.
- `render_*.png` are matplotlib renders, so a few faces sort wrongly in the 3D views. The 2D sections are exact (thin-slab booleans).

## Files
| File | What |
|---|---|
| `case.py` | Parametric model. `python case.py` writes `case_base.step/.stl` (assembly frame, print-ready) and `case_lid.step/.stl` (print orientation) |
| `fit_check.py` | Interference and gap check, writes `assembly.step` and `fit_check_results.json`; exit code 0 = pass |
| `printability.py` | Overhang check in print orientation, writes `printability_results.json` |
| `render.py` | PNG views: `render_exploded_iso.png`, `render_assembled_iso.png`, `render_top_lid_hidden.png`, `render_iso_left_lid_hidden.png`, `render_section_usb.png`, `render_section_m12_5v.png`, `render_section_m16.png` |
| `assembly.step` | Case + board + NodeMCU + standoffs + glands + USB plug, lid in place |

Rebuild everything with `.venv\Scripts\python.exe case.py; .venv\Scripts\python.exe fit_check.py; .venv\Scripts\python.exe printability.py; .venv\Scripts\python.exe render.py`. The venv is CadQuery 2.8.0 on Python 3.12.
