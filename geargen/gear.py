"""High-level gear model: turn :class:`GearParams` into a 3-D :class:`Solid`.

Supports external/internal spur and helical gears with an optional centre bore,
keyway and lightening holes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .geometry import (GearParams, circle_polygon, clean_loop, gear_profile,
                       polar, polygon_area, rotate)
from .solid import Solid, build_extrusion

XY = Tuple[float, float]


@dataclass
class Keyway:
    """A rectangular keyway slot cut into the bore (DIN 6885 style)."""
    width: float          # slot width across the shaft (mm)
    depth: float          # extra depth measured from the bore surface (mm)
    angle: float = 0.0    # angular position of the slot (degrees)


@dataclass
class LighteningHoles:
    count: int            # number of holes
    diameter: float       # hole diameter (mm)
    pitch_circle: float   # bolt-circle diameter the holes sit on (mm)
    phase: float = 0.0    # angular offset of the first hole (degrees)


@dataclass
class GearBuild:
    """Manufacturing options layered on top of the involute geometry."""
    bore: float = 0.0                                 # bore diameter (mm)
    keyway: Optional[Keyway] = None
    lightening: Optional[LighteningHoles] = None
    flank_pts: int = 18                               # samples per involute flank
    arc_pts: int = 6                                  # samples per tip/root arc
    bore_seg: int = 64                                # bore polygon segments
    max_twist_per_layer: float = 4.0                  # helix facet step (degrees)
    rim_for_internal: float = 4.0                     # ring-gear rim thickness (module)


def _bore_loop(radius: float, seg: int, keyway: Optional[Keyway]) -> List[XY]:
    """Return a CW bore loop (a circle, optionally with a keyway slot)."""
    if keyway is None or keyway.width <= 0:
        loop = circle_polygon(radius, seg, cw=False)
    else:
        w = keyway.width
        depth = keyway.depth
        half = w / 2.0
        if half >= radius:
            raise ValueError("keyway wider than the bore")
        x0 = math.sqrt(radius * radius - half * half)
        phi = math.asin(half / radius)
        # Major arc from +phi around to -phi (CCW), skipping the keyway sector.
        loop = []
        n_arc = max(seg - 4, 8)
        for i in range(n_arc + 1):
            a = phi + (2.0 * math.pi - 2.0 * phi) * i / n_arc
            loop.append(polar(radius, a))
        # Outward rectangular detour near angle 0 (closes -phi -> +phi).
        # The arc already ends at (x0,-half) and starts at (x0,+half), so only
        # the two outer corners are added to avoid duplicate points.
        ro = radius + depth
        loop.append((ro, -half))
        loop.append((ro, half))
        if keyway.angle:
            ang = math.radians(keyway.angle)
            loop = [rotate(pt, ang) for pt in loop]
    # Holes must be CW (negative area).
    if polygon_area(loop) > 0:
        loop.reverse()
    return loop


def _circle_hole(cx: float, cy: float, r: float, seg: int = 32) -> List[XY]:
    loop = [(cx + r * math.cos(2 * math.pi * i / seg),
             cy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    loop.reverse()  # CW
    return loop


class Gear:
    """An involute gear that can be turned into a STEP solid."""

    def __init__(self, params: GearParams, build: Optional[GearBuild] = None):
        self.params = params
        self.build = build or GearBuild()

    # ------------------------------------------------------------------ #
    def _outer_profile(self) -> List[XY]:
        p = self.params
        prof = gear_profile(p, self.build.flank_pts, self.build.arc_pts)
        if p.internal:
            # Ring gear: outer boundary is the rim circle; teeth become a hole.
            return prof
        return prof

    def _holes(self) -> List[List[XY]]:
        """Inner loops (bore, keyway, lightening holes), all CW."""
        p = self.params
        b = self.build
        holes: List[List[XY]] = []
        if b.bore > 0:
            holes.append(_bore_loop(b.bore / 2.0, b.bore_seg, b.keyway))
        if b.lightening and b.lightening.count > 0:
            lh = b.lightening
            r_pcd = lh.pitch_circle / 2.0
            for k in range(lh.count):
                ang = math.radians(lh.phase) + 2 * math.pi * k / lh.count
                cx, cy = r_pcd * math.cos(ang), r_pcd * math.sin(ang)
                holes.append(_circle_hole(cx, cy, lh.diameter / 2.0))
        return holes

    def _layers(self):
        """Build stacked cross-sections for the extrusion."""
        p = self.params
        b = self.build
        width = p.face_width

        if p.internal:
            # Ring gear: outer = plain circle rim, inner = the tooth profile.
            rim_r = p.root_diameter / 2.0 + b.rim_for_internal * p.module
            outer = circle_polygon(rim_r, max(96, p.z * 4), cw=False)
            tooth_hole = gear_profile(p, b.flank_pts, b.arc_pts)
            # As a hole it must be CW.
            if polygon_area(tooth_hole) > 0:
                tooth_hole = list(reversed(tooth_hole))
            base_loops = [outer, tooth_hole] + self._holes()
            twisting = [False, True] + [False] * len(self._holes())
        else:
            outer = self._outer_profile()
            base_loops = [outer] + self._holes()
            twisting = [True] + [False] * len(self._holes())

        base_loops = [clean_loop(lp) for lp in base_loops]

        twist = p.twist_over_face()
        if abs(twist) < 1e-9:
            n_layers = 2
        else:
            steps = math.ceil(abs(math.degrees(twist)) / b.max_twist_per_layer)
            n_layers = max(2, steps + 1)

        layers = []
        for li in range(n_layers):
            f = li / (n_layers - 1)
            z = f * width
            ang = twist * f
            loops = []
            for loop, tw in zip(base_loops, twisting):
                if tw and ang != 0.0:
                    loops.append([rotate(pt, ang) for pt in loop])
                else:
                    loops.append(list(loop))
            layers.append((z, loops))
        return layers

    def to_solid(self, name: Optional[str] = None) -> Solid:
        nm = name or f"gear_z{self.params.z}_m{self.params.module:g}"
        return build_extrusion(self._layers(), name=nm)
