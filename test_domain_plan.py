from collections import Counter
from copy import deepcopy
import unittest

from app_model import validate_settings
from domain_plan import (BODY_KEYS, CLASS_IDS, KINDS, SETUPS, make_plan,
                         validate_domain_plan)
from geometry import PipeSpec
from domain_profiles import setup_dimensions, reference_frame


class DomainPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=make_plan()

    def test_exact_primary_setup_and_instance_allocations(self):
        rows=self.plan['samples']
        self.assertEqual(len(rows),3200)
        self.assertEqual(self.plan['expected_primary_counts'],dict(NONE=320,**{kind:720 for kind in KINDS}))
        self.assertEqual(self.plan['expected_instance_counts'],{kind:900 for kind in KINDS})
        for setup in SETUPS:
            subset=[row for row in rows if row['setup']==setup]
            self.assertEqual(len(subset),400)
            self.assertEqual(Counter(row['primary_kind'] for row in subset),dict(NONE=40,**{kind:90 for kind in KINDS}))
            self.assertEqual(sum(len(row['instances'])==2 for row in subset),90)
            self.assertEqual(Counter(row['lighting_regime'] for row in subset),dict(mild=280,stronger=80,stress=40))
        self.assertEqual(Counter(instance['size_bin'] for row in rows for instance in row['instances']),
                         dict(small=1620,medium=1440,large=540))

    def test_full_and_quick_dimensions_match_each_reference_without_changing_framing(self):
        full=make_plan(preview=True,quality='full')
        quick=make_plan(preview=True,quality='quick')
        quick_rows={row['sample_id']:row for row in quick['samples']}
        for row in full['samples']:
            scaled=quick_rows[row['sample_id']]
            for candidate,is_quick in ((row,False),(scaled,True)):
                settings=candidate['settings']
                actual=(settings['resolution'],round(settings['resolution']/settings['frame_aspect']))
                self.assertEqual(actual,setup_dimensions(row['setup'],quick=is_quick))
                self.assertEqual(tuple(candidate['resolution_profile']['expected_dimensions']),actual)
                self.assertEqual(candidate['resolution_profile']['source_dimensions'],reference_frame(row['setup'])['source_dimensions'])
                self.assertFalse(candidate['resolution_profile']['upscaled'])
            for key in ('camera_zoom','camera_shift_x','camera_shift_y','frame_aspect','sensor_noise'):
                self.assertEqual(row['settings'][key],scaled['settings'][key])
        damaged=deepcopy(full)
        damaged['samples'][0]['settings']['resolution']-=1
        with self.assertRaisesRegex(ValueError,'resolution profile'):
            validate_domain_plan(damaged)

    def test_unique_repeatable_specimens_and_valid_settings(self):
        rows=self.plan['samples']
        self.assertEqual(len({row['sample_id'] for row in rows}),len(rows))
        self.assertEqual(len({row['settings']['seed'] for row in rows}),len(rows))
        for row in rows:
            self.assertEqual(validate_settings(row['settings']),row['settings'])
            self.assertEqual(row['split'],'train')
            for instance in row['instances']:
                self.assertEqual(CLASS_IDS[instance['kind']],instance['class_id'])
                if 'spec' in instance:
                    PipeSpec(**instance['spec']).validate()
                    self.assertTrue(all(instance['spec'][key]==row['settings'][key] for key in BODY_KEYS))
        self.assertEqual(make_plan(total=320,seed=25),make_plan(total=320,seed=25))
        self.assertNotEqual(make_plan(total=320,seed=25),make_plan(total=320,seed=26))

    def test_defect_independent_finish_lighting_and_camera_coverage(self):
        for setup in SETUPS:
            for kind in ('NONE',)+KINDS:
                subset=[row for row in self.plan['samples'] if row['setup']==setup and row['primary_kind']==kind]
                self.assertEqual({row['surface_condition'] for row in subset},{'clean','handled','dirty'})
                self.assertEqual({row['lighting_regime'] for row in subset},{'mild','stronger','stress'})
                if kind=='NONE':
                    self.assertTrue(all(not row['instances'] and row['settings']['defect']=='NONE' for row in subset))
        cameras={setup:[row['settings'] for row in self.plan['samples'] if row['setup']==setup] for setup in SETUPS}
        self.assertTrue(all(p['camera_zoom']<.72 and p['camera_shift_x']<-.07 for p in cameras['CAM2534']))
        self.assertTrue(all(p['camera_shift_y']>.19 for p in cameras['CAM7650']))
        self.assertTrue(all(p['camera_shift_x']<-.23 for p in cameras['FOREGROUND']))
        self.assertTrue(all(p['capture_view']=='INVERTED' for p in cameras['INVERTED']))
        self.assertTrue(all(p['length']==8 and p['taper_start']==.8 and p['taper_end']==.88
                            for p in cameras['STUDIO']))

    def test_mixed_instances_are_distinct_and_separated(self):
        pairings=set()
        for row in self.plan['samples']:
            if len(row['instances'])!=2:
                continue
            first,second=row['instances']
            self.assertNotEqual(first['kind'],second['kind'])
            pairings.add((first['kind'],second['kind']))
            first_location=first.get('spec',first.get('spot'))
            second_location=second.get('spec',second.get('spot'))
            self.assertGreaterEqual(abs(first_location['position']-second_location['position']),.12)
        self.assertEqual(pairings,{(a,b) for a in KINDS for b in KINDS if a!=b})

    def test_new_folds_are_majority_and_legacy_shapes_remain(self):
        folds=[row['instances'][0] for row in self.plan['samples'] if row['primary_kind']=='FOLD']
        self.assertEqual(sum(item['spec']['defect_style']=='AXIAL_PINCH' for item in folds),432)
        self.assertEqual(len({item['spec']['defect_style'] for item in folds}),7)
        pinches=[item for item in folds if item['spec']['defect_style']=='AXIAL_PINCH']
        self.assertTrue(all(.82<=item['spec']['position']<=.97 for item in pinches))
        self.assertTrue(any(item['region']=='neck_rim' and item['spec']['position']>.92 for item in pinches))
        self.assertTrue(any(item['region']=='shoulder_neck' and item['spec']['position']<.90 for item in pinches))
        self.assertTrue(all(abs(item['spec']['defect_rotation'])<=28 for item in pinches))

    def test_preview_covers_slit_pocket_clean_dents_stains_and_mixed_in_every_setup(self):
        plan=make_plan(preview=True,quality='quick')
        self.assertEqual(len(plan['samples']),80)
        for setup in SETUPS:
            rows=[row for row in plan['samples'] if row['setup']==setup]
            self.assertEqual(len(rows),10)
            self.assertEqual({row['primary_kind'] for row in rows},set(('NONE',)+KINDS))
            self.assertEqual(sum(len(row['instances'])==2 for row in rows),2)
            self.assertTrue(all(row['split']=='test' and row['settings']['samples']==64 for row in rows))
            folds=[row['instances'][0]['spec'] for row in rows if row['primary_kind']=='FOLD']
            self.assertTrue(any(s['secondary_strength']==.15 and s['defect_style']=='AXIAL_PINCH' for s in folds))
            self.assertTrue(any(s['secondary_strength']==.8 and s['defect_style']=='AXIAL_PINCH' for s in folds))

    def test_invalid_counts_and_corrupted_geometry_are_rejected(self):
        for total in (True,0,3001,321,320.0):
            with self.assertRaises(ValueError):
                make_plan(total=total)
        for seed in (-1,True,2000000000):
            with self.assertRaises(ValueError):
                make_plan(seed=seed)
        damaged=deepcopy(make_plan(total=320))
        row=next(row for row in damaged['samples'] if row['primary_kind']=='FOLD')
        row['instances'][0]['spec']['radius']+=.05
        with self.assertRaisesRegex(ValueError,'shared specimen'):
            validate_domain_plan(damaged)


if __name__=='__main__':
    unittest.main()
