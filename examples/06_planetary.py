"""Example 6 - a planetary (epicyclic) gear set: sun + 3 planets + ring.

Run:  python examples/06_planetary.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import PlanetaryParams, PlanetaryGearSet, write_step

pp = PlanetaryParams(module=2, z_sun=24, z_planet=18, n_planets=3, face_width=12)
pgs = PlanetaryGearSet(pp, bore_sun=12, bore_planet=8)

print("EXAMPLE 6 - PLANETARY GEAR SET")
print(json.dumps(pgs.report(input_rpm=3000), indent=2))

os.makedirs("output", exist_ok=True)
write_step(pgs.solids(), "output/06_planetary.step", "planetary")
print("\nWrote output/06_planetary.step  (sun + 3 planets + ring, zero interference)")
