from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parent/'remote'))
from domain_plan import make_plan,defects_only_plan,restrict_defect_kinds,validate_domain_plan
from remote.fleet import planned_work
from remote.roll_fleet_update import merged_plan


class DefectFilterTests(unittest.TestCase):
    def test_filter_preserves_commits_quality_and_camera_and_excludes_secondary_classes(self):
        original=defects_only_plan(make_plan(320,seed=1247,profile='yolox'))
        plan=restrict_defect_kinds(original,['FOLD','DENT'],17)
        self.assertEqual(plan['samples'][:17],original['samples'][:17])
        self.assertEqual(plan,restrict_defect_kinds(original,['FOLD','DENT'],17))
        for before,after in zip(original['samples'][17:],plan['samples'][17:]):
            self.assertTrue(after['instances'])
            self.assertTrue(all(i['kind'] in ('FOLD','DENT') for i in after['instances']))
            self.assertEqual(before['sample_id'],after['sample_id'])
            for key in ('resolution_profile','fixture_parameters','reflection_context','surface_condition'):
                self.assertEqual(before[key],after[key])
            for key in ('seed','resolution','samples','roughness','camera_yaw','exposure','focus_blur'):
                self.assertEqual(before['settings'][key],after['settings'][key])
        changed=deepcopy(plan)
        for index,row in enumerate(original['samples'][17:],17):
            if any(i['kind'] not in ('FOLD','DENT') for i in row['instances']):
                changed['samples'][index]=row;break
        from remote.roll_fleet_update import recount
        recount(changed)
        with self.assertRaisesRegex(ValueError,'excluded'):validate_domain_plan(changed)

    def test_future_production_smoke_and_rollout_respect_filter(self):
        for smoke in (False,True):
            args=SimpleNamespace(count=320,seed=128,quality='full',smoke=smoke,profile='yolox',
                                 defects_only=True,allowed_defects=['FOLD','DENT'],per_node=True,verification=True)
            plan,assignment=planned_work(args,{'a':{'weight':1},'b':{'weight':1}})
            self.assertEqual(set(plan['expected_primary_counts']),{'FOLD','DENT'})
            self.assertEqual(set(plan['expected_instance_counts']),{'FOLD','DENT'})
            if smoke:self.assertEqual(len(plan['samples']),4)
        old=defects_only_plan(make_plan(320,seed=128))
        latest=restrict_defect_kinds(defects_only_plan(make_plan(320,seed=128,profile='yolox')),['FOLD','DENT'])
        merged=merged_plan(old,latest,13)
        self.assertEqual(merged['samples'][:13],old['samples'][:13])
        self.assertEqual(merged['generation_policy']['allowed_defects'],['FOLD','DENT'])


if __name__=='__main__':unittest.main()
