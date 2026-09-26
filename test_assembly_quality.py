import json
import unittest
import numpy as np
from assembly_quality import inspect_support,counterfactual_assessment,strict_recipe,repair_row,VERSION
from assembly_plan import make_plan,make_specimen
from assembly_geometry import build_assembly_body


class AssemblyQualityTests(unittest.TestCase):
    def test_screen_rejects_dark_glare_and_thin_at_model_scale(self):
        mask=np.zeros((120,192),dtype=bool);mask[40:70,60:100]=True
        for value,reason in ((.05,'too_dark'),(.99,'glare_obscured')):
            result=inspect_support(np.full((120,192,3),value),mask)
            self.assertIn(reason,result['reasons'])
        thin=np.zeros_like(mask);thin[40,60:100]=True
        self.assertIn('too_small_or_thin',inspect_support(np.full((120,192,3),.5),thin)['reasons'])

    def test_identical_images_cannot_pass_counterfactual(self):
        clean=np.full((120,192,3),.4);mask=np.zeros((120,192),bool);mask[40:65,65:100]=True
        result=counterfactual_assessment(clean,clean,mask,np.ones_like(mask))
        self.assertFalse(result['passed']);self.assertIn('weak_rgb_change',result['reasons'])
        beauty=clean.copy();beauty[mask]+=.25
        self.assertTrue(counterfactual_assessment(beauty,clean,mask,np.ones_like(mask))['passed'])

    def test_clean_mesh_keeps_exact_topology_and_other_defects(self):
        recipe=strict_recipe(make_specimen(928001,'dent'))
        vertices,faces,support=build_assembly_body(recipe)
        clean,clean_faces,clean_support=build_assembly_body(recipe,omit_instances=(0,))
        self.assertEqual(len(vertices),len(clean));self.assertEqual(faces,clean_faces)
        self.assertTrue(np.any(np.abs(np.asarray(vertices)-np.asarray(clean))>1e-6))
        self.assertFalse(clean_support[0].any())
        for a,b in zip(support[1:],clean_support[1:]):np.testing.assert_array_equal(a,b)

    def test_reflection_bending_is_not_confused_with_micrograin(self):
        y,x=np.mgrid[:120,:192];shell=np.ones(x.shape,bool)
        mask=(x>65)&(x<105)&(y>40)&(y<78)
        clean=(.4+.2*np.cos(y))[...,None]*np.ones(3)
        warp=2.5*np.exp(-((x-85)/13)**2-((y-59)/14)**2)
        beauty=(.4+.2*np.cos(y+warp))[...,None]*np.ones(3)
        # The old isotropic filter erased straight light bars and called them
        # texture. Their localized bending is the actual inspection cue.
        result=counterfactual_assessment(beauty,clean,mask,shell)
        self.assertTrue(result['passed'],result)
        self.assertLess(result['isotropic_texture_diagnostic']['shape_to_texture_ratio'],1)
        self.assertFalse(counterfactual_assessment(clean,clean,mask,shell)['passed'])
        rng=np.random.default_rng(81)
        grain=np.clip(.4+rng.normal(0,.085,(120,192,3)),0,1)
        shifted=grain.copy();shifted[mask]=np.roll(grain,2,axis=1)[mask]
        result=counterfactual_assessment(shifted,grain,mask,shell)
        self.assertFalse(result['passed'])
        self.assertIn('cue_buried_in_surface_texture',result['reasons'])

    def test_strict_stills_have_unique_groups_and_keep_nuisances_during_repair(self):
        rows=make_plan(40,928010,strict=True)
        self.assertEqual(len({r['split_group'] for r in rows}),40)
        for row in rows:
            self.assertEqual(row['recipe']['quality_profile'],VERSION)
            self.assertTrue(all(not r['instances'] for r in row['companions']))
            repaired=repair_row(row,1)
            for key in ('finish','lighting','environment','condition'):
                self.assertEqual(row['recipe'][key],repaired['recipe'][key])
            self.assertEqual(row['pose'],repaired['pose'])
            self.assertEqual([i['class_id'] for i in row['recipe']['instances']], [i['class_id'] for i in repaired['recipe']['instances']])


if __name__=='__main__':unittest.main()
