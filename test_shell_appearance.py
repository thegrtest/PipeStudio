import unittest
from app_model import validate_settings
from shell_appearance import APPEARANCE_PRESETS, POLYMER_LIMITS, appearance_settings
from flashlight_capture import varied_settings


class ShellAppearanceTests(unittest.TestCase):
    def test_lighting_profiles_preserve_geometry_and_validate(self):
        from shell_lighting import LIGHT_PRESETS
        p=validate_settings(dict(product_mode='FLASHLIGHT',environment='BUTTON_TRACK',defect='TWIST',body_twist=14.,seed=451,flashlight_camera='REAR_45'))
        for profile in LIGHT_PRESETS.values():
            q=validate_settings({**p,**profile})
            for key in ('defect','seed','body_twist','flashlight_camera','flashlight_length_scale'):
                self.assertEqual(p[key],q[key])
        for values in ({'inspection_light_rig':'UNKNOWN'},{'inspection_track_finish':'UNKNOWN'},
                       {'inspection_light_distance':0},{'inspection_light_distance':2}):
            with self.assertRaises(ValueError):validate_settings(values)

    def test_presets_do_not_change_defect_geometry_or_camera_pose(self):
        locked=dict(product_mode='FLASHLIGHT',environment='BUTTON_TRACK',seed=456,
                    flashlight_layout='MIXED',defect='DENT',depth=.07,width=.12,
                    crimp_tightness=.9,body_twist=12.,flashlight_camera='REAR_45',
                    flashlight_length_scale=1.1,key_power=1234.,exposure=-.4)
        p=validate_settings(locked)
        for profile in APPEARANCE_PRESETS:
            q=validate_settings({**p,**appearance_settings(profile)})
            for key in locked:self.assertEqual(q[key],p[key],key)

    def test_clean_off_controls_stay_off_in_varied_captures(self):
        p=validate_settings(dict(product_mode='FLASHLIGHT',environment='BUTTON_TRACK',**appearance_settings('CLEAN')))
        for index in range(40):
            q=varied_settings(p,index)
            for key in ('dust_amount','groove_residue','finish_marks','sensor_noise','inspection_softness','inspection_scatter'):
                self.assertEqual(q[key],0,key)
            self.assertLessEqual(abs(q['plastic_roughness']-p['plastic_roughness']),.025001)
            self.assertEqual(q,varied_settings(p,index))

    def test_control_bounds_and_preset_copy(self):
        for key,(low,high) in POLYMER_LIMITS.items():
            for value in (low-.01,high+.01,float('nan')):
                with self.assertRaises(ValueError):validate_settings({key:value})
        copy=appearance_settings('REFERENCE');copy['plastic_roughness']=.7
        self.assertNotEqual(copy,appearance_settings('REFERENCE'))


if __name__=='__main__':unittest.main()
