"""Topology builder: turn stacked 2-D cross-sections into a closed B-rep mesh.

A :class:`Solid` is a watertight, outward-oriented manifold made of planar
faces.  Cap faces may carry holes (inner loops); side walls are triangulated so
they stay planar even when the section twists (helical gears).

Input convention for :func:`build_extrusion`
--------------------------------------------
``layers`` is an ordered list (increasing z) of ``(z, loops)`` where ``loops``
is ``[outer, hole0, hole1, ...]``.  The outer loop must be CCW, holes CW (the
standard positive-area-outer / negative-area-hole convention).  Every layer
must have the same number of loops and the same number of points per loop so
that consecutive layers can be connected.
"""

from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

XYZ = Tuple[float, float, float]
XY = Tuple[float, float]


def _sub(a: XYZ, b: XYZ) -> XYZ:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: XYZ, b: XYZ) -> XYZ:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a: XYZ) -> XYZ:
    m = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    if m < 1e-12:
        return (0.0, 0.0, 1.0)
    return (a[0] / m, a[1] / m, a[2] / m)


class Face:
    """A planar face: ``loops[0]`` is the outer bound, the rest are holes."""

    __slots__ = ("loops", "normal", "point")

    def __init__(self, loops: List[List[int]], normal: XYZ, point: XYZ):
        self.loops = loops
        self.normal = normal
        self.point = point


class Solid:
    """A closed, outward-oriented manifold B-rep made of planar faces."""

    def __init__(self, name: str = "solid"):
        self.name = name
        self.verts: List[XYZ] = []
        self.faces: List[Face] = []
        self._vcache: dict = {}

    def add_vertex(self, p: XYZ) -> int:
        key = (round(p[0], 7), round(p[1], 7), round(p[2], 7))
        i = self._vcache.get(key)
        if i is None:
            i = len(self.verts)
            self.verts.append((float(p[0]), float(p[1]), float(p[2])))
            self._vcache[key] = i
        return i

    def add_face(self, loops: List[List[int]], normal: XYZ, point: XYZ) -> None:
        self.faces.append(Face(loops, _norm(normal), point))

    def add_triangle(self, a: int, b: int, c: int) -> None:
        pa, pb, pc = self.verts[a], self.verts[b], self.verts[c]
        n = _cross(_sub(pb, pa), _sub(pc, pa))
        if n[0] == 0 and n[1] == 0 and n[2] == 0:
            return  # degenerate, skip
        self.add_face([[a, b, c]], n, pa)

    def translate(self, dx: float, dy: float, dz: float) -> "Solid":
        self.verts = [(x + dx, y + dy, z + dz) for (x, y, z) in self.verts]
        return self

    def rotate_z(self, ang: float) -> "Solid":
        c, s = math.cos(ang), math.sin(ang)
        self.verts = [(x * c - y * s, x * s + y * c, z)
                      for (x, y, z) in self.verts]
        # Face normals/points rotate too.
        for f in self.faces:
            nx, ny, nz = f.normal
            px, py, pz = f.point
            f.normal = (nx * c - ny * s, nx * s + ny * c, nz)
            f.point = (px * c - py * s, px * s + py * c, pz)
        return self

    def rotate_axis(self, axis: XYZ, ang: float,
                    center: XYZ = (0.0, 0.0, 0.0)) -> "Solid":
        """Rotate about an arbitrary axis through ``center`` (Rodrigues)."""
        ux, uy, uz = _norm(axis)
        c, s = math.cos(ang), math.sin(ang)
        cx, cy, cz = center

        def rot(p: XYZ, translate: bool) -> XYZ:
            x, y, z = p
            if translate:
                x, y, z = x - cx, y - cy, z - cz
            dot = ux * x + uy * y + uz * z
            crx = uy * z - uz * y
            cry = uz * x - ux * z
            crz = ux * y - uy * x
            rx = x * c + crx * s + ux * dot * (1 - c)
            ry = y * c + cry * s + uy * dot * (1 - c)
            rz = z * c + crz * s + uz * dot * (1 - c)
            if translate:
                return (rx + cx, ry + cy, rz + cz)
            return (rx, ry, rz)

        self.verts = [rot(p, True) for p in self.verts]
        for f in self.faces:
            f.normal = rot(f.normal, False)
            f.point = rot(f.point, True)
        return self

    def rotate_x(self, ang: float) -> "Solid":
        return self.rotate_axis((1.0, 0.0, 0.0), ang)

    def rotate_y(self, ang: float) -> "Solid":
        return self.rotate_axis((0.0, 1.0, 0.0), ang)

    def is_closed_manifold(self) -> bool:
        """True if every edge is shared by exactly two faces with opposite
        orientation - i.e. the shell is a closed, orientable manifold.

        This is a dependency-free watertightness check (no CAD kernel needed).
        """
        from collections import defaultdict
        directed: dict = defaultdict(int)
        for face in self.faces:
            for loop in face.loops:
                n = len(loop)
                for i in range(n):
                    directed[(loop[i], loop[(i + 1) % n])] += 1
        if not directed:
            return False
        for (a, b), count in directed.items():
            if count != 1:                       # each directed edge used once
                return False
            if directed.get((b, a), 0) != 1:     # reverse must exist exactly once
                return False
        return True

    def edge_count(self) -> int:
        edges = set()
        for face in self.faces:
            for loop in face.loops:
                n = len(loop)
                for i in range(n):
                    a, b = loop[i], loop[(i + 1) % n]
                    edges.add((a, b) if a < b else (b, a))
        return len(edges)

    def bounding_box(self) -> Tuple[XYZ, XYZ]:
        xs = [v[0] for v in self.verts]
        ys = [v[1] for v in self.verts]
        zs = [v[2] for v in self.verts]
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


class Slab:
    """One axial segment of a stepped solid: stacked outer layers + local holes.

    ``layers`` are ``(z, outer_loop)`` pairs (>=2; multiple allow a twist).
    ``holes`` are inner loops local to this slab (e.g. spoke openings) that are
    capped at the slab's two ends.
    """

    def __init__(self, layers: List[Tuple[float, List[XY]]],
                 holes: Optional[List[List[XY]]] = None):
        self.layers = layers
        self.holes = holes or []

    @property
    def z0(self) -> float:
        return self.layers[0][0]

    @property
    def z1(self) -> float:
        return self.layers[-1][0]


def _wall(solid: Solid, lo: List[int], hi: List[int]) -> None:
    m = len(lo)
    for i in range(m):
        a, b = lo[i], lo[(i + 1) % m]
        c, d = hi[(i + 1) % m], hi[i]
        solid.add_triangle(a, b, c)
        solid.add_triangle(a, c, d)


def build_stepped(slabs: Sequence["Slab"], through_holes: Sequence[List[XY]],
                  name: str = "solid") -> Solid:
    """Build a solid from stacked slabs of differing outer profile.

    ``through_holes`` (e.g. the bore) run straight through every slab.  Each
    slab may carry its own local holes (e.g. spoke openings) that terminate at
    the slab boundaries.  A planar step face joins consecutive slabs; the
    smaller outer profile must lie inside the larger one.
    """
    from .geometry import polygon_area
    solid = Solid(name)
    z_min = slabs[0].z0
    z_max = slabs[-1].z1

    # Through-holes: one straight wall + shared bottom/top loops.
    th_lo: List[List[int]] = []
    th_hi: List[List[int]] = []
    for hole in through_holes:
        lo = [solid.add_vertex((x, y, z_min)) for (x, y) in hole]
        hi = [solid.add_vertex((x, y, z_max)) for (x, y) in hole]
        th_lo.append(lo)
        th_hi.append(hi)
        _wall(solid, lo, hi)

    # Outer side walls + local-hole walls within every slab.
    for slab in slabs:
        oidx = [[solid.add_vertex((x, y, z)) for (x, y) in loop]
                for (z, loop) in slab.layers]
        for l in range(len(slab.layers) - 1):
            _wall(solid, oidx[l], oidx[l + 1])
        for hole in slab.holes:
            lo = [solid.add_vertex((x, y, slab.z0)) for (x, y) in hole]
            hi = [solid.add_vertex((x, y, slab.z1)) for (x, y) in hole]
            _wall(solid, lo, hi)

    # Step faces between consecutive slabs.  Orient each loop by signed area:
    # for a +Z face the outer bound winds CCW (area>0) and holes CW (area<0);
    # for a -Z face the senses flip.
    def oriented(loop_xy: List[XY], z: float, want_ccw: bool) -> List[int]:
        seq = loop_xy if (polygon_area(loop_xy) > 0) == want_ccw \
            else list(reversed(loop_xy))
        return [solid.add_vertex((x, y, z)) for (x, y) in seq]

    for s in range(len(slabs) - 1):
        z = slabs[s].z1
        lower, upper = slabs[s].layers[-1][1], slabs[s + 1].layers[0][1]
        if abs(polygon_area(lower)) >= abs(polygon_area(upper)):
            outer, smaller, nz = lower, upper, 1.0
        else:
            outer, smaller, nz = upper, lower, -1.0
        outer_ccw = nz > 0                      # outer-bound target winding
        loops = [oriented(outer, z, outer_ccw)]
        for inner in [smaller] + slabs[s].holes + slabs[s + 1].holes:
            loops.append(oriented(inner, z, not outer_ccw))
        solid.add_face(loops, (0.0, 0.0, nz), (0.0, 0.0, z))

    # Bottom cap (CCW about -Z => reverse every loop).
    bot_outer = [solid.add_vertex((x, y, z_min)) for (x, y) in slabs[0].layers[0][1]]
    bot_holes = th_lo + [[solid.add_vertex((x, y, z_min)) for (x, y) in h]
                         for h in slabs[0].holes]
    bottom = [list(reversed(bot_outer))] + [list(reversed(h)) for h in bot_holes]
    solid.add_face(bottom, (0.0, 0.0, -1.0), (0.0, 0.0, z_min))

    # Top cap (loops as stored about +Z).
    top_outer = [solid.add_vertex((x, y, z_max)) for (x, y) in slabs[-1].layers[-1][1]]
    top_holes = th_hi + [[solid.add_vertex((x, y, z_max)) for (x, y) in h]
                         for h in slabs[-1].holes]
    top = [list(top_outer)] + [list(h) for h in top_holes]
    solid.add_face(top, (0.0, 0.0, 1.0), (0.0, 0.0, z_max))
    return solid


def build_extrusion(layers: Sequence[Tuple[float, List[List[XY]]]],
                    name: str = "solid") -> Solid:
    """Build a closed solid from stacked cross-sections (see module docstring)."""
    if len(layers) < 2:
        raise ValueError("need at least two layers (bottom and top)")
    nloops = len(layers[0][1])
    for _, loops in layers:
        if len(loops) != nloops:
            raise ValueError("every layer must have the same number of loops")

    solid = Solid(name)

    # Register vertices: idx[layer][loop][point].
    idx: List[List[List[int]]] = []
    for z, loops in layers:
        lyr: List[List[int]] = []
        for loop in loops:
            lyr.append([solid.add_vertex((x, y, z)) for (x, y) in loop])
        idx.append(lyr)

    z_bot = layers[0][0]
    z_top = layers[-1][0]

    # Bottom cap: normal -Z, loops reversed so they wind CCW about -Z.
    bottom = [list(reversed(ring)) for ring in idx[0]]
    solid.add_face(bottom, (0.0, 0.0, -1.0), (0.0, 0.0, z_bot))

    # Top cap: normal +Z, loops as-is.
    top = [list(ring) for ring in idx[-1]]
    solid.add_face(top, (0.0, 0.0, 1.0), (0.0, 0.0, z_top))

    # Side walls between consecutive layers, per loop, triangulated.
    for l in range(len(layers) - 1):
        for j in range(nloops):
            lo = idx[l][j]
            hi = idx[l + 1][j]
            m = len(lo)
            if len(hi) != m:
                raise ValueError("loop point counts differ between layers")
            for i in range(m):
                a = lo[i]
                b = lo[(i + 1) % m]
                c = hi[(i + 1) % m]
                d = hi[i]
                solid.add_triangle(a, b, c)
                solid.add_triangle(a, c, d)
    return solid
