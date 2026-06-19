"""Example 10 - a fully-featured industrial gear: root fillet, spoked web, hub,
lightening + keyway... showing the body-structure options.

Run:  python examples/10_complex_gear.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import GearParams, Gear, GearBuild, Spokes, Hub, write_step
from geargen.report import datasheet

params = GearParams(module=4, teeth=50, helix_angle=12, face_width=30,
                    root_fillet=1.2)
build = GearBuild(
    bore=40,
    spokes=Spokes(count=6, hub_diameter=80, rim_inner_diameter=170, spoke_width=22),
    hub=Hub(diameter=70, height=18, both_sides=True),
)
print(datasheet(params, "EXAMPLE 10 - COMPLEX INDUSTRIAL GEAR"))

os.makedirs("output", exist_ok=True)
write_step(Gear(params, build).to_solid(), "output/10_complex_gear.step", "complex_gear")
print("\nWrote output/10_complex_gear.step  (helical + fillet + 6 spokes + hubs)")
