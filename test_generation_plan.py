import copy
import unittest
from collections import Counter,defaultdict
from generation_plan import make_plan,validate_plan,plan_digest
from lighting_profiles import lighting_settings,LIGHTING_IDS,LIGHT_KEYS
from app_model import front_angle

class GenerationTests(unittest.TestCase):
    def test_deterministic_balanced_paired_challenge(self):
        a=make_plan(); b=make_plan()
        self.assertEqual(plan_digest(a),plan_digest(b))
        self.assertNotEqual(plan_digest(a),plan_digest(make_plan(seed=43)))
        self.assertEqual(len(a['samples']),96)
        self.assertEqual(Counter(s['settings']['defect'] for s in a['samples']),{'NONE':24,'DENT':36,'FOLD':36})
        groups=defaultdict(list)
        for sample in a['samples']:
            groups[sample['specimen_id']].append(sample)
        self.assertEqual(len(groups),16)
        for group in groups.values():
            self.assertEqual({s['lighting_profile'] for s in group},set(LIGHTING_IDS))
        validate_plan(a)

    def test_paired_geometry_or_split_cannot_drift(self):
        plan=make_plan(specimens=3,environments=('MACHINE',))
        for key,value in [('split','train'),('radius',1.1)]:
            changed=copy.deepcopy(plan)
            if key=='split': changed['samples'][1][key]=value
            else: changed['samples'][1]['settings'][key]=value
            with self.assertRaises(ValueError): validate_plan(changed)

    def test_bad_ids_and_invalid_numeric_settings_are_rejected(self):
        for name in ('../outside','duplicate'):
            plan=make_plan(specimens=3,environments=('MACHINE',))
            plan['samples'][1]['sample_id']=plan['samples'][0]['sample_id'] if name=='duplicate' else name
            with self.assertRaises(ValueError): validate_plan(plan)
        with self.assertRaises(ValueError): make_plan(seed=True)
        with self.assertRaises(ValueError): make_plan(specimens=0)

    def test_lighting_recipes_are_lighting_only(self):
        for env in ('MACHINE','GODSLIGHT','STUDIO'):
            for light in LIGHTING_IDS:
                self.assertEqual(set(lighting_settings(env,light)),set(LIGHT_KEYS)|{'lighting_profile'})

    def test_front_angle_follows_upright_rotation(self):
        self.assertEqual(front_angle({'environment':'MACHINE','camera_yaw':15}),195)

    def test_small_plan_still_contains_all_classes(self):
        plan=make_plan(specimens=3,environments=('MACHINE',))
        self.assertEqual({s['settings']['defect'] for s in plan['samples']},{'NONE','DENT','FOLD'})

if __name__=='__main__': unittest.main()
