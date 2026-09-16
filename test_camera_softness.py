from collections import Counter
import math
import unittest
from app_model import validate_settings
from domain_profiles import (optical_response,optical_reference_width,sample_camera_softness,
                             SOFTNESS_RANGES)
from domain_plan import make_plan,SETUPS,KINDS


class CameraSoftnessTests(unittest.TestCase):
    def test_combines_variance_and_preserves_default_studio(self):
        for env,camera,base in [('MACHINE','ORIGINAL',.5),('GODSLIGHT','CAM5080',.85),('STUDIO','ORIGINAL',0.)]:
            p=dict(environment=env,inspection_camera=camera)
            self.assertEqual(optical_response(p)['total_sigma_at_reference'],base)
            r=optical_response({**p,'camera_softness':.6})
            self.assertAlmostEqual(r['total_sigma_at_reference'],math.hypot(base,.6))
            self.assertEqual(r,optical_response({**p,'camera_softness':.6,'defect':'DENT','finish_marks':.8}))
        self.assertEqual(optical_response(dict(environment='BUTTON_TRACK',product_mode='BUTTON',camera_softness=1))['extra_sigma_at_reference'],0)

    def test_sampling_repeatable_bounded_and_resolution_independent(self):
        for band,(low,high) in SOFTNESS_RANGES.items():
            values=[sample_camera_softness(seed,band) for seed in range(50)]
            self.assertGreater(len(set(values)),45)
            self.assertTrue(all(low<=v<=high for v in values))
            self.assertEqual(values,[sample_camera_softness(seed,band) for seed in range(50)])
        p=dict(environment='GODSLIGHT',inspection_camera='CAM5080',camera_softness=.6)
        sigma=optical_response(p)['total_sigma_at_reference']
        self.assertAlmostEqual(sigma*960/optical_reference_width(p),sigma*960/1936)
        for bad in (-1,1.1,True,float('nan'),float('inf')):
            with self.assertRaises(ValueError):validate_settings({'camera_softness':bad})

    def test_each_camera_and_class_get_same_mix_without_ratio_changes(self):
        plan=make_plan(3200,915510000,profile='yolox')
        self.assertEqual(plan['expected_primary_counts'],dict(NONE=320,**{k:720 for k in KINDS}))
        for setup in SETUPS:
            for kind in ('NONE',)+KINDS:
                rows=[r for r in plan['samples'] if r['setup']==setup and r['primary_kind']==kind]
                n=len(rows)
                self.assertEqual(Counter(r['camera_softness_band'] for r in rows),
                                 dict(near_reference=n*7//10,gentle=n*2//10,slightly_soft=n//10))
                for row in rows:
                    low,high=SOFTNESS_RANGES[row['camera_softness_band']]
                    self.assertTrue(low<=row['settings']['camera_softness']<=high)


if __name__=='__main__':unittest.main()
