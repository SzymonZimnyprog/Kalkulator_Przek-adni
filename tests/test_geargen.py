"""Dependency-free test-suite for geargen.

Run with either::

    python -m unittest discover -s tests
    pytest
"""

import math
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import (GearParams, Gear, GearBuild, GearPair, GearTrain,
                     gear_profile, write_step)
from geargen.gear import Keyway, LighteningHoles
from geargen.geometry import polygon_area
from geargen.transmission import Stage


class TestGeometry(unittest.TestCase):
    def test_standard_diameters(self):
        p = GearParams(module=2.0, teeth=20, pressure_angle=20.0)
        self.assertAlmostEqual(p.pitch_diameter, 40.0, places=6)
        self.assertAlmostEqual(p.base_diameter, 40.0 * math.cos(math.radians(20)), places=6)
        self.assertAlmostEqual(p.tip_diameter, 44.0, places=6)       # +2*m*ha
        self.assertAlmostEqual(p.root_diameter, 35.0, places=6)      # -2*m*hf
        self.assertAlmostEqual(p.circular_pitch, math.pi * 2.0, places=6)

    def test_profile_shift_changes_diameters(self):
        p = GearParams(module=2.0, teeth=20, profile_shift=0.5)
        self.assertAlmostEqual(p.tip_diameter, 40.0 + 2 * 2.0 * (1.0 + 0.5), places=6)
        self.assertAlmostEqual(p.root_diameter, 40.0 - 2 * 2.0 * (1.25 - 0.5), places=6)

    def test_helical_pitch_diameter(self):
        p = GearParams(module=2.0, teeth=20, helix_angle=20.0)
        self.assertAlmostEqual(p.pitch_diameter, 40.0 / math.cos(math.radians(20)), places=6)

    def test_profile_closed_ccw_and_radii(self):
        p = GearParams(module=2.0, teeth=18)
        prof = gear_profile(p, flank_pts=12, arc_pts=4)
        self.assertGreater(len(prof), 18 * 4)
        self.assertGreater(polygon_area(prof), 0)                    # CCW
        radii = [math.hypot(x, y) for x, y in prof]
        self.assertAlmostEqual(min(radii), p.root_diameter / 2, places=3)
        self.assertAlmostEqual(max(radii), p.tip_diameter / 2, places=3)


class TestSolidValidity(unittest.TestCase):
    def _check(self, solid):
        self.assertTrue(solid.is_closed_manifold(),
                        "solid is not a closed manifold (not watertight)")
        self.assertGreater(len(solid.verts), 0)

    def test_spur(self):
        self._check(Gear(GearParams(module=2, teeth=20, face_width=10)).to_solid())

    def test_spur_with_bore(self):
        self._check(Gear(GearParams(module=2, teeth=20, face_width=10),
                         GearBuild(bore=10)).to_solid())

    def test_keyway(self):
        self._check(Gear(GearParams(module=2, teeth=20, face_width=10),
                         GearBuild(bore=12, keyway=Keyway(4, 1.8))).to_solid())

    def test_lightening_holes(self):
        self._check(Gear(GearParams(module=3, teeth=40, face_width=12),
                         GearBuild(bore=20,
                                   lightening=LighteningHoles(6, 14, 75))).to_solid())

    def test_helical(self):
        self._check(Gear(GearParams(module=2, teeth=24, helix_angle=20,
                                    face_width=15), GearBuild(bore=12)).to_solid())

    def test_internal(self):
        self._check(Gear(GearParams(module=2, teeth=-50, face_width=12)).to_solid())

    def test_profile_shifted(self):
        self._check(Gear(GearParams(module=2, teeth=12, profile_shift=0.5,
                                    face_width=10)).to_solid())


class TestStepFile(unittest.TestCase):
    def test_step_structure(self):
        solid = Gear(GearParams(module=2, teeth=16, face_width=8),
                     GearBuild(bore=8)).to_solid()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "g.step")
            write_step(solid, path, product="g")
            with open(path) as fh:
                text = fh.read()
        self.assertTrue(text.startswith("ISO-10303-21;"))
        self.assertIn("END-ISO-10303-21;", text)
        self.assertIn("MANIFOLD_SOLID_BREP", text)
        self.assertIn("CLOSED_SHELL", text)
        self.assertIn("ADVANCED_BREP_SHAPE_REPRESENTATION", text)
        # No dangling references: every #N used must be defined.
        defined = set(int(m) for m in re.findall(r"^#(\d+)=", text, re.M))
        used = set(int(m) for m in re.findall(r"#(\d+)", text))
        self.assertTrue(used.issubset(defined),
                        f"dangling refs: {sorted(used - defined)[:10]}")

    def test_multiple_solids_in_one_file(self):
        pair = GearPair(GearParams(module=2, teeth=18, face_width=10),
                        GearParams(module=2, teeth=36, face_width=10))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "pair.step")
            write_step(pair.solids(), path)
            with open(path) as fh:
                text = fh.read()
        self.assertEqual(text.count("MANIFOLD_SOLID_BREP"), 2)


class TestTransmission(unittest.TestCase):
    def test_ratio_and_center(self):
        pair = GearPair(GearParams(module=2, teeth=18, face_width=10),
                        GearParams(module=2, teeth=36, face_width=10))
        self.assertAlmostEqual(pair.ratio, 2.0, places=6)
        self.assertAlmostEqual(pair.reference_center, 54.0, places=6)
        self.assertAlmostEqual(pair.working_center, 54.0, places=6)  # x=0
        self.assertAlmostEqual(pair.output_speed(1500), 750.0, places=3)

    def test_contact_ratio_reasonable(self):
        pair = GearPair(GearParams(module=2, teeth=18, face_width=10),
                        GearParams(module=2, teeth=36, face_width=10))
        self.assertGreater(pair.contact_ratio, 1.0)
        self.assertLess(pair.contact_ratio, 2.5)

    def test_both_solids_manifold(self):
        pair = GearPair(GearParams(module=2, teeth=18, face_width=10),
                        GearParams(module=2, teeth=36, face_width=10))
        for s in pair.solids():
            self.assertTrue(s.is_closed_manifold())

    def test_train_ratio(self):
        train = GearTrain([
            Stage(GearParams(module=1.5, teeth=16, face_width=8),
                  GearParams(module=1.5, teeth=48, face_width=8)),
            Stage(GearParams(module=1.5, teeth=18, face_width=8),
                  GearParams(module=1.5, teeth=54, face_width=8)),
        ])
        self.assertAlmostEqual(train.ratio, 9.0, places=6)
        self.assertEqual(len(train.solids()), 4)

    def test_profile_shift_changes_center(self):
        pair = GearPair(GearParams(module=2, teeth=18, profile_shift=0.3, face_width=10),
                        GearParams(module=2, teeth=36, profile_shift=0.3, face_width=10))
        self.assertGreater(pair.working_center, pair.reference_center)


if __name__ == "__main__":
    unittest.main(verbosity=2)
