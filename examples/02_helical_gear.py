"""Example 2 - a helical gear (20 deg helix) with lightening holes.

Run:  python examples/02_helical_gear.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import GearParams, Gear, GearBuild, write_step
from geargen.gear import LighteningHoles
from geargen.report import datasheet

params = GearParams(module=3.0, teeth=40, helix_angle=20.0, face_width=20.0)
build = GearBuild(
    bore=25.0,
    lightening=LighteningHoles(count=6, diameter=18, pitch_circle=85),
)

print(datasheet(params, "EXAMPLE 2 - HELICAL GEAR"))

os.makedirs("output", exist_ok=True)
write_step(Gear(params, build).to_solid(), "output/02_helical_gear.step", "helical_z40")
print("\nWrote output/02_helical_gear.step")
