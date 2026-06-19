"""Straight bevel gears (kola stozkowe) and a right-angle bevel drive.

A straight bevel gear is modelled with Tredgold's approximation: the transverse
involute profile defined at the back (heel) cone is scaled linearly toward the
common apex, so every tooth ruling points at the apex - geometrically exact for
straight bevel flanks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .geometry import GearParams, circle_polygon, clean_loop, gear_profile, polygon_area
from .solid import Solid, build_extrusion

XY = Tuple[float, float]


@dataclass
class BevelParams:
    module: float                 # transverse module at the back (outer) cone
    teeth: int
    pitch_angle: float            # pitch cone half-angle delta (degrees)
    face_width: float
    pressure_angle: float = 20.0
    bore: float = 0.0

    @property
    def z(self) -> int:
        return self.teeth

    @property
    def delta(self) -> float:
        return math.radians(self.pitch_angle)

    @property
    def outer_pitch_radius(self) -> float:
        return self.module * self.teeth / 2.0

    @property
    def cone_distance(self) -> float:           # back-cone distance Re
        return self.outer_pitch_radius / math.sin(self.delta)

    @property
    def inner_ratio(self) -> float:             # Ri / Re
        return (self.cone_distance - self.face_width) / self.cone_distance


class BevelGear:
    """A straight bevel gear with its apex at the origin, axis = +z."""

    def __init__(self, params: BevelParams, flank_pts: int = 18, arc_pts: int = 6):
        self.p = params
        self.flank_pts = flank_pts
        self.arc_pts = arc_pts

    def _gp(self) -> GearParams:
        return GearParams(module=self.p.module, teeth=self.p.teeth,
                          pressure_angle=self.p.pressure_angle,
                          face_width=self.p.face_width)

    def to_solid(self, name: Optional[str] = None, apex_at_origin: bool = True) -> Solid:
        p = self.p
        gp = self._gp()
        prof = clean_loop(gear_profile(gp, self.flank_pts, self.arc_pts))
        cd = math.cos(p.delta)
        z_back = p.cone_distance * cd
        z_toe = (p.cone_distance - p.face_width) * cd
        s = p.inner_ratio

        toe = [(s * x, s * y) for (x, y) in prof]
        back = list(prof)

        loops_toe = [toe]
        loops_back = [back]
        if p.bore > 0:
            rb = p.bore / 2.0
            if rb >= s * p.outer_pitch_radius * 0.6:
                rb = s * p.outer_pitch_radius * 0.5
            bore = circle_polygon(rb, 48, cw=True)
            loops_toe.append(list(bore))
            loops_back.append(list(bore))

        layers = [(z_toe, loops_toe), (z_back, loops_back)]
        solid = build_extrusion(layers, name=name or f"bevel_z{p.teeth}")
        if not apex_at_origin:
            solid.translate(0.0, 0.0, -z_toe)   # toe face down on z=0
        return solid


@dataclass
class BevelPair:
    """A right-angle (or arbitrary shaft-angle) straight bevel drive."""
    pinion: BevelParams
    wheel: BevelParams
    shaft_angle: float = 90.0       # degrees

    def __post_init__(self):
        if abs(self.pinion.module - self.wheel.module) > 1e-9:
            raise ValueError("bevel gears must share the module")
        # Pitch angles should sum to the shaft angle.
        tot = self.pinion.pitch_angle + self.wheel.pitch_angle
        if abs(tot - self.shaft_angle) > 1.0:
            raise ValueError(
                f"pitch angles ({tot:.1f} deg) must sum to the shaft angle "
                f"({self.shaft_angle} deg)")

    @property
    def ratio(self) -> float:
        return self.wheel.z / self.pinion.z

    @classmethod
    def right_angle(cls, module: float, z_pinion: int, z_wheel: int,
                    face_width: float, pressure_angle: float = 20.0,
                    bore_p: float = 0.0, bore_w: float = 0.0) -> "BevelPair":
        """Build a 90-degree pair, computing the pitch cone angles."""
        d1 = math.degrees(math.atan2(z_pinion, z_wheel))
        d2 = 90.0 - d1
        return cls(
            BevelParams(module, z_pinion, d1, face_width, pressure_angle, bore_p),
            BevelParams(module, z_wheel, d2, face_width, pressure_angle, bore_w))

    def solids(self) -> List[Solid]:
        pinion = BevelGear(self.pinion).to_solid(name=f"bevel_pinion_z{self.pinion.z}")
        wheel = BevelGear(self.wheel).to_solid(name=f"bevel_wheel_z{self.wheel.z}")
        # Pinion along +z (apex at origin).  Wheel rotated by the shaft angle
        # about +y so its axis tilts away, sharing the apex; then phased.
        wheel.rotate_z(math.pi - math.pi / self.wheel.z)
        wheel.rotate_y(math.radians(self.shaft_angle))
        return [pinion, wheel]

    def report(self, input_rpm: float = 1000.0, input_torque: float = 10.0) -> dict:
        return {
            "module": self.pinion.module,
            "z_pinion": self.pinion.z,
            "z_wheel": self.wheel.z,
            "shaft_angle_deg": self.shaft_angle,
            "pinion_pitch_angle_deg": round(self.pinion.pitch_angle, 4),
            "wheel_pitch_angle_deg": round(self.wheel.pitch_angle, 4),
            "ratio": round(self.ratio, 5),
            "input_rpm": input_rpm,
            "output_rpm": round(input_rpm / self.ratio, 3),
            "input_torque_Nm": input_torque,
            "output_torque_Nm": round(input_torque * self.ratio * 0.97, 4),
        }
