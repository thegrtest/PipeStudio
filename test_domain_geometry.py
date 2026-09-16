from collections import Counter
from dataclasses import asdict,replace
import math
import unittest

from domain_geometry import build_instances,instance_grid
from geometry import PipeSpec,displacement,radius_at


def instance(spec):
    return dict(kind=spec.defect,spec=asdict(spec))


class DomainGeometryTests(unittest.TestCase):
    def test_single_small_fold_keeps_true_geometry_and_separate_support(self):
        base=PipeSpec(length=8,radius=.9,taper_start=.8,taper_end=.88,defect='NONE',depth=0)
        spec=replace(base,defect='FOLD',defect_style='AXIAL_PINCH',position=.85,
                     width=.02,arc=10,depth=.06)
        instances=[instance(spec)]
        ts,angles,_=instance_grid(base,instances,24,32)
        vertices,faces,masks,regions,individual=build_instances(base,instances,24,32)
        half=len(vertices)//2
        self.assertEqual(masks,individual[0])
        self.assertTrue(any(masks))
        self.assertFalse(any(masks[half:]))
        for i,t in enumerate(ts):
            for j,theta in enumerate(angles):
                index=i*len(angles)+j
                delta,mask=displacement(t,theta,spec)
                self.assertAlmostEqual(math.hypot(*vertices[index][1:]),radius_at(t,base)+delta,places=12)
                self.assertEqual(masks[index],mask)

    def test_mixed_fold_and_dent_supports_are_independent_and_wall_is_closed(self):
        base=PipeSpec(length=8,radius=.9,taper_start=.8,taper_end=.88,defect='NONE',depth=0)
        fold=replace(base,defect='FOLD',defect_style='AXIAL_PINCH',position=.85,width=.02,arc=12,depth=.09)
        dent=replace(base,defect='DENT',defect_style='ELONGATED',position=.48,width=.035,arc=18,depth=.10)
        vertices,faces,masks,regions,individual=build_instances(base,[instance(fold),instance(dent)],24,32)
        half=len(vertices)//2
        self.assertTrue(all(any(values) for values in individual))
        self.assertFalse(any(a and b for a,b in zip(*individual)))
        self.assertEqual(masks,[float(a or b) for a,b in zip(*individual)])
        edges=Counter(tuple(sorted((a,b))) for face in faces for a,b in zip(face,face[1:]+face[:1]))
        self.assertTrue(all(count==2 for count in edges.values()))
        for outer,inner in zip(vertices[:half],vertices[half:]):
            self.assertAlmostEqual(math.hypot(*outer[1:])-math.hypot(*inner[1:]),base.radius*base.wall_ratio,places=12)
            self.assertGreater(math.hypot(*inner[1:]),0)

    def test_overlapping_extreme_defects_remain_bounded_with_positive_inner_bore(self):
        base=PipeSpec(radius=.3,end_ratio=.35,wall_ratio=.22,position=.94,width=.08,arc=30,
                      defect='NONE',depth=0)
        dent=replace(base,defect='DENT',depth=.25)
        vertices,faces,masks,regions,individual=build_instances(base,[instance(dent),instance(dent)],16,16)
        half=len(vertices)//2
        for outer,inner in zip(vertices[:half],vertices[half:]):
            t=outer[0]/base.length+.5
            radius=math.hypot(*outer[1:])
            self.assertLessEqual(abs(radius-radius_at(t,base)),.249001*radius_at(t,base))
            self.assertGreater(math.hypot(*inner[1:]),.005)

    def test_stain_refines_geometry_without_deforming_or_labeling_it(self):
        base=PipeSpec(defect='DENT',depth=.13)
        spot=dict(kind='SOAP_STAIN',spot=dict(position=.58,angle=180,axial_size=.008,angular_size=5))
        ts,angles,specs=instance_grid(base,[spot],24,32)
        self.assertGreater(len(ts),100)
        self.assertGreater(len(angles),100)
        self.assertEqual(specs,[None])
        vertices,faces,masks,regions,individual=build_instances(base,[spot],24,32)
        self.assertFalse(any(masks))
        self.assertFalse(any(individual[0]))
        for outer in vertices[:len(vertices)//2]:
            self.assertAlmostEqual(math.hypot(*outer[1:]),radius_at(outer[0]/base.length+.5,base),places=12)

    def test_mismatched_bodies_and_invalid_stains_are_rejected(self):
        base=PipeSpec()
        with self.assertRaisesRegex(ValueError,'same body'):
            build_instances(base,[instance(replace(base,radius=1))])
        with self.assertRaisesRegex(ValueError,'Invalid stain'):
            build_instances(base,[dict(kind='SOAP_STAIN',spot=dict(position=.5,angle=0,axial_size=0,angular_size=5))])


if __name__=='__main__':
    unittest.main()
