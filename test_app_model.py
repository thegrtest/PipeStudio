import unittest
from app_model import DEFAULTS,PRESETS,validate_settings,front_angle

class SettingsTests(unittest.TestCase):
    def test_all_presets_are_valid(self):
        for preset in PRESETS.values():
            self.assertEqual(validate_settings(preset)['defect'],'DENT')
    def test_invalid_preset_values_are_rejected(self):
        for value in (float('nan'),float('inf'),'x',True,200):
            with self.assertRaises(ValueError):
                validate_settings({'roughness':value})
    def test_bounds_match_blender_float_precision(self):
        result=validate_settings({'end_ratio':.349999994,'width':.180000007})
        self.assertEqual(result['end_ratio'],.35)
        self.assertEqual(result['width'],.18)
    def test_unknown_fields_do_not_enter_renderer(self):
        self.assertNotIn('command',validate_settings({'command':'ignored'}))
    def test_back_and_front_angles(self):
        a=front_angle({**DEFAULTS,'camera_yaw':0,'camera_elevation':0})
        b=front_angle({**DEFAULTS,'camera_yaw':175,'camera_elevation':0})
        self.assertAlmostEqual(a,180)
        self.assertAlmostEqual(b,0)

if __name__=='__main__':
    unittest.main()
