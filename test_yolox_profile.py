from collections import Counter
import unittest
from domain_plan import make_plan,KINDS,SETUPS
from yolox_profile import capture_settings,projected_sizes


class TransferPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.plan=make_plan(3200,914900000,profile='yolox')

    def test_exact_mix_without_losing_good_or_legacy_shapes(self):
        plan=self.plan
        self.assertEqual(plan['expected_primary_counts'],dict(NONE=320,**{k:720 for k in KINDS}))
        self.assertEqual(plan['expected_instance_counts'],{k:1080 for k in KINDS})
        self.assertEqual(sum(len(r['instances'])>=2 for r in plan['samples']),1152)
        self.assertEqual(sum(len(r['instances'])==3 for r in plan['samples']),288)
        styles={a['spec']['defect_style'] for r in plan['samples'] for a in r['instances'] if a['kind']=='FOLD'}
        self.assertEqual(len(styles),8)
        self.assertIn('SOFT_BUCKLE',styles)

    def test_capture_categories_stratified_by_class_and_camera(self):
        for setup in SETUPS:
            for kind in ('NONE',)+KINDS:
                rows=[r for r in self.plan['samples'] if r['setup']==setup and r['primary_kind']==kind]
                n=len(rows)
                self.assertEqual(Counter(r['capture_condition'] for r in rows),
                                 dict(matched=n*7//10,focus_noise=n*2//10,framing_light=n//10))

    def test_capture_variation_preserves_defect_and_resolution(self):
        row=self.plan['samples'][0];p=row['settings']
        for mode in ('matched','focus_noise','framing_light'):
            altered=capture_settings(p,mode,7)
            for key in ('seed','defect','depth','position','angle','resolution','frame_aspect','length','radius'):
                self.assertEqual(altered[key],p[key])
            self.assertEqual(altered,capture_settings(p,mode,7))

    def test_sizing_matches_yolox_letterbox_not_square_stretch(self):
        size=projected_sizes([0,0,60,30],1936,1216)
        self.assertAlmostEqual(size['640']['short_side_px'],9.917,places=3)
        self.assertAlmostEqual(size['960']['short_side_px'],14.876,places=3)
        self.assertTrue(projected_sizes([0,0,6,3],1936,1216)['640']['below_4px'])

    def test_plan_is_repeatable_and_reference_remains_available(self):
        a=make_plan(320,123,profile='yolox')
        self.assertEqual(a,make_plan(320,123,profile='yolox'))
        self.assertNotEqual(a,make_plan(320,123,profile='reference'))


if __name__=='__main__':unittest.main()
