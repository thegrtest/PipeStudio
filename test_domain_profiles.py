import unittest

from domain_profiles import (CAMERAS, FRAME_SIZES, camera_recipe, camera_settings, optical_response,
                             optical_reference_width, setup_dimensions, reference_frame, inspection_light_positions)


class CameraDomainTests(unittest.TestCase):
    def test_fill_illuminates_upper_image_after_camera_roll(self):
        for camera in CAMERAS:
            rig=inspection_light_positions(camera_settings(camera))
            self.assertLess(rig['fill'][1],0)
            image_up=-1 if camera=='CAM2534' else 1
            self.assertGreater(image_up*rig['fill'][2],0)
            self.assertAlmostEqual(sum(v*v for v in rig['fill']),36)

    def test_nuisance_light_angles_change_geometry_without_label_dependence(self):
        for camera in CAMERAS:
            p=camera_settings(camera)
            base=inspection_light_positions(p)
            for angle in (-25,25):
                varied=inspection_light_positions({**p,'light_azimuth':angle})
                self.assertNotEqual(varied['key'],base['key'])
                self.assertNotEqual(varied['fill'],base['fill'])
                self.assertEqual(varied,inspection_light_positions({**p,'light_azimuth':angle,'defect':'DENT','seed':999}))
                self.assertAlmostEqual(sum(v*v for v in varied['fill']),36)

    def test_exact_reference_resolution_contract(self):
        expected={'CAM2534':(1936,1216),'CAM5080':(1936,1216),'CAM7650':(1936,1216),
                  'UPRIGHT':(640,640),'FOREGROUND':(640,640),'INVERTED':(640,640),
                  'MACHINE':(795,638),'STUDIO':(1936,1216)}
        self.assertEqual(FRAME_SIZES,expected)
        for setup,size in expected.items():
            self.assertEqual(setup_dimensions(setup),size)
            quick=setup_dimensions(setup,quick=True)
            self.assertLessEqual(max(quick),960)
            self.assertLessEqual(quick[0],size[0])
            self.assertLessEqual(quick[1],size[1])
            self.assertEqual(quick[1],round(quick[0]/(size[0]/size[1])))
        self.assertEqual(reference_frame('MACHINE')['source_kind'],'screenshot_proxy')
        self.assertEqual(reference_frame('STUDIO')['source_kind'],'studio_proxy')
        self.assertIsNone(reference_frame('STUDIO')['source_reference'])
        for camera in CAMERAS: self.assertEqual(camera_settings(camera)['resolution'],1936)

    def test_optics_use_actual_camera_reference_pixel_width(self):
        for view in ('UPRIGHT','FOREGROUND','INVERTED'):
            p=dict(environment='MACHINE',capture_view=view)
            self.assertEqual(optical_reference_width(p),640)
            self.assertEqual(optical_response(p)['sigma_at_reference']*640/optical_reference_width(p),.50)
        self.assertEqual(optical_reference_width(dict(environment='MACHINE')),795)
        self.assertEqual(optical_reference_width(dict(environment='BUTTON_TRACK')),1200)
        for camera in CAMERAS:
            p=camera_settings(camera)
            self.assertEqual(optical_reference_width(p),1936)
            sigma=optical_response(p)['sigma_at_reference']
            self.assertAlmostEqual(sigma*960/optical_reference_width(p),sigma*960/1936)

    def test_camera_geometry_and_mount_sides_match_references(self):
        left = camera_recipe('CAM2534')
        self.assertEqual((left['roll_degrees'],left['mouth_side'],left['holder_side']),
                         (180.,'left','right'))
        for camera in ('CAM5080','CAM7650'):
            recipe=camera_recipe(camera)
            self.assertEqual((recipe['roll_degrees'],recipe['mouth_side'],recipe['holder_side']),
                             (0.,'right','left'))
        self.assertEqual(len({camera_recipe(c)['background'] for c in CAMERAS}),3)

    def test_camera_framing_follows_reference_subject_location(self):
        for camera in CAMERAS:
            p=camera_settings(camera)
            center=(.5-p['camera_shift_x'],.5+p['camera_shift_y']*p['frame_aspect'])
            expected=camera_recipe(camera)['expected_center']
            for actual,want in zip(center,expected): self.assertAlmostEqual(actual,want,delta=.002)
            # With a side-on length-8 pipe, all endpoints remain in frame.
            half_width=p['camera_zoom']/2.56
            self.assertGreater(center[0]-half_width,0)
            self.assertLess(center[0]+half_width,1)
            half_height=.9/(8*1.28/p['camera_zoom'])*p['frame_aspect']
            self.assertGreater(center[1]-half_height,0)
            self.assertLess(center[1]+half_height,1)

    def test_seeded_variation_is_repeatable_and_label_independent(self):
        for camera in CAMERAS:
            self.assertEqual(camera_settings(camera,5,.8),camera_settings(camera,5,.8))
            self.assertNotEqual(camera_settings(camera,5,.8),camera_settings(camera,6,.8))
            self.assertEqual(camera_settings(camera,5,0),camera_settings(camera,6,0))
            self.assertTrue({'defect','defect_style','position','angle','depth','seed'}.isdisjoint(camera_settings(camera)))

    def test_varied_recipes_stay_valid_without_clipping_camera_framing(self):
        from app_model import validate_settings
        for camera in CAMERAS:
            for seed in range(50):
                p=camera_settings(camera,seed,2)
                validated=validate_settings(p)
                for key in ('camera_shift_x','camera_shift_y','key_power','color_cast'):
                    self.assertAlmostEqual(validated[key],p[key],delta=1e-6)

    def test_optics_variation_can_be_disabled_and_is_bounded(self):
        p=camera_settings('CAM5080')
        clean=optical_response({**p,'optical_blur':0,'highlight_scatter':0})
        self.assertEqual(clean['sigma_at_reference'],0)
        self.assertEqual(clean['scatter'],0)
        bound=optical_response({**p,'optical_blur':50,'highlight_scatter':50})
        self.assertEqual(bound['sigma_at_reference'],1.7)
        self.assertEqual(bound['scatter'],.15)
        self.assertEqual(optical_response({'environment':'MACHINE'})['sigma_at_reference'],.50)

    def test_bad_camera_and_variation_are_rejected(self):
        with self.assertRaises(ValueError): camera_settings('unknown')
        for variation in (-1,3,float('nan'),float('inf'),'high'):
            with self.assertRaises(ValueError): camera_settings('CAM2534',variation=variation)

    def test_recipe_results_do_not_mutate_global_baselines(self):
        p=camera_recipe('CAM2534')
        original=p['settings']['key_power']
        p['settings']['key_power']=999
        self.assertEqual(camera_recipe('CAM2534')['settings']['key_power'],original)

    def test_acquisition_session_changes_only_known_camera_framing(self):
        from app_model import validate_settings
        for camera in CAMERAS:
            older=camera_settings(camera);newer=camera_settings(camera,session='AUG20')
            self.assertEqual(newer['capture_session'],'AUG20')
            self.assertEqual(newer['resolution'],older['resolution'])
            self.assertAlmostEqual(newer['camera_shift_y']-older['camera_shift_y'],.120 if camera=='CAM5080' else 0)
            validate_settings(newer)
        with self.assertRaises(ValueError):camera_settings('CAM5080',session='unknown')


if __name__=='__main__': unittest.main()
