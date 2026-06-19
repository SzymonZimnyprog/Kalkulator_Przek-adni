"""High-level gear model: turn :class:`GearParams` into a 3-D :class:`Solid`.

Supports external/internal spur, helical and herringbone gears with an optional
centre bore, keyway or spline, lightening holes, a spoked/webbed body and an
axial hub.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .geometry import (GearParams, circle_polygon, clean_loop, gear_profile,
                       polar, polygon_area, rotate)
from .solid import Slab, Solid, build_extrusion, build_stepped

XY = Tuple[float, float]


# --------------------------------------------------------------------------- #
# Build option data classes
# --------------------------------------------------------------------------- #
@dataclass
class Keyway:
    """A rectangular keyway slot cut into the bore (DIN 6885 style)."""
    width: float
    depth: float
    angle: float = 0.0    # angular position (degrees)


@dataclass
class Spline:
    """A straight-sided internal spline replacing a plain bore."""
    count: int            # number of spline teeth
    minor_diameter: float  # tip circle of the internal teeth (smallest bore)
    major_diameter: float  # root circle of the spline (largest)
    width_ratio: float = 0.5   # tooth width as a fraction of the pitch


@dataclass
class LighteningHoles:
    count: int
    diameter: float
    pitch_circle: float
    phase: float = 0.0


@dataclass
class Spokes:
    """A spoked / webbed body: ``count`` arms link a central hub to the rim."""
    count: int
    hub_diameter: float      # outer diameter of the central hub web
    rim_inner_diameter: float  # inner diameter of the toothed rim
    spoke_width: float       # tangential width of each arm (mm)
    phase: float = 0.0       # angular offset (degrees)


@dataclass
class Hub:
    """An axial cylindrical boss protruding from one or both faces."""
    diameter: float
    height: float            # protrusion height per active side (mm)
    both_sides: bool = False


@dataclass
class GearBuild:
    """Manufacturing options layered on top of the involute geometry."""
    bore: float = 0.0
    keyway: Optional[Keyway] = None
    spline: Optional[Spline] = None
    lightening: Optional[LighteningHoles] = None
    spokes: Optional[Spokes] = None
    hub: Optional[Hub] = None
    herringbone: bool = False
    flank_pts: int = 18
    arc_pts: int = 6
    bore_seg: int = 64
    max_twist_per_layer: float = 4.0
    rim_for_internal: float = 4.0


# --------------------------------------------------------------------------- #
# Inner-loop (hole) helpers - all returned CW
# --------------------------------------------------------------------------- #
def _as_hole(loop: List[XY]) -> List[XY]:
    if polygon_area(loop) > 0:
        loop = list(reversed(loop))
    return loop


def _bore_loop(radius: float, seg: int, keyway: Optional[Keyway]) -> List[XY]:
    if keyway is None or keyway.width <= 0:
        loop = circle_polygon(radius, seg, cw=False)
    else:
        w, depth = keyway.width, keyway.depth
        half = w / 2.0
        if half >= radius:
            raise ValueError("keyway wider than the bore")
        phi = math.asin(half / radius)
        loop = []
        n_arc = max(seg - 4, 8)
        for i in range(n_arc + 1):
            a = phi + (2.0 * math.pi - 2.0 * phi) * i / n_arc
            loop.append(polar(radius, a))
        ro = radius + depth
        loop.append((ro, -half))
        loop.append((ro, half))
        if keyway.angle:
            ang = math.radians(keyway.angle)
            loop = [rotate(pt, ang) for pt in loop]
    return _as_hole(loop)


def _spline_loop(sp: Spline, arc_seg: int = 4) -> List[XY]:
    """Straight-sided internal spline as a single CW loop."""
    n = sp.count
    r_min = sp.minor_diameter / 2.0
    r_maj = sp.major_diameter / 2.0
    pitch = 2.0 * math.pi / n
    half_tooth = pitch * sp.width_ratio / 2.0
    loop: List[XY] = []
    for k in range(n):
        c = k * pitch
        # Internal tooth tip land at r_min (between -half_tooth..+half_tooth).
        for a in (c - half_tooth, c + half_tooth):
            loop.append(polar(r_min, a))
        # Slot bottom land at r_maj (between this tooth and the next).
        for a in (c + half_tooth, c + pitch - half_tooth):
            loop.append(polar(r_maj, a))
    return _as_hole(clean_loop(loop))


def _circle_hole(cx: float, cy: float, r: float, seg: int = 32) -> List[XY]:
    loop = [(cx + r * math.cos(2 * math.pi * i / seg),
             cy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
    return _as_hole(loop)


def _spoke_openings(sp: Spokes, arc_seg: int = 14) -> List[List[XY]]:
    """Return the openings (CW holes) between spokes."""
    n = sp.count
    r_hub = sp.hub_diameter / 2.0
    r_rim = sp.rim_inner_diameter / 2.0
    hw = sp.spoke_width / 2.0
    if r_rim <= r_hub:
        raise ValueError("rim_inner_diameter must exceed hub_diameter")
    if hw >= r_hub:
        raise ValueError("spoke too wide for the hub")
    phase = math.radians(sp.phase)
    openings: List[List[XY]] = []
    for k in range(n):
        a_lo = phase + k * 2.0 * math.pi / n          # this spoke centreline
        a_hi = phase + (k + 1) * 2.0 * math.pi / n    # next spoke centreline
        # Edge angles where the constant-width arm sides cross each radius.
        def edge(r, sign):
            return math.asin(min(1.0, hw / r)) * sign
        loop: List[XY] = []
        # inner arc (r_hub) from spoke k side to spoke k+1 side, CCW
        a0 = a_lo + edge(r_hub, +1)
        a1 = a_hi - edge(r_hub, +1)
        for i in range(arc_seg + 1):
            loop.append(polar(r_hub, a0 + (a1 - a0) * i / arc_seg))
        # outer arc (r_rim) back, CW
        b1 = a_hi - edge(r_rim, +1)
        b0 = a_lo + edge(r_rim, +1)
        for i in range(arc_seg + 1):
            loop.append(polar(r_rim, b1 + (b0 - b1) * i / arc_seg))
        openings.append(_as_hole(clean_loop(loop)))
    return openings


# --------------------------------------------------------------------------- #
# Gear
# --------------------------------------------------------------------------- #
class Gear:
    """An involute gear that can be turned into a STEP solid."""

    def __init__(self, params: GearParams, build: Optional[GearBuild] = None):
        self.params = params
        self.build = build or GearBuild()

    # -- 2-D loops --------------------------------------------------------- #
    def _bore_holes(self) -> List[List[XY]]:
        """Central bore / keyway / spline (the through-hole set)."""
        p, b = self.params, self.build
        holes: List[List[XY]] = []
        if b.spline is not None:
            holes.append(_spline_loop(b.spline))
        elif b.bore > 0:
            holes.append(_bore_loop(b.bore / 2.0, b.bore_seg, b.keyway))
        return holes

    def _web_holes(self) -> List[List[XY]]:
        """Web features (lightening holes, spoke openings)."""
        p, b = self.params, self.build
        holes: List[List[XY]] = []
        if b.spokes is not None and b.spokes.count > 0:
            holes.extend(_spoke_openings(b.spokes))
        if b.lightening and b.lightening.count > 0:
            lh = b.lightening
            r_pcd = lh.pitch_circle / 2.0
            for k in range(lh.count):
                ang = math.radians(lh.phase) + 2 * math.pi * k / lh.count
                cx, cy = r_pcd * math.cos(ang), r_pcd * math.sin(ang)
                holes.append(_circle_hole(cx, cy, lh.diameter / 2.0))
        return holes

    def _outer_and_internal(self):
        """Return (outer_loop, internal_tooth_hole_or_None, twist_outer?)."""
        p, b = self.params, self.build
        if p.internal:
            rim_r = p.root_diameter / 2.0 + b.rim_for_internal * p.module
            outer = circle_polygon(rim_r, max(96, p.z * 4), cw=False)
            tooth = _as_hole(gear_profile(p, b.flank_pts, b.arc_pts))
            return outer, tooth, False
        return gear_profile(p, b.flank_pts, b.arc_pts), None, True

    # -- twist profile ----------------------------------------------------- #
    def _twist_schedule(self):
        """Return a list of (fraction, angle) samples for the extrusion."""
        p, b = self.params, self.build
        twist = p.twist_over_face()
        if abs(twist) < 1e-9:
            return [(0.0, 0.0), (1.0, 0.0)]
        if b.herringbone:
            peak = twist / 2.0
            half = max(1, math.ceil(abs(math.degrees(peak)) /
                                    b.max_twist_per_layer))
            fs = ([0.5 * i / half for i in range(half + 1)] +
                  [0.5 + 0.5 * i / half for i in range(1, half + 1)])
            return [(f, peak * (1.0 - abs(2.0 * f - 1.0))) for f in fs]
        steps = max(1, math.ceil(abs(math.degrees(twist)) /
                                 b.max_twist_per_layer))
        return [(i / steps, twist * i / steps) for i in range(steps + 1)]

    def _outer_layers(self, z0: float, z1: float):
        """Outer-profile layers between z0 and z1 honouring the twist."""
        outer, tooth, twist_outer = self._outer_and_internal()
        outer = clean_loop(outer)
        sched = self._twist_schedule()
        layers = []
        for f, ang in sched:
            z = z0 + (z1 - z0) * f
            if twist_outer and ang != 0.0:
                layers.append((z, [rotate(pt, ang) for pt in outer]))
            else:
                layers.append((z, list(outer)))
        return layers, tooth, sched

    # -- solid ------------------------------------------------------------- #
    def to_solid(self, name: Optional[str] = None) -> Solid:
        p, b = self.params, self.build
        nm = name or f"gear_z{p.z}_m{p.module:g}"
        width = p.face_width

        outer_layers, tooth, sched = self._outer_layers(0.0, width)
        bore_holes = self._bore_holes()
        web_holes = self._web_holes()

        # Internal-tooth hole twists with the rim for a helical ring gear.
        internal_layers = None
        if tooth is not None:
            internal_layers = []
            for f, ang in sched:
                if abs(ang) > 0:
                    internal_layers.append([rotate(pt, ang) for pt in tooth])
                else:
                    internal_layers.append(list(tooth))

        if b.hub is None:
            # Single uniform extrusion (fast path).
            layers = []
            for i, (z, oloop) in enumerate(outer_layers):
                loops = [oloop]
                if tooth is not None:
                    loops.append(internal_layers[i])
                loops += [list(h) for h in bore_holes + web_holes]
                layers.append((z, [clean_loop(lp) for lp in loops]))
            return build_extrusion(layers, name=nm)

        # Stepped solid: gear body slab + hub slab(s).
        if tooth is not None:
            raise ValueError("a hub is not supported on internal (ring) gears")
        hub = b.hub
        hub_circle = circle_polygon(hub.diameter / 2.0, max(48, b.bore_seg), cw=False)
        body = Slab(outer_layers, holes=web_holes)
        slabs = [body]
        if hub.both_sides:
            bottom_hub = Slab([(-hub.height, list(hub_circle)),
                               (0.0, list(hub_circle))])
            slabs.insert(0, bottom_hub)
        top_hub = Slab([(width, list(hub_circle)),
                        (width + hub.height, list(hub_circle))])
        slabs.append(top_hub)
        return build_stepped(slabs, through_holes=bore_holes, name=nm)
