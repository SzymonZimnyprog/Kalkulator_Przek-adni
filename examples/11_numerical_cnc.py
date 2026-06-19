"""Example 11 - numerical generation (envelope/hob method) + CNC output.

Generates a gear profile by simulating a rolling rack cutter (real machined
shape with trochoidal root + undercut detection), then writes G-code for
wire-EDM, milling and laser, plus coordinate tables (CSV/JSON).

Run:  python examples/11_numerical_cnc.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import GearParams, Gear, GearBuild, write_step, cnc
from geargen.generating import generate_profile

p = GearParams(module=2.0, teeth=14, pressure_angle=20, face_width=8)

# Numerical generation (the manufacturing simulation).
res = generate_profile(p.module, p.z, p.pressure_angle, rolls=600, bins=240)
print("EXAMPLE 11 - NUMERICAL GENERATION + CNC")
print(f"  teeth z={p.z}  root r={res.root_radius:.3f}  tip r={res.tip_radius:.3f}")
print(f"  undercut detected: {res.undercut}  (z_min ~ 17 for 20 deg)")

# A real, machinable gear (generated profile) + STEP.
g = Gear(p, GearBuild(bore=10, keyway=__import__('geargen').Keyway(4, 1.8),
                      generated=True, gen_points=120))
loops = g.section_loops()

os.makedirs("output", exist_ok=True)
write_step(g.to_solid(), "output/11_generated.step", "generated_z14")

# CNC programs for every process.
cnc.write_gcode(cnc.gcode_wedm(loops, "GEAR z14 m2", feed=2.2), "output/11_gear.wedm.nc")
cnc.write_gcode(cnc.gcode_mill(loops, "GEAR z14 m2", depth=8, doc=1.5, tool_d=2),
                "output/11_gear.mill.nc")
cnc.write_gcode(cnc.gcode_laser(loops, "GEAR z14 m2", power=850), "output/11_gear.laser.nc")
cnc.to_csv(loops, "output/11_gear.csv")
cnc.to_json({"module": 2, "teeth": 14, "undercut": res.undercut}, loops,
            "output/11_gear.json")
print("\nWrote: 11_generated.step + .wedm.nc / .mill.nc / .laser.nc + .csv / .json")
