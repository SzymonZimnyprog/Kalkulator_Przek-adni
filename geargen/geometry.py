"""Involute gear geometry (pure Python, ``math`` only).

Computes 2-D involute tooth profiles for external/internal spur and helical
gears.  All lengths are millimetres; angles are radians internally.

Standard involute relations used here::

    d   = m * z / cos(beta)              reference (pitch) diameter
    db  = d * cos(alpha_t)               base-circle diameter
    da  = d +/- 2*m*(ha* + x)            tip diameter (+ external, - internal)
    df  = d -/+ 2*m*(hf* - x)            root diameter
    s   = m*(pi/2 + 2*x*tan(alpha))      tooth thickness on the pitch circle
    inv(a) = tan(a) - a                  involute function

The active flank between base and tip circles is a true involute of the base
circle.  Below the base circle the flank drops radially to the root circle;
an optional circular fillet rounds the root.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

Point = Tuple[float, float]


# --------------------------------------------------------------------------- #
# Small numeric helpers (avoid a numpy dependency)
# --------------------------------------------------------------------------- #
def linspace(a: float, b: float, n: int) -> List[float]:
    """``n`` evenly spaced samples from ``a`` to ``b`` inclusive."""
    if n <= 1:
        return [a]
    step = (b - a) / (n - 1)
    return [a + step * i for i in range(n)]


def involute(angle: float) -> float:
    """Involute function ``inv(a) = tan(a) - a``."""
    return math.tan(angle) - angle


def rotate(p: Point, ang: float) -> Point:
    """Rotate a 2-D point about the origin by ``ang`` radians."""
    c, s = math.cos(ang), math.sin(ang)
    x, y = p
    return (x * c - y * s, x * s + y * c)


def polar(r: float, ang: float) -> Point:
    return (r * math.cos(ang), r * math.sin(ang))


def polygon_area(pts: List[Point]) -> float:
    """Signed area of a polygon (positive = counter-clockwise)."""
    a = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2.0


# --------------------------------------------------------------------------- #
# Gear parameters
# --------------------------------------------------------------------------- #
@dataclass
class GearParams:
    """Parameters of one involute gear.

    ``teeth`` negative selects an internal (ring) gear.  ``pressure_angle`` and
    ``helix_angle`` are given in degrees.
    """

    module: float
    teeth: int
    pressure_angle: float = 20.0
    profile_shift: float = 0.0
    helix_angle: float = 0.0
    face_width: float = 10.0
    addendum_coef: float = 1.0
    dedendum_coef: float = 1.25
    backlash: float = 0.0
    root_fillet: float = 0.0

    # -- flags / basics ---------------------------------------------------- #
    @property
    def internal(self) -> bool:
        return self.teeth < 0

    @property
    def z(self) -> int:
        return abs(self.teeth)

    @property
    def alpha(self) -> float:
        return math.radians(self.pressure_angle)

    @property
    def beta(self) -> float:
        return math.radians(self.helix_angle)

    @property
    def alpha_t(self) -> float:
        """Transverse pressure angle (= alpha for spur gears)."""
        if self.beta == 0.0:
            return self.alpha
        return math.atan(math.tan(self.alpha) / math.cos(self.beta))

    # -- diameters --------------------------------------------------------- #
    @property
    def pitch_diameter(self) -> float:
        return self.module * self.z / math.cos(self.beta)

    @property
    def base_diameter(self) -> float:
        return self.pitch_diameter * math.cos(self.alpha_t)

    @property
    def addendum(self) -> float:
        return self.module * (self.addendum_coef + self.profile_shift)

    @property
    def dedendum(self) -> float:
        return self.module * (self.dedendum_coef - self.profile_shift)

    @property
    def tip_diameter(self) -> float:
        if self.internal:
            return self.pitch_diameter - 2.0 * self.addendum
        return self.pitch_diameter + 2.0 * self.addendum

    @property
    def root_diameter(self) -> float:
        if self.internal:
            return self.pitch_diameter + 2.0 * self.dedendum
        return self.pitch_diameter - 2.0 * self.dedendum

    @property
    def circular_pitch(self) -> float:
        return math.pi * self.module

    @property
    def tooth_thickness(self) -> float:
        """Transverse tooth thickness on the pitch circle."""
        return (self.module * (math.pi / 2.0 + 2.0 * self.profile_shift *
                               math.tan(self.alpha)) - self.backlash / 2.0)

    @property
    def lead(self) -> float:
        """Axial lead of the helix (mm per full turn); inf for spur gears."""
        if self.beta == 0.0:
            return math.inf
        return math.pi * self.pitch_diameter / math.tan(self.beta)

    def twist_over_face(self) -> float:
        """Total twist angle (rad) of the helix across the face width."""
        if self.beta == 0.0:
            return 0.0
        return 2.0 * self.face_width * math.tan(self.beta) / self.pitch_diameter

    def validate(self) -> List[str]:
        """Return a list of human-readable warnings/errors (empty if OK)."""
        msgs: List[str] = []
        if self.module <= 0:
            msgs.append("module must be > 0")
        if self.z < 3:
            msgs.append("teeth count should be >= 3")
        if self.tip_diameter <= self.base_diameter and not self.internal:
            msgs.append("tip diameter is below the base circle (no involute)")
        zmin = 2.0 * self.addendum_coef / max(math.sin(self.alpha) ** 2, 1e-9)
        if not self.internal and self.profile_shift == 0 and self.z < zmin - 1:
            msgs.append(
                f"undercut likely: z={self.z} < zmin≈{zmin:.0f}; "
                f"add profile shift x≈{(zmin - self.z) / zmin:.2f}")
        if self.face_width <= 0:
            msgs.append("face_width must be > 0")
        return msgs

    def summary(self) -> dict:
        return {
            "module": self.module,
            "teeth": self.teeth,
            "pressure_angle_deg": self.pressure_angle,
            "helix_angle_deg": self.helix_angle,
            "profile_shift": self.profile_shift,
            "face_width": self.face_width,
            "pitch_diameter": round(self.pitch_diameter, 6),
            "base_diameter": round(self.base_diameter, 6),
            "tip_diameter": round(self.tip_diameter, 6),
            "root_diameter": round(self.root_diameter, 6),
            "circular_pitch": round(self.circular_pitch, 6),
            "tooth_thickness_pitch": round(self.tooth_thickness, 6),
            "addendum": round(self.addendum, 6),
            "dedendum": round(self.dedendum, 6),
            "lead": self.lead,
            "internal": self.internal,
        }


# --------------------------------------------------------------------------- #
# Tooth / gear 2-D profile construction
# --------------------------------------------------------------------------- #
def _half_angle(p: GearParams, r: float, psi_pitch: float,
                inv_alpha: float, rb: float) -> float:
    """Half tooth-angle at radius ``r`` (radians, positive)."""
    if r <= rb:
        return psi_pitch + inv_alpha
    a = math.acos(min(1.0, rb / r))
    return psi_pitch + inv_alpha - involute(a)


def _flank(p: GearParams, n: int) -> List[Point]:
    """One involute flank, root -> tip, for a tooth centred on +x.

    Returns points on the *clockwise* (negative-angle) flank.  The first point
    is on the root circle, the last on the tip circle.
    """
    rb = p.base_diameter / 2.0
    ra = p.tip_diameter / 2.0
    rf = p.root_diameter / 2.0
    psi_pitch = p.tooth_thickness / p.pitch_diameter
    inv_alpha = involute(p.alpha_t)

    pts: List[Point] = []

    if p.internal:
        # Internal tooth: the "tooth" is the space of a virtual external tooth;
        # the involute runs from base outward to the root (which is larger).
        r_lo = min(rb, ra)
        r_hi = max(rf, rb)
        for r in linspace(r_lo, r_hi, n):
            ang = _half_angle(p, r, psi_pitch, inv_alpha, rb)
            pts.append((r * math.cos(ang), -r * math.sin(ang)))
        return pts

    # External gear.
    r_start = max(rb, rf)
    if r_start >= ra:
        r_start = 0.999 * ra

    if rf < rb - 1e-9:
        ang_base = _half_angle(p, rb, psi_pitch, inv_alpha, rb)
        rho = max(0.0, p.root_fillet)
        # A circular fillet tangent to the radial flank and the root circle
        # smooths the transition (realistic, stress-reducing root).
        if rho > 1e-6:
            # Tangent point on the flank (radial line at angle -ang_base).
            r_tf = math.sqrt(rf * rf + 2.0 * rf * rho)
            if r_tf < rb:                       # fillet fits below base circle
                d_ang = math.asin(rho / (rf + rho))
                psi_c = -ang_base - d_ang       # fillet centre angle (space side)
                cx = (rf + rho) * math.cos(psi_c)
                cy = (rf + rho) * math.sin(psi_c)
                # Tangent points: on root circle (radius rf) and on the flank.
                t_root = (rf * math.cos(psi_c), rf * math.sin(psi_c))
                t_flank = (r_tf * math.cos(-ang_base), r_tf * math.sin(-ang_base))
                a_root = math.atan2(t_root[1] - cy, t_root[0] - cx)
                a_flank = math.atan2(t_flank[1] - cy, t_flank[0] - cx)
                for a in linspace(a_root, a_flank, max(4, n // 3)):
                    pts.append((cx + rho * math.cos(a), cy + rho * math.sin(a)))
            else:
                pts.append((rf * math.cos(ang_base), -rf * math.sin(ang_base)))
        else:
            # Sharp radial root.
            pts.append((rf * math.cos(ang_base), -rf * math.sin(ang_base)))

    for r in linspace(r_start, ra, n):
        ang = _half_angle(p, r, psi_pitch, inv_alpha, rb)
        pts.append((r * math.cos(ang), -r * math.sin(ang)))
    return pts


def _arc(r: float, a0: float, a1: float, n: int) -> List[Point]:
    """Sample a circular arc of radius ``r`` from angle ``a0`` to ``a1``."""
    return [polar(r, a) for a in linspace(a0, a1, n)]


def tooth_profile(p: GearParams, flank_pts: int = 16,
                  arc_pts: int = 6) -> List[Point]:
    """Return one tooth + trailing space as a CCW point list (tooth at +x)."""
    right = _flank(p, flank_pts)                       # root -> tip, angle < 0
    left = [(x, -y) for (x, y) in right]               # mirror -> angle > 0
    left.reverse()                                     # tip -> root

    ra = p.tip_diameter / 2.0
    rf = p.root_diameter / 2.0
    r_root = math.hypot(*right[0])

    # Tip arc joins the two flank tips.
    tip_a0 = math.atan2(right[-1][1], right[-1][0])
    tip_a1 = math.atan2(left[0][1], left[0][0])
    tip = _arc(ra, tip_a0, tip_a1, arc_pts)[1:-1]

    pts: List[Point] = []
    pts.extend(right)
    pts.extend(tip)
    pts.extend(left)

    # Root land arc from this tooth's left-root to the next tooth's right-root.
    pitch_ang = 2.0 * math.pi / p.z
    root_a0 = math.atan2(left[-1][1], left[-1][0])
    next_right0 = rotate(right[0], pitch_ang)
    root_a1 = math.atan2(next_right0[1], next_right0[0])
    root = _arc(r_root, root_a0, root_a1, arc_pts)[1:-1]
    pts.extend(root)
    return pts


def gear_profile(p: GearParams, flank_pts: int = 16,
                 arc_pts: int = 6) -> List[Point]:
    """Full outer boundary of the gear as a closed CCW polygon."""
    one = tooth_profile(p, flank_pts, arc_pts)
    pitch_ang = 2.0 * math.pi / p.z
    pts: List[Point] = []
    for k in range(p.z):
        ang = k * pitch_ang
        pts.extend(rotate(pt, ang) for pt in one)
    # Ensure CCW orientation.
    if polygon_area(pts) < 0:
        pts.reverse()
    return pts


def clean_loop(loop: List[Point], tol: float = 1e-6) -> List[Point]:
    """Remove consecutive duplicate points (including first==last wrap)."""
    if not loop:
        return loop
    out: List[Point] = [loop[0]]
    for p in loop[1:]:
        if abs(p[0] - out[-1][0]) > tol or abs(p[1] - out[-1][1]) > tol:
            out.append(p)
    # Wrap-around duplicate.
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) <= tol and \
            abs(out[0][1] - out[-1][1]) <= tol:
        out.pop()
    return out


def circle_polygon(radius: float, n: int, cw: bool = False) -> List[Point]:
    """Return a regular polygon approximating a circle (CCW by default)."""
    pts = [polar(radius, 2.0 * math.pi * i / n) for i in range(n)]
    if cw:
        pts.reverse()
    return pts
