"""Planetary (epicyclic) gear set: sun + planets + ring + carrier.

Geometry constraints (equal module, standard teeth)::

    z_ring = z_sun + 2 * z_planet
    carrier radius  rc = m * (z_sun + z_planet) / 2
    assembly:  (z_sun + z_ring) must be divisible by the planet count

Speed ratios depend on which member is held::

    ring fixed  : i = n_sun / n_carrier = 1 + z_ring / z_sun
    sun fixed   : i = n_ring / n_carrier = 1 + z_sun / z_ring
    carrier fix : i = n_ring / n_sun     = -z_ring / z_sun   (star, reversing)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional

from .geometry import GearParams
from .gear import Gear, GearBuild
from .solid import Solid


@dataclass
class PlanetaryParams:
    module: float
    z_sun: int
    z_planet: int
    n_planets: int = 3
    pressure_angle: float = 20.0
    face_width: float = 10.0

    @property
    def z_ring(self) -> int:
        return self.z_sun + 2 * self.z_planet

    @property
    def carrier_radius(self) -> float:
        return self.module * (self.z_sun + self.z_planet) / 2.0

    def validate(self) -> List[str]:
        msgs = []
        if (self.z_sun + self.z_ring) % self.n_planets != 0:
            msgs.append(
                f"assembly condition failed: (z_sun+z_ring)="
                f"{self.z_sun + self.z_ring} not divisible by "
                f"n_planets={self.n_planets}")
        if self.z_planet < 3:
            msgs.append("z_planet too small")
        # Adjacent planets must not collide.
        if self.n_planets > 1:
            gap = 2.0 * self.carrier_radius * math.sin(math.pi / self.n_planets)
            tip = self.module * (self.z_planet + 2.0)
            if gap <= tip:
                msgs.append("planets collide: reduce n_planets or z_planet")
        return msgs

    # -- ratios ------------------------------------------------------------ #
    def ratio_ring_fixed(self) -> float:
        return 1.0 + self.z_ring / self.z_sun

    def ratio_sun_fixed(self) -> float:
        return 1.0 + self.z_sun / self.z_ring

    def ratio_carrier_fixed(self) -> float:
        return -self.z_ring / self.z_sun


class PlanetaryGearSet:
    def __init__(self, params: PlanetaryParams,
                 bore_sun: float = 0.0, bore_planet: float = 0.0,
                 build: Optional[GearBuild] = None):
        self.p = params
        self.bore_sun = bore_sun
        self.bore_planet = bore_planet
        self._build = build or GearBuild()

    def _gp(self, teeth: int) -> GearParams:
        return GearParams(module=self.p.module, teeth=teeth,
                          pressure_angle=self.p.pressure_angle,
                          face_width=self.p.face_width)

    def _build_for(self, bore: float) -> GearBuild:
        b = self._build
        return GearBuild(bore=bore, flank_pts=b.flank_pts, arc_pts=b.arc_pts)

    def planet_phase(self, theta: float) -> float:
        """Orientation of a planet whose centre sits at angle ``theta``."""
        zs, zp = self.p.z_sun, self.p.z_planet
        return theta * (1.0 - zs / zp) + (math.pi - math.pi / zp)

    def ring_phase(self) -> float:
        """Ring rotation so its teeth mesh the planets (internal mesh)."""
        zr = self.p.z_ring
        # A ring tooth space must face each planet; with the assembly condition
        # satisfied, phasing to planet 0 (on +x) phases them all.
        return math.pi / zr

    def solids(self, with_ring: bool = True) -> List[Solid]:
        p = self.p
        rc = p.carrier_radius
        out: List[Solid] = []

        sun = Gear(self._gp(p.z_sun), self._build_for(self.bore_sun)).to_solid(
            name=f"sun_z{p.z_sun}")
        # Sun: a tooth space should face planet 0 just like an external pair.
        sun.rotate_z(math.pi - math.pi / p.z_sun)
        out.append(sun)

        for k in range(p.n_planets):
            theta = 2.0 * math.pi * k / p.n_planets
            planet = Gear(self._gp(p.z_planet),
                          self._build_for(self.bore_planet)).to_solid(
                name=f"planet{k+1}_z{p.z_planet}")
            planet.rotate_z(self.planet_phase(theta))
            planet.translate(rc * math.cos(theta), rc * math.sin(theta), 0.0)
            out.append(planet)

        if with_ring:
            ring = Gear(self._gp(-p.z_ring), self._build_for(0.0)).to_solid(
                name=f"ring_z{p.z_ring}")
            ring.rotate_z(self.ring_phase())
            out.append(ring)
        return out

    def report(self, input_rpm: float = 1500.0) -> dict:
        p = self.p
        return {
            "module": p.module,
            "z_sun": p.z_sun,
            "z_planet": p.z_planet,
            "z_ring": p.z_ring,
            "n_planets": p.n_planets,
            "carrier_radius": round(p.carrier_radius, 4),
            "ratio_ring_fixed": round(p.ratio_ring_fixed(), 5),
            "ratio_sun_fixed": round(p.ratio_sun_fixed(), 5),
            "ratio_carrier_fixed": round(p.ratio_carrier_fixed(), 5),
            "input_rpm": input_rpm,
            "carrier_rpm_ring_fixed": round(input_rpm / p.ratio_ring_fixed(), 3),
            "warnings": p.validate(),
        }
