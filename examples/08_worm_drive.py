"""Example 8 - a worm drive (large reduction in one stage).

Run:  python examples/08_worm_drive.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import WormParams, WormDrive, write_step

wd = WormDrive(WormParams(module=3, starts=2, pitch_diameter=32, length=55, bore=12),
               wheel_teeth=40, wheel_face_width=18, wheel_bore=16)
print("EXAMPLE 8 - WORM DRIVE")
print(json.dumps(wd.report(worm_rpm=1500, input_torque=6), indent=2))

os.makedirs("output", exist_ok=True)
write_step(wd.solids(), "output/08_worm_drive.step", "worm_drive")
print("\nWrote output/08_worm_drive.step  (ratio %.0f:1)" % wd.ratio)
