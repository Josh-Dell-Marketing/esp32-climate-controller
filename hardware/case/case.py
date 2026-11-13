r"""
Parametric 3D-printable enclosure for the climate-controller relay board.

CadQuery. Run:  .venv\\Scripts\\python.exe case.py
Writes case_base.step/.stl and case_lid.step/.stl (lid STL in print orientation).

ASSEMBLY FRAME (used everywhere in this file and in fit_check.py)
  X = board x (mm, board left edge = 0, right edge = 90)
  Y = -board y (board top edge = 0, bottom edge = -86; +Y points at the TOP wall)
  Z = height above the case's outer bottom face (z = 0)
STEP -> assembly:  X = Xs - 50,  Y = Ys + 50,  Z = Zs + BOARD_BOT_Z
(the KiCad STEP has the board at x 50..140, y -136..-50, board bottom z = 0;
 verified in fit_check.py).

All dimensions live in the PARAMETERS block below.
"""
import math
import cadquery as cq

# =============================================================================
# PARAMETERS
# =============================================================================
# --- board -------------------------------------------------------------------
BOARD_W, BOARD_H, BOARD_T = 90.0, 86.0, 1.6
MOUNT_HOLES = [(3.5, 24.0), (86.5, 24.0), (3.2, 82.8), (37.5, 83.0)]  # board coords (x, y-down)

# --- shell -------------------------------------------------------------------
WALL = 2.0            # side wall thickness
FLOOR = 2.0           # floor thickness
LID_T = 2.0           # lid plate thickness
CORNER_R = 4.0        # outer vertical corner radius (inner = CORNER_R - WALL)

GAP_LEFT = 5.0        # board left edge  -> left wall inner face  (J1 wire bend room)
GAP_RIGHT = 1.0       # board right edge -> right wall inner face (USB socket sits in the slot)
GAP_TOP = 8.0         # board top edge   -> top wall inner face (terminal openings are at y=0.7 -> 8.7 mm)
GAP_BOTTOM = 2.0      # board bottom edge-> bottom wall inner face

STANDOFF_FLOOR = 5.0  # floor top -> board bottom (TH leads stick out 1.91 mm below)
LID_UNDERSIDE = 27.5  # z of the lid underside = top of the base walls
# derived
INNER_X0 = -GAP_LEFT
INNER_X1 = BOARD_W + GAP_RIGHT
INNER_Y1 = GAP_TOP
INNER_Y0 = -BOARD_H - GAP_BOTTOM
OUT_X0, OUT_X1 = INNER_X0 - WALL, INNER_X1 + WALL
OUT_Y0, OUT_Y1 = INNER_Y0 - WALL, INNER_Y1 + WALL
BOARD_BOT_Z = FLOOR + STANDOFF_FLOOR
BOARD_TOP_Z = BOARD_BOT_Z + BOARD_T
TOTAL_H = LID_UNDERSIDE + LID_T

# --- PCB bosses (floor) ------------------------------------------------------
INSERT_MODE = "heatset"      # "heatset" or "selftap"
INSERT_HOLE_D = 4.1          # M3 x 5.7 heat-set insert (4.0-4.2)
SELFTAP_HOLE_D = 2.5         # M3 self-tapping pilot (2.5-2.6)
INSERT_DEPTH = 6.2           # insert 5.7 + 0.5 for melt-out
PCB_BOSS_D = 6.4             # = 2 x 3.2 mm keep-out radius on the PCB
PCB_BOSS_FOOT_D = 10.4       # wider foot, below the lead tips
PCB_BOSS_FOOT_TOP = FLOOR + 2.0  # foot ends here (45 deg cone to PCB_BOSS_D); lead tips are at ~BOARD_BOT_Z-1.91

# PCB is held by M3 male-female hex standoffs that also carry the lid screws
STANDOFF_LEN = 18.0          # hex body length (board top -> top of standoff)
STANDOFF_AF = 5.5            # across flats
STANDOFF_MALE = 6.0          # male thread length (through 1.6 PCB + 4.4 into the insert)
LID_PAD_D = 7.0              # pads under the lid that meet the standoffs
LID_PAD_GAP = 0.2            # pad underside -> standoff top (screw pulls it closed)

# --- lid screws in the two top corners (mains side) ---------------------------
CORNER_COL_D = 7.0
CORNER_COL_INSET = 3.5       # column centre distance from the two inner wall faces
LID_SCREW_HOLE_D = 3.4
LID_CSK_D = 6.6              # M3 countersunk (ISO 10642 head 6.0) 90 deg
CORNER_INSERT_DEPTH = 7.0

# --- lid locating lip --------------------------------------------------------
LIP_H = 2.0
LIP_T = 1.2
LIP_GAP = 0.3                # to the wall inner faces
LIP_KEEPOUT = 1.0            # lip is cut back this far around nuts/columns

# --- cable glands ------------------------------------------------------------
TEARDROP = True              # wall holes get a 45 deg roof (printable), flat-topped
M16_HOLE_D = 16.4
M12_HOLE_D = 12.4
M16_NUT_AC, M16_NUT_T = 22.0, 5.0   # inside locknut (across corners, thickness)
M12_NUT_AC, M12_NUT_T = 17.0, 5.0   # assumed: M12x1.5 locknut AF 15 -> AC 17
M16_THREAD_L, M12_THREAD_L = 8.0, 8.0  # thread length from the outer wall face
M16_BODY = (22.0, 18.0)      # outside body (dia, length) - visual only
M12_BODY = (17.0, 15.0)
GLAND_CAVITY_MID = (FLOOR + LID_UNDERSIDE) / 2

# position: (wall, along-wall coordinate in assembly frame, z centre)
#   top wall: along = X ; left/right walls: along = Y
GLANDS = [
    # name,        size, wall,   along,  zc
    ("M16 mains A", 16, "top",   25.0,  GLAND_CAVITY_MID),   # serves K1/K2 terminals (x 7.4..42.6)
    ("M16 mains B", 16, "top",   65.0,  GLAND_CAVITY_MID),   # serves K3/K4 terminals (x 47.4..82.6)
    ("M12 5V in",   12, "left",  -46.0, 18.2),               # J1 at board y 60.4..70.5, faces the left wall
    ("M12 sensor",  12, "right", -44.0, 18.2),               # cable crosses the LV half to J6
]

# --- USB opening (right wall) -----------------------------------------------
USB_Y = -(68.0 + 75.8) / 2            # socket centre, board y 71.9
USB_Z = BOARD_TOP_Z + (10.1 + 12.9) / 2
USB_SLOT_W = 13.5                     # along Y
USB_SLOT_H = 9.0                      # along Z
USB_SLOT_R = 1.5
USB_TAB_CLEAR = 0.2                   # lid tab -> notch side clearance

# --- LED windows in the lid (board coords) ----------------------------------
LEDS = [(10.53, 43.5), (30.53, 43.5), (50.53, 43.5), (70.53, 43.5), (23.57, 70.5)]
LED_WINDOW = "thin"         # "thin" (0.6 mm skin, pocket from inside) or "hole"
LED_WINDOW_D = 5.0
LED_SKIN = 0.6

# --- vents (low-voltage half only) ------------------------------------------
VENTS = True
LID_VENT_X = [50 + 4 * i for i in range(8)]   # slot centres (X)
LID_VENT_Y = (-81.0, -63.0)                   # slot extent (Y)
LID_VENT_W = 1.6
WALL_VENT_X = [48 + 4 * i for i in range(10)]  # bottom wall, vertical slots
WALL_VENT_Z = (11.0, 21.0)
WALL_VENT_W = 1.8

# --- wall mounting (through the floor, low-voltage area) ---------------------
WALL_MOUNT = [(18.0, -52.0), (72.0, -52.0)]   # assembly X, Y
WALL_MOUNT_HOLE_D = 4.5
WALL_MOUNT_CSK_D = 8.5      # 4 mm countersunk wood screw
WALL_MOUNT_PAD_D = 12.0
WALL_MOUNT_PAD_H = 1.5      # local floor thickening so the countersink has a land

# --- lid text ----------------------------------------------------------------
TEXT = "DANGER 230V"
TEXT_SIZE = 8.0
TEXT_DEPTH = 0.6
TEXT_POS = (45.0, -23.0)    # over the relays

# =============================================================================


def bxy(x, y):
    """board coords (y down) -> assembly XY"""
    return (x, -y)


def rrect(x0, y0, x1, y1, r, z0, h):
    """rounded rectangle prism"""
    w, d = x1 - x0, y1 - y0
    s = (cq.Workplane("XY").workplane(offset=z0)
         .center((x0 + x1) / 2, (y0 + y1) / 2).rect(w, d).extrude(h))
    if r > 0:
        s = s.edges("|Z").fillet(r)
    return s


def teardrop_profile(r, flat_h):
    """2D teardrop (apex +v), truncated at v = flat_h, as a Workplane-able wire list in (u, v)"""
    a = r / math.sqrt(2)
    apex = r * math.sqrt(2)
    flat_h = min(flat_h, apex)
    w = apex - flat_h
    return [(a, a), (w, flat_h), (-w, flat_h), (-a, a), (0, 0)]


def gland_hole_cutter(d, wall, along, zc):
    """solid that cuts the gland hole through the given wall (teardrop roof points +Z)"""
    r = d / 2
    L = WALL + 2.0
    # XZ workplane: local x = X, local y = Z, normal along Y -> symmetric extrude
    c = cq.Workplane("XZ").circle(r).extrude(L / 2, both=True)
    if TEARDROP:
        pts = teardrop_profile(r, r + 1.5)
        td = cq.Workplane("XZ").polyline(pts).close().extrude(L / 2, both=True)
        c = c.union(td)
    if wall in ("left", "right"):
        c = c.rotate((0, 0, 0), (0, 0, 1), 90)   # hole axis -> X, profile u -> Y
    xi, yi, _ = wall_point(wall, along, zc, "inner")
    xo, yo, _ = wall_point(wall, along, zc, "outer")
    return c.translate(((xi + xo) / 2, (yi + yo) / 2, zc))


WALL_NORMAL_IN = {"top": (0, -1, 0), "bottom": (0, 1, 0), "left": (1, 0, 0), "right": (-1, 0, 0)}


def orient_z_to(s, n):
    """rotate a solid built along +Z so that +Z points along unit axis n"""
    if n == (0, 0, 1):
        return s
    if n == (0, 1, 0):
        return s.rotate((0, 0, 0), (1, 0, 0), -90)
    if n == (0, -1, 0):
        return s.rotate((0, 0, 0), (1, 0, 0), 90)
    if n == (1, 0, 0):
        return s.rotate((0, 0, 0), (0, 1, 0), 90)
    if n == (-1, 0, 0):
        return s.rotate((0, 0, 0), (0, 1, 0), -90)
    raise ValueError(n)


def wall_point(wall, along, zc, face="inner"):
    if wall == "top":
        return (along, INNER_Y1 if face == "inner" else OUT_Y1, zc)
    if wall == "bottom":
        return (along, INNER_Y0 if face == "inner" else OUT_Y0, zc)
    if wall == "left":
        return (INNER_X0 if face == "inner" else OUT_X0, along, zc)
    if wall == "right":
        return (INNER_X1 if face == "inner" else OUT_X1, along, zc)
    raise ValueError(wall)


def gland_parts(size, wall, along, zc, grow=0.0):
    """inside locknut, thread stub (inside part) and outside body as solids.
    grow > 0 inflates nut/stub (used for keep-outs)."""
    if size == 16:
        ac, t, thr, body, d = M16_NUT_AC, M16_NUT_T, M16_THREAD_L, M16_BODY, 16.0
    else:
        ac, t, thr, body, d = M12_NUT_AC, M12_NUT_T, M12_THREAD_L, M12_BODY, 12.0
    n_in = WALL_NORMAL_IN[wall]
    n_out = tuple(-c for c in n_in)
    # locknut modelled as its across-corners cylinder = worst case for any rotation
    nut = cq.Workplane("XY").circle(ac / 2 + grow).extrude(t + grow)
    # thread: from the outer face through the wall into the cavity
    stub = cq.Workplane("XY").workplane(offset=-WALL).circle(d / 2 + grow).extrude(thr + grow)
    body_s = cq.Workplane("XY").circle(body[0] / 2).extrude(body[1])
    p_in = wall_point(wall, along, zc, "inner")
    p_out = wall_point(wall, along, zc, "outer")
    nut = orient_z_to(nut, n_in).translate(p_in)
    stub = orient_z_to(stub, n_in).translate(p_in)
    body_s = orient_z_to(body_s, n_out).translate(p_out)
    return nut, stub, body_s


def corner_columns():
    """(x, y) centres of the two lid-screw columns in the top corners"""
    return [(INNER_X0 + CORNER_COL_INSET, INNER_Y1 - CORNER_COL_INSET),
            (INNER_X1 - CORNER_COL_INSET, INNER_Y1 - CORNER_COL_INSET)]


def lid_screw_points():
    pts = [bxy(*h) for h in MOUNT_HOLES]
    return pts + corner_columns()


def hole_d():
    return INSERT_HOLE_D if INSERT_MODE == "heatset" else SELFTAP_HOLE_D


# -----------------------------------------------------------------------------
def make_base():
    inner_r = CORNER_R - WALL
    base = rrect(OUT_X0, OUT_Y0, OUT_X1, OUT_Y1, CORNER_R, 0, LID_UNDERSIDE)
    cavity = rrect(INNER_X0, INNER_Y0, INNER_X1, INNER_Y1, inner_r, FLOOR, LID_UNDERSIDE)
    base = base.cut(cavity)

    # PCB bosses: foot (cone) + column to the board underside
    for (bx, by) in MOUNT_HOLES:
        x, y = bxy(bx, by)
        foot_h = PCB_BOSS_FOOT_TOP - FLOOR
        foot = (cq.Workplane("XY").workplane(offset=FLOOR - 0.01).center(x, y)
                .circle(PCB_BOSS_FOOT_D / 2).workplane(offset=foot_h)
                .circle(PCB_BOSS_D / 2).loft())
        col = (cq.Workplane("XY").workplane(offset=FLOOR - 0.01).center(x, y)
               .circle(PCB_BOSS_D / 2).extrude(BOARD_BOT_Z - FLOOR + 0.01))
        base = base.union(foot).union(col)
        hole = (cq.Workplane("XY").workplane(offset=BOARD_BOT_Z - INSERT_DEPTH).center(x, y)
                .circle(hole_d() / 2).extrude(INSERT_DEPTH + 1))
        base = base.cut(hole)

    # lid-screw columns in the two top corners (full height)
    for (x, y) in corner_columns():
        col = (cq.Workplane("XY").workplane(offset=FLOOR - 0.01).center(x, y)
               .circle(CORNER_COL_D / 2).extrude(LID_UNDERSIDE - FLOOR + 0.01))
        # tie the column into both walls with a square back so there is no thin sliver
        sq = (cq.Workplane("XY").workplane(offset=FLOOR - 0.01)
              .center(x + (-1 if x < 45 else 1) * CORNER_COL_D / 4, y + CORNER_COL_D / 4)
              .rect(CORNER_COL_D / 2, CORNER_COL_D / 2).extrude(LID_UNDERSIDE - FLOOR + 0.01))
        base = base.union(col).union(sq)
        hole = (cq.Workplane("XY").workplane(offset=LID_UNDERSIDE - CORNER_INSERT_DEPTH).center(x, y)
                .circle(hole_d() / 2).extrude(CORNER_INSERT_DEPTH + 1))
        base = base.cut(hole)

    # gland holes
    for (_, size, wall, along, zc) in GLANDS:
        d = M16_HOLE_D if size == 16 else M12_HOLE_D
        base = base.cut(gland_hole_cutter(d, wall, along, zc))

    # USB notch in the right wall: from slot bottom up through the wall top (lid tab closes it)
    z0 = USB_Z - USB_SLOT_H / 2
    notch_h = LID_UNDERSIDE - z0 + 1.0
    notch = (cq.Workplane("YZ").workplane(offset=INNER_X1 - 0.5)
             .center(USB_Y, z0 + notch_h / 2).rect(USB_SLOT_W, notch_h).extrude(WALL + 1.0))
    notch = notch.edges("|X and <Z").fillet(USB_SLOT_R)
    base = base.cut(notch)

    # wall-mount holes with a countersink from inside on a local pad
    for (x, y) in WALL_MOUNT:
        pad = (cq.Workplane("XY").workplane(offset=FLOOR - 0.01).center(x, y)
               .circle(WALL_MOUNT_PAD_D / 2).extrude(WALL_MOUNT_PAD_H + 0.01))
        base = base.union(pad)
        top = FLOOR + WALL_MOUNT_PAD_H
        csk_depth = (WALL_MOUNT_CSK_D - WALL_MOUNT_HOLE_D) / 2
        thru = cq.Workplane("XY").workplane(offset=-1).center(x, y).circle(WALL_MOUNT_HOLE_D / 2).extrude(top + 2)
        csk = (cq.Workplane("XY").workplane(offset=top - csk_depth).center(x, y)
               .circle(WALL_MOUNT_HOLE_D / 2).workplane(offset=csk_depth + 0.01)
               .circle(WALL_MOUNT_CSK_D / 2 + 0.01).loft())
        base = base.cut(thru).cut(csk)

    # vents: vertical slots in the bottom wall (low-voltage side)
    if VENTS:
        for x in WALL_VENT_X:
            h = WALL_VENT_Z[1] - WALL_VENT_Z[0]
            w = WALL_VENT_W / 2   # rectangle with a 45 deg pointed roof (no bridge)
            pts = [(x - w, WALL_VENT_Z[0]), (x + w, WALL_VENT_Z[0]), (x + w, WALL_VENT_Z[1] - w),
                   (x, WALL_VENT_Z[1]), (x - w, WALL_VENT_Z[1] - w)]
            s = (cq.Workplane("XZ").workplane(offset=-(INNER_Y0 + 0.5))
                 .polyline(pts).close().extrude(WALL + 1.0))
            base = base.cut(s)
    return base


def lip_keepouts():
    """solids the lid lip must avoid (gland nuts/stubs + corner columns), grown by LIP_KEEPOUT"""
    k = []
    for (_, size, wall, along, zc) in GLANDS:
        nut, stub, _b = gland_parts(size, wall, along, zc, grow=LIP_KEEPOUT)
        k += [nut, stub]
    for (bx, by) in MOUNT_HOLES:   # PCB standoffs (hex across corners / 2 + keep-out)
        x, y = bxy(bx, by)
        k.append(cq.Workplane("XY").center(x, y)
                 .circle(STANDOFF_AF / math.cos(math.pi / 6) / 2 + LIP_KEEPOUT).extrude(TOTAL_H))
    for (x, y) in corner_columns():
        k.append(cq.Workplane("XY").center(x, y).circle(CORNER_COL_D / 2 + LIP_KEEPOUT)
                 .extrude(TOTAL_H))
        k.append(cq.Workplane("XY").center(x + (-1 if x < 45 else 1) * CORNER_COL_D / 4,
                                           y + CORNER_COL_D / 4)
                 .rect(CORNER_COL_D / 2 + 2 * LIP_KEEPOUT, CORNER_COL_D / 2 + 2 * LIP_KEEPOUT)
                 .extrude(TOTAL_H))
    return k


def make_lid():
    """lid in ASSEMBLY position (underside at LID_UNDERSIDE)"""
    inner_r = CORNER_R - WALL
    lid = rrect(OUT_X0, OUT_Y0, OUT_X1, OUT_Y1, CORNER_R, LID_UNDERSIDE, LID_T)

    # locating lip
    lo = LIP_GAP
    li = LIP_GAP + LIP_T
    outer = rrect(INNER_X0 + lo, INNER_Y0 + lo, INNER_X1 - lo, INNER_Y1 - lo,
                  max(inner_r - lo, 0.2), LID_UNDERSIDE - LIP_H, LIP_H + 0.01)
    inner = rrect(INNER_X0 + li, INNER_Y0 + li, INNER_X1 - li, INNER_Y1 - li,
                  max(inner_r - li, 0.2), LID_UNDERSIDE - LIP_H - 1, LIP_H + 2)
    lip = outer.cut(inner)
    for k in lip_keepouts():
        lip = lip.cut(k)
    lid = lid.union(lip)

    # pads that meet the PCB standoffs
    st_top = BOARD_TOP_Z + STANDOFF_LEN
    pad_h = LID_UNDERSIDE - (st_top + LID_PAD_GAP)
    for (bx, by) in MOUNT_HOLES:
        x, y = bxy(bx, by)
        if pad_h > 0.05:
            pad = (cq.Workplane("XY").workplane(offset=LID_UNDERSIDE - pad_h).center(x, y)
                   .circle(LID_PAD_D / 2).extrude(pad_h + 0.01))
            lid = lid.union(pad)

    # USB tab: fills the right-wall notch above the slot
    z_top_slot = USB_Z + USB_SLOT_H / 2
    tab_h = LID_UNDERSIDE - z_top_slot
    tab = (cq.Workplane("YZ").workplane(offset=INNER_X1 + USB_TAB_CLEAR)
           .center(USB_Y, z_top_slot + (tab_h + 0.01) / 2)
           .rect(USB_SLOT_W - 2 * USB_TAB_CLEAR, tab_h + 0.01).extrude(WALL - USB_TAB_CLEAR))
    tab = tab.edges("|X and <Z").fillet(USB_SLOT_R)
    lid = lid.union(tab)

    # screw holes + countersinks (countersink at the outer top face)
    top = LID_UNDERSIDE + LID_T
    csk_depth = (LID_CSK_D - LID_SCREW_HOLE_D) / 2
    for (x, y) in lid_screw_points():
        thru = (cq.Workplane("XY").workplane(offset=LID_UNDERSIDE - 3).center(x, y)
                .circle(LID_SCREW_HOLE_D / 2).extrude(LID_T + 4))
        csk = (cq.Workplane("XY").workplane(offset=top - csk_depth).center(x, y)
               .circle(LID_SCREW_HOLE_D / 2).workplane(offset=csk_depth + 0.01)
               .circle(LID_CSK_D / 2 + 0.01).loft())
        lid = lid.cut(thru).cut(csk)

    # LED windows
    for (bx, by) in LEDS:
        x, y = bxy(bx, by)
        if LED_WINDOW == "thin":
            depth = LID_T - LED_SKIN
            p = (cq.Workplane("XY").workplane(offset=LID_UNDERSIDE - 1).center(x, y)
                 .circle(LED_WINDOW_D / 2).extrude(depth + 1))
        else:
            p = (cq.Workplane("XY").workplane(offset=LID_UNDERSIDE - 1).center(x, y)
                 .circle(2.0 / 2).extrude(LID_T + 2))
        lid = lid.cut(p)

    # vents over the NodeMCU (low-voltage half)
    if VENTS:
        L = LID_VENT_Y[1] - LID_VENT_Y[0]
        for x in LID_VENT_X:
            s = (cq.Workplane("XY").workplane(offset=LID_UNDERSIDE - 1)
                 .center(x, (LID_VENT_Y[0] + LID_VENT_Y[1]) / 2)
                 .slot2D(L, LID_VENT_W, angle=90).extrude(LID_T + 2))
            lid = lid.cut(s)

    # debossed warning text on the outer face
    if TEXT:
        txt = (cq.Workplane("XY").workplane(offset=top - TEXT_DEPTH)
               .center(*TEXT_POS)
               .text(TEXT, TEXT_SIZE, TEXT_DEPTH + 0.5, kind="bold", combine=False,
                     halign="center", valign="center"))
        lid = lid.cut(txt)
    return lid


def lid_print_orientation(lid):
    """flip the lid top-face-down onto z = 0"""
    return lid.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, TOTAL_H))


# --- accessories (for fit check / assembly / render) ------------------------
def make_standoffs():
    out = []
    for (bx, by) in MOUNT_HOLES:
        x, y = bxy(bx, by)
        hexb = (cq.Workplane("XY").workplane(offset=BOARD_TOP_Z).center(x, y)
                .polygon(6, STANDOFF_AF / math.cos(math.pi / 6)).extrude(STANDOFF_LEN))
        male = (cq.Workplane("XY").workplane(offset=BOARD_TOP_Z - STANDOFF_MALE).center(x, y)
                .circle(1.5).extrude(STANDOFF_MALE))
        out.append(hexb.union(male))
    return out


def make_glands():
    """list of (name, nut, stub, body)"""
    res = []
    for (name, size, wall, along, zc) in GLANDS:
        nut, stub, body = gland_parts(size, wall, along, zc)
        res.append((name, nut, stub, body))
    return res


def make_usb_plug():
    """12 (Y) x 7 (Z) x 25 (X) overmould, front face at the socket face x = 90.6"""
    return (cq.Workplane("XY").box(25.0, 12.0, 7.0)
            .translate((90.6 + 12.5, USB_Y, USB_Z)))


def make_nodemcu():
    """NodeMCU dev board as solids (its model is VRML-only, so it is missing from the STEP)"""
    zb = BOARD_TOP_Z + 8.5
    zt = BOARD_TOP_Z + 10.1

    def box(x0, x1, y0, y1, z0, z1):
        return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0)
                .translate(((x0 + x1) / 2, -(y0 + y1) / 2, (z0 + z1) / 2)))
    return {
        "NodeMCU PCB": box(41.5, 89.8, 59.23, 84.63, zb, zt),
        "NodeMCU ESP-12 + shield": box(41.5, 65.5, 63.9, 79.9, zt, BOARD_TOP_Z + 14.5),
        "NodeMCU micro-USB": box(84.3, 90.6, 68.0, 75.8, zt, BOARD_TOP_Z + 12.9),
        # envelope for buttons / USB-UART chip / regulator (not in the brief; conservative)
        "NodeMCU top parts (envelope)": box(65.5, 84.3, 59.23, 84.63, zt, zt + 3.5),
    }


def make_keepouts():
    """estimated volumes that must stay free (not physical parts)"""
    def box(x0, x1, y0, y1, z0, z1):
        return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0)
                .translate(((x0 + x1) / 2, -(y0 + y1) / 2, (z0 + z1) / 2)))
    return {
        # JST-XH 4-pin housing mated into J6 (approx. 11 mm above the board)
        "J6 mated XH plug (est.)": box(7.35, 19.75, 79.15, 84.9, BOARD_TOP_Z, BOARD_TOP_Z + 11.0),
    }


def build():
    return make_base(), make_lid()


if __name__ == "__main__":
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    base, lid = build()
    cq.exporters.export(base, os.path.join(here, "case_base.step"))
    cq.exporters.export(base, os.path.join(here, "case_base.stl"), tolerance=0.02, angularTolerance=0.1)
    lid_p = lid_print_orientation(lid)
    cq.exporters.export(lid_p, os.path.join(here, "case_lid.step"))
    cq.exporters.export(lid_p, os.path.join(here, "case_lid.stl"), tolerance=0.02, angularTolerance=0.1)
    bb = base.val().BoundingBox()
    print(f"base bbox  X {bb.xmin:.2f}..{bb.xmax:.2f}  Y {bb.ymin:.2f}..{bb.ymax:.2f}  Z {bb.zmin:.2f}..{bb.zmax:.2f}")
    bb = lid.val().BoundingBox()
    print(f"lid  bbox  X {bb.xmin:.2f}..{bb.xmax:.2f}  Y {bb.ymin:.2f}..{bb.ymax:.2f}  Z {bb.zmin:.2f}..{bb.zmax:.2f}")
    print("valid:", base.val().isValid(), lid.val().isValid())
