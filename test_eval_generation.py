from collections import Counter
from dataclasses import replace
import math
import unittest

from domain_plan import make_plan,SETUPS,KINDS,validate_domain_plan
from eval_generation import fixture_parameters,VERSION
from geometry import PipeSpec,displacement,radius_at,sampling_grid


class EvalGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.plan=make_plan(3200,915100000,profile='yolox')

    def test_hard_negatives_and_reflections_are_not_tied_to_class(self):
        for setup in SETUPS:
            for kind in ('NONE',)+KINDS:
                rows=[r for r in self.plan['samples'] if r['setup']==setup and r['primary_kind']==kind]
                n=len(rows)
                self.assertEqual(Counter(r['reflection_context'] for r in rows),dict(normal=n*7//10,reflective=n*3//10))
                self.assertEqual(Counter(r['lighting_regime'] for r in rows),dict(mild=n*7//10,stronger=n*2//10,stress=n//10))
                self.assertEqual({r['surface_condition'] for r in rows},{'clean','handled','dirty'})
                self.assertTrue(all(r['generation_revision']==VERSION for r in rows))
        for context in ('normal','reflective'):
            self.assertEqual(fixture_parameters(75,context),fixture_parameters(75,context))
        good=[r for r in self.plan['samples'] if r['primary_kind']=='NONE']
        self.assertTrue(all(not r['instances'] and r['settings']['defect']=='NONE' for r in good))

    def test_repeated_instances_have_separate_labels_and_positions(self):
        repeated=[r for r in self.plan['samples'] if len(r['instances'])==3]
        self.assertEqual(Counter(r['primary_kind'] for r in repeated),{k:72 for k in KINDS})
        for row in repeated:
            items=row['instances']
            self.assertEqual(len({a['instance_id'] for a in items}),3)
            self.assertEqual(items[0]['kind'],items[2]['kind'])
            for i,a in enumerate(items):
                for b in items[i+1:]:
                    pa=a.get('spec',a.get('spot'))['position'];pb=b.get('spec',b.get('spot'))['position']
                    self.assertGreaterEqual(abs(pa-pb),.12)
        validate_domain_plan(self.plan)

    def test_broad_dents_are_shallow_and_legacy_shapes_remain(self):
        broad=[a for r in self.plan['samples'] for a in r['instances'] if a.get('spec',{}).get('defect_style')=='SHALLOW_SWEEP']
        self.assertGreater(len(broad),300)
        self.assertTrue(all(a['kind']=='DENT' and .025<=a['spec']['depth']<=.085 for a in broad))
        self.assertTrue(any(a['spec']['width']>.09 for a in broad))
        self.assertEqual({a['size_bin'] for a in broad},{'small','medium','large'})

    def test_broad_mask_covers_center_and_shallow_flanks(self):
        s=PipeSpec(defect='DENT',defect_style='SHALLOW_SWEEP',position=.53,width=.08,depth=.045,arc=26)
        for u in (-1.,0.,1.):
            t=s.position+u*s.width
            delta,mask=displacement(t,math.radians(s.angle),s)
            self.assertLess(delta,0)
            self.assertEqual(mask,1.)
        self.assertEqual(displacement(s.position+2.2*s.width,math.radians(s.angle),s),(0.,0.))
        ts,angles=sampling_grid(s,24,32,adaptive=True)
        self.assertIn(s.position,ts)
        self.assertGreater(len(ts),25)

    def test_preview_covers_new_families_and_three_instances_in_every_setup(self):
        plan=make_plan(seed=915200000,preview=True,profile='yolox')
        for setup in SETUPS:
            rows=[r for r in plan['samples'] if r['setup']==setup]
            styles={a['spec']['defect_style'] for r in rows for a in r['instances'] if 'spec' in a}
            self.assertTrue({'SHALLOW_SWEEP','SOFT_BUCKLE','AXIAL_PINCH'}.issubset(styles))
            self.assertTrue(any(len(r['instances'])==3 for r in rows))


if __name__=='__main__':unittest.main()
