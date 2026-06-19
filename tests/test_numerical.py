"""Tests for the numerical generator (envelope method) and CNC output."""

import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import (GearParams, Gear, GearBuild, generate_profile,
                     generated_gear_profile, cnc)
from geargen.geometry import polygon_area


class TestGenerating(unittest.TestCase):
    def test_diameters_match(self):
        res = generate_profile(m=2, z=24, pressure_angle=20, rolls=300, bins=160)
        p = GearParams(2, 24)
        self.assertAlmostEqual(res.root_radius, p.root_diameter / 2, places=3)
        self.assertAlmostEqual(res.tip_radius, p.tip_diameter / 2, places=3)
        self.assertAlmostEqual(res.base_radius, p.base_diameter / 2, places=3)

    def test_flank_matches_involute_thickness(self):
        # Generated tooth thickness at the pitch circle must equal the analytic
        # value (proves the flank is the correct involute).
        res = generate_profile(m=2, z=30, pressure_angle=20, rolls=500, bins=240)
        p = GearParams(2, 30)
        rp = p.pitch_diameter / 2
        half = math.pi / 30
        space_half = None
        for (r, th) in res.sector:
            if th > 0 and abs(r - rp) < 0.03:
                space_half = th
        self.assertIsNotNone(space_half)
        thickness = (2 * half - 2 * space_half) * rp
        self.assertAlmostEqual(thickness, p.tooth_thickness, places=2)

    def test_undercut_flag(self):
        self.assertTrue(generate_profile(m=2, z=10).undercut)
        self.assertTrue(generate_profile(m=2, z=14).undercut)
        self.assertFalse(generate_profile(m=2, z=20).undercut)
        # Profile shift removes undercut on a low tooth count.
        self.assertFalse(generate_profile(m=2, z=12, profile_shift=0.5).undercut)

    def test_generated_profile_closed_ccw(self):
        prof = generated_gear_profile(GearParams(2, 18), rolls=300, bins=150)
        self.assertGreater(polygon_area(prof), 0)               # CCW
        self.assertEqual(len(prof) % 18, 0)                     # z teeth

    def test_generated_solid_manifold(self):
        s = Gear(GearParams(2, 20, face_width=10),
                 GearBuild(bore=10, generated=True, gen_points=40)).to_solid()
        self.assertTrue(s.is_closed_manifold())


class TestCNC(unittest.TestCase):
    def setUp(self):
        self.gear = Gear(GearParams(2, 20, face_width=8),
                         GearBuild(bore=10))
        self.loops = self.gear.section_loops()

    def test_section_loops(self):
        self.assertEqual(len(self.loops), 2)        # outer + bore
        self.assertGreater(polygon_area(self.loops[0]), 0)      # outer CCW
        self.assertLess(polygon_area(self.loops[1]), 0)         # bore CW

    def test_wedm_gcode(self):
        g = cnc.gcode_wedm(self.loops, "T")
        self.assertTrue(g.startswith("%"))
        self.assertIn("G21", g)
        self.assertIn("G01", g)
        self.assertIn("M02", g)
        self.assertNotIn("Y-0\n", g)                # no negative zero

    def test_mill_gcode_passes(self):
        g = cnc.gcode_mill(self.loops, "T", depth=6, doc=2, tool_d=2)
        # 3 passes (-2,-4,-6), one set per contour (outer + bore).
        self.assertEqual(g.count("Z-6"), len(self.loops))
        self.assertIn("Z-2 ", g)
        self.assertIn("M30", g)

    def test_laser_gcode(self):
        g = cnc.gcode_laser(self.loops, "T", power=500)
        self.assertIn("S500", g)
        self.assertIn("M03", g)
        self.assertIn("M05", g)

    def test_csv_export(self):
        with tempfile.TemporaryDirectory() as d:
            path = cnc.to_csv(self.loops, os.path.join(d, "g.csv"))
            with open(path) as fh:
                lines = fh.read().splitlines()
        self.assertEqual(lines[0], "contour,point,x_mm,y_mm")
        self.assertGreater(len(lines), sum(len(l) for l in self.loops))

    def test_json_export(self):
        with tempfile.TemporaryDirectory() as d:
            path = cnc.to_json({"module": 2, "teeth": 20}, self.loops,
                               os.path.join(d, "g.json"))
            with open(path) as fh:
                data = json.load(fh)
        self.assertEqual(data["units"], "mm")
        self.assertEqual(len(data["contours"]), 2)
        self.assertEqual(data["metadata"]["teeth"], 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
