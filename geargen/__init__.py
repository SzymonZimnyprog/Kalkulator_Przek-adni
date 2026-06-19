"""geargen - involute gear & gear-train generator with STEP (CAD) export.

Pure-Python, dependency-free.  Typical use::

    from geargen import GearParams, Gear, write_step

    g = Gear(GearParams(module=2, teeth=24, face_width=12), )
    write_step(g.to_solid(), "gear.step")
"""

from .geometry import GearParams, gear_profile, tooth_profile
from .gear import Gear, GearBuild, Keyway, LighteningHoles
from .solid import Solid, build_extrusion
from .step import write_step, StepWriter
from .transmission import GearPair, GearTrain

__version__ = "1.0.0"

__all__ = [
    "GearParams",
    "Gear",
    "GearBuild",
    "Keyway",
    "LighteningHoles",
    "Solid",
    "build_extrusion",
    "gear_profile",
    "tooth_profile",
    "write_step",
    "StepWriter",
    "GearPair",
    "GearTrain",
    "__version__",
]
