"""Single source of truth for the climate controller carrier board.

Everything the schematic and PCB generators need lives here:
parts, values, footprints, connections (net per pin) and board placement.
Coordinates for the PCB are in mm, relative to the board's top-left corner.
"""

PROJECT = "climate-controller"
TITLE = "Climate Controller - Relay Carrier"
REV = "1.0"
DATE = "2026-11-13"

BOARD_W = 90.0
BOARD_H = 86.0

# Horizontal Phoenix MKDS terminal footprints in KiCad: the wire entry faces
# local +Y (checked in the MKDS STEP model: the openings are on the +Y face).
TERM_ENTRY_LOCAL_Y = +1

# ---------------------------------------------------------------------------
# Relay channels: physical order on the board, left to right.
# The order follows the NodeMCU pin order so the control traces don't cross.
# gpio_pin = NodeMCU footprint pin number (see NODEMCU_PINS).
# ---------------------------------------------------------------------------
CHANNELS = [
    # n, tag,   label on silkscreen, NodeMCU pin, GPIO name, firmware role
    (1, "FAN", "FAN", 16, "D0", "fan"),
    (2, "HUM", "HUMIDIFIER", 23, "D5", "humidifier"),
    (3, "COMP", "COMPRESSOR", 24, "D6", "compressor"),
    (4, "HEAT", "HEATER", 25, "D7", "heater"),
]
CH_X = [15.0, 35.0, 55.0, 75.0]   # channel centre lines
RELAY_COM_Y = 32.0                # relay COM pin
TERM_Y = 5.3                      # relay output terminal pin row

# NodeMCU v2 (Amica, 0.9" row spacing) pin names. Pins 1-15 are the A0..VIN
# row, 16-30 the D0..3V3 row. On the board the USB end faces the right edge,
# the D0..3V3 row is the upper row and pin 1/16 are at the antenna (left) end.
NODEMCU_PINS = {
    1: "A0", 2: "RSV", 3: "RSV", 4: "SD3", 5: "SD2", 6: "SD1", 7: "CMD", 8: "SD0",
    9: "CLK", 10: "GND", 11: "3V3", 12: "EN", 13: "RST", 14: "GND", 15: "VIN",
    16: "D0", 17: "D1", 18: "D2", 19: "D3", 20: "D4", 21: "3V3", 22: "GND", 23: "D5",
    24: "D6", 25: "D7", 26: "D8", 27: "RX", 28: "TX", 29: "GND", 30: "3V3",
}
NODEMCU_POS = (65.65, 71.93)      # centre of the pin field
NODEMCU_ROW_SPACING = 22.86
NODEMCU_OUTLINE = (48.3, 25.4)    # board size, assumed centred on the pin field

# ---------------------------------------------------------------------------
# Footprints
# ---------------------------------------------------------------------------
FP_R = "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal"
FP_D_SIG = "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal"
FP_D_PWR = "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal"
FP_LED = "LED_THT:LED_D3.0mm"
FP_Q = "Package_TO_SOT_THT:TO-92_Inline_Wide"
FP_RELAY = "Relay_THT:Relay_SPDT_SANYOU_SRD_Series_Form_C"
FP_TERM2 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
FP_TERM3 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal"
FP_JST4 = "Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical"
FP_HDR4 = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
FP_CP = "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm"
FP_C = "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P5.00mm"
FP_PTC = "Fuse:Fuse_Bourns_MF-RHT100"
FP_NODEMCU = "climate:NodeMCU_v2_Socket"
FP_HOLE = "MountingHole:MountingHole_3.2mm_M3"

# ---------------------------------------------------------------------------
# Parts: ref -> dict(lib_id, value, footprint, pins={pin: net}, pos=(x, y, rot))
# Unlisted symbol pins are marked no-connect in the schematic.
# ---------------------------------------------------------------------------
PARTS = {}


def part(ref, lib_id, value, footprint, pins, pos, block, **extra):
    PARTS[ref] = dict(lib_id=lib_id, value=value, footprint=footprint, pins=pins,
                      pos=pos, block=block, **extra)


# Terminal pin order depends on which way the footprint is turned.
_t_flip = TERM_ENTRY_LOCAL_Y > 0          # rotate 180 if entry is local +Y
TERM_ROT = 180 if _t_flip else 0
# Pins left->right on the board after rotation
_TERM_LEFT_TO_RIGHT = ["3", "2", "1"] if _t_flip else ["1", "2", "3"]
J1_ROT = 270 if _t_flip else 90

for i, (n, tag, label, gpio_pin, gpio, role) in enumerate(CHANNELS):
    cx = CH_X[i]
    com, no, nc = f"{tag}_COM", f"{tag}_NO", f"{tag}_NC"
    ctrl, base, coil, led = f"{tag}_CTRL", f"{tag}_BASE", f"{tag}_COIL", f"{tag}_LED"
    # Relay K: pin1 COM, 2 & 5 coil, 3 NO, 4 NC. Rotated 90: NC left, NO right.
    part(f"K{n}", "Relay:SANYOU_SRD_Form_C", "SRD-05VDC-SL-C", FP_RELAY,
         {"1": com, "2": coil, "3": no, "4": nc, "5": "+5V"}, (cx, RELAY_COM_Y, 90), f"ch{n}",
         descr=f"{label} relay")
    left, mid, right = _TERM_LEFT_TO_RIGHT
    part(f"J{n + 1}", "Connector:Screw_Terminal_01x03", "Phoenix MKDS 1,5/3-5,08", FP_TERM3,
         {left: nc, mid: com, right: no},
         ((cx + 5.08) if _t_flip else (cx - 5.08), TERM_Y, TERM_ROT), f"ch{n}")
    part(f"Q{n}", "Transistor_BJT:BC337", "BC337-40", FP_Q,
         {"1": coil, "2": base, "3": "GND"}, (cx + 1.27, 49.0, 0), f"ch{n}")
    part(f"D{n}", "Diode:1N4148", "1N4148", FP_D_SIG,
         {"1": "+5V", "2": coil}, (cx - 3.81, 39.0, 0), f"ch{n}")
    part(f"D{n + 5}", "Device:LED", "Red", FP_LED,
         {"1": led, "2": "+5V"}, (cx - 3.0, 43.5, 180), f"ch{n}")
    part(f"R{n}", "Device:R", "1k", FP_R, {"1": ctrl, "2": base}, (cx - 8.4, 53.5, 0), f"ch{n}")
    part(f"R{n + 4}", "Device:R", "4.7k", FP_R, {"1": base, "2": "GND"}, (cx + 1.6, 53.5, 0), f"ch{n}")
    part(f"R{n + 8}", "Device:R", "1k", FP_R, {"1": led, "2": coil}, (cx - 0.6, 43.5, 0), f"ch{n}")

# NodeMCU
nodemcu_pins = {}
for p in range(1, 31):
    nodemcu_pins[str(p)] = None
for n, tag, label, gpio_pin, gpio, role in CHANNELS:
    nodemcu_pins[str(gpio_pin)] = f"{tag}_CTRL"
nodemcu_pins.update({"17": "I2C_SCL", "18": "I2C_SDA", "21": "+3V3", "15": "+5V",
                     "10": "GND", "14": "GND", "22": "GND", "29": "GND"})
part("U1", "climate:NodeMCU_v2", "NodeMCU v2 (ESP-12E/F)", FP_NODEMCU,
     {k: v for k, v in nodemcu_pins.items() if v}, (*NODEMCU_POS, 0), "mcu")

# Power input
part("J1", "Connector:Screw_Terminal_01x02", "Phoenix MKDS 1,5/2-5,08", FP_TERM2,
     {"1": "VIN_RAW", "2": "GND"}, (5.3, 62.92, J1_ROT) if _t_flip else (6.0, 68.0, J1_ROT), "power")
part("F1", "Device:Polyfuse", "MF-RHT100 (1 A hold)", FP_PTC,
     {"1": "VIN_RAW", "2": "VIN_FUSED"}, (15.0, 58.6, 0), "power")
part("D5", "Diode:1N5819", "1N5819", FP_D_PWR,
     {"1": "+5V", "2": "VIN_FUSED"}, (23.16, 64.5, 180), "power")
part("C1", "Device:C_Polarized", "470uF 10V", FP_CP, {"1": "+5V", "2": "GND"}, (28.5, 60.5, 0), "power")
part("C2", "Device:C", "100nF", FP_C, {"1": "+5V", "2": "GND"}, (28.5, 67.0, 0), "power")
part("R13", "Device:R", "1k", FP_R, {"1": "+5V", "2": "PWR_LED"}, (12.5, 70.5, 0), "power")
part("D10", "Device:LED", "Green", FP_LED, {"1": "GND", "2": "PWR_LED"}, (25.04, 70.5, 180), "power")

# Sensor
part("R14", "Device:R", "4.7k", FP_R, {"1": "+3V3", "2": "I2C_SCL"}, (12.5, 75.0, 0), "sensor")
part("R15", "Device:R", "4.7k", FP_R, {"1": "+3V3", "2": "I2C_SDA"}, (23.0, 75.0, 0), "sensor")
part("C3", "Device:C", "100nF", FP_C, {"1": "+3V3", "2": "GND"}, (29.5, 78.3, 0), "sensor")
part("J6", "Connector_Generic:Conn_01x04", "JST B4B-XH-A (SHT31-D)", FP_JST4,
     {"1": "+3V3", "2": "GND", "3": "I2C_SCL", "4": "I2C_SDA"}, (9.8, 81.5, 0), "sensor")
part("J7", "Connector_Generic:Conn_01x04", "Pin header 1x4 (I2C)", FP_HDR4,
     {"1": "+3V3", "2": "GND", "3": "I2C_SCL", "4": "I2C_SDA"}, (24.0, 82.0, 90), "sensor")

# Mounting holes (board only, not in the schematic)
HOLES = [(3.5, 24.0), (86.5, 24.0), (3.2, 82.8), (37.5, 83.0)]

# ---------------------------------------------------------------------------
# Net classes (also written to the .kicad_pro)
# ---------------------------------------------------------------------------
MAINS_NETS = [f"{c[1]}_{s}" for c in CHANNELS for s in ("COM", "NO", "NC")]
POWER_NETS = ["+5V", "GND", "VIN_RAW", "VIN_FUSED"]
COIL_NETS = [f"{c[1]}_COIL" for c in CHANNELS]

# Track widths (mm) used by the router / manual routes
WIDTH = {"mains": 2.0, "+5V": 1.0, "GND": 0.8, "VIN_RAW": 1.0, "VIN_FUSED": 1.0,
         "coil": 0.6, "+3V3": 0.5, "signal": 0.35}


def width_for(net):
    if net in MAINS_NETS:
        return WIDTH["mains"]
    if net in WIDTH:
        return WIDTH[net]
    if net in COIL_NETS:
        return WIDTH["coil"]
    return WIDTH["signal"]


def nets():
    """net -> list of (ref, pin)."""
    out = {}
    for ref, p in PARTS.items():
        for pin, net in p["pins"].items():
            out.setdefault(net, []).append((ref, pin))
    return out
