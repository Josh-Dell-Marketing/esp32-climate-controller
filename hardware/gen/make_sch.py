"""Generate the KiCad schematic, project symbol library and lib tables.

Run with KiCad's Python:  "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" make_sch.py
"""
import math
import os
import uuid

import design as D
from sexpr import Str, dump, find, find_all, parse

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
SYMDIR = r"C:\Program Files\KiCad\10.0\share\kicad\symbols"
SCH_VERSION = 20250610


def uid():
    return Str(str(uuid.uuid4()))


def r4(v):
    return round(v + 0.0, 4)


# ---------------------------------------------------------------------------
# Library symbols
# ---------------------------------------------------------------------------
_lib_cache = {}


def load_lib(lib):
    if lib not in _lib_cache:
        with open(os.path.join(SYMDIR, lib + ".kicad_sym"), encoding="utf-8") as f:
            tree = parse(f.read())
        _lib_cache[lib] = {s[1]: s for s in find_all(tree, "symbol")}
    return _lib_cache[lib]


def rename_units(sym, old, new):
    for c in sym:
        if isinstance(c, list) and c and c[0] == "symbol" and isinstance(c[1], str) and c[1].startswith(old + "_"):
            c[1] = Str(new + c[1][len(old):])


def flat_symbol(lib, name):
    """Return a deep-copied, flattened symbol renamed to 'lib:name'."""
    import copy
    syms = load_lib(lib)
    sym = copy.deepcopy(syms[name])
    ext = find(sym, "extends")
    if ext:
        parent = flat_symbol(lib, ext[1])
        parent_name = parent[1].split(":", 1)[1]
        child_props = {p[1]: p for p in find_all(sym, "property")}
        out = ["symbol", Str(f"{lib}:{name}")]
        for c in parent[2:]:
            if isinstance(c, list) and c[0] == "property" and c[1] in child_props:
                out.append(child_props.pop(c[1]))
            else:
                out.append(c)
        out.extend(child_props.values())
        rename_units(out, parent_name, name)
        return out
    sym[1] = Str(f"{lib}:{name}")
    return sym


def nodemcu_symbol(lib_prefix=True):
    name = "climate:NodeMCU_v2" if lib_prefix else "NodeMCU_v2"

    def prop(k, v, x, y, hide=False):
        p = ["property", Str(k), Str(v), ["at", x, y, 0], ["effects", ["font", ["size", 1.27, 1.27]]]]
        if hide:
            p.insert(4, ["hide", "yes"])
        return p

    pins = []
    for num in range(1, 31):
        pname = D.NODEMCU_PINS[num]
        if num <= 15:
            x, y, ang = -15.24, 17.78 - (num - 1) * 2.54, 0
        else:
            x, y, ang = 15.24, 17.78 - (num - 16) * 2.54, 180
        if pname == "GND" or pname == "VIN":
            etype = "power_in"
        elif pname == "3V3":
            etype = "power_out"
        elif pname.startswith("D") or pname in ("RX", "TX", "A0"):
            etype = "bidirectional"
        elif pname in ("EN", "RST"):
            etype = "input"
        else:
            etype = "passive"
        pins.append(["pin", etype, "line", ["at", x, y, ang], ["length", 5.08],
                     ["name", Str(pname), ["effects", ["font", ["size", 1.27, 1.27]]]],
                     ["number", Str(str(num)), ["effects", ["font", ["size", 1.27, 1.27]]]]])
    body = ["symbol", Str("NodeMCU_v2_0_1"),
            ["rectangle", ["start", -10.16, 20.32], ["end", 10.16, -20.32],
             ["stroke", ["width", 0.254], ["type", "default"]], ["fill", ["type", "background"]]]]
    unit = ["symbol", Str("NodeMCU_v2_1_1")] + pins
    return ["symbol", Str(name),
            ["pin_names", ["offset", 1.016]],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            prop("Reference", "U", 0, 22.86),
            prop("Value", "NodeMCU_v2", 0, -22.86),
            prop("Footprint", D.FP_NODEMCU, 0, -25.4, hide=True),
            prop("Datasheet", "https://github.com/nodemcu/nodemcu-devkit-v1.0", 0, -27.94, hide=True),
            prop("Description", "NodeMCU v2 (Amica) ESP8266 dev board, 0.9in row spacing, plugged into 2x 1x15 sockets", 0, -30.48, hide=True),
            body, unit]


def symbol_def(lib_id):
    if lib_id == "climate:NodeMCU_v2":
        return nodemcu_symbol()
    lib, name = lib_id.split(":")
    return flat_symbol(lib, name)


def symbol_pins(sym):
    """pin number -> (x, y, angle) in symbol (y-up) coordinates."""
    pins = {}

    def walk(node):
        for c in node:
            if isinstance(c, list) and c:
                if c[0] == "pin":
                    at = find(c, "at")
                    num = find(c, "number")[1]
                    pins[str(num)] = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0)
                elif c[0] == "symbol":
                    walk(c)
    walk(sym)
    return pins


# ---------------------------------------------------------------------------
# Schematic placement (sheet mm, y down). Symbols are placed by reference.
# ---------------------------------------------------------------------------
SCH_POS = {
    # power block
    "J1": (38.1, 63.5, 180), "F1": (63.5, 58.42, 90), "D5": (88.9, 58.42, 180),
    "C1": (109.22, 66.04, 0), "C2": (124.46, 66.04, 0), "R13": (139.7, 63.5, 0), "D10": (139.7, 81.28, 90),
    # sensor block
    "R14": (40.64, 134.62, 0), "R15": (55.88, 134.62, 0), "C3": (71.12, 134.62, 0),
    "J6": (114.3, 139.7, 0), "J7": (114.3, 170.18, 0),
    # MCU
    "U1": (195.58, 147.32, 0),
}
CH_ORIGIN = [(241.3, 38.1), (325.12, 38.1), (241.3, 154.94), (325.12, 154.94)]
CH_LAYOUT = {  # offsets inside a channel box, and rotation
    "K": (50.8, 33.02, 0), "J": (71.12, 30.48, 0),
    "Dfb": (30.48, 30.48, 90), "Dled": (12.7, 27.94, 90), "Rled": (12.7, 45.72, 0),
    "Q": (50.8, 66.04, 0), "Rb": (15.24, 66.04, 90), "Rpd": (33.02, 81.28, 0),
}
for i, (n, tag, label, gpio_pin, gpio, role) in enumerate(D.CHANNELS):
    ox, oy = CH_ORIGIN[i]
    for key, ref in (("K", f"K{n}"), ("J", f"J{n + 1}"), ("Dfb", f"D{n}"), ("Dled", f"D{n + 5}"),
                     ("Rled", f"R{n + 8}"), ("Q", f"Q{n}"), ("Rb", f"R{n}"), ("Rpd", f"R{n + 4}")):
        dx, dy, rot = CH_LAYOUT[key]
        SCH_POS[ref] = (ox + dx, oy + dy, rot)

BLOCKS = [  # (title, x1, y1, x2, y2)
    ("POWER INPUT  5 V DC", 20.32, 38.1, 157.48, 96.52),
    ("SENSOR  SHT31-D on I2C (address 0x44)", 20.32, 111.76, 157.48, 187.96),
    ("CONTROLLER  NodeMCU v2 in sockets", 167.64, 111.76, 228.6, 187.96),
] + [(f"RELAY {i + 1}  {c[2]}  ({c[4]} / GPIO, active HIGH)", CH_ORIGIN[i][0] - 2.54, CH_ORIGIN[i][1] - 7.62,
      CH_ORIGIN[i][0] + 80.01, CH_ORIGIN[i][1] + 99.06) for i, c in enumerate(D.CHANNELS)]

POWER_SYMBOLS = {"+5V": "power:+5V", "+3V3": "power:+3V3", "GND": "power:GND"}

NOTES = [
    "Relay drivers are ACTIVE HIGH (GPIO high = relay on). Firmware: RELAY_ACTIVE_LOW = false.",
    "Relay contacts (COM/NO/NC) may carry mains. Keep >= 3 mm clearance and 4 mm creepage to all low-voltage parts.",
    "Contact rating on this PCB: 5 A per channel. Use a contactor for the compressor and for heaters over ~1 kW.",
    "U1 is a plug-in NodeMCU v2 (Amica, 0.9 in / 22.86 mm row spacing). Check your board's spacing before ordering.",
    "J6 pin order matches SHT31-D breakouts: VIN, GND, SCL, SDA. R14/R15 are the I2C pull-ups.",
    "D5 protects against reverse polarity but drops ~0.35-0.5 V: use a 5.1-5.25 V, >= 1 A supply so the NodeMCU 3.3 V regulator keeps headroom.",
    "R5-R8 (4.7k) hold the relays off while the ESP8266 boots, even if a GPIO pull-up is enabled. Run I2C at 100 kHz.",
]


def rot_vec(x, y, ang):
    a = math.radians(ang)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def outward(ang_total):
    """Sheet-space unit vector pointing away from the body for a pin angle."""
    a = math.radians(ang_total + 180)
    dx, dy = math.cos(a), -math.sin(a)
    return round(dx), round(dy)


class Sheet:
    def __init__(self):
        self.root = uid()
        self.items = []
        self.pwr_n = 0

    def wire(self, x1, y1, x2, y2):
        self.items.append(["wire", ["pts", ["xy", r4(x1), r4(y1)], ["xy", r4(x2), r4(y2)]],
                           ["stroke", ["width", 0], ["type", "default"]], ["uuid", uid()]])

    def label(self, name, x, y, d):
        ang, just = {(1, 0): (0, "left"), (-1, 0): (180, "right"), (0, -1): (90, "left"), (0, 1): (270, "right")}[d]
        self.items.append(["label", Str(name), ["at", r4(x), r4(y), ang],
                           ["effects", ["font", ["size", 1.27, 1.27]], ["justify", just, "bottom"]], ["uuid", uid()]])

    def no_connect(self, x, y):
        self.items.append(["no_connect", ["at", r4(x), r4(y)], ["uuid", uid()]])

    def text(self, s, x, y, size=1.27, bold=False):
        font = ["font", ["size", size, size]]
        if bold:
            font.append(["bold", "yes"])
        self.items.append(["text", Str(s), ["exclude_from_sim", "no"], ["at", r4(x), r4(y), 0],
                           ["effects", font, ["justify", "left", "bottom"]], ["uuid", uid()]])

    def rect(self, x1, y1, x2, y2):
        self.items.append(["rectangle", ["start", r4(x1), r4(y1)], ["end", r4(x2), r4(y2)],
                           ["stroke", ["width", 0.254], ["type", "dash"]], ["fill", ["type", "none"]], ["uuid", uid()]])

    def symbol(self, lib_id, ref, value, footprint, x, y, rot, pin_nums, in_bom=True, ref_off=None, val_off=None):
        def prop(k, v, px, py, hide=False):
            p = ["property", Str(k), Str(v), ["at", r4(px), r4(py), 0]]
            if hide:
                p.append(["hide", "yes"])
            p.append(["effects", ["font", ["size", 1.27, 1.27]]])
            return p
        rx, ry = ref_off if ref_off else (2.54, -2.54)
        vx, vy = val_off if val_off else (2.54, 2.54)
        is_pwr = ref.startswith("#")
        node = ["symbol", ["lib_id", Str(lib_id)], ["at", r4(x), r4(y), rot], ["unit", 1],
                ["exclude_from_sim", "no"], ["in_bom", "yes" if in_bom else "no"], ["on_board", "yes"],
                ["dnp", "no"], ["uuid", uid()],
                prop("Reference", ref, x + rx, y + ry, hide=is_pwr),
                prop("Value", value, x + vx, y + vy),
                prop("Footprint", footprint, x, y, hide=True),
                prop("Datasheet", "", x, y, hide=True),
                prop("Description", "", x, y, hide=True)]
        for pn in pin_nums:
            node.append(["pin", Str(pn), ["uuid", uid()]])
        node.append(["instances", ["project", Str(D.PROJECT),
                                   ["path", Str("/" + self.root), ["reference", Str(ref)], ["unit", 1]]]])
        self.items.append(node)
        return node

    def power(self, net, x, y, d):
        """Place a power symbol whose pin is at (x, y), body pointing in direction d."""
        self.pwr_n += 1
        lib_id = POWER_SYMBOLS[net]
        if net == "GND":
            rot = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}[d]
        else:
            rot = {(0, -1): 0, (-1, 0): 90, (0, 1): 180, (1, 0): 270}[d]
        self.symbol(lib_id, f"#PWR{self.pwr_n:03d}", net, "", x, y, rot, ["1"], in_bom=False,
                    ref_off=(0, 0), val_off=(0, -3.81 if d == (0, -1) else 3.81))

    def flag(self, x, y):
        self.pwr_n += 1
        self.symbol("power:PWR_FLAG", f"#FLG{self.pwr_n:03d}", "PWR_FLAG", "", x, y, 0, ["1"], in_bom=False,
                    ref_off=(0, 0), val_off=(0, -3.81))


def build():
    lib_ids = sorted({p["lib_id"] for p in D.PARTS.values()} | set(POWER_SYMBOLS.values()) | {"power:PWR_FLAG"})
    defs = {lid: symbol_def(lid) for lid in lib_ids}
    pins_of = {lid: symbol_pins(defs[lid]) for lid in lib_ids}

    sh = Sheet()
    for title, x1, y1, x2, y2 in BLOCKS:
        sh.rect(x1, y1, x2, y2)
        sh.text(title, x1 + 1.27, y1 + 3.81, size=1.8, bold=True)

    unknown = []
    points = {}
    pending = {}

    def claim(x, y, net, ref, pn):
        """Fail if two different nets would share a connection point."""
        key = (round(x, 2), round(y, 2))
        prev = points.get(key)
        if prev and prev[0] != net:
            raise SystemExit(f"connection point {key} shared by {prev} and {(net, ref, pn)}")
        points[key] = (net, ref, pn)

    for ref, p in sorted(D.PARTS.items()):
        x, y, rot = SCH_POS[ref]
        lid = p["lib_id"]
        pdefs = pins_of[lid]
        missing = set(p["pins"]) - set(pdefs)
        if missing:
            unknown.append((ref, missing))
        sh.symbol(lid, ref, p["value"], p["footprint"], x, y, rot, sorted(pdefs, key=lambda s: int(s)))
        for pn, (px, py, pang) in pdefs.items():
            qx, qy = rot_vec(px, py, rot)
            ex, ey = x + qx, y - qy                    # pin connection point on the sheet
            d = outward(pang + rot)
            net = p["pins"].get(pn)
            if net is None:
                sh.no_connect(ex, ey)
                continue
            sx, sy = ex + d[0] * 2.54, ey + d[1] * 2.54
            claim(ex, ey, net, ref, pn)
            claim(sx, sy, net, ref, pn)
            sh.wire(ex, ey, sx, sy)
            if net in POWER_SYMBOLS:
                # Power symbol straight out from the pin, so it can never land
                # on a neighbouring pin's stub.
                sh.power(net, sx, sy, d)
            else:
                pending.setdefault(net, []).append((sx, sy, d))

    # Two-pin nets whose stubs face each other on one line: draw a wire
    # instead of two overlapping labels. Everything else gets labels.
    def clear_between(a, b):
        for (px, py) in points:
            if (px, py) in ((round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2))):
                continue
            if abs(a[1] - b[1]) < 0.01 and abs(py - a[1]) < 0.01 and min(a[0], b[0]) <= px <= max(a[0], b[0]):
                return False
            if abs(a[0] - b[0]) < 0.01 and abs(px - a[0]) < 0.01 and min(a[1], b[1]) <= py <= max(a[1], b[1]):
                return False
        return True

    for net, ends in pending.items():
        if len(ends) == 2:
            (ax, ay, ad), (bx, by, bd) = ends
            facing = ad == (-bd[0], -bd[1]) and (
                (abs(ay - by) < 0.01 and (bx - ax) * ad[0] > 0) or (abs(ax - bx) < 0.01 and (by - ay) * ad[1] > 0))
            if facing and clear_between((ax, ay), (bx, by)):
                sh.wire(ax, ay, bx, by)
                continue
        for (sx, sy, d) in ends:
            sh.label(net, sx, sy, d)

    if unknown:
        raise SystemExit(f"pins not found in symbols: {unknown}")

    # PWR_FLAGs: +5V and GND are fed from the input connector, not a power output pin
    for net, (x, y), d in (("+5V", (101.6, 50.8), (0, -1)), ("GND", (124.46, 50.8), (0, 1))):
        sh.power(net, x, y, d)
        sh.wire(x, y, x + 5.08, y)
        sh.flag(x + 5.08, y)

    # Notes
    ny = 205.74
    sh.text("DESIGN NOTES", 20.32, ny, size=1.8, bold=True)
    for i, note in enumerate(NOTES):
        sh.text(f"{i + 1}. {note}", 20.32, ny + 5.08 * (i + 1))

    # Assemble
    lib_symbols = ["lib_symbols"] + [defs[lid] for lid in lib_ids]
    doc = ["kicad_sch", ["version", SCH_VERSION], ["generator", Str("climate_gen")], ["generator_version", Str("1.0")],
           ["uuid", sh.root], ["paper", Str("A3")],
           ["title_block", ["title", Str(D.TITLE)], ["date", Str(D.DATE)], ["rev", Str(D.REV)],
            ["comment", 1, Str("4x SRD-05VDC-SL-C relays, NodeMCU v2 (ESP8266), SHT31-D sensor")],
            ["comment", 2, Str("Generated by hardware/gen/make_sch.py - edit design.py, not this file")]],
           lib_symbols] + sh.items + [["sheet_instances", ["path", Str("/"), ["page", Str("1")]]],
                                      ["embedded_fonts", "no"]]
    return doc


def write_symbol_lib():
    os.makedirs(os.path.join(HW, "lib"), exist_ok=True)
    lib = ["kicad_symbol_lib", ["version", 20241209], ["generator", Str("climate_gen")],
           ["generator_version", Str("1.0")], nodemcu_symbol(lib_prefix=False)]
    with open(os.path.join(HW, "lib", "climate.kicad_sym"), "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(lib) + "\n")
    with open(os.path.join(HW, "sym-lib-table"), "w", encoding="utf-8", newline="\n") as f:
        f.write('(sym_lib_table\n\t(version 7)\n\t(lib (name "climate")(type "KiCad")(uri "${KIPRJMOD}/lib/climate.kicad_sym")'
                '(options "")(descr "Climate controller project symbols"))\n)\n')
    with open(os.path.join(HW, "fp-lib-table"), "w", encoding="utf-8", newline="\n") as f:
        f.write('(fp_lib_table\n\t(version 7)\n\t(lib (name "climate")(type "KiCad")(uri "${KIPRJMOD}/lib/climate.pretty")'
                '(options "")(descr "Climate controller project footprints"))\n)\n')


if __name__ == "__main__":
    write_symbol_lib()
    doc = build()
    out = os.path.join(HW, D.PROJECT + ".kicad_sch")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(doc) + "\n")
    print("wrote", out)
