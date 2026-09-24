import unittest
from collections import Counter
import math
import numpy as np

from assembly_plan import make_plan,make_specimen,capture_pose,visible_box,yolo_line,NATIVE_SIZE,DEFECT_CLASSES
from assembly_generate import split_rows


class AssemblyPlanTests(unittest.TestCase):
    def test_camera_plates_do_not_follow_alternating_class_schedule(self):
        from assembly_camera_match import choose_plate,PLATES
        for parity in (0,1):
            counts=Counter(choose_plate(seed) for seed in range(10000+parity,14000,2))
            self.assertEqual(set(counts),set(PLATES))
            self.assertTrue(all(850<n<1150 for n in counts.values()),counts)

    def test_small_shallow_dent_distribution(self):
        recipes=[make_specimen(seed,'dent',allowed_defects=('dent',)) for seed in range(1000,2000)]
        families=Counter(r['instances'][0]['dent_family'] for r in recipes)
        self.assertTrue(350<families['small_circular']<450,families)
        self.assertTrue(170<families['shallow_circular']<270,families)
        self.assertTrue(210<families['shallow_band']<310,families)
        self.assertTrue(80<families['large_varied']<170,families)
        for r in recipes:
            item=r['instances'][0];d=item.get('round_dent')
            if d:
                self.assertLess(d['depth'],.031)
                if item['dent_family']=='shallow_band':
                    self.assertTrue(.48<=d['aspect']<=.78)
                    self.assertLessEqual(abs(d['rotation']),.28)
                elif item['dent_family']=='small_circular':
                    self.assertTrue(.92<=d['aspect']<=1.10)
                else:
                    self.assertTrue(.85<=d['aspect']<=1.15)

    def test_soft_fold_distribution_covers_low_contrast_buckles(self):
        recipes=[make_specimen(seed,'deformity',allowed_defects=('deformity',)) for seed in range(2000,3000)]
        styles=Counter(r['instances'][0]['spec']['defect_style'] for r in recipes)
        self.assertTrue(500<styles['SOFT_BUCKLE']<610,styles)
        self.assertTrue(250<styles['AXIAL_PINCH']<360,styles)
        self.assertTrue(110<styles['WRINKLED']<200,styles)
        soft=[r['instances'][0]['spec'] for r in recipes if r['instances'][0]['spec']['defect_style']=='SOFT_BUCKLE']
        self.assertTrue(all(.035<=s['depth']<=.09 for s in soft))
        self.assertTrue(all(-25<=s['defect_rotation']<=25 for s in soft))

    def test_round_dent_is_smooth_bowl_with_matching_support(self):
        from assembly_dents import round_dent_field
        from geometry import PipeSpec,radius_at
        r=next(make_specimen(s,'dent',allowed_defects=('dent',)) for s in range(50) if 'round_dent' in make_specimen(s,'dent',allowed_defects=('dent',))['instances'][0])
        item=r['instances'][0];d=item['round_dent'];d.update(aspect=1,asymmetry=0,rotation=0)
        base=PipeSpec(**r['base']);p=item['spec'];center=math.radians(p['angle']);rr=radius_at(p['position'],base)
        distances=np.linspace(-d['radius']*1.2,d['radius']*1.2,101)
        a,support=round_dent_field(p['position']+distances/base.length,np.full(101,center),item,base)
        b,_=round_dent_field(np.full(101,p['position']),center+distances/rr,item,base)
        self.assertTrue(np.allclose(a,b,atol=1e-12))
        self.assertTrue(np.all(a<=0));self.assertAlmostEqual(a[50],-d['depth'])
        self.assertTrue(np.all(a[np.abs(distances)>=d['radius']]==0))
        self.assertTrue(np.array_equal(support,(-a/d['depth']>=.03).astype(np.float32)))

    def test_small_dent_mesh_is_resolved_and_closed_thickness(self):
        from assembly_geometry import build_assembly_body
        r=next(make_specimen(s,'dent',allowed_defects=('dent',)) for s in range(50) if 'round_dent' in make_specimen(s,'dent',allowed_defects=('dent',))['instances'][0])
        vertices,faces,supports=build_assembly_body(r)
        v=np.asarray(vertices);half=len(v)//2
        self.assertGreater(supports[0][:half].sum(),100)
        self.assertTrue(np.allclose(np.linalg.norm(v[:half,1:],axis=1)-np.linalg.norm(v[half:,1:],axis=1),r['base']['radius']*r['base']['wall_ratio']))

    def test_dents_folds_only_balance_and_companions(self):
        rows=make_plan(120,260916,defect_set='DENTS_FOLDS')
        self.assertEqual(Counter(r['recipe']['condition'] for r in rows),dict(dent=54,deformity=54,good=12))
        mixed=0
        for row in rows:
            for recipe in [row['recipe']]+row['companions']:
                kinds={i['kind'] for i in recipe['instances']}
                self.assertTrue(kinds<= {'dent','deformity'})
                mixed+=len(kinds)==2
                if row['recipe']['condition']=='good':self.assertFalse(kinds)
                for item in recipe['instances']:
                    self.assertEqual(item['class_id'],0 if item['kind']=='dent' else 3)
                    self.assertEqual(item['spec']['defect'],'DENT' if item['kind']=='dent' else 'FOLD')
        self.assertGreater(mixed,0)
        with self.assertRaises(ValueError):make_plan(3,defect_set='UNKNOWN')

    def test_lighting_changes_do_not_move_defects(self):
        from assembly_realism import LIGHTING_PRESETS,profile
        recipes=[make_specimen(410,'scratch','REFINED',p) for p in LIGHTING_PRESETS]
        for r in recipes:
            self.assertEqual(r['base'],recipes[0]['base'])
            self.assertEqual(r['instances'],recipes[0]['instances'])
            self.assertEqual(r['finish'],recipes[0]['finish'])
        self.assertGreater(profile('BALANCED')['width'],profile('FOUR_LINES')['width'])
        self.assertEqual(len(profile('FOUR_LINES')['heights']),4)
        with self.assertRaises(ValueError):make_specimen(1,lighting='UNKNOWN')

    def test_preserved_look_and_companion_position(self):
        from assembly_realism import companion_offset
        r=make_specimen(260915,'good','ORIGINAL','CURRENT')
        self.assertEqual(companion_offset(r),-18)
        self.assertEqual(r['base']['length'],6.6)
        self.assertEqual(r['base']['radius'],.62)
        self.assertEqual(companion_offset(make_specimen(260915,look='REFINED')),-13)
        self.assertEqual(companion_offset(make_specimen(260915,look='CAMERA_MATCHED')),8)

    def test_native_camera_and_repeatability(self):
        self.assertEqual(NATIVE_SIZE,(1920,1200))
        self.assertEqual(make_plan(15,15),make_plan(15,15))
        self.assertNotEqual(make_plan(15,15),make_plan(15,16))

    def test_balanced_primary_conditions(self):
        counts=Counter(r['recipe']['condition'] for r in make_plan(120))
        self.assertEqual(counts,dict(good=12,dent=27,ding=27,scratch=27,deformity=27))

    def test_same_specimen_finish_and_group_across_roll(self):
        rows=make_plan(15)
        for start in range(0,15,3):
            group=rows[start:start+3]
            self.assertTrue(all(r['recipe']==group[0]['recipe'] for r in group))
            self.assertEqual(len({r['split_group'] for r in group}),1)
            self.assertEqual(len({r['pose']['roll'] for r in group}),3)
            for a,b in zip(group,group[1:]):
                self.assertAlmostEqual((b['pose']['roll']-a['pose']['roll'])*a['recipe']['base']['radius'],b['pose']['travel']-a['pose']['travel'])

    def test_no_shared_specimens_across_split(self):
        split=split_rows(make_plan(120))
        groups=[{r['split_group'] for r in split[k]} for k in ('train','val')]
        self.assertTrue(groups[0] and groups[1]);self.assertFalse(groups[0]&groups[1])
        ids=[{s['specimen_id'] for r in split[k] for s in [r['recipe']]+r['companions']} for k in ('train','val')]
        self.assertFalse(ids[0]&ids[1])

    def test_good_frames_have_no_defects_on_any_part(self):
        for r in make_plan(120):
            if r['recipe']['condition']=='good':
                self.assertFalse(r['recipe']['instances'])
                self.assertTrue(all(not c['instances'] for c in r['companions']))

    def test_lighting_not_condition_encoded(self):
        recipes=[make_specimen(99,k) for k in ('good',)+DEFECT_CLASSES]
        self.assertTrue(all(r['finish']==recipes[0]['finish'] for r in recipes))
        self.assertTrue(all(r['environment']==recipes[0]['environment'] for r in recipes))
        self.assertTrue(all(r['initial_roll']==recipes[0]['initial_roll'] for r in recipes))

    def test_visible_box_clipping_and_normalization(self):
        mask=np.zeros((1200,1920),bool);mask[1190:,1900:]=True
        box=visible_box(mask);self.assertEqual(box,[1900,1190,20,10])
        vals=yolo_line(1,box,1920,1200).split()
        self.assertEqual(vals[0],'1');self.assertTrue(all(0<float(v)<=1 for v in vals[1:]))
        self.assertIsNone(visible_box(np.zeros((10,10),bool)))
        with self.assertRaises(ValueError):yolo_line(0,[1910,0,20,4],1920,1200)

    def test_deformation_support_and_wall_thickness(self):
        from assembly_geometry import build_assembly_body
        for kind in ('ding','scratch','deformity'):
            r=make_specimen(420,kind);r['instances']=r['instances'][:1]
            vertices,faces,supports=build_assembly_body(r)
            v=np.asarray(vertices);half=len(v)//2
            self.assertTrue(np.isfinite(v).all());self.assertGreater(len(faces),1000)
            self.assertGreater(supports[0][:half].sum(),0);self.assertEqual(supports[0][half:].sum(),0)
            radii=np.linalg.norm(v[:,1:],axis=1)
            self.assertTrue(np.all(radii>0))
            self.assertTrue(np.allclose(radii[:half]-radii[half:],r['base']['radius']*r['base']['wall_ratio']))


if __name__=='__main__':unittest.main()
