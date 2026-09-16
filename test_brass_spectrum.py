import hashlib
import unittest
import numpy as np
from brass_spectrum import synthesize,_profile

class BrassSpectrumTests(unittest.TestCase):
    def test_reproducible_unique_specimens(self):
        first=synthesize(61,256,192)
        np.testing.assert_array_equal(first,synthesize(61,256,192))
        hashes={hashlib.sha256(synthesize(seed,256,192).tobytes()).hexdigest() for seed in range(8)}
        self.assertEqual(len(hashes),8)
        self.assertTrue(np.isfinite(first).all())
        self.assertGreaterEqual(float(first.min()),.039)
        self.assertLessEqual(float(first.max()),.961)
        self.assertAlmostEqual(float(first.mean()),.5,delta=.005)
        self.assertAlmostEqual(float(first.std()),.06,delta=.005)

    def test_reference_has_no_pixels_phase_or_labeled_defect_overlap(self):
        p=_profile()
        self.assertEqual(np.asarray(p['log_power']).shape,(65,65))
        self.assertEqual(len(p['references']),3)
        self.assertTrue(all(r['no_label_overlap'] and r['checked_annotations']>0 for r in p['references']))
        self.assertNotIn('pixels',p)
        self.assertNotIn('phase',p)

    def test_physical_dimensions_change_texture_frequency(self):
        first=synthesize(62,256,192,length=8,radius=.9)
        self.assertFalse(np.array_equal(first,synthesize(62,256,192,length=6,radius=.9)))
        self.assertFalse(np.array_equal(first,synthesize(62,256,192,length=8,radius=.6)))

if __name__=='__main__':unittest.main()
