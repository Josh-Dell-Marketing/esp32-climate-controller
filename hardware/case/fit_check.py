r"""
Fit check: places the KiCad STEP of the populated board (+ NodeMCU solids, USB plug,
gland locknuts/threads, PCB standoffs) in the case and computes real boolean
intersection volumes and minimum gaps. Also exports assembly.step.

Run:  .venv\\Scripts\\python.exe fit_check.py        (writes fit_check_results.json too)
"""
import json
import os
import sys
import time

import cadquery as cq
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool

import case as C

HERE = os.path.dirname(os.path.abspath(__file__))
STEP = os.path.normpath(os.path.join(HERE, "..", "build", "fab", "climate-controller.step"))
EPS_VOL = 1e-3   # mm^3; anything above this is reported as a collision


# -----------------------------------------------------------------------------
def load_board_step(path=STEP):
    """returns [(name, cq.Shape)] in the ASSEMBLY frame, plus the raw STEP frame info"""
    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    r = STEPCAFControl_Reader()
    r.SetNameMode(True)
    if r.ReadFile(path) != IFSelect_RetDone:
        raise RuntimeError("cannot read " + path)
    r.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    free = TDF_LabelSequence()
    st.GetFreeShapes(free)

    def name(l):
        n = TDataStd_Name()
        if l.FindAttribute(TDataStd_Name.GetID_s(), n):
            return n.Get().ToExtString()
        return "?"

    items = []

    def walk(l):
        comps = TDF_LabelSequence()
        st.GetComponents_s(l, comps)
        if comps.Length() == 0:
            sh = st.GetShape_s(l)
            if not sh.IsNull():
                items.append((name(l), cq.Shape.cast(sh)))
            return
        for i in range(1, comps.Length() + 1):
            walk(comps.Value(i))

    for i in range(1, free.Length() + 1):
        walk(free.Value(i))

    # explode into solids, rename the board
    raw = []
    for nm, sh in items:
        sols = sh.Solids()
        for k, s in enumerate(sols):
            n = nm if len(sols) == 1 else f"{nm}#{k}"
            raw.append((n, s))
    # identify the PCB = largest XY footprint, thin
    def fp(s):
        b = s.BoundingBox()
        return (b.xmax - b.xmin) * (b.ymax - b.ymin) if (b.zmax - b.zmin) < 2.0 else 0
    pcb_i = max(range(len(raw)), key=lambda i: fp(raw[i][1]))
    raw[pcb_i] = ("PCB", raw[pcb_i][1])
    # disambiguate duplicate names (U1 = the two female sockets)
    seen = {}
    out = []
    for n, s in raw:
        seen[n] = seen.get(n, 0) + 1
        out.append((n if seen[n] == 1 else f"{n}#{seen[n]}", s))

    pcb_bb = raw[pcb_i][1].BoundingBox()
    allbb = cq.Compound.makeCompound([s for _, s in out]).BoundingBox()
    frame = {
        "pcb_bbox_step": [round(v, 3) for v in (pcb_bb.xmin, pcb_bb.xmax, pcb_bb.ymin, pcb_bb.ymax, pcb_bb.zmin, pcb_bb.zmax)],
        "all_bbox_step": [round(v, 3) for v in (allbb.xmin, allbb.xmax, allbb.ymin, allbb.ymax, allbb.zmin, allbb.zmax)],
    }
    # frame verification (board top-left at STEP (50, -50), bottom at z = 0)
    ok = (abs(pcb_bb.xmin - 50) < 0.01 and abs(pcb_bb.xmax - 140) < 0.01 and
          abs(pcb_bb.ymin + 136) < 0.01 and abs(pcb_bb.ymax + 50) < 0.01 and abs(pcb_bb.zmin) < 0.01)
    frame["frame_as_expected"] = ok
    if not ok:
        raise RuntimeError(f"unexpected STEP frame: {frame}")
    dx, dy, dz = -pcb_bb.xmin, -pcb_bb.ymax, C.BOARD_BOT_Z - pcb_bb.zmin
    frame["step_to_assembly"] = [dx, dy, dz]
    moved = [(n, s.translate(cq.Vector(dx, dy, dz))) for n, s in out]
    return moved, frame


def shp(x):
    return x.val() if isinstance(x, cq.Workplane) else x


def bbox_overlap(a, b, tol=0.01):
    A, B = a.BoundingBox(), b.BoundingBox()
    return not (A.xmax < B.xmin - tol or B.xmax < A.xmin - tol or
                A.ymax < B.ymin - tol or B.ymax < A.ymin - tol or
                A.zmax < B.zmin - tol or B.zmax < A.zmin - tol)


def inter_vol(a, b):
    if not bbox_overlap(a, b):
        return 0.0
    try:
        return abs(a.intersect(b).Volume())
    except Exception as e:  # pragma: no cover
        print("  boolean failed:", e)
        return float("nan")


def dist(a, b):
    return a.distance(b)


def build_scene():
    base, lid = C.build()
    base, lid = shp(base), shp(lid)
    board, frame = load_board_step()
    nodemcu = [(k, shp(v)) for k, v in C.make_nodemcu().items()]
    keepouts = [(k, shp(v)) for k, v in C.make_keepouts().items()]
    plug = shp(C.make_usb_plug())
    standoffs = [(f"standoff @ board ({x}, {y})", shp(s)) for (x, y), s in zip(C.MOUNT_HOLES, C.make_standoffs())]
    glands = []
    for (name, nut, stub, body) in C.make_glands():
        glands.append((name, shp(nut), shp(stub), shp(body)))
    return dict(base=base, lid=lid, board=board, frame=frame, nodemcu=nodemcu,
                keepouts=keepouts, plug=plug, standoffs=standoffs, glands=glands)


def main():
    t0 = time.time()
    sc = build_scene()
    base, lid = sc["base"], sc["lid"]
    board = sc["board"]
    print("STEP frame:", sc["frame"])

    components = board + sc["nodemcu"]               # physical board-side parts
    board_side = components + sc["keepouts"] + [("USB plug 12x7x25", sc["plug"])]
    hardware = []
    for (name, nut, stub, body) in sc["glands"]:
        hardware += [(f"{name} locknut", nut), (f"{name} thread", stub)]
    hardware += sc["standoffs"]

    res = {"frame": sc["frame"], "collisions": [], "pairs_checked": 0}

    def check(label_a, a, items, skip=()):
        tot = 0.0
        for n, s in items:
            if n in skip:
                continue
            v = inter_vol(a, s)
            res["pairs_checked"] += 1
            if v > EPS_VOL or v != v:
                res["collisions"].append({"a": label_a, "b": n, "volume_mm3": round(v, 4)})
            tot += v if v == v else 0
        return tot

    vols = {}
    vols["base x board/components/NodeMCU/plug/keep-outs"] = check("base", base, board_side)
    vols["lid x board/components/NodeMCU/plug/keep-outs"] = check("lid", lid, board_side)
    vols["base x lid"] = check("base", base, [("lid", lid)])
    gl = []
    for (name, nut, stub, body) in sc["glands"]:
        gl += [(f"{name} locknut", nut), (f"{name} thread", stub)]
    tot = 0
    for n, s in gl:
        tot += check(n, s, board_side + [("lid", lid), ("base", base)] + sc["standoffs"])
    vols["gland locknuts+threads x board/plug/lid/base/standoffs"] = tot
    vols["gland outside bodies x base/lid"] = sum(
        check(f"{name} outside body", body, [("base", base), ("lid", lid)]) for (name, _, _, body) in sc["glands"])
    tot = 0
    for n, s in sc["standoffs"]:
        tot += check(n, s, board_side + [("lid", lid), ("base", base)])
    vols["PCB standoffs x board parts/lid/base (incl. PCB: M3 thread passes the 3.2 hole)"] = tot
    # straight insertion path of the USB plug: plug box extruded 40 mm outward
    path = shp(cq.Workplane("XY").box(40.0, 12.0, 7.0).translate((90.6 + 20.0, C.USB_Y, C.USB_Z)))
    vols["USB plug insertion path (40 mm sweep) x base/lid"] = check("USB plug path", path, [("base", base), ("lid", lid)])
    vols["NodeMCU solids x STEP parts (info)"] = sum(
        check(n, s, board, skip=()) for n, s in sc["nodemcu"])
    res["intersection_volumes_mm3"] = {k: round(v, 4) for k, v in vols.items()}

    # ------------------------------------------------------------------ gaps
    gaps = {}
    pcb = dict(board)["PCB"]
    pb = pcb.BoundingBox()
    # walls only = base minus everything inside the inner outline
    inner = shp(C.rrect(C.INNER_X0, C.INNER_Y0, C.INNER_X1, C.INNER_Y1, C.CORNER_R - C.WALL, -1, 100))
    walls = base.cut(inner)
    big = 500

    def side_box(side):
        if side == "left":
            return shp(cq.Workplane("XY").box(big, big, big).translate((C.INNER_X0 + 0.01 - big / 2, -43, 0)))
        if side == "right":
            return shp(cq.Workplane("XY").box(big, big, big).translate((C.INNER_X1 - 0.01 + big / 2, -43, 0)))
        if side == "top":
            return shp(cq.Workplane("XY").box(big, big, big).translate((45, C.INNER_Y1 - 0.01 + big / 2, 0)))
        return shp(cq.Workplane("XY").box(big, big, big).translate((45, C.INNER_Y0 + 0.01 - big / 2, 0)))

    for side in ("left", "right", "top", "bottom"):
        w = walls.intersect(side_box(side))
        gaps[f"PCB edge -> {side} wall (measured)"] = round(dist(pcb, w), 3)
    # tallest component to lid
    lid_under = C.LID_UNDERSIDE
    zmax = max(s.BoundingBox().zmax for n, s in components)
    tallest = max(components, key=lambda t: t[1].BoundingBox().zmax)
    gaps["tallest part"] = f"{tallest[0]} top z={tallest[1].BoundingBox().zmax:.2f} ({tallest[1].BoundingBox().zmax - C.BOARD_TOP_Z:.2f} above board top)"
    gaps["tallest part top -> lid underside plane"] = round(lid_under - zmax, 3)
    dl = sorted(((round(dist(lid, s), 3), n) for n, s in components), key=lambda t: t[0])
    gaps["min distance lid (incl. lip, pads, USB tab) -> any component"] = dl[0]
    gaps["5 closest components to the lid"] = dl[:5]
    # relays specifically
    relays = [(n, s) for n, s in board if n.startswith("K")]
    gaps["relays top -> lid underside"] = round(lid_under - max(s.BoundingBox().zmax for _, s in relays), 3)
    # terminals to top wall
    terms = [(n, s) for n, s in board if n in ("J2", "J3", "J4", "J5")]
    tw = walls.intersect(side_box("top"))
    gaps["terminal block bodies (wire openings) -> top wall inner face"] = round(
        C.INNER_Y1 - max(s.BoundingBox().ymax for _, s in terms), 3)
    gaps["terminal blocks -> top wall (measured min distance)"] = round(min(dist(s, tw) for _, s in terms), 3)
    j1 = dict(board)["J1"]
    gaps["J1 (5 V in) wire openings -> left wall inner face"] = round(j1.BoundingBox().xmin - C.INNER_X0, 3)
    # USB
    plug = sc["plug"]
    gaps["USB plug -> base (min)"] = round(dist(plug, base), 3)
    gaps["USB plug -> lid (min)"] = round(dist(plug, lid), 3)
    gaps["USB plug front face -> socket face"] = round(plug.BoundingBox().xmin - dict(sc["nodemcu"])["NodeMCU micro-USB"].BoundingBox().xmax, 3)
    # glands
    for (name, nut, stub, body) in sc["glands"]:
        dmin = min((round(dist(nut, s), 3), n) for n, s in components + sc["standoffs"])
        dmin2 = min((round(dist(stub, s), 3), n) for n, s in components + sc["standoffs"])
        gaps[f"{name}: locknut -> nearest part"] = dmin
        gaps[f"{name}: thread -> nearest part"] = dmin2
        gaps[f"{name}: locknut -> lid"] = round(dist(nut, lid), 3)
        bbn = nut.BoundingBox()
        gaps[f"{name}: locknut -> floor top"] = round(bbn.zmin - C.FLOOR, 3)
    for n, s in sc["standoffs"]:
        others = [(round(dist(s, o), 3), on) for on, o in components if on != "PCB"]
        gaps[f"{n} -> nearest component"] = min(others)
    gaps["NodeMCU micro-USB socket -> base (sits in the slot)"] = round(
        dist(dict(sc["nodemcu"])["NodeMCU micro-USB"], base), 3)
    db = sorted(((round(dist(base, s), 3), n) for n, s in components
                 if n != "PCB" and not n.startswith("U1")), key=lambda t: t[0])
    gaps["5 closest components to the base (excl. PCB/sockets)"] = db[:5]
    for n, s in sc["keepouts"]:
        gaps[f"{n} -> lid"] = round(dist(s, lid), 3)
    # leads to floor
    zmin = min(s.BoundingBox().zmin for n, s in components)
    gaps["lowest lead tip -> floor top"] = round(zmin - C.FLOOR, 3)
    gaps["PCB bottom -> floor top"] = round(pb.zmin - C.FLOOR, 3)
    res["gaps_mm"] = gaps

    # ------------------------------------------------------------------ outer dims
    ab = cq.Compound.makeCompound([base, lid]).BoundingBox()
    dims = (round(ab.xmax - ab.xmin, 3), round(ab.ymax - ab.ymin, 3), round(ab.zmax - ab.zmin, 3))
    res["outer_dims_mm"] = dims
    res["outer_dims_ok"] = dims[0] <= 100.0 and dims[1] <= 100.0 and dims[2] <= 30.0
    res["base_valid"], res["lid_valid"] = base.isValid(), lid.isValid()
    res["base_volume_cm3"] = round(base.Volume() / 1000, 2)
    res["lid_volume_cm3"] = round(lid.Volume() / 1000, 2)
    res["PASS"] = (not res["collisions"]) and res["outer_dims_ok"]
    res["runtime_s"] = round(time.time() - t0, 1)

    # ------------------------------------------------------------------ assembly export
    asm = cq.Assembly(name="climate-controller-case")
    asm.add(base, name="case_base", color=cq.Color(0.85, 0.85, 0.82))
    asm.add(lid, name="case_lid", color=cq.Color(0.95, 0.55, 0.15, 0.6))
    for n, s in board:
        nm = n.replace("#", "_")
        col = cq.Color(0.1, 0.45, 0.2) if n == "PCB" else cq.Color(0.25, 0.25, 0.3)
        asm.add(s, name=f"board_{nm}", color=col)
    for n, s in sc["nodemcu"]:
        asm.add(s, name=n.replace(" ", "_").replace("(", "").replace(")", "").replace("+", "and").replace("-", "_"),
                color=cq.Color(0.1, 0.2, 0.6))
    asm.add(sc["plug"], name="usb_plug", color=cq.Color(0.1, 0.1, 0.1))
    for i, (n, s) in enumerate(sc["standoffs"]):
        asm.add(s, name=f"standoff_{i+1}", color=cq.Color(0.9, 0.9, 0.9))
    for i, (name, nut, stub, body) in enumerate(sc["glands"]):
        tag = name.replace(" ", "_")
        asm.add(nut, name=f"{tag}_locknut", color=cq.Color(0.2, 0.2, 0.2))
        asm.add(stub, name=f"{tag}_thread", color=cq.Color(0.3, 0.3, 0.3))
        asm.add(body, name=f"{tag}_body", color=cq.Color(0.2, 0.2, 0.2))
    asm.save(os.path.join(HERE, "assembly.step"))

    with open(os.path.join(HERE, "fit_check_results.json"), "w") as f:
        json.dump(res, f, indent=2, default=str)

    print(json.dumps(res, indent=2, default=str))
    return 0 if res["PASS"] else 1


if __name__ == "__main__":
    sys.exit(main())
