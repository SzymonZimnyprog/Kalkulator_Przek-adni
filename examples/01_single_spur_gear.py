"""Example 1 - a single spur gear with a bore and keyway.

Run:  python examples/01_single_spur_gear.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import GearParams, Gear, GearBuild, write_step
from geargen.gear import Keyway
from geargen.report import datasheet, gear_dxf, gear_svg

params = GearParams(
    module=2.0,        # m = 2 mm
    teeth=24,          # z = 24
    pressure_angle=20, # standard
    face_width=12,     # b = 12 mm
)
build = GearBuild(
    bore=12.0,                       # 12 mm shaft bore
    keyway=Keyway(width=4, depth=1.8),
)

print(datasheet(params, "EXAMPLE 1 - SPUR GEAR"))

os.makedirs("output", exist_ok=True)
write_step(Gear(params, build).to_solid(), "output/01_spur_gear.step", "spur_z24")
gear_dxf(params, "output/01_spur_gear.dxf", with_bore=12)
gear_svg(params, "output/01_spur_gear.svg", with_bore=12)
print("\nWrote output/01_spur_gear.step / .dxf / .svg")
