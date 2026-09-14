import unittest
from app_model import validate_settings, DEFAULTS, front_angle
from product_modes import initial_settings

class ProductModeTests(unittest.TestCase):
    def test_crimp_conditions_scoped_to_button_track(self):
        for kind in ('OPEN_CENTER','PROTRUDING_CRIMP'):
            self.assertEqual(validate_settings({'product_mode':'FLASHLIGHT','environment':'BUTTON_TRACK','defect':kind})['defect'],kind)
            for environment in ('TRACK','TRACK_GRAZING'):
                with self.assertRaises(ValueError):validate_settings({'product_mode':'FLASHLIGHT','environment':environment,'defect':kind})
            with self.assertRaises(ValueError):validate_settings({'defect':kind})
    def test_crimp_severity_limits(self):
        for key,value in [('crimp_opening',0),('crimp_opening',.5),('crimp_lift',-.01),('crimp_spread',.5),('crimp_twist',90)]:
            with self.assertRaises(ValueError):validate_settings({key:value})
    def test_clean_fold_envelope_and_raised_center(self):
        import crimp_geometry as crimp
        co,delta=crimp.point(crimp.RADIUS+1e-15,.5,0,{})
        self.assertAlmostEqual(co[1],crimp.RIM)
        for depth in (.035,.085,.14):
            for twist in (0,18,40):
                item=dict(crimp_twist=twist,crimp_fold_depth=depth)
                for k in range(25):
                    for j in range(17):
                        co,delta=crimp.point(crimp.RADIUS*k/24,j/16,0,item)
                        self.assertLessEqual(co[1],crimp.RIM+1e-8)
                d=dict(kind='protruding_crimp',spread=.26,lift=.08,irregularity=.5,angle=1)
                co,delta=crimp.point(0,.5,0,item,d)
                self.assertAlmostEqual(co[1],crimp.RIM+.08)
    def test_crimp_tightness_preserves_clean_rim_and_lift(self):
        import crimp_geometry as crimp
        for amount in (0,.5,.85,1):
            item=dict(crimp_tightness=amount,crimp_fold_depth=.14)
            for k in range(31):
                for j in range(25):
                    co,delta=crimp.point(crimp.RADIUS*k/30,j/24,0,item)
                    self.assertLessEqual(co[1],crimp.RIM+1e-8)
            co,delta=crimp.point(0,.5,0,item,dict(kind='protruding_crimp',spread=.26,lift=.08,irregularity=.5,angle=1))
            self.assertAlmostEqual(co[1],crimp.RIM+.08)
    def test_dust_can_be_disabled_and_is_bounded(self):
        from flashlight_capture import varied_settings
        p=validate_settings({'product_mode':'FLASHLIGHT','environment':'BUTTON_TRACK','dust_amount':0})
        self.assertEqual(varied_settings(p,7)['dust_amount'],0)
        with self.assertRaises(ValueError):validate_settings({'dust_amount':1.1})
    def test_capture_variation_reproducible_and_diverse(self):
        from flashlight_capture import varied_settings,STYLES
        p=validate_settings({'product_mode':'FLASHLIGHT','environment':'BUTTON_TRACK'})
        rows=[varied_settings(p,i) for i in range(40)]
        self.assertEqual(rows,[varied_settings(p,i) for i in range(40)])
        self.assertEqual({r['defect_style'] for r in rows},set(STYLES))
        self.assertGreater(len({r['depth'] for r in rows}),3)
        self.assertGreater(len({r['roughness'] for r in rows}),20)
        reference=varied_settings({**p,'flashlight_variation':'REFERENCE'},3)
        for key in ('roughness','exposure','key_power','camera_shift_x','sensor_noise'):
            self.assertEqual(reference[key],p[key])
    def test_button_track_camera_and_region_choices(self):
        p=validate_settings({'product_mode':'FLASHLIGHT','environment':'BUTTON_TRACK','defect':'SCRATCH','flashlight_surface':'PLASTIC','flashlight_region':'PLASTIC_FACE'})
        self.assertEqual(p['flashlight_capture'],'ALL')
        for values in ({'flashlight_camera':'SIDE'},{'flashlight_region':'BUTTON'},{'flashlight_capture':'UNKNOWN'}):
            with self.assertRaises(ValueError):validate_settings({**p,**values})
    def test_legacy_pipe_setup_unchanged(self):
        p=validate_settings({'defect':'FOLD','environment':'MACHINE'})
        self.assertEqual(p['product_mode'],'PIPE')
        self.assertEqual(p['defect'],'FOLD')
    def test_modes_have_valid_separate_defaults(self):
        for mode in ('PIPE','FLASHLIGHT'):
            p=validate_settings(initial_settings(mode,DEFAULTS))
            self.assertEqual(p['product_mode'],mode)
    def test_reject_cross_product_environment_and_defect(self):
        for settings in ({'environment':'TRACK'}, {'product_mode':'FLASHLIGHT','environment':'MACHINE'},
                         {'product_mode':'FLASHLIGHT','defect':'FOLD'}, {'defect':'SCRATCH'},
                         {'product_mode':'FLASHLIGHT','defect':'SCRATCH','flashlight_surface':'PLASTIC'}):
            with self.assertRaises(ValueError): validate_settings(settings)
    def test_index_and_count_validation(self):
        for settings in ({'flashlight_count':2,'flashlight_index':2},{'flashlight_count':3.2},{'battery_probability':float('nan')}):
            with self.assertRaises(ValueError):validate_settings({'product_mode':'FLASHLIGHT',**settings})
    def test_body_twist_validation_and_boundaries(self):
        from shell_deformation import twist
        p=validate_settings({'product_mode':'FLASHLIGHT','environment':'BUTTON_TRACK','defect':'TWIST','body_twist':-120})
        self.assertEqual(p['body_twist'],-120)
        from flashlight_capture import varied_settings
        self.assertEqual(varied_settings({**p,'body_twist':0},3)['body_twist'],0)
        for angle in (-140,-35,-5,0,5,35,140):
            d=dict(position=.5,twist_span=.7,twist_degrees=angle)
            for y in (-1.055,1.35):
                r,theta,marked=twist(y,0,.488,d)
                self.assertAlmostEqual(r,.488)
                self.assertFalse(marked)
                self.assertAlmostEqual(theta,0 if y<0 else __import__('math').radians(angle))
            for n in range(101):
                r,theta,marked=twist(-1.055+2.405*n/100,n*.12,.488,d)
                self.assertGreater(r,.4)
        for values in ({'body_twist':141},{'body_twist_span':0}):
            with self.assertRaises(ValueError):validate_settings({**p,**values})
        with self.assertRaises(ValueError):validate_settings({'product_mode':'FLASHLIGHT','environment':'TRACK','defect':'TWIST'})
    def test_front_tracks_roll(self):
        self.assertEqual(front_angle({'product_mode':'FLASHLIGHT','flashlight_roll':-180}),270)

if __name__=='__main__': unittest.main()
