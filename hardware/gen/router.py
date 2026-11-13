"""Small 2-layer grid router (A* with 45-degree moves, turn penalties and vias).

Works in board-relative mm. Obstacles are rasterised per net with that net's
clearance + half track width, so any path found is DRC-clean by construction
(up to grid rounding, which the margin absorbs).
"""
import heapq
import math

import numpy as np

G = 0.25                      # grid pitch, mm
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
STEP = [1.0, math.sqrt(2)] * 4
VIA_COST = 14.0               # in grid steps (3.5 mm)
TURN_45 = 0.6
TURN_90 = 2.0
LAYER_BIAS = [1.0, 1.06]      # slight preference for the top layer


class Item:
    """An obstacle / copper item.

    kind: 'circle' (x, y, r), 'rect' (x1, y1, x2, y2), 'seg' (x1, y1, x2, y2, r)
    layers: tuple of layer indices (0 = F.Cu, 1 = B.Cu)
    net: net name or None
    """

    def __init__(self, kind, geom, layers, net, cls="Default"):
        self.kind, self.geom, self.layers, self.net, self.cls = kind, geom, layers, net, cls

    def bbox(self, infl):
        g = self.geom
        if self.kind == "circle":
            x, y, r = g
            return x - r - infl, y - r - infl, x + r + infl, y + r + infl
        if self.kind == "rect":
            return g[0] - infl, g[1] - infl, g[2] + infl, g[3] + infl
        x1, y1, x2, y2, r = g
        return min(x1, x2) - r - infl, min(y1, y2) - r - infl, max(x1, x2) + r + infl, max(y1, y2) + r + infl

    def dist(self, X, Y):
        """Distance from points to the item's copper edge (<= 0 inside)."""
        g = self.geom
        if self.kind == "circle":
            return np.hypot(X - g[0], Y - g[1]) - g[2]
        if self.kind == "rect":
            dx = np.maximum(np.maximum(g[0] - X, X - g[2]), 0)
            dy = np.maximum(np.maximum(g[1] - Y, Y - g[3]), 0)
            inside = (X >= g[0]) & (X <= g[2]) & (Y >= g[1]) & (Y <= g[3])
            return np.where(inside, -1.0, np.hypot(dx, dy))
        x1, y1, x2, y2, r = g
        vx, vy = x2 - x1, y2 - y1
        L2 = vx * vx + vy * vy
        if L2 == 0:
            return np.hypot(X - x1, Y - y1) - r
        t = np.clip(((X - x1) * vx + (Y - y1) * vy) / L2, 0, 1)
        return np.hypot(X - (x1 + t * vx), Y - (y1 + t * vy)) - r


class Router:
    def __init__(self, width, height, clearance_fn, edge_clear=0.5):
        self.W, self.H = width, height
        self.nx = int(round(width / G)) + 1
        self.ny = int(round(height / G)) + 1
        self.items = []
        self.edges = []            # Items (layers both) representing board edges / slots
        self.clearance_fn = clearance_fn
        self.edge_clear = edge_clear
        xs = np.arange(self.nx) * G
        ys = np.arange(self.ny) * G
        self.X, self.Y = np.meshgrid(xs, ys, indexing="ij")
        self.routes = []           # (net, layer, [(x, y), ...], width)
        self.vias = []             # (net, x, y, diameter, drill)

    # ---- rasterising -----------------------------------------------------------
    def _mark(self, grid, item, infl):
        x1, y1, x2, y2 = item.bbox(infl)
        i1, i2 = max(0, int(math.floor(x1 / G))), min(self.nx - 1, int(math.ceil(x2 / G)))
        j1, j2 = max(0, int(math.floor(y1 / G))), min(self.ny - 1, int(math.ceil(y2 / G)))
        if i1 > i2 or j1 > j2:
            return
        X = self.X[i1:i2 + 1, j1:j2 + 1]
        Y = self.Y[i1:i2 + 1, j1:j2 + 1]
        grid[i1:i2 + 1, j1:j2 + 1] |= item.dist(X, Y) < infl

    def blocked(self, net, cls, half):
        """Per-layer boolean maps of cells where a track/via centre may not go."""
        maps = [np.zeros((self.nx, self.ny), bool) for _ in range(2)]
        # board edge band
        m = self.edge_clear + half
        band = (self.X < m) | (self.X > self.W - m) | (self.Y < m) | (self.Y > self.H - m)
        for L in range(2):
            maps[L] |= band
        for e in self.edges:
            for L in range(2):
                self._mark(maps[L], e, self.edge_clear + half)
        for it in self.items:
            if it.net is not None and it.net == net:
                continue
            c = self.clearance_fn(cls, it.cls) + half
            for L in it.layers:
                self._mark(maps[L], it, c)
        return maps

    def cells_of(self, item):
        """Cells covered by the item's copper (for goal sets)."""
        grid = np.zeros((self.nx, self.ny), bool)
        self._mark(grid, item, 1e-6)
        if not grid.any():
            gx, gy = self.snap(*item.geom[:2])
            grid[gx, gy] = True
        return grid

    def snap(self, x, y):
        return (min(self.nx - 1, max(0, int(round(x / G)))), min(self.ny - 1, max(0, int(round(y / G)))))

    # ---- search ------------------------------------------------------------------
    def astar(self, starts, goal_maps, target_xy, block, via_block, region):
        """starts: list of (layer, i, j). goal_maps: per-layer bool arrays."""
        i_lo, j_lo, i_hi, j_hi = region
        tx, ty = target_xy
        tgi, tgj = tx / G, ty / G

        def h(i, j):
            dx, dy = abs(i - tgi), abs(j - tgj)
            return (max(dx, dy) - min(dx, dy)) + math.sqrt(2) * min(dx, dy)

        openh = []
        best = {}
        came = {}
        for (L, i, j) in starts:
            s = (L, i, j, 8)
            best[s] = 0.0
            heapq.heappush(openh, (h(i, j), 0.0, s))
        expanded = 0
        while openh:
            f, g, s = heapq.heappop(openh)
            if best.get(s, 1e18) < g - 1e-9:
                continue
            L, i, j, d = s
            if goal_maps[L][i, j] and g > 0:
                path = [s]
                while path[-1] in came:
                    path.append(came[path[-1]])
                return path[::-1]
            expanded += 1
            if expanded > 600000:
                return None
            # moves
            for nd, (di, dj) in enumerate(DIRS):
                if d != 8:
                    diff = min((nd - d) % 8, (d - nd) % 8)
                    if diff > 2:
                        continue
                    tc = 0 if diff == 0 else (TURN_45 if diff == 1 else TURN_90)
                else:
                    tc = 0
                ni, nj = i + di, j + dj
                if ni < i_lo or ni > i_hi or nj < j_lo or nj > j_hi:
                    continue
                if block[L][ni, nj] and not goal_maps[L][ni, nj]:
                    continue
                if di and dj:   # no corner cutting
                    if block[L][i + di, j] and block[L][i, j + dj]:
                        continue
                ng = g + STEP[nd] * LAYER_BIAS[L] + tc
                ns = (L, ni, nj, nd)
                if ng < best.get(ns, 1e18):
                    best[ns] = ng
                    came[ns] = s
                    heapq.heappush(openh, (ng + h(ni, nj), ng, ns))
            # via
            if not via_block[i, j]:
                nL = 1 - L
                ns = (nL, i, j, d)
                ng = g + VIA_COST
                if ng < best.get(ns, 1e18):
                    best[ns] = ng
                    came[ns] = s
                    heapq.heappush(openh, (ng + h(i, j), ng, ns))
        return None

    # ---- public --------------------------------------------------------------------
    def add_item(self, item):
        self.items.append(item)

    def route_net(self, net, cls, pads, width, via_d, via_drill, margin=14.0):
        """pads: list of Items (copper of this net). Returns True if all joined."""
        half = width / 2
        block = self.blocked(net, cls, half)
        vblock_l = self.blocked(net, cls, via_d / 2)
        via_block = vblock_l[0] | vblock_l[1]

        # Prim-style ordering: start from the first pad, join nearest next.
        def centre(it):
            g = it.geom
            if it.kind == "rect":
                return ((g[0] + g[2]) / 2, (g[1] + g[3]) / 2)
            return (g[0], g[1])

        remaining = list(pads)
        tree_items = [remaining.pop(0)]
        goal = [np.zeros((self.nx, self.ny), bool) for _ in range(2)]

        def add_goal(it):
            cells = self.cells_of(it)
            for L in it.layers:
                goal[L] |= cells

        add_goal(tree_items[0])
        tree_pts = [centre(tree_items[0])]
        ok = True
        while remaining:
            # nearest remaining pad to any tree point
            best = None
            for it in remaining:
                c = centre(it)
                for p in tree_pts:
                    dd = math.hypot(c[0] - p[0], c[1] - p[1])
                    if best is None or dd < best[0]:
                        best = (dd, it, p)
            _, it, tgt = best
            remaining.remove(it)
            cx, cy = centre(it)
            si, sj = self.snap(cx, cy)
            starts = [(L, si, sj) for L in it.layers]
            for attempt_margin in (margin, margin * 2.5, 1e9):
                x1 = min(cx, tgt[0]) - attempt_margin
                y1 = min(cy, tgt[1]) - attempt_margin
                x2 = max(cx, tgt[0]) + attempt_margin
                y2 = max(cy, tgt[1]) + attempt_margin
                region = (max(1, int(x1 / G)), max(1, int(y1 / G)),
                          min(self.nx - 2, int(x2 / G)), min(self.ny - 2, int(y2 / G)))
                path = self.astar(starts, goal, tgt, block, via_block, region)
                if path:
                    break
            if not path:
                ok = False
                print(f"   FAILED to connect a pad of {net}")
                add_goal(it)
                tree_pts.append((cx, cy))
                continue
            self._commit(net, cls, path, width, via_d, via_drill, (cx, cy), goal, tree_pts)
            add_goal(it)
            tree_pts.append((cx, cy))
        return ok

    def _commit(self, net, cls, path, width, via_d, via_drill, start_xy, goal, tree_pts):
        # split into layer runs
        runs = []
        cur_L = path[0][0]
        cur = [(path[0][1], path[0][2])]
        for (L, i, j, d) in path[1:]:
            if L != cur_L:
                runs.append((cur_L, cur))
                x, y = cur[-1][0] * G, cur[-1][1] * G
                self.vias.append((net, x, y, via_d, via_drill))
                self.items.append(Item("circle", (x, y, via_d / 2), (0, 1), net, cls))
                cur_L = L
                cur = [(i, j)]
            else:
                cur.append((i, j))
        runs.append((cur_L, cur))
        for ri, (L, cells) in enumerate(runs):
            pts = [(c[0] * G, c[1] * G) for c in cells]
            if ri == 0:
                pts.insert(0, start_xy)     # start exactly on the pad centre
            pts = simplify(pts)
            if len(pts) < 2:
                continue
            self.routes.append((net, L, pts, width))
            for a, b in zip(pts, pts[1:]):
                seg = Item("seg", (a[0], a[1], b[0], b[1], width / 2), (L,), net, cls)
                self.items.append(seg)
                cells_ = self.cells_of(seg)
                goal[L] |= cells_
            tree_pts.extend(pts)


def simplify(pts):
    """Drop collinear points and duplicate points."""
    out = []
    for p in pts:
        if out and abs(p[0] - out[-1][0]) < 1e-9 and abs(p[1] - out[-1][1]) < 1e-9:
            continue
        out.append(p)
    if len(out) < 3:
        return out
    res = [out[0]]
    for k in range(1, len(out) - 1):
        a, b, c = res[-1], out[k], out[k + 1]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) > 1e-9:
            res.append(b)
    res.append(out[-1])
    return res
