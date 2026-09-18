"""Repeatability and physical-scale properties of the camera finish field."""
import unittest
import math
import numpy as np
from assembly_finish import grain_field


class AssemblyFinishTests(unittest.TestCase):
    def test_finish_is_repeatable_and_seed_specific(self):
        a=grain_field(31,6.6,.62,384,256)
        self.assertTrue(np.array_equal(a,grain_field(31,6.6,.62,384,256)))
        self.assertFalse(np.array_equal(a,grain_field(32,6.6,.62,384,256)))
        self.assertTrue(np.isfinite(a).all())
        self.assertGreaterEqual(a.min(),.08);self.assertLessEqual(a.max(),.92)
        self.assertAlmostEqual(float(a.mean()),.5,places=3)
        self.assertAlmostEqual(float(a.std()),.065,places=3)

    def test_grain_is_finer_around_the_circumference_without_seam(self):
        a=grain_field(31,6.6,.62,1024,768)
        dx=np.diff(a,axis=1)/(6.6/1024)
        dy=np.diff(a,axis=0)/(math.tau*.62/768)
        self.assertLess(float(dx.std()),float(dy.std())*.8)
        seam=(a[0]-a[-1]).std();interior=np.diff(a,axis=0).std()
        self.assertTrue(.6<float(seam/interior)<1.4)


if __name__=='__main__':unittest.main()
