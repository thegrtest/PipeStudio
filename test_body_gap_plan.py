from collections import Counter
from dataclasses import replace
import unittest

from body_gap_plan import make_plan
from geometry import PipeSpec, _style_form, sampling_grid
from domain_plan import validate_domain_plan


class BodyGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=make_plan(3200,seed=923100000)

    def test_single_environment_and_balanced_labels(self):
        p=self.plan; rows=p['samples']
        self.assertEqual(p['expected_setup_counts'],{'INVERTED':3200})
        self.assertEqual(p['expected_primary_counts'],{'FOLD':1600,'DENT':1600})
        self.assertEqual(p['expected_instance_counts'],{'FOLD':2400,'DENT':2400})
        self.assertEqual(Counter(len(r['instances']) for r in rows),{1:1920,2:960,3:320})
        self.assertEqual(len({r['settings']['seed'] for r in rows}),3200)
        for r in rows:
            self.assertEqual(r['settings']['capture_view'],'INVERTED')
            self.assertEqual(r['settings']['environment'],'MACHINE')
            self.assertEqual(r['resolution_profile']['expected_dimensions'],[640,640])
            self.assertEqual((r['settings']['resolution'],r['settings']['frame_aspect']),(640,1))
            self.assertTrue(all(i['class_id'] in (0,1) for i in r['instances']))

    def test_class_independent_nuisance_coverage(self):
        for kind in ('FOLD','DENT'):
            rows=[r for r in self.plan['samples'] if r['primary_kind']==kind]
            self.assertEqual(Counter(r['surface_condition'] for r in rows),{'clean':480,'handled':560,'dirty':560})
            self.assertEqual(Counter(r['lighting_regime'] for r in rows),{'mild':1120,'stronger':320,'stress':160})
            self.assertEqual(Counter(r['gap_visibility'] for r in rows),{'body_shadow':960,'ordinary':640})
            self.assertEqual(Counter(r['gap_targeted'] for r in rows),{True:1120,False:480})
            self.assertEqual(Counter(r['split'] for r in rows),{'train':1280,'val':320})
        self.assertEqual(Counter(i['size_bin'] for r in self.plan['samples'] for i in r['instances']),
                         {'small':2160,'medium':1920,'large':720})

    def test_repeatable_and_target_geometry_valid(self):
        self.assertEqual(make_plan(320,seed=4321),make_plan(320,seed=4321))
        validate_domain_plan(self.plan)
        targets=[r['instances'][0] for r in self.plan['samples'] if r['gap_targeted']]
        self.assertTrue(all(i['region']=='body' for i in targets))
        self.assertTrue(all(.34<=i['spec']['position']<=.75 for i in targets))
        for item in targets:
            spec=PipeSpec(**item['spec']).validate()
            self.assertLessEqual(spec.depth,.211 if item['kind']=='FOLD' else .161)

    def test_background_is_seeded_and_both_classes_cover_new_shapes(self):
        from capture_variation import parameters
        for row in self.plan['samples']:
            self.assertEqual(row['background_variation'],parameters(row['settings']['seed']))
        for kind,expected in [('DENT',{'DEFAULT','ELONGATED','DOUBLE'}),
                              ('FOLD',{'BODY_BUCKLE','WRINKLED','SOFT_BUCKLE'})]:
            styles={r['instances'][0]['spec']['defect_style'] for r in self.plan['samples']
                    if r['gap_targeted'] and r['primary_kind']==kind}
            self.assertEqual(styles,expected)

    def test_body_buckle_is_transposed_soft_buckle_and_grid_resolves_it(self):
        body=PipeSpec(defect='FOLD',defect_style='BODY_BUCKLE',width=.022,arc=18)
        soft=replace(body,defect_style='SOFT_BUCKLE')
        for u in (-1.6,-.6,0,.6,1.6):
            for v in (-1.8,-.6,0,.6,1.8):
                self.assertAlmostEqual(_style_form(u,v,body,.78),_style_form(v,u,soft,.78))
        ts,angles=sampling_grid(body,adaptive=True)
        self.assertGreater(len(ts),145)
        self.assertGreater(len(angles),128)

    def test_remote_smoke_and_production_have_no_desktop_work(self):
        import sys
        from pathlib import Path
        from types import SimpleNamespace
        sys.path.insert(0,str(Path(__file__).resolve().parent/'remote'))
        from fleet import planned_work
        nodes={'spark':{'weight':4},'agx':{'weight':1}}
        args=SimpleNamespace(profile='body-gap',count=3200,seed=923272000,quality='full',
                             smoke=True,verification=True,defects_only=True,
                             allowed_defects=['FOLD','DENT'],per_node=False)
        plan,assignments=planned_work(args,nodes)
        self.assertEqual(set(assignments),{'spark','agx'})
        self.assertEqual(len(plan['samples']),4)
        for indices in assignments.values():
            self.assertEqual({plan['samples'][i]['primary_kind'] for i in indices},{'FOLD','DENT'})
        self.assertTrue(all(r['setup']=='INVERTED' and r['split']=='test' for r in plan['samples']))
        args.smoke=False
        production,assignments=planned_work(args,nodes)
        self.assertEqual(production['expected_setup_counts'],{'INVERTED':3200})
        self.assertEqual(sorted(i for ids in assignments.values() for i in ids),list(range(3200)))


if __name__=='__main__':unittest.main()
