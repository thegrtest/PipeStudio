import unittest

import numpy as np

from soap_residue import SUBTYPES, coverage, sample_parameters


class SoapResidueTests(unittest.TestCase):
    def setUp(self):
        self.u,self.v=np.meshgrid(np.linspace(-1.8,1.8,180),np.linspace(-1.8,1.8,180))

    def test_seeded_fields_are_bounded_with_quiet_interiors_and_soft_edges(self):
        for subtype in SUBTYPES:
            spot=dict(seed=1024,subtype=subtype,strength=.48)
            alpha,mask=coverage(self.u,self.v,spot)
            np.testing.assert_array_equal(alpha,coverage(self.u,self.v,spot)[0])
            self.assertTrue(np.isfinite(alpha).all())
            self.assertGreater(alpha.max(),.35)
            self.assertLess(alpha.max(),.49)
            self.assertGreater(mask.sum(),100)
            self.assertTrue(np.all(alpha[mask>0]>=.11))
            self.assertTrue(np.any((alpha>0)&(alpha<.11)))
            self.assertTrue(np.all(alpha[np.hypot(self.u,self.v)>1.6]==0))
            interior=alpha[(mask>0)&(np.hypot(self.u,self.v)<.2)]
            self.assertLess(interior.std(),.045)
            self.assertFalse(np.array_equal(alpha,coverage(self.u,self.v,{**spot,'seed':1025})[0]))

    def test_new_reference_styles_are_sampled_in_all_environments_without_class_changes(self):
        from domain_plan import make_plan, SETUPS
        plan=make_plan(total=320,seed=928100)
        for setup in SETUPS:
            soaps=[i for row in plan['samples'] if row['setup']==setup for i in row['instances'] if i['kind']=='SOAP_STAIN']
            self.assertTrue(any(i['spot']['subtype'] in SUBTYPES for i in soaps))
            self.assertTrue(all(i['class_id']==2 for i in soaps))
        self.assertEqual(plan['expected_primary_counts']['SOAP_STAIN'],72)

    def test_material_is_tinted_film_with_partial_underlying_metal_response(self):
        for subtype in SUBTYPES:
            p=sample_parameters(2193,subtype)
            self.assertLess(p['color'][0],1.)
            self.assertLess(p['color'][2],p['color'][0])
            self.assertLess(p['metallic'],.6)
            self.assertGreater(p['roughness'],.45)


if __name__=='__main__':unittest.main()
