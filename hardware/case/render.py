r"""
PNG views of the assembly (matplotlib on the tessellated B-rep).
Run:  .venv\\Scripts\\python.exe render.py
Writes render_exploded_iso.png, render_top_lid_hidden.png, render_assembled_iso.png,
render_section_usb.png, render_section_m12_5v.png, render_section_m16.png
"""
import os

import cadquery as cq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import case as C
from fit_check import build_scene

HERE = os.path.dirname(os.path.abspath(__file__))

COL = {
    "base": (0.82, 0.82, 0.78),
    "lid": (0.95, 0.55, 0.15),
    "pcb": (0.10, 0.50, 0.25),
    "part": (0.30, 0.30, 0.36),
    "relay": (0.15, 0.35, 0.75),
    "term": (0.10, 0.55, 0.30),
    "nodemcu": (0.10, 0.15, 0.45),
    "plug": (0.08, 0.08, 0.08),
    "gland": (0.35, 0.35, 0.35),
    "standoff": (0.95, 0.95, 0.95),
    "keepout": (0.90, 0.20, 0.20),
}


def tri(shape, tol=0.15, max_edge=None):
    v, t = shape.tessellate(tol, 0.3)
    v = np.array([(p.x, p.y, p.z) for p in v])
    t = np.array(t)
    if len(t) == 0:
        return np.zeros((0, 3, 3))
    T = v[t]
    if max_edge:
        T = subdivide(T, max_edge)
    return T


def subdivide(T, max_edge):
    """split long triangles (4-way midpoint) so the painter's sort in matplotlib behaves"""
    out = []
    todo = T
    for _ in range(8):
        e = np.max(np.stack([np.linalg.norm(todo[:, 1] - todo[:, 0], axis=1),
                             np.linalg.norm(todo[:, 2] - todo[:, 1], axis=1),
                             np.linalg.norm(todo[:, 0] - todo[:, 2], axis=1)]), axis=0)
        ok = e <= max_edge
        out.append(todo[ok])
        big = todo[~ok]
        if len(big) == 0:
            break
        a, b, c = big[:, 0], big[:, 1], big[:, 2]
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        todo = np.concatenate([np.stack([a, ab, ca], 1), np.stack([ab, b, bc], 1),
                               np.stack([ca, bc, c], 1), np.stack([ab, bc, ca], 1)])
    else:
        out.append(todo)
    return np.concatenate(out)


def board_color(n):
    if n == "PCB":
        return COL["pcb"]
    if n.startswith("K"):
        return COL["relay"]
    if n.startswith("J"):
        return COL["term"]
    return COL["part"]


def scene_items(sc, lid_dz=0.0, show_lid=True, explode=0.0):
    items = []
    items.append((sc["base"], COL["base"]))
    if show_lid:
        items.append((sc["lid"].translate(cq.Vector(0, 0, lid_dz)), COL["lid"]))
    bz = explode * 0.4
    for n, s in sc["board"]:
        items.append((s.translate(cq.Vector(0, 0, bz)), board_color(n)))
    for n, s in sc["nodemcu"]:
        items.append((s.translate(cq.Vector(0, 0, bz)), COL["nodemcu"]))
    for n, s in sc["standoffs"]:
        items.append((s.translate(cq.Vector(0, 0, bz)), COL["standoff"]))
    items.append((sc["plug"].translate(cq.Vector(explode * 0.6, 0, 0)), COL["plug"]))
    for (name, nut, stub, body) in sc["glands"]:
        for s in (nut, stub, body):
            items.append((s, COL["gland"]))
    return items


def render3d(items, fname, elev, azim, title, xlim=None, ylim=None, zlim=None, alpha_map=None):
    polys, cols = [], []
    light = np.array([0.4, -0.5, 0.75])
    light /= np.linalg.norm(light)
    for shape, c in items:
        T = tri(shape, max_edge=4.0)
        if len(T) == 0:
            continue
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        nn = np.linalg.norm(n, axis=1, keepdims=True)
        nn[nn == 0] = 1
        n = n / nn
        shade = 0.45 + 0.55 * np.abs(n @ light)
        a = 1.0
        if alpha_map and c in alpha_map:
            a = alpha_map[c]
        for k in range(len(T)):
            polys.append(T[k])
            cols.append((c[0] * shade[k], c[1] * shade[k], c[2] * shade[k], a))
    fig = plt.figure(figsize=(11, 9), dpi=130)
    ax = fig.add_subplot(111, projection="3d", proj_type="ortho")
    pc = Poly3DCollection(polys, facecolors=cols, edgecolors="none", linewidths=0)
    ax.add_collection3d(pc)
    allp = np.concatenate([p for p in polys])
    lo, hi = allp.min(0), allp.max(0)
    xlim = xlim or (lo[0], hi[0])
    ylim = ylim or (lo[1], hi[1])
    zlim = zlim or (lo[2], hi[2])
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_zlim(*zlim)
    ax.set_box_aspect((xlim[1] - xlim[0], ylim[1] - ylim[0], zlim[1] - zlim[0]))
    ax.view_init(elev=elev, azim=azim)
    ax.set_xlabel("X (board x)"); ax.set_ylabel("Y (-board y)"); ax.set_zlabel("Z")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, fname))
    plt.close(fig)
    print("wrote", fname)


def section(sc, axis, value, fname, title, extra_lines=()):
    """2D section: intersect every solid with a thin slab normal to `axis`."""
    t = 0.05
    if axis == "y":
        slab = cq.Workplane("XY").box(400, t, 400).translate((0, value, 0)).val()
        proj = lambda P: P[:, :, [0, 2]]
        xl = "X (mm)"
    else:
        slab = cq.Workplane("XY").box(t, 400, 400).translate((value, 0, 0)).val()
        proj = lambda P: P[:, :, [1, 2]]
        xl = "Y (mm)  (+Y = top wall)"
    items = []
    items.append((sc["base"], COL["base"], "base"))
    items.append((sc["lid"], COL["lid"], "lid"))
    for n, s in sc["board"]:
        items.append((s, board_color(n), n))
    for n, s in sc["nodemcu"]:
        items.append((s, COL["nodemcu"], n))
    for n, s in sc["standoffs"]:
        items.append((s, COL["standoff"], n))
    items.append((sc["plug"], COL["plug"], "USB plug"))
    for (name, nut, stub, body) in sc["glands"]:
        items += [(nut, COL["gland"], name), (stub, (0.5, 0.5, 0.5), name), (body, COL["gland"], name)]
    for n, s in sc["keepouts"]:
        items.append((s, COL["keepout"], n))
    fig, ax = plt.subplots(figsize=(13, 5.5), dpi=130)
    for s, c, n in items:
        bb = s.BoundingBox()
        lo, hi = (bb.ymin, bb.ymax) if axis == "y" else (bb.xmin, bb.xmax)
        if not (lo - 0.1 <= value <= hi + 0.1):
            continue
        try:
            sec = s.intersect(slab)
        except Exception:
            continue
        if sec.Volume() <= 0:
            continue
        T = tri(sec, 0.05)
        if len(T) == 0:
            continue
        P = proj(T)
        alpha = 0.35 if c == COL["keepout"] else 1.0
        ax.add_collection(PolyCollection(P, facecolors=[c + (alpha,)], edgecolors=[c + (alpha,)], linewidths=0.2))
    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_xlabel(xl); ax.set_ylabel("Z (mm)")
    ax.axhline(C.LID_UNDERSIDE, color="orange", lw=0.5, ls="--")
    ax.axhline(C.FLOOR, color="grey", lw=0.5, ls="--")
    for (txt, x, y) in extra_lines:
        ax.annotate(txt, (x, y), fontsize=8)
    ax.set_title(title)
    ax.grid(True, lw=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, fname))
    plt.close(fig)
    print("wrote", fname)


def main():
    sc = build_scene()
    # exploded iso
    render3d(scene_items(sc, lid_dz=35, explode=0), "render_exploded_iso.png", 28, -58,
             "Exploded iso: lid raised 35 mm (orange), base, board + NodeMCU, standoffs, glands, USB plug")
    render3d(scene_items(sc, show_lid=True), "render_assembled_iso.png", 30, -125,
             "Assembled (lid on), from the bottom-left corner: 5 V gland (left wall), vents (bottom wall), sensor gland + USB plug (right wall)")
    render3d(scene_items(sc, show_lid=False), "render_top_lid_hidden.png", 90, -90,
             "Top view, lid hidden (board top edge = +Y = top wall with the M16 glands)")
    render3d(scene_items(sc, show_lid=False), "render_iso_left_lid_hidden.png", 35, -150,
             "Lid hidden, from the left: M12 5 V gland beside J1, PCB standoffs")
    section(sc, "y", C.USB_Y, "render_section_usb.png",
            f"Section Y = {C.USB_Y:.2f} (through the micro-USB socket and slot), looking from the bottom wall")
    section(sc, "y", -46.0, "render_section_m12_5v.png",
            "Section Y = -46.0 (through the M12 5 V gland, left) - also cuts near the M12 sensor gland (right, Y=-44)")
    section(sc, "x", 25.0, "render_section_m16.png",
            "Section X = 25.0 (through M16 gland A in the top wall, right of picture = top wall)")


if __name__ == "__main__":
    main()
