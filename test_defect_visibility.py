import unittest
from unittest.mock import patch
from pathlib import Path
from dataclasses import asdict,replace
import numpy as np

from defect_visibility import assess,repair_instances,VisibilityRejected
from geometry import PipeSpec
from domain_geometry import build_instances


class VisibilityTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(9)
        self.clean=np.clip(.25+rng.normal(0,.02,(128,128,3)),0,1)
        self.mask=np.zeros((128,128),bool);self.mask[52:76,54:74]=True
        self.pipe=np.zeros((128,128),bool);self.pipe[:,32:96]=True

    def test_identical_grain_and_bright_glare_do_not_pass(self):
        self.clean[53:62,56:72]=1
        result=assess(self.clean,self.clean.copy(),self.mask,self.pipe)
        self.assertFalse(result['passed']);self.assertEqual(result['p90_change_codes'],0)

    def test_local_highlight_shadow_survives_and_is_measured_at_model_size(self):
        damaged=self.clean.copy();damaged[55:64,56:72]+=.04;damaged[64:73,56:72]-=.04
        result=assess(damaged,self.clean,self.mask,self.pipe)
        self.assertTrue(result['passed'],result)
        self.assertGreater(result['largest_changed_component'],100)
        # An imperceptible perturbation must not pass merely due to a big mask.
        faint=self.clean+(damaged-self.clean)*.03
        self.assertFalse(assess(faint,self.clean,self.mask,self.pipe)['passed'])

    def test_independent_render_noise_is_not_a_coherent_dent(self):
        noise=np.random.default_rng(8).normal(0,.025,self.clean.shape)
        result=assess(np.clip(self.clean+noise,0,1),self.clean,self.mask,self.pipe)
        self.assertFalse(result['passed'],result)

    def test_global_exposure_mismatch_cannot_masquerade_as_a_local_dent(self):
        self.assertFalse(assess(self.clean+.04,self.clean,self.mask,self.pipe)['passed'])

    def test_broad_small_change_buried_in_texture_is_rejected(self):
        damaged=self.clean.copy();damaged[self.mask]+=.018
        result=assess(damaged,self.clean,self.mask,self.pipe)
        self.assertFalse(result['passed'])
        self.assertIn('cue_buried_in_surface_texture',result['reasons'])

    def test_native_detail_that_disappears_on_resize_is_rejected(self):
        clean=np.full((1280,1280,3),.25);damaged=clean.copy();mask=np.zeros((1280,1280),bool)
        mask[640:642,640:642]=True;damaged[mask]=.6
        result=assess(damaged,clean,mask,np.ones(mask.shape,bool))
        self.assertEqual(result['model_dimensions'],[640,640]);self.assertFalse(result['passed'])

    def test_one_removed_instance_preserves_grid_and_the_other_defect(self):
        base=PipeSpec(defect='NONE',depth=0)
        a=replace(base,defect='DENT',position=.30,width=.012,depth=.10)
        b=replace(base,defect='DENT',position=.70,width=.012,depth=.08)
        items=[dict(kind='DENT',spec=asdict(a)),dict(kind='DENT',spec=asdict(b))]
        damaged=build_instances(base,items,16,16)
        control=build_instances(base,items,16,16,omit_instance=0)
        self.assertEqual(damaged[1],control[1]);self.assertEqual(len(damaged[0]),len(control[0]))
        self.assertFalse(any(control[4][0]));self.assertEqual(damaged[4][1],control[4][1])
        dv=np.array(damaged[0]);cv=np.array(control[0]);other=np.array(damaged[4][1])>0
        np.testing.assert_allclose(dv[other],cv[other]);self.assertGreater(np.abs(dv-cv).max(),.02)

    def test_repair_preserves_class_footprint_and_background(self):
        row=dict(instances=[dict(kind='DENT',class_id=1,spec=dict(depth=.02,width=.04)),
                            dict(kind='FOLD',class_id=0,spec=dict(depth=.2,width=.03))],
                 settings=dict(seed=123,exposure=-.3),background_variation=dict(brightness=.93))
        fixed=repair_instances(row,[0])
        self.assertEqual(fixed['instances'][0]['spec']['depth'],.032)
        self.assertEqual(fixed['instances'][1],row['instances'][1])
        self.assertEqual(fixed['settings'],row['settings'])
        self.assertEqual(fixed['background_variation'],row['background_variation'])
        self.assertEqual(row['instances'][0]['spec']['depth'],.02)

    def test_export_stops_after_three_failed_candidates(self):
        import domain_render
        report=dict(sample_id='test',instances=[dict(instance_index=0,passed=False)])
        row=dict(sample_id='test',instances=[dict(spec=dict(depth=.02))])
        with patch.object(domain_render,'_render_candidate',side_effect=VisibilityRejected(report)) as render, \
             patch.object(domain_render,'atomic_json'),patch.object(Path,'mkdir'),patch.object(Path,'exists',return_value=False):
            with self.assertRaises(VisibilityRejected):domain_render.render_sample(None,None,row,Path('unused'))
        self.assertEqual(render.call_count,3)
        self.assertEqual(row['instances'][0]['spec']['depth'],.02)


if __name__=='__main__':unittest.main()
