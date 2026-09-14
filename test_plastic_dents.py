import unittest,math
from plastic_dents import parameters,field
from app_model import validate_settings

class PlasticDentTests(unittest.TestCase):
    def test_profiles_are_bounded_local_and_asymmetric(self):
        families=set()
        for seed in range(12):
            p=parameters(seed);families.add(p['profile'])
            d=dict(depth=.06,irregularity=.4,shape_parameters=p)
            samples=[field(x/10,y/10,d) for x in range(-20,21) for y in range(-20,21)]
            self.assertTrue(all(math.isfinite(v) and -.006<=v<=.060001 for v in samples))
            self.assertGreater(max(samples),.02)
            self.assertEqual(field(5,5,d),0)
            self.assertTrue(any(abs(field(x,.2,d)-field(-x,.2,d))>1e-4 for x in (.2,.4,.6)))
        self.assertEqual(families,{0,1,2})
    def test_seed_and_zero_depth(self):
        self.assertEqual(parameters(75),parameters(75))
        self.assertNotEqual(parameters(75),parameters(76))
        self.assertEqual(field(.2,.1,dict(depth=0,shape_parameters=parameters(75))),0)
    def test_reference_camera_and_proportion_limits(self):
        p=validate_settings(dict(product_mode='FLASHLIGHT',environment='BUTTON_TRACK',flashlight_camera='REFERENCE',
            flashlight_length_scale=1.,flashlight_reference_elevation=55.))
        self.assertEqual(p['flashlight_camera'],'REFERENCE')
        for bad in ({'flashlight_length_scale':0},{'flashlight_reference_elevation':90}):
            with self.assertRaises(ValueError):validate_settings({**p,**bad})

if __name__=='__main__':unittest.main()
