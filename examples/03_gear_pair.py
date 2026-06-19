"""Example 3 - a meshing gear pair (transmission stage) in a single STEP file.

Run:  python examples/03_gear_pair.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import GearParams, GearPair, GearBuild, write_step

pinion = GearParams(module=2.0, teeth=18, face_width=14)
wheel = GearParams(module=2.0, teeth=45, face_width=14)

pair = GearPair(
    pinion, wheel,
    pinion_build=GearBuild(bore=10),
    wheel_build=GearBuild(bore=16),
)

print("EXAMPLE 3 - GEAR PAIR")
print(json.dumps(pair.report(input_rpm=1500, input_torque=15), indent=2))

os.makedirs("output", exist_ok=True)
write_step(pair.solids(), "output/03_gear_pair.step", "pair_18_45")
print("\nWrote output/03_gear_pair.step  (pinion + wheel, meshed)")
