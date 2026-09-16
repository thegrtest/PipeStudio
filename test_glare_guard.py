import unittest
import numpy as np
from glare_guard import assess


class GlareTests(unittest.TestCase):
    def setUp(self):
        self.rgb=np.full((100,100,3),.4,dtype=np.float32)
        self.pipe=np.zeros((100,100),bool);self.pipe[10:90,20:80]=True
        self.defect=np.zeros((100,100),bool);self.defect[30:40,40:50]=True

    def check(self): return assess(self.rgb,[self.defect],self.pipe)

    def test_white_and_yellow_over_defect_rejected(self):
        for color in ((1,1,1),(1,1,.7)):
            self.rgb[self.defect]=color
            self.assertFalse(self.check()['passed'])

    def test_soap_with_detail_not_rejected(self):
        self.rgb[self.defect]=(.90,.92,.89)
        self.assertTrue(self.check()['passed'])

    def test_small_specular_glint_allowed(self):
        self.rgb[30,40]=1
        self.assertTrue(self.check()['passed'])

    def test_white_fixture_not_counted(self):
        self.rgb[~self.pipe]=1
        self.assertTrue(self.check()['passed'])

    def test_dark_defect_inside_glare_is_rejected(self):
        self.rgb[26:44,36:54]=1
        self.rgb[self.defect]=.3
        self.assertFalse(self.check()['passed'])

    def test_good_specimen_also_gated(self):
        self.rgb[20:40,30:60]=1
        self.assertFalse(assess(self.rgb,[],self.pipe)['passed'])

    def test_each_defect_checked(self):
        other=np.zeros_like(self.defect);other[70:80,50:60]=True
        self.rgb[other]=1
        report=assess(self.rgb,[self.defect,other],self.pipe)
        self.assertTrue(report['instances'][0]['passed'])
        self.assertFalse(report['instances'][1]['passed'])

    def test_invalid_support_never_silently_accepted(self):
        with self.assertRaises(ValueError): assess(self.rgb,[np.zeros_like(self.defect)],self.pipe)


if __name__=='__main__': unittest.main()
