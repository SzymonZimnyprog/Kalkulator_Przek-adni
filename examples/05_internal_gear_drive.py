"""Example 5 - an internal (ring) gear meshing with a pinion.

Run:  python examples/05_internal_gear_drive.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import GearParams, GearPair, GearBuild, write_step

pinion = GearParams(module=2.0, teeth=18, face_width=12)
ring = GearParams(module=2.0, teeth=-60, face_width=12)   # negative => internal

pair = GearPair(pinion, ring, pinion_build=GearBuild(bore=10))

print("EXAMPLE 5 - INTERNAL GEAR DRIVE")
print(f"  ratio                {pair.ratio:.4f}")
print(f"  centre distance      {pair.working_center:.3f} mm")

os.makedirs("output", exist_ok=True)
write_step(pair.solids(), "output/05_internal_drive.step", "internal_drive")
print("\nWrote output/05_internal_drive.step")
