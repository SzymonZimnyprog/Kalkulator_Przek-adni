"""Gear transmissions: meshing pairs and multi-stage trains.

Computes gear ratios, (working) centre distances and the relative phase needed
for two gears to mesh, and assembles the gears into positioned solids ready for
a single STEP file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .geometry import GearParams, involute
from .gear import Gear, GearBuild
from .solid import Solid


def _inv_inverse(inv_value: float) -> float:
    """Invert the involute function (find a such that inv(a) = value)."""
    a = 0.4
    for _ in range(60):
        f = math.tan(a) - a - inv_value
        df = 1.0 / math.cos(a) ** 2 - 1.0
        if abs(df) < 1e-12:
            break
        a -= f / df
        a = min(max(a, 1e-6), math.radians(89.0))
    return a


@dataclass
class GearPair:
    """A meshing pinion + wheel.

    The pinion sits at the origin; the wheel is placed at the working centre
    distance along +x and phased so the teeth mesh.  A negative ``wheel.teeth``
    makes it an internal (ring) mesh.
    """

    pinion: GearParams
    wheel: GearParams
    pinion_build: GearBuild = field(default_factory=GearBuild)
    wheel_build: GearBuild = field(default_factory=GearBuild)

    def __post_init__(self):
        if abs(self.pinion.module - self.wheel.module) > 1e-9:
            raise ValueError("meshing gears must share the same module")
        if abs(self.pinion.pressure_angle - self.wheel.pressure_angle) > 1e-9:
            raise ValueError("meshing gears must share the same pressure angle")

    # -- ratings ----------------------------------------------------------- #
    @property
    def internal(self) -> bool:
        return self.wheel.internal

    @property
    def ratio(self) -> float:
        """Speed ratio i = n_pinion / n_wheel = z_wheel / z_pinion."""
        return self.wheel.z / self.pinion.z

    @property
    def reference_center(self) -> float:
        m = self.pinion.module
        beta = self.pinion.beta
        if self.internal:
            return m * (self.wheel.z - self.pinion.z) / (2.0 * math.cos(beta))
        return m * (self.pinion.z + self.wheel.z) / (2.0 * math.cos(beta))

    @property
    def working_center(self) -> float:
        """Working centre distance accounting for profile shift."""
        p, w = self.pinion, self.wheel
        x_sum = p.profile_shift + (w.profile_shift if not self.internal
                                   else -w.profile_shift)
        if abs(x_sum) < 1e-12:
            return self.reference_center
        z_sum = (p.z + w.z) if not self.internal else (w.z - p.z)
        inv_aw = involute(p.alpha_t) + 2.0 * x_sum / z_sum * math.tan(p.alpha)
        alpha_w = _inv_inverse(inv_aw)
        return self.reference_center * math.cos(p.alpha_t) / math.cos(alpha_w)

    @property
    def contact_ratio(self) -> float:
        """Transverse contact ratio (approximate, external mesh)."""
        p, w = self.pinion, self.wheel
        if self.internal:
            return float("nan")
        m = p.module
        ra1 = p.tip_diameter / 2.0
        ra2 = w.tip_diameter / 2.0
        rb1 = p.base_diameter / 2.0
        rb2 = w.base_diameter / 2.0
        a = self.working_center
        at = p.alpha_t
        try:
            g = (math.sqrt(max(ra1 ** 2 - rb1 ** 2, 0)) +
                 math.sqrt(max(ra2 ** 2 - rb2 ** 2, 0)) -
                 a * math.sin(at))
            pb = math.pi * m * math.cos(at)
            return g / pb
        except ValueError:
            return float("nan")

    def output_speed(self, input_rpm: float) -> float:
        return input_rpm / self.ratio

    def output_torque(self, input_torque: float, efficiency: float = 0.98) -> float:
        return input_torque * self.ratio * efficiency

    # -- meshing phase ----------------------------------------------------- #
    def wheel_phase(self) -> float:
        """Rotation (rad) applied to the wheel so its teeth mesh the pinion."""
        z2 = self.wheel.z
        if self.internal:
            # Internal gear: a tooth faces the pinion's tooth space.
            return math.pi
        # External gear: a tooth *space* faces the pinion's tooth at the
        # line of centres (angle 0 on the pinion, angle pi on the wheel).
        return math.pi - math.pi / z2

    # -- assembly ---------------------------------------------------------- #
    def solids(self) -> List[Solid]:
        a = self.working_center
        pinion = Gear(self.pinion, self.pinion_build).to_solid(
            name=f"pinion_z{self.pinion.z}")
        wheel = Gear(self.wheel, self.wheel_build).to_solid(
            name=f"wheel_z{self.wheel.z}")
        wheel.rotate_z(self.wheel_phase()).translate(a, 0.0, 0.0)
        return [pinion, wheel]

    def report(self, input_rpm: float = 1500.0,
               input_torque: float = 10.0) -> dict:
        return {
            "type": "internal" if self.internal else "external",
            "module": self.pinion.module,
            "z_pinion": self.pinion.z,
            "z_wheel": self.wheel.z,
            "ratio": round(self.ratio, 5),
            "reference_center_distance": round(self.reference_center, 5),
            "working_center_distance": round(self.working_center, 5),
            "contact_ratio": round(self.contact_ratio, 4),
            "input_rpm": input_rpm,
            "output_rpm": round(self.output_speed(input_rpm), 3),
            "input_torque_Nm": input_torque,
            "output_torque_Nm": round(self.output_torque(input_torque), 4),
        }


@dataclass
class Stage:
    pinion: GearParams
    wheel: GearParams


class GearTrain:
    """A multi-stage gear train (series of meshing stages).

    Each stage's wheel shares a shaft with the next stage's pinion.  Overall
    ratio is the product of the stage ratios.  Solids are laid out with shaft
    centres along +x and successive stages stacked in z so nothing collides.
    """

    def __init__(self, stages: List[Stage],
                 builds: Optional[List[Tuple[GearBuild, GearBuild]]] = None):
        if not stages:
            raise ValueError("a train needs at least one stage")
        self.stages = stages
        self.builds = builds

    @property
    def pairs(self) -> List[GearPair]:
        out = []
        for i, st in enumerate(self.stages):
            if self.builds:
                pb, wb = self.builds[i]
            else:
                pb, wb = GearBuild(), GearBuild()
            out.append(GearPair(st.pinion, st.wheel, pb, wb))
        return out

    @property
    def ratio(self) -> float:
        r = 1.0
        for pair in self.pairs:
            r *= pair.ratio
        return r

    def output_speed(self, input_rpm: float) -> float:
        return input_rpm / self.ratio

    def solids(self) -> List[Solid]:
        solids: List[Solid] = []
        shaft_x = 0.0
        z_off = 0.0
        prev_wheel_solid_added = False
        for i, pair in enumerate(self.pairs):
            a = pair.working_center
            pinion = Gear(pair.pinion, pair.pinion_build).to_solid(
                name=f"s{i+1}_pinion_z{pair.pinion.z}")
            pinion.translate(shaft_x, 0.0, z_off)
            wheel = Gear(pair.wheel, pair.wheel_build).to_solid(
                name=f"s{i+1}_wheel_z{pair.wheel.z}")
            wheel.rotate_z(pair.wheel_phase()).translate(shaft_x + a, 0.0, z_off)
            solids.append(pinion)
            solids.append(wheel)
            # Next stage pinion sits on this stage's wheel shaft, stacked in z.
            shaft_x += a
            z_off += max(pair.pinion.face_width, pair.wheel.face_width) * 1.2
        return solids

    def report(self, input_rpm: float = 1500.0) -> dict:
        stages = [p.report(input_rpm) for p in self.pairs]
        return {
            "stages": len(self.stages),
            "overall_ratio": round(self.ratio, 5),
            "input_rpm": input_rpm,
            "output_rpm": round(self.output_speed(input_rpm), 3),
            "stage_details": stages,
        }
