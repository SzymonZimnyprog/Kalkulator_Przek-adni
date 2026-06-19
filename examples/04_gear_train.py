"""Example 4 - a two-stage reduction gear train (overall ratio 9:1).

Run:  python examples/04_gear_train.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import GearParams, GearTrain, write_step
from geargen.transmission import Stage

train = GearTrain([
    Stage(GearParams(module=1.5, teeth=16, face_width=10),
          GearParams(module=1.5, teeth=48, face_width=10)),   # i1 = 3.0
    Stage(GearParams(module=2.0, teeth=18, face_width=12),
          GearParams(module=2.0, teeth=54, face_width=12)),   # i2 = 3.0
])

print("EXAMPLE 4 - GEAR TRAIN")
print(json.dumps(train.report(input_rpm=2900), indent=2))

os.makedirs("output", exist_ok=True)
write_step(train.solids(), "output/04_gear_train.step", "gear_train")
print("\nWrote output/04_gear_train.step  (4 gears, stages stacked in Z)")
