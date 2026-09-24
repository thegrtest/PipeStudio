import hashlib
import unittest
import numpy as np
from brass_microdetail import synthesize_details


class BrassMicrodetailTests(unittest.TestCase):
    def test_repeatability_unique_seeds_and_bounded_channels(self):
        hashes=set()
        for seed in range(6):
            a, audit=synthesize_details(seed,width=384,height=256)
            b, repeated=synthesize_details(seed,width=384,height=256)
            np.testing.assert_array_equal(a,b)
            self.assertEqual(audit,repeated)
            hashes.add(hashlib.sha256(a.tobytes()).hexdigest())
            self.assertTrue(np.isfinite(a).all())
            self.assertGreaterEqual(float(a[...,0].min())*1.5,.439)
            self.assertLessEqual(float(a[...,0].max())*1.5,1.321)
            self.assertGreaterEqual(float(a[...,1].min()),.249)
            self.assertLessEqual(float(a[...,1].max()),.751)
            self.assertTrue((a[...,3]==1).all())
        self.assertEqual(len(hashes),6)

    def test_quiet_regions_and_sparse_resolved_details(self):
        a,_=synthesize_details(75,width=768,height=512,finish_marks=.3)
        detail=abs(a[...,0]*1.5-1.)
        # Faint continuous forming texture is now present in quiet areas too;
        # most of the surface must still vary by less than five percent.
        self.assertGreater(float((detail<.05).mean()),.70)
        self.assertGreater(float((detail>.04).mean()),.002)
        self.assertLess(float((detail>.12).mean()),.08)
        # Similar mean finish may still hide uniform spatial distribution.
        tiles=detail.reshape(8,64,8,96).transpose(0,2,1,3).mean(axis=(2,3))
        self.assertGreater(float(tiles.std()/tiles.mean()),.20)

    def test_clean_has_fewer_marks_and_different_dimensions_change_scale(self):
        clean,ca=synthesize_details(76,width=384,height=256,finish_marks=.08)
        dirty,da=synthesize_details(76,width=384,height=256,finish_marks=.7)
        self.assertLess(ca['traces'],da['traces'])
        self.assertLess(ca['specks'],da['specks'])
        self.assertFalse(np.array_equal(clean,dirty))
        other,_=synthesize_details(76,width=384,height=256,finish_marks=.08,radius=.5)
        self.assertFalse(np.array_equal(clean,other))

    def test_angular_seam_has_no_hard_boundary(self):
        a,_=synthesize_details(75,width=768,height=512,finish_marks=.7)
        seam=abs(a[0,:,:3]-a[-1,:,:3]).mean()
        ordinary=abs(np.diff(a[...,:3],axis=0)).mean()
        self.assertLess(float(seam),float(ordinary)*4+.0001)

    def test_forming_details_follow_taper_without_changing_handling_identity(self):
        a, first=synthesize_details(381,width=512,height=384,taper_start=.8,taper_end=.88)
        b, second=synthesize_details(381,width=512,height=384,taper_start=.55,taper_end=.7)
        self.assertFalse(np.array_equal(a,b))
        for key in ('contacts','traces','specks','patches','forming_tracks','forming_segments'):
            self.assertEqual(first[key],second[key])
        # Moving the shoulder leaves most of the earlier body unchanged.
        np.testing.assert_allclose(a[:,:180],b[:,:180],atol=.0001)

    def test_clean_part_still_has_forming_texture(self):
        a, audit=synthesize_details(34,width=512,height=384,finish_marks=0,wear=0)
        self.assertGreater(audit['forming_segments'],audit['forming_tracks'])
        self.assertGreater(audit['neck_rubs'],0)
        self.assertGreater(float(a[...,:3].std()),0)
        for kw in (dict(taper_start=.9,taper_end=.8),dict(end_ratio=0),dict(end_ratio=1.1)):
            with self.assertRaises(ValueError):synthesize_details(1,width=32,height=32,**kw)


if __name__=='__main__':unittest.main()
