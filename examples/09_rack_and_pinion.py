"""Example 9 - rack and pinion (rotation -> linear motion).

Run:  python examples/09_rack_and_pinion.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import GearParams, RackParams, RackAndPinion, GearBuild, write_step

rp = RackAndPinion(GearParams(module=2, teeth=18, face_width=12),
                   RackParams(module=2, teeth=16, face_width=12),
                   GearBuild(bore=10))
print("EXAMPLE 9 - RACK & PINION")
print(json.dumps(rp.report(pinion_rpm=120), indent=2))

os.makedirs("output", exist_ok=True)
write_step(rp.solids(), "output/09_rack_pinion.step", "rack_pinion")
print("\nWrote output/09_rack_pinion.step")
