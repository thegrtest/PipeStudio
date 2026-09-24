from dataclasses import replace,asdict
from bisect import bisect_right
import math
import unittest
from domain_geometry import build_instances,instance_grid
from geometry import PipeSpec,displacement,axial_displacement,radius_at,sampling_grid
from neck_defect_plan import make_plan


class NeckDefectTests(unittest.TestCase):
    def test_crescent_trough_curves_and_has_one_raised_edge(self):
        s=PipeSpec(defect_style='CRESCENT_CREASE',position=.885,width=.025,arc=18,
                   irregularity=0,secondary_strength=.7)
        troughs=[]
        for v in (-.8,0,.8):
            line=[(u/100,displacement(s.position+u/100*s.width,math.radians(s.angle+v*s.arc),s)[0])
                  for u in range(-150,151)]
            troughs.append(min(line,key=lambda pair:pair[1])[0])
            self.assertGreater(max(a for u,a in line),.02*s.depth*radius_at(s.position,s))
        self.assertGreater(troughs[0]-troughs[1],.14)
        self.assertGreater(troughs[2]-troughs[1],.14)

    def test_rolled_rim_cannot_reverse_axial_rings_and_mask_covers_drop(self):
        s=PipeSpec(defect_style='ROLLED_LIP',position=.945,width=.04,arc=24,
                   taper_start=.79,taper_end=.88,depth=.25,secondary_strength=1)
        center=math.radians(s.angle)
        self.assertLess(axial_displacement(1,center,s),-.05)
        self.assertAlmostEqual(axial_displacement(1,center+math.pi,s),0)
        for theta in (center-.3,center,center+.3):
            xs=[(i/1000-.5)*s.length+axial_displacement(i/1000,theta,s) for i in range(1001)]
            self.assertTrue(all(b>a for a,b in zip(xs,xs[1:])))
            for i in range(881,1001):
                t=i/1000
                if abs(axial_displacement(t,theta,s))>=.03*s.depth*s.radius:
                    self.assertEqual(displacement(t,theta,s)[1],1)
        for clean in (replace(s,depth=0),replace(s,defect='NONE')):
            self.assertEqual(axial_displacement(1,center,clean),0)

    def test_counterfactual_restores_rim_and_keeps_topology_other_dent(self):
        base=PipeSpec(defect='NONE',depth=0)
        rim=replace(base,defect='DENT',defect_style='ROLLED_LIP',position=.945,width=.04,depth=.2)
        dent=replace(base,defect='DENT',position=.45,width=.03,depth=.08)
        items=[dict(kind='DENT',spec=asdict(s)) for s in (rim,dent)]
        full=build_instances(base,items,16,16);control=build_instances(base,items,16,16,omit_instance=0)
        ts,angles,_=instance_grid(base,items,16,16)
        self.assertEqual(full[1],control[1]);self.assertEqual(len(full[0]),len(control[0]))
        self.assertEqual(full[4][1],control[4][1]);self.assertFalse(any(control[4][0]))
        self.assertTrue(any(a[0]!=b[0] for a,b in zip(full[0],control[0])))
        for i,t in enumerate(ts):
            for j,theta in enumerate(angles):
                point=control[0][i*len(angles)+j]
                self.assertAlmostEqual(point[0],(t-.5)*base.length)
                self.assertAlmostEqual(math.hypot(*point[1:]),radius_at(t,base)+displacement(t,theta,dent)[0])
        with self.assertRaisesRegex(ValueError,'At most one'):
            build_instances(base,[items[0],items[0]],16,16)

    def test_recipe_is_deterministic_balanced_opt_in_and_keeps_real_class(self):
        plan=make_plan(12);self.assertEqual(plan,make_plan(12));self.assertNotEqual(plan,make_plan(12,99))
        self.assertEqual(plan['expected_setup_counts'],{'UPRIGHT':6,'FOREGROUND':6})
        self.assertEqual(plan['expected_instance_counts'],{'DENT':12})
        for row in plan['samples']:
            self.assertEqual(row['settings']['resolution'],640)
            self.assertEqual(row['instances'][0]['class_id'],1)
        with self.assertRaises(ValueError):make_plan(7)

    def test_adaptive_sampling_retains_narrow_crescent_without_zipper_edges(self):
        for row in make_plan()['samples']:
            s=PipeSpec(**row['instances'][0]['spec'])
            ts,angles=sampling_grid(s,adaptive=True)
            peak=s.depth*radius_at(s.position,s)
            self.assertLessEqual(2*len(ts)*len(angles),200000)
            for v in (-.7,0,.7):
                theta=math.radians(s.angle+v*s.arc)
                for i in range(-210,160):
                    t=s.position+i/100*s.width
                    if not 0<t<1:continue
                    k=bisect_right(ts,t)-1;a,b=ts[k:k+2]
                    left,right=displacement(a,theta,s)[0],displacement(b,theta,s)[0]
                    interpolated=left+(right-left)*(t-a)/(b-a)
                    self.assertLess(abs(interpolated-displacement(t,theta,s)[0])/peak,.05)


if __name__=='__main__':unittest.main()
