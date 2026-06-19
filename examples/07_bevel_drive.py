"""Example 7 - a 90-degree straight bevel drive.

Run:  python examples/07_bevel_drive.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import BevelPair, write_step

pair = BevelPair.right_angle(module=3, z_pinion=18, z_wheel=27,
                             face_width=14, bore_p=10, bore_w=16)
print("EXAMPLE 7 - BEVEL DRIVE (90 deg)")
print(json.dumps(pair.report(input_rpm=1200, input_torque=18), indent=2))

os.makedirs("output", exist_ok=True)
write_step(pair.solids(), "output/07_bevel_drive.step", "bevel_pair")
print("\nWrote output/07_bevel_drive.step")
