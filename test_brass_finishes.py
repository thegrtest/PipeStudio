import unittest
from brass_finishes import FINISH_ITEMS,FINISH_KEYS,finish_settings
from app_model import validate_settings
from scene_presets import SCENE_PRESETS
from generation_plan import make_plan,validate_plan
import copy

class BrassFinishTests(unittest.TestCase):
    def test_material_only_valid_recipes(self):
        for env in SCENE_PRESETS:
            for profile,_,_ in FINISH_ITEMS:
                values=finish_settings(env,profile)
                self.assertEqual(set(values),set(FINISH_KEYS))
                result=validate_settings({**SCENE_PRESETS[env],**values})
                self.assertEqual(result['camera_yaw'],SCENE_PRESETS[env]['camera_yaw'])
                self.assertEqual(result['key_power'],SCENE_PRESETS[env]['key_power'])

    def test_invalid_finish_values_rejected(self):
        for key in ('oxide_amount','polish_amount'):
            for value in (float('nan'),float('inf'),True,-.1,1.1):
                with self.assertRaises(ValueError): validate_settings({key:value})
        with self.assertRaises(ValueError): finish_settings('MACHINE','invalid')

    def test_paired_lighting_preserves_new_material_fields(self):
        plan=make_plan(specimens=3,environments=('MACHINE',))
        validate_plan(plan)
        for key in ('oxide_amount','polish_amount'):
            broken=copy.deepcopy(plan)
            broken['samples'][1]['settings'][key]=1
            with self.assertRaises(ValueError): validate_plan(broken)

if __name__=='__main__': unittest.main()
