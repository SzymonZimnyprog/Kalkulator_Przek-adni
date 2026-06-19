"""Minimal but valid STEP (ISO 10303-21, AP214) B-rep writer.

Serialises one or more :class:`~geargen.solid.Solid` objects as
``MANIFOLD_SOLID_BREP`` entities with shared vertices and edges, wrapped in the
standard product/representation structure so the file opens in FreeCAD,
SolidWorks, Fusion 360, Onshape, etc.

Faces are planar; curved gear flanks are represented by a fine polyline
tessellation (set via the ``flank_pts`` / ``arc_pts`` resolution of the
profile).  This keeps the writer dependency-free while producing a true,
watertight solid (not a mesh shell).
"""

from __future__ import annotations

import datetime as _dt
import math
import re
from typing import Dict, List, Sequence, Tuple

from .solid import Solid

XYZ = Tuple[float, float, float]


def _r(x: float) -> str:
    """Format a float as a STEP REAL (always has a decimal point)."""
    s = "%.10g" % float(x)
    if "e" in s or "E" in s:
        mant, exp = re.split("[eE]", s)
        if "." not in mant:
            mant += "."
        return f"{mant}E{int(exp)}"
    if "." not in s:
        s += "."
    return s


def _perp(n: XYZ) -> XYZ:
    """Return a unit vector perpendicular to ``n`` (the face ref direction)."""
    a = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    x = (a[1] * n[2] - a[2] * n[1],
         a[2] * n[0] - a[0] * n[2],
         a[0] * n[1] - a[1] * n[0])
    m = math.sqrt(x[0] ** 2 + x[1] ** 2 + x[2] ** 2)
    return (x[0] / m, x[1] / m, x[2] / m)


class StepWriter:
    def __init__(self) -> None:
        self._lines: List[str] = []
        self._id = 0
        self._pt: Dict[tuple, int] = {}
        self._dir: Dict[tuple, int] = {}
        self._vtx: Dict[int, int] = {}
        self._edge: Dict[tuple, tuple] = {}

    # -- low level --------------------------------------------------------- #
    def _add(self, body: str) -> int:
        self._id += 1
        self._lines.append(f"#{self._id}={body};")
        return self._id

    def _point(self, p: XYZ) -> int:
        key = (round(p[0], 7), round(p[1], 7), round(p[2], 7))
        i = self._pt.get(key)
        if i is None:
            i = self._add(f"CARTESIAN_POINT('',({_r(p[0])},{_r(p[1])},{_r(p[2])}))")
            self._pt[key] = i
        return i

    def _dir3(self, d: XYZ) -> int:
        key = (round(d[0], 9), round(d[1], 9), round(d[2], 9))
        i = self._dir.get(key)
        if i is None:
            i = self._add(f"DIRECTION('',({_r(d[0])},{_r(d[1])},{_r(d[2])}))")
            self._dir[key] = i
        return i

    def _vertex(self, vi: int, coord: XYZ) -> int:
        i = self._vtx.get(vi)
        if i is None:
            i = self._add(f"VERTEX_POINT('',#{self._point(coord)})")
            self._vtx[vi] = i
        return i

    def _edge_curve(self, va: int, vb: int, verts: List[XYZ]) -> Tuple[int, bool]:
        """Return ``(edge_curve_id, forward)`` for the undirected edge va-vb.

        ``forward`` is True when the stored EDGE_CURVE runs va -> vb.
        """
        key = (va, vb) if va < vb else (vb, va)
        rec = self._edge.get(key)
        if rec is None:
            s, e = key
            ps, pe = verts[s], verts[e]
            vs = self._vertex(s, ps)
            ve = self._vertex(e, pe)
            d = (pe[0] - ps[0], pe[1] - ps[1], pe[2] - ps[2])
            m = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
            d = (d[0] / m, d[1] / m, d[2] / m)
            vec = self._add(f"VECTOR('',#{self._dir3(d)},1.)")
            line = self._add(f"LINE('',#{self._point(ps)},#{vec})")
            ec = self._add(f"EDGE_CURVE('',#{vs},#{ve},#{line},.T.)")
            self._edge[key] = (ec, s, e)
            rec = self._edge[key]
        ec = rec[0]
        forward = (rec[1] == va)
        return ec, forward

    def _edge_loop(self, loop: Sequence[int], verts: List[XYZ]) -> int:
        oriented: List[int] = []
        n = len(loop)
        for i in range(n):
            va = loop[i]
            vb = loop[(i + 1) % n]
            ec, forward = self._edge_curve(va, vb, verts)
            flag = ".T." if forward else ".F."
            oriented.append(self._add(f"ORIENTED_EDGE('',*,*,#{ec},{flag})"))
        refs = ",".join(f"#{o}" for o in oriented)
        return self._add(f"EDGE_LOOP('',({refs}))")

    # -- solids ------------------------------------------------------------ #
    def add_solid(self, solid: Solid) -> int:
        # Each solid is an independent closed shell: reset all caches so no
        # vertices/edges/points are shared between solids (per-solid vertex
        # indices would otherwise collide and corrupt the topology).
        self._pt = {}
        self._dir = {}
        self._vtx = {}
        self._edge = {}
        verts = solid.verts
        face_ids: List[int] = []
        for face in solid.faces:
            n = face.normal
            axis = self._dir3(n)
            ref = self._dir3(_perp(n))
            origin = self._point(face.point)
            placement = self._add(
                f"AXIS2_PLACEMENT_3D('',#{origin},#{axis},#{ref})")
            plane = self._add(f"PLANE('',#{placement})")
            bounds: List[int] = []
            for k, loop in enumerate(face.loops):
                el = self._edge_loop(loop, verts)
                kind = "FACE_OUTER_BOUND" if k == 0 else "FACE_BOUND"
                bounds.append(self._add(f"{kind}('',#{el},.T.)"))
            refs = ",".join(f"#{b}" for b in bounds)
            face_ids.append(self._add(
                f"ADVANCED_FACE('',({refs}),#{plane},.T.)"))
        shell = self._add(
            f"CLOSED_SHELL('',({','.join(f'#{f}' for f in face_ids)}))")
        return self._add(f"MANIFOLD_SOLID_BREP('{solid.name}',#{shell})")

    # -- assembly / file --------------------------------------------------- #
    def build(self, solids: Sequence[Solid], product: str = "gear") -> str:
        # Geometry first.
        brep_ids = [self.add_solid(s) for s in solids]

        # Units + geometric context.
        u_len = self._add("(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.))")
        u_ang = self._add("(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.))")
        u_sol = self._add("(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT())")
        unc = self._add(
            f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-06),#{u_len},"
            f"'distance_accuracy_value','confusion accuracy')")
        ctx = self._add(
            "(GEOMETRIC_REPRESENTATION_CONTEXT(3)"
            f"GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{unc}))"
            f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{u_len},#{u_ang},#{u_sol}))"
            "REPRESENTATION_CONTEXT('Context #1','3D Context'))")

        # A world origin axis placement (representation item).
        o = self._point((0.0, 0.0, 0.0))
        zd = self._dir3((0.0, 0.0, 1.0))
        xd = self._dir3((1.0, 0.0, 0.0))
        world = self._add(f"AXIS2_PLACEMENT_3D('',#{o},#{zd},#{xd})")

        items = ",".join(f"#{b}" for b in brep_ids + [world])
        shape_rep = self._add(
            f"ADVANCED_BREP_SHAPE_REPRESENTATION('{product}',({items}),#{ctx})")

        # Product structure.
        app = self._add("APPLICATION_CONTEXT('automotive design')")
        self._add(
            "APPLICATION_PROTOCOL_DEFINITION('international standard',"
            f"'automotive_design',2010,#{app})")
        pctx = self._add(f"PRODUCT_CONTEXT('',#{app},'mechanical')")
        prod = self._add(
            f"PRODUCT('{product}','{product}','',(#{pctx}))")
        pdf = self._add(
            f"PRODUCT_DEFINITION_FORMATION('','',#{prod})")
        pdctx = self._add(f"PRODUCT_DEFINITION_CONTEXT('part definition',#{app},'design')")
        pd = self._add(f"PRODUCT_DEFINITION('design','',#{pdf},#{pdctx})")
        pds = self._add(f"PRODUCT_DEFINITION_SHAPE('','',#{pd})")
        self._add(f"SHAPE_DEFINITION_REPRESENTATION(#{pds},#{shape_rep})")

        # Product category / related (helps some readers).
        self._add(f"PRODUCT_RELATED_PRODUCT_CATEGORY('part','',(#{prod}))")

        return self._render(product)

    def _render(self, product: str) -> str:
        ts = _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        header = (
            "ISO-10303-21;\n"
            "HEADER;\n"
            "FILE_DESCRIPTION(('STEP AP214 generated by geargen'),'2;1');\n"
            f"FILE_NAME('{product}.step','{ts}',(''),(''),"
            "'geargen','geargen','');\n"
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\n"
            "ENDSEC;\n"
            "DATA;\n"
        )
        footer = "ENDSEC;\nEND-ISO-10303-21;\n"
        return header + "\n".join(self._lines) + "\n" + footer


def write_step(solids, path: str, product: str = "gear") -> str:
    """Write ``solids`` (a Solid or list of Solids) to ``path`` as STEP."""
    if isinstance(solids, Solid):
        solids = [solids]
    text = StepWriter().build(list(solids), product=product)
    with open(path, "w") as fh:
        fh.write(text)
    return path
