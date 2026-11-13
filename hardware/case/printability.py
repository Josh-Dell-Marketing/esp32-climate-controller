r"""
Overhang check on the parts in PRINT orientation (base floor-down, lid top-face-down).
Flags every downward-facing triangle steeper than 45 deg from vertical that is not
on the bed, groups them into clusters and reports area + location.
Run:  .venv\Scripts\python.exe printability.py
"""
import json
import os

import numpy as np

import case as C

HERE = os.path.dirname(os.path.abspath(__file__))
LIMIT_DEG = 45.0
TOL_DEG = 0.5      # facet noise on exact-45 deg cones (countersinks, boss feet)


def overhangs(shape, tol=0.05):
    """per face: tessellate, pre-select steep downward facets, then confirm with the EXACT
    B-rep surface normal at the facet centroid (removes facet noise on cones)."""
    import cadquery as cq
    zmin = shape.BoundingBox().zmin
    lim = -np.sin(np.radians(LIMIT_DEG + TOL_DEG))
    cents, areas = [], []
    for f in shape.Faces():
        v, t = f.tessellate(tol, 0.2)
        if not t:
            continue
        v = np.array([(p.x, p.y, p.z) for p in v])
        T = v[np.array(t)]
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        ar = np.linalg.norm(n, axis=1) / 2
        nz = n[:, 2] / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
        cz = T[:, :, 2].mean(1)
        cand = np.where((np.abs(nz) > 0.5) & (cz > zmin + 0.05) & (ar > 1e-6))[0]
        for i in cand:
            c = T[i].mean(0)
            ex = f.normalAt(cq.Vector(*c))
            # facet winding tells us outward side; exact normal fixes the angle
            sign = 1.0 if (ex.z * nz[i]) >= 0 else -1.0
            if sign * ex.z < lim:
                cents.append(c)
                areas.append(ar[i])
    cent = np.array(cents) if cents else np.zeros((0, 3))
    a = np.array(areas)
    # cluster by 3 mm grid
    clusters = {}
    for c, ar in zip(cent, a):
        k = tuple(np.round(c / 3.0).astype(int))
        clusters.setdefault(k, [np.zeros(3), 0.0, []])
        clusters[k][0] += c * ar
        clusters[k][1] += ar
        clusters[k][2].append(c)
    # merge neighbouring grid cells
    keys = list(clusters)
    parent = {k: k for k in keys}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    ks = set(keys)
    for k in keys:
        for d in [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, -1, 0)]:
            nb = (k[0] + d[0], k[1] + d[1], k[2] + d[2])
            if nb in ks:
                parent[find(k)] = find(nb)
    groups = {}
    for k in keys:
        r = find(k)
        g = groups.setdefault(r, [np.zeros(3), 0.0, [], []])
        g[0] += clusters[k][0]
        g[1] += clusters[k][1]
        g[2] += clusters[k][2]
    out = []
    for g in groups.values():
        pts = np.array(g[2])
        out.append({"centre": [round(x, 1) for x in (g[0] / g[1])],
                    "area_mm2": round(g[1], 2),
                    "extent_mm": [round(x, 1) for x in (pts.max(0) - pts.min(0))]})
    out.sort(key=lambda d: -d["area_mm2"])
    return float(a.sum()), out


def main():
    base, lid = C.build()
    lid_p = C.lid_print_orientation(lid)
    res = {}
    for name, s in (("base (floor down)", base.val()), ("lid (top face down)", lid_p.val())):
        tot, groups = overhangs(s)
        res[name] = {"total_overhang_area_mm2": round(tot, 2), "clusters": groups}
        print(f"\n{name}: {tot:.1f} mm2 steeper than {LIMIT_DEG} deg, {len(groups)} clusters")
        for g in groups:
            print("  ", g)
    with open(os.path.join(HERE, "printability_results.json"), "w") as f:
        json.dump(res, f, indent=2)


if __name__ == "__main__":
    main()
