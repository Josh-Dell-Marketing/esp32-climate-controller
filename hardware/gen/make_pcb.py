"""Build the PCB: footprints, placement, outline + isolation slots, mains
routing, low-voltage auto-routing, ground pours, silkscreen.

Run with KiCad's Python after make_sch.py:
    "C:\\Program Files\\KiCad\\10.0\\bin\\python.exe" make_pcb.py
"""
import math
import os
import subprocess
import sys
import time

import pcbnew

import design as D
from router import Item, Router
from sexpr import Str, dump, find, find_all, parse

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
KICAD_BIN = r"C:\Program Files\KiCad\10.0\bin"
FPDIR = r"C:\Program Files\KiCad\10.0\share\kicad\footprints"
SCH = os.path.join(HW, D.PROJECT + ".kicad_sch")
PCB = os.path.join(HW, D.PROJECT + ".kicad_pcb")
NETLIST = os.path.join(HW, "build", D.PROJECT + ".net")

OX, OY = 50.0, 50.0           # board top-left on the KiCad page, mm


def mm(v):
    return pcbnew.FromMM(v)


def P(x, y):
    """Board-relative mm -> KiCad VECTOR2I."""
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


def rel(v):
    return pcbnew.ToMM(v.x) - OX, pcbnew.ToMM(v.y) - OY


# ---------------------------------------------------------------------------
# Project footprint: NodeMCU v2 in two 1x15 sockets (+ a simple 3D model)
# ---------------------------------------------------------------------------
def write_nodemcu_footprint():
    libdir = os.path.join(HW, "lib", "climate.pretty")
    os.makedirs(libdir, exist_ok=True)
    os.makedirs(os.path.join(HW, "lib", "climate.3dshapes"), exist_ok=True)
    half_row = D.NODEMCU_ROW_SPACING / 2
    L, Wd = D.NODEMCU_OUTLINE
    hx, hy = L / 2, Wd / 2

    def line(x1, y1, x2, y2, layer, w):
        return ["fp_line", ["start", x1, y1], ["end", x2, y2], ["stroke", ["width", w], ["type", "solid"]],
                ["layer", Str(layer)]]

    def txt(kind, value, x, y, layer, hide=False, size=1.0):
        p = ["property", Str(kind), Str(value), ["at", x, y, 0], ["layer", Str(layer)]]
        if hide:
            p.append(["hide", "yes"])
        p.append(["effects", ["font", ["size", size, size], ["thickness", 0.15]]])
        return p

    items = ["footprint", Str("NodeMCU_v2_Socket"), ["version", 20241229], ["generator", Str("climate_gen")],
             ["layer", Str("F.Cu")],
             ["descr", Str("NodeMCU v2 (Amica) ESP8266 board on two 1x15 2.54 mm female sockets, 22.86 mm row spacing. "
                           "Pins 1-15: A0..VIN row, 16-30: D0..3V3 row. USB end at +X.")],
             ["tags", Str("NodeMCU ESP8266 socket")],
             txt("Reference", "REF**", -hx + 12, -hy + 2.2, "F.SilkS"),
             txt("Value", "NodeMCU_v2", 0, 0, "F.Fab"),
             txt("Datasheet", "", 0, 0, "F.Fab", hide=True),
             txt("Description", "", 0, 0, "F.Fab", hide=True),
             ["attr", "through_hole"]]
    # board outline (fab + silk), courtyard
    for (x1, y1, x2, y2) in ((-hx, -hy, hx, -hy), (hx, -hy, hx, hy), (hx, hy, -hx, hy), (-hx, hy, -hx, -hy)):
        items.append(line(x1, y1, x2, y2, "F.Fab", 0.1))
        items.append(line(x1, y1, x2, y2, "F.SilkS", 0.12))
    c = 0.25
    for (x1, y1, x2, y2) in ((-hx - c, -hy - c, hx + c, -hy - c), (hx + c, -hy - c, hx + c, hy + c),
                             (hx + c, hy + c, -hx - c, hy + c), (-hx - c, hy + c, -hx - c, -hy - c)):
        items.append(line(x1, y1, x2, y2, "F.CrtYd", 0.05))
    # USB marker and antenna marker on silk
    items.append(line(hx - 4, -3.5, hx, -3.5, "F.SilkS", 0.12))
    items.append(line(hx - 4, 3.5, hx, 3.5, "F.SilkS", 0.12))
    items.append(["fp_text", "user", Str("USB"), ["at", hx - 6.5, 0, 90], ["layer", Str("F.SilkS")],
                  ["effects", ["font", ["size", 1.0, 1.0], ["thickness", 0.15]]]])
    items.append(["fp_text", "user", Str("ANTENNA - KEEP CLEAR"), ["at", -hx + 3.0, 0, 90], ["layer", Str("F.SilkS")],
                  ["effects", ["font", ["size", 0.9, 0.9], ["thickness", 0.13]]]])
    # pads
    for num in range(1, 31):
        if num <= 15:
            x, y = -17.78 + (num - 1) * 2.54, half_row
        else:
            x, y = -17.78 + (num - 16) * 2.54, -half_row
        shape = "rect" if num in (1, 16) else "circle"
        items.append(["pad", Str(str(num)), "thru_hole", shape, ["at", round(x, 3), round(y, 3)],
                      ["size", 1.7, 1.7], ["drill", 1.0], ["layers", Str("*.Cu"), Str("*.Mask")],
                      ["remove_unused_layers", "no"]])
        # pin names on fab
        items.append(["fp_text", "user", Str(D.NODEMCU_PINS[num]),
                      ["at", round(x, 3), round(y + (-2.0 if num <= 15 else 2.0), 3), 90], ["layer", Str("F.Fab")],
                      ["effects", ["font", ["size", 0.6, 0.6], ["thickness", 0.09]]]])
    # 3D: two sockets + the NodeMCU board itself
    sock = "${KICAD10_3DMODEL_DIR}/Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x15_P2.54mm_Vertical.step"
    for y in (half_row, -half_row):
        items.append(["model", Str(sock), ["offset", ["xyz", -17.78, -y, 0]], ["scale", ["xyz", 1, 1, 1]],
                      ["rotate", ["xyz", 0, 0, -90]]])
    items.append(["model", Str("${KIPRJMOD}/lib/climate.3dshapes/NodeMCU_v2.wrl"), ["offset", ["xyz", 0, 0, 0]],
                  ["scale", ["xyz", 1, 1, 1]], ["rotate", ["xyz", 0, 0, 0]]])
    with open(os.path.join(libdir, "NodeMCU_v2_Socket.kicad_mod"), "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(items) + "\n")
    write_nodemcu_wrl(hx, hy)


def write_nodemcu_wrl(hx, hy):
    """Boxes for the NodeMCU: PCB on 8.5 mm sockets, ESP-12 module, USB socket.
    KiCad VRML units are 0.1 inch."""
    u = 1 / 2.54
    z0 = 8.5            # socket body height
    boxes = [
        # (x1, y1, z1, x2, y2, z2, r, g, b)  in mm, 3D y is -footprint y (symmetric here)
        (-hx, -hy, z0, hx, hy, z0 + 1.6, 0.05, 0.2, 0.55),            # PCB
        (-hx, -8.0, z0 + 1.6, -hx + 24.0, 8.0, z0 + 1.6 + 0.8, 0.1, 0.1, 0.1),   # module PCB
        (-hx + 7.0, -6.0, z0 + 2.4, -hx + 22.0, 6.0, z0 + 4.4, 0.75, 0.75, 0.78),  # shield
        (hx - 5.5, -3.9, z0 + 1.6, hx + 0.8, 3.9, z0 + 4.4, 0.8, 0.8, 0.82),       # micro USB
        (hx - 16, -6, z0 + 1.6, hx - 10, 6, z0 + 2.8, 0.12, 0.12, 0.12),            # CP2102
    ]
    out = ["#VRML V2.0 utf8", "# NodeMCU v2 approximate model (generated)"]
    for (x1, y1, z1, x2, y2, z2, r, g, b) in boxes:
        pts = [(x, y, z) for z in (z1, z2) for y in (y1, y2) for x in (x1, x2)]
        coords = ", ".join(f"{x * u:.4f} {y * u:.4f} {z * u:.4f}" for x, y, z in pts)
        faces = "0,2,3,1,-1, 4,5,7,6,-1, 0,1,5,4,-1, 2,6,7,3,-1, 0,4,6,2,-1, 1,3,7,5,-1"
        out.append("Shape { appearance Appearance { material Material { diffuseColor %.2f %.2f %.2f } }"
                   " geometry IndexedFaceSet { solid FALSE coord Coordinate { point [ %s ] } coordIndex [ %s ] } }"
                   % (r, g, b, coords, faces))
    with open(os.path.join(HW, "lib", "climate.3dshapes", "NodeMCU_v2.wrl"), "w", newline="\n") as f:
        f.write("\n".join(out) + "\n")


# ---------------------------------------------------------------------------
# Netlist + schematic symbol UUIDs
# ---------------------------------------------------------------------------
def export_netlist():
    os.makedirs(os.path.dirname(NETLIST), exist_ok=True)
    subprocess.run([os.path.join(KICAD_BIN, "kicad-cli.exe"), "sch", "export", "netlist", "--format", "kicadsexpr",
                    "-o", NETLIST, SCH], check=True, capture_output=True)
    with open(NETLIST, encoding="utf-8") as f:
        tree = parse(f.read())
    comps = {}
    for comp in find_all(find(tree, "components"), "comp"):
        ref = find(comp, "ref")[1]
        comps[ref] = dict(value=find(comp, "value")[1], footprint=find(comp, "footprint")[1],
                          tstamp=find(comp, "tstamps")[1])
    pin_net = {}
    netnames = []
    for net in find_all(find(tree, "nets"), "net"):
        name = find(net, "name")[1]
        netnames.append(name)
        for node in find_all(net, "node"):
            pin_net[(find(node, "ref")[1], find(node, "pin")[1])] = name
    return comps, pin_net, netnames


def short(netname):
    return netname.lstrip("/")


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------
def add_line(board, x1, y1, x2, y2, layer, width):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(x1, y1))
    s.SetEnd(P(x2, y2))
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    board.Add(s)


def add_poly_outline(board, pts, layer=pcbnew.Edge_Cuts, width=0.1):
    for a, b in zip(pts, pts[1:] + pts[:1]):
        add_line(board, a[0], a[1], b[0], b[1], layer, width)


def add_text(board, text, x, y, size=1.2, layer=pcbnew.F_SilkS, angle=0, bold=False, justify=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text)
    t.SetPosition(P(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * (0.2 if bold else 0.15)))
    t.SetTextAngleDegrees(angle)
    if justify == "left":
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)


def slot_polys():
    """U-shaped isolation slots around each relay COM pin (board-relative)."""
    polys = []
    y_top, y_in, y_bot = D.RELAY_COM_Y - 4.5, D.RELAY_COM_Y + 2.65, D.RELAY_COM_Y + 3.65
    for cx in D.CH_X:
        polys.append([(cx - 3.65, y_top), (cx - 2.65, y_top), (cx - 2.65, y_in), (cx + 2.65, y_in),
                      (cx + 2.65, y_top), (cx + 3.65, y_top), (cx + 3.65, y_bot), (cx - 3.65, y_bot)])
    return polys


def slot_rects():
    """The same slots as rectangles, for the router's edge clearance."""
    rects = []
    y_top, y_in, y_bot = D.RELAY_COM_Y - 4.5, D.RELAY_COM_Y + 2.65, D.RELAY_COM_Y + 3.65
    for cx in D.CH_X:
        rects += [(cx - 3.65, y_top, cx - 2.65, y_bot), (cx + 2.65, y_top, cx + 3.65, y_bot),
                  (cx - 3.65, y_in, cx + 3.65, y_bot)]
    return rects


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = os.path.join(HW, "lib", "climate.pretty") if lib == "climate" else os.path.join(FPDIR, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit(f"footprint not found: {fpid}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def clearance_fn(a_cls, b_cls):
    if a_cls == "Mains" or b_cls == "Mains":
        if a_cls == b_cls:
            return 2.0
        return 3.6        # rule is 3.0 mm; extra margin for creepage and grid rounding
    if "Power" in (a_cls, b_cls):
        return 0.4
    return 0.35           # rule 0.25 + grid margin


def net_class(n):
    s = short(n)
    if s in D.MAINS_NETS:
        return "Mains"
    if s in D.POWER_NETS or s in D.COIL_NETS:
        return "Power"
    return "Default"


def build():
    t0 = time.time()
    write_nodemcu_footprint()
    comps, pin_net, netnames = export_netlist()

    board = pcbnew.NewBoard(PCB)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)

    # nets
    netinfo = {}
    for name in netnames:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netinfo[name] = ni

    # outline
    add_poly_outline(board, [(0, 0), (D.BOARD_W, 0), (D.BOARD_W, D.BOARD_H), (0, D.BOARD_H)])
    for poly in slot_polys():
        add_poly_outline(board, poly)

    # footprints
    fps = {}
    for ref, p in D.PARTS.items():
        c = comps[ref]
        fp = load_fp(p["footprint"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetPath(pcbnew.KIID_PATH("/" + c["tstamp"]))
        x, y, rot = p["pos"]
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        board.Add(fp)
        for pad in fp.Pads():
            net = pin_net.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(netinfo[net])
        fps[ref] = fp
    for i, (hx, hy) in enumerate(D.HOLES):
        fp = load_fp(D.FP_HOLE)
        fp.SetReference(f"H{i + 1}")
        fp.SetValue("M3")
        fp.SetPosition(P(hx, hy))
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM
                         | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        board.Add(fp)
        fps[f"H{i + 1}"] = fp

    # tidy reference text: put it on fab for the dense driver parts, keep silk refs small
    for ref, fp in fps.items():
        r = fp.Reference()
        r.SetTextSize(pcbnew.VECTOR2I(mm(0.9), mm(0.9)))
        r.SetTextThickness(mm(0.14))

    check_geometry(fps)

    # -------------------------------------------------------------------------
    # Router setup
    # -------------------------------------------------------------------------
    R = Router(D.BOARD_W, D.BOARD_H, clearance_fn, edge_clear=0.6)
    for (x1, y1, x2, y2) in slot_rects():
        R.edges.append(Item("rect", (x1, y1, x2, y2), (0, 1), None))
    pad_items = {}
    for ref, fp in fps.items():
        for pad in fp.Pads():
            net = pad.GetNetname() or None
            cls = net_class(net) if net else "Default"
            layers = (0, 1) if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else (0,)
            cx, cy = rel(pad.GetPosition())
            if pad.GetShape() == pcbnew.PAD_SHAPE_CIRCLE or pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                r = pcbnew.ToMM(max(pad.GetSize().x, pad.GetDrillSize().x)) / 2
                it = Item("circle", (cx, cy, r), layers, net, cls)
            else:
                bb = pad.GetBoundingBox()
                it = Item("rect", (pcbnew.ToMM(bb.GetLeft()) - OX, pcbnew.ToMM(bb.GetTop()) - OY,
                                   pcbnew.ToMM(bb.GetRight()) - OX, pcbnew.ToMM(bb.GetBottom()) - OY), layers, net, cls)
            R.add_item(it)
            if net:
                pad_items.setdefault(net, []).append(it)

    # -------------------------------------------------------------------------
    # Mains: hand routes, same on both layers
    # -------------------------------------------------------------------------
    mains_w = D.WIDTH["mains"]
    for (n, tag, label, gpio_pin, gpio, role) in D.CHANNELS:
        K = fps[f"K{n}"]
        J = fps[f"J{n + 1}"]
        kp = {p.GetNumber(): rel(p.GetPosition()) for p in K.Pads()}
        jp = {}
        for p in J.Pads():
            jp[short(p.GetNetname())] = rel(p.GetPosition())
        routes = []
        for pin, suffix in (("1", "COM"), ("3", "NO"), ("4", "NC")):
            net = f"/{tag}_{suffix}"
            a = kp[pin]
            b = jp[f"{tag}_{suffix}"]
            dx = b[0] - a[0]
            if abs(dx) < 0.01:
                pts = [a, b]
            else:
                mid = (b[0], a[1] - abs(dx))          # 45-degree jog then straight
                pts = [a, mid, b]
            routes.append((net, pts))
        for net, pts in routes:
            for L, layer in ((0, pcbnew.F_Cu), (1, pcbnew.B_Cu)):
                for a, b in zip(pts, pts[1:]):
                    tr = pcbnew.PCB_TRACK(board)
                    tr.SetStart(P(*a))
                    tr.SetEnd(P(*b))
                    tr.SetWidth(mm(mains_w))
                    tr.SetLayer(layer)
                    tr.SetNet(netinfo[net])
                    board.Add(tr)
                    R.add_item(Item("seg", (a[0], a[1], b[0], b[1], mains_w / 2), (L,), net, "Mains"))

    # -------------------------------------------------------------------------
    # Low-voltage auto-routing
    # -------------------------------------------------------------------------
    order = []
    for (n, tag, *_ ) in D.CHANNELS:
        order += [f"/{tag}_LED", f"/{tag}_BASE", f"/{tag}_COIL"]
    order += ["+5V", "/VIN_RAW", "/VIN_FUSED", "/PWR_LED"]
    order += [f"/{c[1]}_CTRL" for c in D.CHANNELS]
    order += ["/I2C_SCL", "/I2C_SDA", "+3V3", "GND"]
    missing = [n for n in pad_items if n not in order and net_class(n) != "Mains"]
    order += missing
    failed = []
    for net in order:
        if net not in pad_items or len(pad_items[net]) < 2:
            continue
        cls = net_class(net)
        w = D.width_for(short(net))
        via_d, via_drill = (1.0, 0.5) if cls == "Power" else (0.8, 0.4)
        t1 = time.time()
        ok = R.route_net(net, cls, pad_items[net], w, via_d, via_drill)
        print(f"  routed {net:14s} {'ok' if ok else 'FAILED'}  ({time.time() - t1:.1f}s)")
        if not ok:
            failed.append(net)

    for (net, L, pts, width) in R.routes:
        for a, b in zip(pts, pts[1:]):
            tr = pcbnew.PCB_TRACK(board)
            tr.SetStart(P(*a))
            tr.SetEnd(P(*b))
            tr.SetWidth(mm(width))
            tr.SetLayer(pcbnew.F_Cu if L == 0 else pcbnew.B_Cu)
            tr.SetNet(netinfo[net])
            board.Add(tr)
    for (net, x, y, d, drill) in R.vias:
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(P(x, y))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetWidth(mm(d))
        v.SetDrill(mm(drill))
        v.SetNet(netinfo[net])
        board.Add(v)

    # -------------------------------------------------------------------------
    # Ground pours (low-voltage area only) and antenna keep-out
    # -------------------------------------------------------------------------
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(netinfo["GND"])
        z.SetLocalClearance(mm(0.35))
        z.SetMinThickness(mm(0.3))
        z.SetThermalReliefGap(mm(0.5))
        z.SetThermalReliefSpokeWidth(mm(0.6))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetAssignedPriority(0)
        ol = z.Outline()
        ol.NewOutline()
        ztop = D.RELAY_COM_Y + 5.6
        for (x, y) in ((0.6, ztop), (D.BOARD_W - 0.6, ztop), (D.BOARD_W - 0.6, D.BOARD_H - 0.6), (0.6, D.BOARD_H - 0.6)):
            ol.Append(mm(OX + x), mm(OY + y))
        board.Add(z)
    # no copper fill around the (metal) mounting screws
    for i, (hx, hy) in enumerate(D.HOLES):
        kh = pcbnew.ZONE(board)
        kh.SetIsRuleArea(True)
        kh.SetDoNotAllowZoneFills(True)
        kh.SetDoNotAllowTracks(False)
        kh.SetDoNotAllowVias(False)
        kh.SetDoNotAllowPads(False)
        kh.SetDoNotAllowFootprints(False)
        kh.SetLayerSet(pcbnew.LSET.AllCuMask())
        kh.SetZoneName(f"H{i + 1} screw keep-out")
        ol = kh.Outline()
        ol.NewOutline()
        for k in range(16):
            a = 2 * math.pi * k / 16
            ol.Append(mm(OX + hx + 3.2 * math.cos(a)), mm(OY + hy + 3.2 * math.sin(a)))
        board.Add(kh)

    ka = pcbnew.ZONE(board)
    ka.SetIsRuleArea(True)
    ka.SetDoNotAllowZoneFills(True)
    ka.SetDoNotAllowTracks(False)
    ka.SetDoNotAllowVias(False)
    ka.SetDoNotAllowPads(False)
    ka.SetDoNotAllowFootprints(False)
    ka.SetLayerSet(pcbnew.LSET.AllCuMask())
    ka.SetZoneName("ESP antenna keep-out")
    ol = ka.Outline()
    ol.NewOutline()
    ax0 = D.NODEMCU_POS[0] - D.NODEMCU_OUTLINE[0] / 2 - 1.0
    for (x, y) in ((ax0, 56.5), (ax0 + 9.0, 56.5), (ax0 + 9.0, D.BOARD_H - 0.2), (ax0, D.BOARD_H - 0.2)):
        ol.Append(mm(OX + x), mm(OY + y))
    board.Add(ka)

    # -------------------------------------------------------------------------
    # Silkscreen
    # -------------------------------------------------------------------------
    silk(board, fps)

    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    board.Save(PCB)
    print(f"saved {PCB}  ({time.time() - t0:.0f}s)")
    if failed:
        print("UNROUTED NETS:", failed)
        sys.exit(2)


def silk(board, fps):
    F = pcbnew.F_SilkS
    for i, (n, tag, label, gpio_pin, gpio, role) in enumerate(D.CHANNELS):
        cx = D.CH_X[i]
        J = fps[f"J{n + 1}"]
        names = {short(p.GetNetname()).split("_")[-1]: rel(p.GetPosition()) for p in J.Pads()}
        # strip between the terminal body and the relay
        for nm, (x, y) in names.items():
            add_text(board, nm, x, y + 6.7, size=0.9)
        # channel name in the low-voltage area, just under the COM isolation slot
        add_text(board, f"{n} {label}", cx + 0.8, D.RELAY_COM_Y + 5.0, size=0.9, bold=True)
        # move the flyback diode's reference off the channel name, to its anode end
        dref = fps[f"D{n}"].Reference()
        dref.SetPosition(P(cx + 6.7, D.PARTS[f"D{n}"]["pos"][1]))
        dref.SetTextAngleDegrees(0)
    fps["J6"].Reference().SetVisible(False)     # named in the legend below instead
    # mains warnings in the free strips beside the outer terminals
    add_text(board, "DANGER MAINS", 2.6, 11.0, size=1.1, angle=90, bold=True)
    add_text(board, "DANGER MAINS", D.BOARD_W - 2.6, 11.0, size=1.1, angle=90, bold=True)
    j1 = {short(p.GetNetname()): rel(p.GetPosition()) for p in fps["J1"].Pads()}
    vx, vy = j1["VIN_RAW"]
    gx, gy = j1["GND"]
    add_text(board, "5V DC IN", 5.6, 58.2, size=0.9, bold=True)
    add_text(board, "+", 11.9, vy, size=1.4, bold=True)
    add_text(board, "-", 11.9, gy, size=1.4, bold=True)
    add_text(board, "J6 SHT31-D: 3V3 GND SCL SDA", 14.3, 77.6, size=0.7)
    add_text(board, "J7 I2C: 3V3 GND SCL SDA", 27.8, 85.0, size=0.7)
    # back side title
    B = pcbnew.B_SilkS
    add_text(board, "DANGER: RELAY CONTACTS MAY CARRY MAINS VOLTAGE", D.BOARD_W / 2, 20.0, size=1.2, layer=B, bold=True)
    # back-side title in the clear area between the NodeMCU socket rows
    tx, ty = D.NODEMCU_POS[0] + 1.0, D.NODEMCU_POS[1]
    add_text(board, "Climate Controller", tx, ty - 5.0, size=1.5, layer=B, bold=True)
    add_text(board, "Relay Carrier", tx, ty - 2.4, size=1.5, layer=B, bold=True)
    add_text(board, f"Rev {D.REV}  {D.DATE}", tx, ty + 0.6, size=1.1, layer=B)
    add_text(board, "Relay contacts: 5 A max per channel", tx, ty + 3.2, size=0.9, layer=B)
    add_text(board, "Mains wiring by a competent person only", tx, ty + 5.0, size=0.9, layer=B)


def check_geometry(fps):
    """Sanity-check the orientation assumptions in design.py."""
    for i, (n, tag, *_ ) in enumerate(D.CHANNELS):
        cx = D.CH_X[i]
        kp = {p.GetNumber(): rel(p.GetPosition()) for p in fps[f"K{n}"].Pads()}
        assert abs(kp["1"][0] - cx) < 0.01, kp
        assert kp["4"][0] < cx < kp["3"][0], f"K{n}: expected NC (4) left, NO (3) right: {kp}"
        assert kp["3"][1] < kp["1"][1], f"K{n}: contacts should be above COM: {kp}"
        assert kp["5"][0] < cx < kp["2"][0], f"K{n}: expected coil 5 left, 2 right: {kp}"


if __name__ == "__main__":
    build()
