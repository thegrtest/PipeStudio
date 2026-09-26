import contextlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / 'remote'))
from assembly_fleet import make_node_plan
from assembly_fleet_runtime import supervise
from fleet_common import digest_json, write_json, read_json
from fleet_node import action
from test_domain_runtime import fixture


class AssemblyFleetTests(unittest.TestCase):
    def test_warm_track_is_separate_single_part_profile(self):
        plan=make_node_plan(15,925260,64,'WARM_TRACK','FOUR_LINES','ALL')
        self.assertEqual(set(plan['policy']['primary_conditions']),{'good','dent','ding','scratch','deformity'})
        self.assertEqual(plan['settings']['look'],'WARM_TRACK')
        self.assertIn('assets/assembly_warm_track/empty_track.png',plan['settings']['renderer_sha256'])
        self.assertNotIn('assets/assembly_cam3936/provenance.json',plan['settings']['renderer_sha256'])
        for row in plan['rows']:
            self.assertEqual(row['companions'],[])
            self.assertEqual(row['recipe']['lighting'],'FOUR_LINES')
        from assembly_camera_match import plate_assets
        self.assertTrue(set(plate_assets('WARM_TRACK'))<=set(plate_assets()))

    def test_warm_lighting_keeps_geometry_and_finish_fixed(self):
        from assembly_plan import make_specimen
        from assembly_realism import profile
        recipes=[make_specimen(925261,'dent','WARM_TRACK',p) for p in ('CURRENT','BALANCED','FOUR_LINES')]
        for recipe in recipes[1:]:
            self.assertEqual(recipe['instances'],recipes[0]['instances'])
            self.assertEqual(recipe['finish'],recipes[0]['finish'])
        self.assertGreater(profile('CURRENT','WARM_TRACK')['width'],profile('BALANCED','WARM_TRACK')['width'])
        self.assertGreater(profile('BALANCED','WARM_TRACK')['width'],profile('FOUR_LINES','WARM_TRACK')['width'])

    def test_disjoint_specimens_and_stable_lighting_across_views(self):
        plans = [make_node_plan(120, seed) for seed in (700000, 1700000)]
        groups = []
        for plan in plans:
            self.assertEqual(plan['policy']['primary_conditions'], dict(dent=54, deformity=54, good=12))
            lighting = {}
            ids = set()
            for row in plan['rows']:
                recipe = row['recipe']
                self.assertEqual(lighting.setdefault(row['split_group'], recipe['lighting']), recipe['lighting'])
                self.assertEqual(recipe['look'], 'CAMERA_MATCHED')
                for r in [recipe] + row['companions']:
                    ids.add(r['specimen_id'])
                    self.assertLessEqual({i['kind'] for i in r['instances']}, {'dent', 'deformity'})
            groups.append(ids)
        self.assertFalse(groups[0] & groups[1])

    def test_assembly_prepare_does_not_create_old_schema_manifest(self):
        with fixture() as root:
            plan = make_node_plan(3, 100)
            result = action(root, dict(action='prepare', job='assembly-test', plan=plan,
                                      config=dict(pipeline='assembly', release='release', plan_sha256=digest_json(plan))))
            self.assertEqual(result['prepared'], 'assembly-test')
            folder = root / 'jobs/assembly-test'
            self.assertFalse((folder / 'all/manifest.json').exists())
            self.assertEqual(read_json(folder / 'fleet_status.json')['total'], 3)
            action(root, dict(action='stop', job='assembly-test'))
            self.assertTrue((folder / 'cancel.flag').exists())

    def test_no_progress_is_bounded_and_pause_does_not_render(self):
        with fixture() as root:
            job = 'assembly-test'; folder = root / 'jobs' / job
            plan = make_node_plan(3, 100)
            write_json(folder / 'render_plan.json', plan)
            write_json(folder / 'fleet_job.json', dict(pipeline='assembly', release='release',
                       plan_sha256=digest_json(plan), blender=['fake-blender']))
            write_json(root / 'releases/release/release.json', dict(files={}))
            with patch('assembly_fleet_runtime.complete', return_value=False), \
                 patch('assembly_fleet_runtime.subprocess.run', return_value=SimpleNamespace(returncode=1)) as render:
                with self.assertRaisesRegex(RuntimeError, 'Three attempts'):
                    supervise(root, job, lambda path: contextlib.nullcontext())
                self.assertEqual(render.call_count, 3)
                self.assertEqual(read_json(folder / 'fleet_status.json')['state'], 'failed')
                (folder / 'cancel.flag').touch()
                render.reset_mock()
                supervise(root, job, lambda path: contextlib.nullcontext())
                render.assert_not_called()
                self.assertEqual(read_json(folder / 'fleet_status.json')['state'], 'paused')


if __name__ == '__main__':
    unittest.main()
