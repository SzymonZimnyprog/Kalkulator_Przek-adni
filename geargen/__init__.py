"""geargen - involute gear & transmission generator with STEP (CAD) export.

Pure-Python, dependency-free.  Typical use::

    from geargen import GearParams, Gear, write_step

    g = Gear(GearParams(module=2, teeth=24, face_width=12))
    write_step(g.to_solid(), "gear.step")

Supported gears:    spur, helical, herringbone, internal (ring), bevel, worm,
                    rack.
Supported drives:   gear pair, multi-stage train, planetary (epicyclic),
                    rack & pinion, bevel (right-angle), worm drive.
Body features:      bore, keyway, spline, lightening holes, spokes/web, hub,
                    root fillet.
"""

from .geometry import GearParams, gear_profile, tooth_profile
from .gear import (Gear, GearBuild, Keyway, Spline, LighteningHoles, Spokes,
                   Hub)
from .solid import Solid, Slab, build_extrusion, build_stepped
from .step import write_step, StepWriter
from .transmission import GearPair, GearTrain, Stage
from .planetary import PlanetaryGearSet, PlanetaryParams
from .bevel import BevelGear, BevelParams, BevelPair
from .worm import Worm, WormParams, WormDrive
from .rack import Rack, RackParams, RackAndPinion
from .engineering import analyse_mesh, MeshAnalysis

__version__ = "2.0.0"

__all__ = [
    # core
    "GearParams", "Gear", "GearBuild", "gear_profile", "tooth_profile",
    "Solid", "Slab", "build_extrusion", "build_stepped",
    "write_step", "StepWriter",
    # body features
    "Keyway", "Spline", "LighteningHoles", "Spokes", "Hub",
    # transmissions
    "GearPair", "GearTrain", "Stage",
    "PlanetaryGearSet", "PlanetaryParams",
    "BevelGear", "BevelParams", "BevelPair",
    "Worm", "WormParams", "WormDrive",
    "Rack", "RackParams", "RackAndPinion",
    # analysis
    "analyse_mesh", "MeshAnalysis",
    "__version__",
]
