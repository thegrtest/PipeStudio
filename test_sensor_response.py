import unittest
import numpy as np
from sensor_response import apply_sensor_noise
from environment_fields import profiles,sample_field

class SensorResponseTests(unittest.TestCase):
    def test_noise_is_repeatable_and_preserves_alpha(self):
        p=dict(environment='GODSLIGHT',inspection_camera='CAM2534',resolution=1936,sensor_noise=.01,seed=123)
        source=np.full((10000,4),.1,dtype=np.float32);source[:,3]=.4
        first=apply_sensor_noise(source.copy(),p);second=apply_sensor_noise(source.copy(),p)
        np.testing.assert_array_equal(first,second)
        np.testing.assert_array_equal(first[:,3],source[:,3])
        self.assertGreater(np.std(first[:,2]),np.std(first[:,1])*2)
        self.assertTrue(np.isfinite(first).all())
        self.assertTrue(((first>=0)&(first<=1)).all())

    def test_disabled_noise_is_an_exact_pass_through(self):
        pixels=np.array([[.1,.2,.3,1]],dtype=np.float32)
        np.testing.assert_array_equal(apply_sensor_noise(pixels.copy(),{'sensor_noise':0}),pixels)

    def test_quick_reference_scale_reduces_noise(self):
        p=dict(environment='GODSLIGHT',inspection_camera='CAM5080',sensor_noise=.01,seed=11)
        source=np.full((10000,4),.2,dtype=np.float32)
        full=apply_sensor_noise(source.copy(),{**p,'resolution':1936})
        quick=apply_sensor_noise(source.copy(),{**p,'resolution':960})
        self.assertLess(np.std(quick[:,1]),np.std(full[:,1])*.60)

    def test_fitted_fields_are_finite_reproducible_and_record_reference_sources(self):
        self.assertEqual(len(profiles()),6)
        for profile in profiles().values():
            first=sample_field(profile,32,20);second=sample_field(profile,32,20)
            np.testing.assert_array_equal(first,second)
            self.assertTrue(np.isfinite(first).all())
            self.assertTrue((first>=0).all())
            self.assertEqual(len(profile['source_references']),6)
            np.testing.assert_array_equal(first[:,:,3],1)

if __name__=='__main__':unittest.main()
