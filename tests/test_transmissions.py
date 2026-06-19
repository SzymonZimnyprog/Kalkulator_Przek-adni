"""Tests for the extended transmissions and body features."""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geargen import (GearParams, Gear, GearBuild, Keyway, Spline, Spokes, Hub,
                     LighteningHoles, PlanetaryParams, PlanetaryGearSet,
                     BevelPair, WormParams, WormDrive, RackParams, Rack,
                     RackAndPinion, analyse_mesh)


def manifold(solid):
    return solid.is_closed_manifold()


class TestBodyFeatures(unittest.TestCase):
    def test_root_fillet(self):
        s = Gear(GearParams(3, 14, face_width=10, root_fillet=0.9),
                 GearBuild(bore=8)).to_solid()
        self.assertTrue(manifold(s))

    def test_spline(self):
        s = Gear(GearParams(2, 24, face_width=12),
                 GearBuild(spline=Spline(8, 12, 15))).to_solid()
        self.assertTrue(manifold(s))

    def test_spokes(self):
        s = Gear(GearParams(3, 40, face_width=14),
                 GearBuild(bore=24, spokes=Spokes(5, 44, 95, 12))).to_solid()
        self.assertTrue(manifold(s))

    def test_hub(self):
        s = Gear(GearParams(2, 24, face_width=10),
                 GearBuild(bore=10, hub=Hub(24, 8))).to_solid()
        self.assertTrue(manifold(s))

    def test_hub_both_sides(self):
        s = Gear(GearParams(2, 24, face_width=10),
                 GearBuild(bore=10, hub=Hub(24, 6, both_sides=True))).to_solid()
        self.assertTrue(manifold(s))

    def test_spokes_and_hub(self):
        s = Gear(GearParams(3, 40, face_width=14),
                 GearBuild(bore=24, spokes=Spokes(5, 44, 95, 12),
                           hub=Hub(38, 10))).to_solid()
        self.assertTrue(manifold(s))

    def test_herringbone(self):
        s = Gear(GearParams(2, 30, helix_angle=25, face_width=24),
                 GearBuild(bore=14, herringbone=True)).to_solid()
        self.assertTrue(manifold(s))

    def test_hub_rejects_internal(self):
        with self.assertRaises(ValueError):
            Gear(GearParams(2, -50, face_width=10),
                 GearBuild(hub=Hub(20, 5))).to_solid()


class TestPlanetary(unittest.TestCase):
    def test_constraints_and_ratio(self):
        pp = PlanetaryParams(2, 24, 18, 3)
        self.assertEqual(pp.z_ring, 60)             # 24 + 2*18
        self.assertEqual(pp.validate(), [])         # assembly ok
        self.assertAlmostEqual(pp.ratio_ring_fixed(), 1 + 60 / 24, places=6)
        self.assertAlmostEqual(pp.carrier_radius, 2 * (24 + 18) / 2, places=6)

    def test_assembly_condition_detected(self):
        pp = PlanetaryParams(2, 25, 18, 4)          # (25+61)=86 not div by 4
        self.assertTrue(any("assembly" in w for w in pp.validate()))

    def test_solids_manifold(self):
        pgs = PlanetaryGearSet(PlanetaryParams(2, 24, 18, 3),
                               bore_sun=10, bore_planet=8)
        sols = pgs.solids()
        self.assertEqual(len(sols), 5)              # sun + 3 planets + ring
        for s in sols:
            self.assertTrue(manifold(s))


class TestBevel(unittest.TestCase):
    def test_right_angle_pair(self):
        pair = BevelPair.right_angle(3, 18, 27, 14)
        self.assertAlmostEqual(pair.ratio, 1.5, places=6)
        self.assertAlmostEqual(pair.pinion.pitch_angle + pair.wheel.pitch_angle,
                               90.0, places=4)
        for s in pair.solids():
            self.assertTrue(manifold(s))

    def test_pitch_angle_validation(self):
        from geargen import BevelParams
        with self.assertRaises(ValueError):
            BevelPair(BevelParams(3, 18, 20, 10), BevelParams(3, 27, 20, 10))


class TestWorm(unittest.TestCase):
    def test_ratio_and_lead(self):
        wd = WormDrive(WormParams(3, 2, 30, 50), wheel_teeth=40)
        self.assertAlmostEqual(wd.ratio, 20.0, places=6)
        self.assertAlmostEqual(wd.worm.lead, 2 * math.pi * 3, places=6)

    def test_solids_manifold(self):
        wd = WormDrive(WormParams(3, 2, 30, 40), wheel_teeth=40,
                       wheel_face_width=14)
        sols = wd.solids()
        self.assertEqual(len(sols), 2)
        for s in sols:
            self.assertTrue(manifold(s))

    def test_self_locking_single_start(self):
        wd = WormDrive(WormParams(2, 1, 40, 40), wheel_teeth=40)
        self.assertTrue(wd.self_locking())          # small lead angle


class TestRack(unittest.TestCase):
    def test_rack_manifold(self):
        self.assertTrue(manifold(Rack(RackParams(2, 12, face_width=10)).to_solid()))

    def test_rack_and_pinion(self):
        rp = RackAndPinion(GearParams(2, 16, face_width=10),
                           RackParams(2, 12, face_width=10))
        self.assertAlmostEqual(rp.travel_per_rev, math.pi * 32.0, places=4)
        for s in rp.solids():
            self.assertTrue(manifold(s))


class TestEngineering(unittest.TestCase):
    def test_forces(self):
        a = analyse_mesh(GearParams(2, 20, face_width=20), rpm=1000,
                         torque_Nm=50)
        # Ft = 2*T/d = 2*50000/40 = 2500 N
        self.assertAlmostEqual(a.tangential_force, 2500.0, places=1)
        self.assertAlmostEqual(a.radial_force,
                               2500.0 * math.tan(math.radians(20)), places=1)
        self.assertGreater(a.pitch_line_velocity, 0)
        self.assertGreater(a.bending_stress, 0)

    def test_helical_has_axial_force(self):
        a = analyse_mesh(GearParams(2, 20, helix_angle=20, face_width=20),
                         rpm=1000, torque_Nm=50)
        self.assertGreater(a.axial_force, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
