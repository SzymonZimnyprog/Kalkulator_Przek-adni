"""Rack (zebatka) and rack-and-pinion drive.

A rack is the limiting case of a gear with infinite radius: straight,
trapezoidal teeth.  Combined with a pinion it converts rotation into linear
motion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .geometry import GearParams
from .gear import Gear, GearBuild
from .solid import Solid, build_extrusion

XY = Tuple[float, float]


@dataclass
class RackParams:
    module: float
    teeth: int
    pressure_angle: float = 20.0
    face_width: float = 10.0          # extrusion depth (Z)
    base_height: float = 0.0          # bar height below the root line (mm)
    addendum_coef: float = 1.0
    dedendum_coef: float = 1.25

    @property
    def pitch(self) -> float:
        return math.pi * self.module

    @property
    def length(self) -> float:
        return self.teeth * self.pitch

    @property
    def addendum(self) -> float:
        return self.module * self.addendum_coef

    @property
    def dedendum(self) -> float:
        return self.module * self.dedendum_coef


def rack_profile(p: RackParams) -> List[XY]:
    """Closed CCW 2-D rack profile in the XY plane (teeth point +Y)."""
    m = p.module
    pitch = p.pitch
    ha = p.addendum
    hf = p.dedendum
    ta = math.tan(math.radians(p.pressure_angle))
    base = hf + (p.base_height if p.base_height > 0 else 2.0 * m)
    quarter = pitch / 4.0

    top: List[XY] = [(0.0, -hf)]
    for k in range(p.teeth):
        xc = (k + 0.5) * pitch
        top.append((xc - (quarter + hf * ta), -hf))   # left root
        top.append((xc - (quarter - ha * ta), ha))    # left tip
        top.append((xc + (quarter - ha * ta), ha))    # right tip
        top.append((xc + (quarter + hf * ta), -hf))   # right root
    top.append((p.length, -hf))

    # Close the bar (CCW): top edge L->R, then down the right side and back.
    loop = list(top)
    loop.append((p.length, -base))
    loop.append((0.0, -base))
    return loop


class Rack:
    def __init__(self, params: RackParams):
        self.params = params

    def to_solid(self, name: Optional[str] = None) -> Solid:
        p = self.params
        prof = rack_profile(p)
        layers = [(0.0, [list(prof)]), (p.face_width, [list(prof)])]
        return build_extrusion(layers, name=name or f"rack_z{p.teeth}")


@dataclass
class RackAndPinion:
    """A pinion meshing with a rack (rotation -> linear motion)."""
    pinion: GearParams
    rack: RackParams
    pinion_build: GearBuild = field(default_factory=GearBuild)

    def __post_init__(self):
        if abs(self.pinion.module - self.rack.module) > 1e-9:
            raise ValueError("pinion and rack must share the module")

    @property
    def travel_per_rev(self) -> float:
        """Linear rack travel per pinion revolution (mm)."""
        return math.pi * self.pinion.pitch_diameter

    def linear_speed(self, pinion_rpm: float) -> float:
        """Rack speed (mm/min) for a given pinion speed."""
        return pinion_rpm * self.travel_per_rev

    def solids(self) -> List[Solid]:
        rack = Rack(self.rack).to_solid(name="rack")
        pinion = Gear(self.pinion, self.pinion_build).to_solid(
            name=f"pinion_z{self.pinion.z}")
        # Pinion pitch circle tangent to the rack pitch line (y = 0 of the rack
        # = root line + dedendum).  Place pinion centre above the rack.
        rp = self.pinion.pitch_diameter / 2.0
        # Rack pitch line sits at y = 0 in rack_profile coordinates (teeth tips
        # at +addendum); centre the rack under the pinion.
        rack.translate(-self.rack.length / 2.0, 0.0, 0.0)
        # A tooth space of the pinion faces straight down (-Y) to receive a
        # rack tooth; rotate so a gap points down.
        phase = math.pi / 2.0 + math.pi / self.pinion.z
        pinion.rotate_z(phase).translate(0.0, rp, 0.0)
        return [rack, pinion]

    def report(self, pinion_rpm: float = 100.0) -> dict:
        return {
            "module": self.pinion.module,
            "pinion_teeth": self.pinion.z,
            "rack_teeth": self.rack.teeth,
            "pinion_pitch_diameter": round(self.pinion.pitch_diameter, 4),
            "travel_per_rev_mm": round(self.travel_per_rev, 4),
            "pinion_rpm": pinion_rpm,
            "rack_speed_mm_per_min": round(self.linear_speed(pinion_rpm), 3),
        }
