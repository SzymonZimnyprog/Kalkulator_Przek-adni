"""Worm drive (przekladnia slimakowa): worm + worm wheel.

The worm is modelled as a ``z_w``-start helical thread (a transverse lobed
section twisted one full turn per lead).  The worm wheel is approximated by a
helical gear whose helix angle equals the worm's lead angle, meshing at 90 deg.
Worm drives give a very large reduction in one stage and can be self-locking.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .geometry import GearParams, circle_polygon, clean_loop, polar
from .gear import Gear, GearBuild
from .solid import Solid, build_extrusion

XY = Tuple[float, float]


@dataclass
class WormParams:
    module: float                 # axial module
    starts: int                   # number of thread starts z_w (1..4)
    pitch_diameter: float         # worm pitch diameter d_w (mm)
    length: float                 # threaded length (mm)
    pressure_angle: float = 20.0
    bore: float = 0.0
    addendum_coef: float = 1.0
    dedendum_coef: float = 1.25

    @property
    def lead(self) -> float:
        return self.starts * math.pi * self.module

    @property
    def lead_angle(self) -> float:               # lambda (radians)
        return math.atan2(self.lead, math.pi * self.pitch_diameter)


def worm_section(p: WormParams, n_flank: int = 4, n_arc: int = 6) -> List[XY]:
    """Transverse section of the worm: a circle with ``starts`` trapezoidal
    lobes (CCW closed loop)."""
    m = p.module
    rp = p.pitch_diameter / 2.0
    ra = rp + p.addendum_coef * m
    rf = rp - p.dedendum_coef * m
    ta = math.tan(math.radians(p.pressure_angle))
    z = p.starts
    psi_p = math.pi / (2.0 * z)                  # half tooth angle at pitch
    psi_a = max(0.02, psi_p - p.addendum_coef * m * ta / rp)
    psi_f = psi_p + p.dedendum_coef * m * ta / rp
    pitch = 2.0 * math.pi / z

    loop: List[XY] = []
    for k in range(z):
        c = k * pitch
        # right flank root->tip, tip land, left flank tip->root
        for r, a in ((rf, c - psi_f), (ra, c - psi_a),
                     (ra, c + psi_a), (rf, c + psi_f)):
            loop.append(polar(r, a))
        # root land arc to the next lobe
        a0 = c + psi_f
        a1 = c + pitch - psi_f
        for i in range(1, n_arc):
            loop.append(polar(rf, a0 + (a1 - a0) * i / n_arc))
    return clean_loop(loop)


class Worm:
    def __init__(self, params: WormParams, max_twist_per_layer: float = 8.0):
        self.p = params
        self.max_twist = max_twist_per_layer

    def to_solid(self, name: Optional[str] = None) -> Solid:
        p = self.p
        section = worm_section(p)
        total_twist = 2.0 * math.pi * p.length / p.lead     # rad over length
        steps = max(2, math.ceil(abs(math.degrees(total_twist)) / self.max_twist))
        bore = None
        if p.bore > 0:
            bore = circle_polygon(p.bore / 2.0, 48, cw=True)
        layers = []
        for i in range(steps + 1):
            f = i / steps
            z = f * p.length
            ang = total_twist * f
            outer = [(x * math.cos(ang) - y * math.sin(ang),
                      x * math.sin(ang) + y * math.cos(ang)) for (x, y) in section]
            loops = [outer]
            if bore is not None:
                loops.append(list(bore))
            layers.append((z, loops))
        return build_extrusion(layers, name=name or f"worm_z{p.starts}")


@dataclass
class WormDrive:
    """A worm meshing with a worm wheel at 90 degrees."""
    worm: WormParams
    wheel_teeth: int
    wheel_face_width: float = 12.0
    wheel_bore: float = 0.0

    def __post_init__(self):
        pass

    @property
    def ratio(self) -> float:
        """Reduction ratio = wheel teeth / worm starts."""
        return self.wheel_teeth / self.worm.starts

    @property
    def wheel(self) -> GearParams:
        # Helical gear; helix angle = worm lead angle so the axes cross at 90.
        return GearParams(module=self.worm.module, teeth=self.wheel_teeth,
                          pressure_angle=self.worm.pressure_angle,
                          helix_angle=math.degrees(self.worm.lead_angle),
                          face_width=self.wheel_face_width)

    @property
    def center_distance(self) -> float:
        return (self.worm.pitch_diameter + self.wheel.pitch_diameter) / 2.0

    def self_locking(self) -> bool:
        """A worm drive tends to self-lock when the lead angle is small."""
        # Roughly self-locking when lead angle < friction angle (~5.5 deg).
        return math.degrees(self.worm.lead_angle) < 5.5

    def solids(self) -> List[Solid]:
        a = self.center_distance
        worm = Worm(self.worm).to_solid(name=f"worm_z{self.worm.starts}")
        # Worm axis = +z (as built); centre it on z.
        worm.translate(0.0, 0.0, -self.worm.length / 2.0)
        wheel = Gear(self.wheel, GearBuild(bore=self.wheel_bore)).to_solid(
            name=f"worm_wheel_z{self.wheel_teeth}")
        # Wheel axis perpendicular to the worm: rotate so its axis = +x, then
        # offset by the centre distance along +y.
        wheel.translate(0.0, 0.0, -self.wheel_face_width / 2.0)
        wheel.rotate_y(math.pi / 2.0)
        wheel.translate(0.0, a, 0.0)
        return [worm, wheel]

    def report(self, worm_rpm: float = 1500.0, input_torque: float = 5.0) -> dict:
        return {
            "module": self.worm.module,
            "worm_starts": self.worm.starts,
            "wheel_teeth": self.wheel_teeth,
            "ratio": round(self.ratio, 5),
            "worm_pitch_diameter": self.worm.pitch_diameter,
            "lead": round(self.worm.lead, 4),
            "lead_angle_deg": round(math.degrees(self.worm.lead_angle), 4),
            "centre_distance": round(self.center_distance, 4),
            "self_locking": self.self_locking(),
            "worm_rpm": worm_rpm,
            "wheel_rpm": round(worm_rpm / self.ratio, 4),
            "input_torque_Nm": input_torque,
            "output_torque_Nm": round(input_torque * self.ratio * 0.7, 3),
        }
