"""Engineering analysis of a gear mesh: kinematics, forces and strength.

Provides pitch-line velocity, the tooth forces (tangential / radial / axial /
normal), a Lewis bending-stress estimate with a velocity (dynamic) factor, and
transmitted power.  Units: mm, N, MPa (N/mm^2), m/s, rpm, W.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .geometry import GearParams


def lewis_form_factor(z: int) -> float:
    """Module-based Lewis form factor Y for 20 deg full-depth teeth.

    Used as ``sigma = Ft / (b * m * Y)``.  Approximation Y = 0.484 - 2.87/z.
    """
    z = max(abs(z), 10)
    return 0.484 - 2.87 / z


def velocity_factor(v: float, quality: str = "cut") -> float:
    """Barth velocity (dynamic) factor Kv for pitch-line velocity v [m/s]."""
    if quality == "precision":          # hobbed/ground, high quality
        return (5.56 + math.sqrt(v)) / 5.56
    if quality == "commercial":
        return (3.05 + v) / 3.05
    return (6.1 + v) / 6.1               # ordinary cut gears


@dataclass
class MeshAnalysis:
    pitch_line_velocity: float          # m/s
    tangential_force: float             # N (Ft)
    radial_force: float                 # N (Fr)
    axial_force: float                  # N (Fa, helical/worm)
    normal_force: float                 # N (Fn)
    transmitted_power: float            # W
    bending_stress: float               # MPa (Lewis, with Kv)
    velocity_factor: float
    lewis_Y: float
    torque: float                       # Nm on this gear

    def as_dict(self) -> dict:
        return {
            "pitch_line_velocity_m_s": round(self.pitch_line_velocity, 4),
            "torque_Nm": round(self.torque, 4),
            "transmitted_power_W": round(self.transmitted_power, 2),
            "tangential_force_Ft_N": round(self.tangential_force, 2),
            "radial_force_Fr_N": round(self.radial_force, 2),
            "axial_force_Fa_N": round(self.axial_force, 2),
            "normal_force_Fn_N": round(self.normal_force, 2),
            "lewis_form_factor_Y": round(self.lewis_Y, 4),
            "velocity_factor_Kv": round(self.velocity_factor, 4),
            "bending_stress_MPa": round(self.bending_stress, 2),
        }


def analyse_mesh(gear: GearParams, rpm: float,
                 torque_Nm: Optional[float] = None,
                 power_kW: Optional[float] = None,
                 quality: str = "cut") -> MeshAnalysis:
    """Analyse one gear given its speed and either input torque or power."""
    d = gear.pitch_diameter                     # mm
    alpha_t = gear.alpha_t
    beta = gear.beta

    v = math.pi * d * rpm / 60000.0             # m/s  (d mm -> m)
    omega = 2.0 * math.pi * rpm / 60.0          # rad/s

    if torque_Nm is None and power_kW is None:
        raise ValueError("supply torque_Nm or power_kW")
    if torque_Nm is None:
        torque_Nm = power_kW * 1000.0 / omega if omega else 0.0
    power_W = torque_Nm * omega

    ft = 2.0 * (torque_Nm * 1000.0) / d         # N  (torque Nmm / radius mm)
    fr = ft * math.tan(alpha_t)
    fa = ft * math.tan(beta)
    fn = ft / max(math.cos(alpha_t) * math.cos(beta), 1e-6)

    Y = lewis_form_factor(gear.z)
    kv = velocity_factor(v, quality)
    b = gear.face_width
    sigma = ft * kv / (b * gear.module * Y) if (b and Y) else 0.0

    return MeshAnalysis(v, ft, fr, fa, fn, power_W, sigma, kv, Y, torque_Nm)
