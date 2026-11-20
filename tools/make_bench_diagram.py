"""Writes docs/bench-wiring.svg: breadboard wiring for bench-testing the Mainboard
and the Controller. Run: python tools/make_bench_diagram.py

Pins here must match src/mainboard/config.h and src/controller/config.h.
"""
from pathlib import Path

W, H = 1600, 1120
out = []

C = {
    "5V": "#d62728", "3V3M": "#ff7f0e", "3V3C": "#e8a33d", "GND": "#333333",
    "sda": "#1f77b4", "scl": "#e6b800", "relay": "#2ca02c", "pwm": "#9467bd",
    "tach": "#8c564b", "link_tx": "#17becf", "link_rx": "#e377c2", "enc": "#2ca02c",
    "board": "#2b4c7e", "board2": "#3d6b3d", "mod": "#f2f2f2", "text": "#222222",
}


def add(s):
    out.append(s)


def text(x, y, s, size=13, anchor="start", weight="normal", color=None, italic=False):
    st = ' font-style="italic"' if italic else ""
    add(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" '
        f'fill="{color or C["text"]}"{st}>{s}</text>')


def rect(x, y, w, h, fill, stroke="#555", rx=6, sw=1.5):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def wire(points, color, width=3):
    d = " ".join(f"{x},{y}" for x, y in points)
    add(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
        f'stroke-linejoin="round" stroke-linecap="round"/>')
    for x, y in (points[0], points[-1]):
        add(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')


def tag(x, y, label, color, side="left", stub=22):
    """Power/jump label: a short stub from a pin with a coloured pill at its end."""
    w = 9 + 7.4 * len(label)
    if side == "left":
        x2 = x - stub
        wire([(x, y), (x2, y)], color)
        bx = x2 - w
    elif side == "right":
        x2 = x + stub
        wire([(x, y), (x2, y)], color)
        bx = x2
    elif side == "down":
        wire([(x, y), (x, y + stub)], color)
        bx, y = x - w / 2, y + stub + 9
    else:  # up
        wire([(x, y), (x, y - stub)], color)
        bx, y = x - w / 2, y - stub - 9
    add(f'<rect x="{bx:.0f}" y="{y - 9}" width="{w:.0f}" height="18" rx="9" fill="{color}"/>')
    text(bx + w / 2, y + 4.5, label, 12, "middle", "bold", "#ffffff")


def pin(x, y, label, side, used=True):
    add(f'<circle cx="{x}" cy="{y}" r="5" fill="{"#ffd700" if used else "#bbbbbb"}" stroke="#333"/>')
    color = "#ffffff" if used else "#9fb3d1"
    if side == "left":
        text(x + 10, y + 4.5, label, 12, "start", "bold" if used else "normal", color)
    else:
        text(x - 10, y + 4.5, label, 12, "end", "bold" if used else "normal", color)


def mod_pin(x, y, label, pos):
    """Pin on a module edge. pos: label placement relative to the pin."""
    add(f'<circle cx="{x}" cy="{y}" r="5" fill="#ffd700" stroke="#333"/>')
    if pos == "above":
        text(x, y - 10, label, 12, "middle", "bold")
    elif pos == "below":
        text(x, y + 20, label, 12, "middle", "bold")
    elif pos == "left":
        text(x - 10, y + 4.5, label, 12, "end", "bold")
    else:
        text(x + 10, y + 4.5, label, 12, "start", "bold")


add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
    'font-family="Segoe UI, Arial, Helvetica, sans-serif">')
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
text(30, 40, "Bench wiring: Mainboard (ESP32 WROOM-32) and Controller (ESP32-C3 SuperMini)", 22, weight="bold")
text(30, 64, "Both boards powered from USB. Low voltage only: nothing on the relay contacts. "
     "Pills are connections to a breadboard rail or a named point. Wire by the labels printed on your boards.",
     13, color="#555")

# Breadboard areas
rect(20, 85, 760, 1015, "#fafaf5", "#cfcfc0", 10, 1)
rect(830, 85, 750, 1015, "#f5faf5", "#c0cfc0", 10, 1)
text(35, 1088, "Breadboard 1: Mainboard", 14, weight="bold", color="#777")
text(845, 1088, "Breadboard 2: Controller", 14, weight="bold", color="#777")

# ---------------------------------------------------------------------------
# Mainboard: 30-pin ESP32 DevKit, USB at the bottom
# ---------------------------------------------------------------------------
MX0, MX1, MY0, P = 560, 740, 300, 32
rect(MX0, MY0 - 45, MX1 - MX0, 15 * P + 60, C["board"], "#1b2f50", 8, 2)
text((MX0 + MX1) / 2, MY0 - 22, "MAINBOARD", 15, "middle", "bold", "#ffffff")
text((MX0 + MX1) / 2, MY0 - 6, "ESP32 WROOM-32", 11, "middle", color="#cfe0ff")
rect((MX0 + MX1) / 2 - 22, MY0 + 15 * P - 2, 44, 30, "#c0c0c0", "#666", 3)
text((MX0 + MX1) / 2, MY0 + 15 * P + 48, "USB to PC", 12, "middle", "bold")
LEFT = ["EN", "36", "39", "34", "35", "32", "33", "25", "26", "27", "14", "12", "13", "GND", "VIN"]
RIGHT = ["23", "22", "TX0", "RX0", "21", "19", "18", "5", "17", "16", "4", "2", "15", "GND", "3V3"]
USED_L = {"34", "32", "33", "25", "26", "27", "GND", "VIN"}
USED_R = {"22", "21", "17", "16", "GND", "3V3"}
ml = {n: (MX0, MY0 + i * P) for i, n in enumerate(LEFT)}
mr = {n: (MX1, MY0 + i * P) for i, n in enumerate(RIGHT)}
for n, (x, y) in ml.items():
    pin(x, y, n if not n.isdigit() else "G" + n, "left", n in USED_L)
for n, (x, y) in mr.items():
    pin(x, y, n if not n.isdigit() else "G" + n, "right", n in USED_R)

# Relay board
rect(50, 130, 230, 215, C["mod"])
text(60, 152, "4-RELAY BOARD", 14, weight="bold")
for i, name in enumerate(["K1 Fan", "K2 Heater", "K3 Humidifier", "K4 Compressor"]):
    rect(62, 165 + i * 40, 120, 30, "#4a90d9", "#2a5d99", 4)
    text(122, 185 + i * 40, name, 11, "middle", "bold", "#ffffff")
text(60, 338, "Keep JD-VCC jumper on for the bench", 10, color="#555", italic=True)
RX = 280
rp = {"GND": 165, "IN1": 195, "IN2": 225, "IN3": 255, "IN4": 285, "VCC": 315}
for n, y in rp.items():
    mod_pin(RX, y, n, "left")
tag(RX, rp["GND"], "GND", C["GND"], "right", 30)
tag(RX, rp["VCC"], "5V", C["5V"], "right", 30)
wire([ml["26"], (460, ml["26"][1]), (460, rp["IN1"]), (RX, rp["IN1"])], C["relay"])
wire([ml["27"], (440, ml["27"][1]), (440, rp["IN2"]), (RX, rp["IN2"])], "#1a7a1a")
wire([ml["32"], (500, ml["32"][1]), (500, rp["IN3"]), (RX, rp["IN3"])], "#5cbf5c")
wire([ml["33"], (480, ml["33"][1]), (480, rp["IN4"]), (RX, rp["IN4"])], "#0f5c0f")
text(52, 362, "IN1 G26 · IN2 G27 · IN3 G32 · IN4 G33", 11, color="#2a6a2a", weight="bold")

# PWM -> 0-10 V converter
CY = ml["25"][1]
rect(70, CY - 60, 220, 150, C["mod"])
text(80, CY - 38, "PWM → 0-10 V", 14, weight="bold")
text(80, CY - 22, "CONVERTER", 14, weight="bold")
mod_pin(290, CY, "PWM", "left")
mod_pin(290, CY + 40, "GND (PWM)", "left")
tag(290, CY + 40, "GND", C["GND"], "right", 30)
mod_pin(100, CY + 90, "V+", "above")
mod_pin(150, CY + 90, "GND", "above")
mod_pin(205, CY + 90, "0-10V", "above")
mod_pin(255, CY + 90, "GND", "above")
wire([ml["25"], (290, CY)], C["pwm"])
text(80, CY + 122, "V+/GND: its own supply (often 12-24 V).", 11, color="#555")
text(80, CY + 137, "0-10V/GND: multimeter for the bench.", 11, color="#555")
text(80, CY + 152, "Later to the fan's 0-10 V input.", 11, color="#555")

# Tach input conditioning
tag(*ml["34"], "TACH", C["tach"], "left", 26)
TX0, TY = 80, 840
rect(50, TY - 40, 480, 220, C["mod"])
text(60, TY - 18, "FAN TACH INPUT (on the breadboard)", 14, weight="bold")
# node A at (230, TY+40), node B at (380, TY+40)
ax, bx, ny = 230, 390, TY + 85
wire([(110, ny), (ax, ny)], C["tach"])
mod_pin(110, ny, "Fan tach wire", "below")
text(110, ny + 36, "(open collector)", 10, "middle", color="#555")
# 10k up to 3V3
wire([(ax, ny), (ax, ny - 18)], C["tach"])
rect(ax - 9, ny - 58, 18, 40, "#e8d8b0", "#7a6a40", 2)
text(ax + 14, ny - 34, "10 kΩ", 12, weight="bold")
tag(ax, ny - 58, "3V3 (M)", C["3V3M"], "up", 14)
# 1k series
wire([(ax, ny), (ax + 50, ny)], C["tach"])
rect(ax + 50, ny - 9, 40, 18, "#e8d8b0", "#7a6a40", 2)
text(ax + 70, ny - 16, "1 kΩ", 12, "middle", "bold")
wire([(ax + 90, ny), (bx, ny)], C["tach"])
# 10 nF to GND
wire([(bx, ny), (bx, ny + 20)], C["tach"])
add(f'<line x1="{bx - 14}" y1="{ny + 20}" x2="{bx + 14}" y2="{ny + 20}" stroke="#333" stroke-width="3"/>')
add(f'<line x1="{bx - 14}" y1="{ny + 28}" x2="{bx + 14}" y2="{ny + 28}" stroke="#333" stroke-width="3"/>')
text(bx + 20, ny + 29, "10 nF", 12, weight="bold")
tag(bx, ny + 28, "GND", C["GND"], "down", 14)
wire([(bx, ny), (bx + 40, ny)], C["tach"])
tag(bx + 40, ny, "TACH → G34", C["tach"], "right", 4)
text(60, TY + 160, "No fan yet? Leave the tach wire open and type: set fanfaultrpm 0", 11, color="#555", italic=True)

# Sensor
SX = 810
rect(SX - 100, 120, 160, 90, C["mod"])
text(SX - 92, 142, "AHT20 + BMP280", 13, weight="bold")
sp = {"VIN": SX - 80, "GND": SX - 40, "SCL": SX, "SDA": SX + 40}
for n, x in sp.items():
    mod_pin(x, 210, n, "above")
tag(sp["VIN"], 210, "3V3 (M)", C["3V3M"], "down", 14)
tag(sp["GND"], 210, "GND", C["GND"], "down", 40)
wire([mr["22"], (sp["SCL"], mr["22"][1]), (sp["SCL"], 210)], C["scl"])
wire([mr["21"], (sp["SDA"], mr["21"][1]), (sp["SDA"], 210)], C["sda"])

# Mainboard power pins
tag(*ml["GND"], "GND", C["GND"], "left", 30)
tag(*ml["VIN"], "5V", C["5V"], "left", 30)
tag(*mr["GND"], "GND", C["GND"], "right", 8)
tag(*mr["3V3"], "3V3 (M)", C["3V3M"], "right", 8)

# ---------------------------------------------------------------------------
# Controller: ESP32-C3 SuperMini, USB at the top
# ---------------------------------------------------------------------------
CX0, CX1, CY0, CP = 1100, 1260, 430, 36
rect(CX0, CY0 - 75, CX1 - CX0, 8 * CP + 85, C["board2"], "#1f401f", 8, 2)
rect((CX0 + CX1) / 2 - 20, CY0 - 90, 40, 26, "#c0c0c0", "#666", 3)
text((CX0 + CX1) / 2, CY0 - 100, "USB to PC", 12, "middle", "bold")
text((CX0 + CX1) / 2, CY0 - 45, "CONTROLLER", 15, "middle", "bold", "#ffffff")
text((CX0 + CX1) / 2, CY0 - 29, "ESP32-C3 SuperMini", 11, "middle", color="#d0f0d0")
CL = ["5V", "GND", "3V3", "4", "3", "2", "1", "0"]
CR = ["5", "6", "7", "8", "9", "10", "20", "21"]
cl = {n: (CX0, CY0 + i * CP) for i, n in enumerate(CL)}
cr = {n: (CX1, CY0 + i * CP) for i, n in enumerate(CR)}
for n, (x, y) in cl.items():
    pin(x, y, n if not n.isdigit() else "G" + n, "left", n not in ("5V", "2"))
for n, (x, y) in cr.items():
    pin(x, y, n if not n.isdigit() else "G" + n, "right", n not in ("6", "7"))
tag(*cl["GND"], "GND", C["GND"], "left", 24)
tag(*cl["3V3"], "3V3 (C)", C["3V3C"], "left", 24)
add(f'<text x="{CX0 - 14}" y="{cl["5V"][1] + 4}" font-size="11" fill="#d62728" text-anchor="end" '
    'font-weight="bold">5V: leave open on the bench</text>')
tag(*cl["4"], "ENC2 CLK", C["enc"], "left", 24)
tag(*cr["5"], "ENC2 DT", C["enc"], "right", 24)
tag(*cr["10"], "ENC2 SW", C["enc"], "right", 24)

# OLED
OX = 1380
rect(OX - 70, 130, 200, 110, "#1a1a1a", "#000", 6)
rect(OX - 55, 145, 170, 62, "#0a2a4a", "#333", 2)
text(OX + 30, 182, "1.3\" OLED (DST-013)", 12, "middle", "bold", "#9fd0ff")
op = {"VDD": OX - 40, "GND": OX, "SCK": OX + 40, "SDA": OX + 80}
for n, x in op.items():
    add(f'<circle cx="{x}" cy="240" r="5" fill="#ffd700" stroke="#333"/>')
    text(x, 230, n, 11, "middle", "bold", "#ffffff")
tag(op["VDD"], 240, "3V3 (C)", C["3V3C"], "down", 16)
tag(op["GND"], 240, "GND", C["GND"], "down", 48)
wire([cr["9"], (op["SCK"], cr["9"][1]), (op["SCK"], 240)], C["scl"])
wire([cr["8"], (op["SDA"], cr["8"][1]), (op["SDA"], 240)], C["sda"])

# Encoder 1 (wired directly)
E1 = {"GND": 870, "+": 900, "SW": 930, "DT": 960, "CLK": 990}
EY = 790
rect(850, EY, 160, 95, C["mod"])
add(f'<circle cx="930" cy="{EY + 52}" r="20" fill="#888" stroke="#444" stroke-width="2"/>')
add(f'<circle cx="930" cy="{EY + 52}" r="7" fill="#ccc"/>')
text(1018, EY + 40, "ENCODER 1", 13, weight="bold")
text(1018, EY + 56, "temp / mode", 11, color="#555")
for n, x in E1.items():
    mod_pin(x, EY, n, "below" if False else "above")
tag(E1["GND"], EY, "GND", C["GND"], "up", 40)
tag(E1["+"], EY, "3V3 (C)", C["3V3C"], "up", 70)
wire([cl["0"], (E1["CLK"], cl["0"][1]), (E1["CLK"], EY)], C["enc"])
wire([cl["1"], (E1["DT"], cl["1"][1]), (E1["DT"], EY)], "#1a7a1a")
wire([cl["3"], (E1["SW"], cl["3"][1]), (E1["SW"], EY)], "#5cbf5c")

# Encoder 2 (by tags)
E2 = {"GND": 1300, "+": 1340, "SW": 1380, "DT": 1420, "CLK": 1460}
rect(1280, EY, 200, 95, C["mod"])
add(f'<circle cx="1380" cy="{EY + 52}" r="20" fill="#888" stroke="#444" stroke-width="2"/>')
add(f'<circle cx="1380" cy="{EY + 52}" r="7" fill="#ccc"/>')
text(1410, EY + 52, "ENCODER 2", 13, weight="bold")
text(1410, EY + 68, "hum / menu", 11, color="#555")
for n, x in E2.items():
    mod_pin(x, EY, n, "above")
tag(E2["GND"], EY, "GND", C["GND"], "up", 30)
tag(E2["+"], EY, "3V3 (C)", C["3V3C"], "up", 56)
for n, g, ln in (("SW", "G10", 30), ("DT", "G5", 56), ("CLK", "G4", 82)):
    tag(E2[n], EY, g, C["enc"], "up", ln)
text(850, EY + 112, "Bare EC11 encoder: A = CLK, B = DT, middle pin C = GND; one switch pin = SW, other = GND.",
     11, color="#555")

# ---------------------------------------------------------------------------
# Link between the boards (TX/RX crossed) and GND
# ---------------------------------------------------------------------------
wire([mr["17"], (815, mr["17"][1]), (815, 1010), (1545, 1010), (1545, cr["20"][1]), cr["20"]], C["link_tx"], 4)
wire([mr["16"], (835, mr["16"][1]), (835, 995), (1525, 995), (1525, cr["21"][1]), cr["21"]], C["link_rx"], 4)
text(1010, 990, "Mainboard G17 TX2 → Controller G20 RX", 12, weight="bold", color="#0f8f9f")
text(1000, 1030, "Mainboard G16 RX2 ← Controller G21 TX", 12, weight="bold", color="#b0408f")
# GND bridge between breadboards
add('<line x1="760" y1="1060" x2="850" y2="1060" stroke="#333" stroke-width="5" stroke-linecap="round"/>')
tag(760, 1060, "GND", C["GND"], "left", 4)
tag(850, 1060, "GND", C["GND"], "right", 4)
text(900, 1065, "Join the GND rails of both breadboards (needed for the link)", 12, weight="bold")

add("</svg>")
p = Path(__file__).resolve().parent.parent / "docs" / "bench-wiring.svg"
p.parent.mkdir(exist_ok=True)
p.write_text("\n".join(out), encoding="utf-8")
print("wrote", p)
