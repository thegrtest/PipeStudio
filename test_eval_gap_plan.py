from collections import Counter
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from domain_plan import validate_domain_plan
from eval_gap_plan import make_plan, preview_plan, recount, reposition
from defect_visibility import VisibilityRejected,repair_instances,replay_visibility_repairs
from domain_render import render_sample


class EvalGapTests(unittest.TestCase):
    def test_remote_preflight_covers_clean_and_both_classes_on_each_node(self):
        import sys
        from types import SimpleNamespace
        sys.path.insert(0,str(Path(__file__).parent/'remote'))
        from fleet import planned_work
        from fleet_common import split_plan
        args=SimpleNamespace(profile='eval-gap',count=3000,seed=924140000,quality='full',smoke=True,per_node=False)
        p,assignment=planned_work(args,{'spark':{'weight':4},'agx':{'weight':1}})
        for shard in split_plan(p,assignment).values():
            self.assertEqual(set(shard['expected_primary_counts']),{'NONE','FOLD','DENT'})
            self.assertEqual(set(shard['expected_setup_counts']),{'UPRIGHT','FOREGROUND','INVERTED'})
        self.assertFalse(set(range(args.seed,args.seed+args.count)) & {r['settings']['seed'] for r in p['samples']})

    def test_balanced_training_only_three_cameras(self):
        p=make_plan(300)
        self.assertEqual(p,make_plan(300))
        self.assertEqual(p['expected_primary_counts'],{'DENT':135,'FOLD':135,'NONE':30})
        self.assertEqual(p['expected_instance_counts'],{'DENT':225,'FOLD':225})
        self.assertEqual(Counter(len(r['instances']) for r in p['samples']),{0:30,1:150,2:60,3:60})
        for setup in ('UPRIGHT','FOREGROUND','INVERTED'):
            rows=[r for r in p['samples'] if r['setup']==setup]
            self.assertEqual(Counter(r['primary_kind'] for r in rows),{'DENT':45,'FOLD':45,'NONE':10})
        self.assertTrue(all(r['split']=='train' and r['settings']['resolution']==640 for r in p['samples']))
        self.assertEqual(len({r['settings']['seed'] for r in p['samples']}),300)
        self.assertFalse({r['settings']['seed'] for r in p['samples']} & {r['settings']['seed'] for r in preview_plan()['samples']})

    def test_compact_pair_exception_does_not_accept_colliding_broad_defects(self):
        p=make_plan(60);r=next(r for r in p['samples'] if len(r['instances'])==2 and abs(r['instances'][0]['spec']['position']-r['instances'][1]['spec']['position'])<.12)
        r['instances'][1]['spec']['position']=r['instances'][0]['spec']['position']+.02
        with self.assertRaisesRegex(ValueError,'separately visible'):validate_domain_plan(p)
        r['instances'][1]['spec']['position']=r['instances'][0]['spec']['position']+.08
        r['instances'][1]['spec']['width']=.06
        with self.assertRaisesRegex(ValueError,'separately visible'):validate_domain_plan(p)

    def test_visibility_retry_preserves_identity_nuisance_and_class(self):
        row=next(r for r in make_plan(60)['samples'] if len(r['instances'])==3);original=deepcopy(row)
        changed=reposition(row,1)
        self.assertEqual(row,original);self.assertEqual(changed['settings'],row['settings'])
        self.assertEqual(changed['sample_id'],row['sample_id'])
        for a,b in zip(changed['instances'],row['instances']):
            a['spec']['angle']=b['spec']['angle'];self.assertEqual(a,b)

    def test_fail_closed_and_only_retry_visibility_failures(self):
        row=next(r for r in make_plan(60)['samples'] if r['instances'])
        with patch('domain_render._render_with_depth_repairs',side_effect=VisibilityRejected({'passed':False})) as f:
            with self.assertRaises(VisibilityRejected):render_sample(None,None,row,Path('.'))
            self.assertEqual(f.call_count,4)
        with patch('domain_render._render_with_depth_repairs',side_effect=OSError('disk full')) as f:
            with self.assertRaises(OSError):render_sample(None,None,row,Path('.'))
            self.assertEqual(f.call_count,1)

    def test_validator_reconstructs_repairs_but_rejects_unexplained_changes(self):
        row=next(r for r in make_plan(60)['samples'] if r['instances'])
        moved=reposition(row,1);report={'passed':False,'instances':[{'instance_index':0,'passed':False}]}
        record=dict(visibility_reposition_attempt=1,visibility_reposition_history=[{'attempt':0,'report':report}],
                    visibility_repair_history=[{'attempt':0,'instances':deepcopy(moved['instances']),'report':report}])
        expected=repair_instances(moved,[0]);got=replay_visibility_repairs(row,record)
        self.assertEqual(got['instances'],expected['instances'])
        record['visibility_repair_history'][0]['instances'][0]['spec']['width']*=2
        with self.assertRaises(ValueError):replay_visibility_repairs(row,record)


if __name__=='__main__':unittest.main()
