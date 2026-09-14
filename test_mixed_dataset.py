import copy
from collections import Counter
import unittest
from generation_plan import plan_digest,validate_plan
from mixed_dataset import make_mixed_plan,validate_mixed_plan,make_preflight

class MixedDatasetTests(unittest.TestCase):
    def test_exact_four_way_counts_unique_specimens_and_balanced_environments(self):
        for counts in ({'NONE':50,'FOLD':225,'DENT':225},{'NONE':100,'FOLD':200,'DENT':200}):
            all_samples=[]
            for batch in range(1,5):
                plan=make_mixed_plan(batch,counts);validate_mixed_plan(plan)
                self.assertEqual(Counter(s['settings']['defect'] for s in plan['samples']),counts)
                all_samples+=plan['samples']
            self.assertEqual(len({s['settings']['seed'] for s in all_samples}),2000)
            self.assertEqual(len({s['sample_id'] for s in all_samples}),2000)
            for kind,count in counts.items():
                for env in ('MACHINE','GODSLIGHT'):
                    self.assertEqual(sum(s['settings']['defect']==kind and s['settings']['environment']==env for s in all_samples),count*2)

    def test_reproducible_mixed_order_and_small_defect_coverage(self):
        counts={'NONE':50,'FOLD':225,'DENT':225}
        a=make_mixed_plan(1,counts);b=make_mixed_plan(1,counts)
        self.assertEqual(plan_digest(a),plan_digest(b))
        self.assertNotEqual(plan_digest(a),plan_digest(make_mixed_plan(1,counts,99)))
        first=a['samples'][:30]
        self.assertEqual({s['settings']['environment'] for s in first},{'MACHINE','GODSLIGHT'})
        self.assertEqual({s['settings']['defect'] for s in first},{'NONE','FOLD','DENT'})
        for s in a['samples']:
            if s['severity']=='small':
                self.assertLessEqual(s['settings']['depth'],.06)
                self.assertLessEqual(s['settings']['width'],.018)

    def test_bad_counts_and_changed_allocation_rejected(self):
        for counts in ({'NONE':50,'FOLD':200,'DENT':200},{'NONE':50,'FOLD':True,'DENT':449}):
            with self.assertRaises(ValueError): make_mixed_plan(1,counts)
        plan=make_mixed_plan(1,{'NONE':50,'FOLD':225,'DENT':225})
        changed=copy.deepcopy(plan);changed['samples'][0]['settings']['environment']='STUDIO'
        with self.assertRaises(ValueError): validate_mixed_plan(changed)

    def test_preflight_covers_all_rigs_classes_and_small_defects(self):
        plan=make_preflight();validate_plan(plan)
        self.assertEqual(len(plan['samples']),16)
        for env in ('MACHINE','GODSLIGHT'):
            samples=[s for s in plan['samples'] if s['settings']['environment']==env]
            self.assertEqual({s['settings']['defect'] for s in samples},{'NONE','FOLD','DENT'})
            self.assertEqual({s['settings']['defect'] for s in samples if s['severity']=='small'},{'FOLD','DENT'})

if __name__=='__main__': unittest.main()
