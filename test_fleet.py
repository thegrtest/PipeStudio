from collections import Counter
from pathlib import Path
import sys
import io
import json
import tarfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).parent/'remote'))
from fleet_common import allocate, digest_file, digest_json, inside, split_plan, write_json, read_json
from fleet_node import action, lock
import fleet
from domain_plan import make_plan, validate_domain_plan, defects_only_plan, SETUPS, KINDS
from test_domain_runtime import fixture


class FleetPlanningTests(unittest.TestCase):
    def test_update_applies_latest_profile_only_to_unrendered_specimens(self):
        from roll_fleet_update import merged_plan
        old=defects_only_plan(make_plan(320,seed=909))
        latest=defects_only_plan(make_plan(320,seed=909,profile='yolox'))
        merged=merged_plan(old,latest,23)
        self.assertEqual(merged['samples'][:23],old['samples'][:23])
        self.assertEqual([r['sample_id'] for r in merged['samples']],[r['sample_id'] for r in old['samples']])
        self.assertTrue(all(r['sampling_profile']=='yolox' and r['instances'] for r in merged['samples'][23:]))
        self.assertEqual(len(merged['samples']),320)

    def test_defects_only_preserves_commits_and_replaces_only_future_good_rows(self):
        plan=make_plan(320,seed=5211)
        changed=defects_only_plan(plan,37)
        self.assertEqual(changed['samples'][:37],plan['samples'][:37])
        self.assertEqual([r['sample_id'] for r in changed['samples']],[r['sample_id'] for r in plan['samples']])
        for before,after in zip(plan['samples'][37:],changed['samples'][37:]):
            if before['primary_kind']!='NONE': self.assertEqual(before,after)
            self.assertNotEqual(after['primary_kind'],'NONE')
            self.assertTrue(after['instances'])
            self.assertEqual(before['settings']['seed'],after['settings']['seed'])
        fresh=defects_only_plan(plan)
        self.assertNotIn('NONE',fresh['expected_primary_counts'])
        self.assertEqual(fresh['expected_primary_counts'],{kind:80 for kind in KINDS})
        for shard in split_plan(changed,allocate(320,{'a':{},'b':{}})).values(): validate_domain_plan(shard)

    def test_defects_only_continuation_carries_verified_files_without_changing_parent(self):
        with fixture() as root:
            original=make_plan(320,seed=700)
            config={'release':'test-release','blender':['test']}
            action(root,dict(action='prepare',job='parent',plan=original,config=config))
            parent=root/'jobs/parent'; sid=original['samples'][0]['sample_id']
            image=parent/'all/images'/f'{sid}.png'; image.parent.mkdir()
            image.write_bytes(b'committed image')
            record=dict(sample_id=sid,image=f'images/{sid}.png',output_sha256={f'images/{sid}.png':digest_file(image)})
            manifest=dict(samples=[record],plan_sha256=digest_json(original),renderer_sources={'test':'hash'},blender_runtime='test')
            write_json(parent/'all/manifest.json',manifest)
            changed=defects_only_plan(original,1)
            request=dict(action='continue_defects',job='child',parent_job='parent',completed=1,plan=changed,config=config)
            with lock(root/'worker.lock'):
                with self.assertRaises(RuntimeError): action(root,request)
            result=action(root,request)
            self.assertEqual(result['preserved'],1)
            self.assertEqual(action(root,request)['preserved'],1)
            carried=root/'jobs/child/all/images'/f'{sid}.png'
            self.assertEqual(carried.read_bytes(),image.read_bytes())
            self.assertEqual(read_json(parent/'all/manifest.json'),manifest)
            updated=read_json(root/'jobs/child/all/manifest.json')
            self.assertEqual(updated['plan_sha256'],digest_json(changed))
            self.assertEqual(updated['renderer_sources'],manifest['renderer_sources'])
            self.assertEqual(updated['samples'],manifest['samples'])
            image.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'hash mismatch'): action(root,dict(request,job='bad-child'))

    def test_exact_three_thousand_per_device_have_balanced_unique_specimens(self):
        nodes={'desktop':{'weight':8},'spark':{'weight':4},'agx':{'weight':1}}
        args=SimpleNamespace(count=3000,seed=920000,quality='full',smoke=False,per_node=True)
        plan,assignments=fleet.planned_work(args,nodes)
        self.assertEqual(len(plan['samples']),9000)
        self.assertEqual(len({r['settings']['seed'] for r in plan['samples']}),9000)
        self.assertEqual(len({r['sample_id'] for r in plan['samples']}),9000)
        for shard in split_plan(plan,assignments).values():
            validate_domain_plan(shard)
            self.assertEqual(len(shard['samples']),3000)
            self.assertEqual(shard['expected_primary_counts'],dict(NONE=300,**{kind:675 for kind in KINDS}))
            self.assertEqual(shard['expected_setup_counts'],{setup:375 for setup in SETUPS})
            self.assertEqual(sum(len(r['instances'])==2 for r in shard['samples']),675)
            self.assertTrue(all(r['split']=='train' and r['settings']['samples']==128 for r in shard['samples']))
            for kind in ('NONE',)+KINDS:
                counts=[sum(r['primary_kind']==kind and r['setup']==setup for r in shard['samples']) for setup in SETUPS]
                self.assertLessEqual(max(counts)-min(counts),1)

    def test_three_nodes_cover_production_once_and_preserve_distribution(self):
        plan=make_plan(320,seed=910000)
        nodes={'desktop':{'weight':6},'spark':{'weight':2},'agx':{'weight':1}}
        assignments=allocate(len(plan['samples']),nodes)
        self.assertEqual(assignments,allocate(len(plan['samples']),nodes))
        shards=split_plan(plan,assignments)
        rows=[row for shard in shards.values() for row in shard['samples']]
        self.assertEqual(len({row['sample_id'] for row in rows}),320)
        self.assertEqual(Counter(row['primary_kind'] for row in rows),plan['expected_primary_counts'])
        self.assertEqual(Counter(row['setup'] for row in rows),plan['expected_setup_counts'])
        self.assertGreater(len(shards['desktop']['samples']),len(shards['spark']['samples']))
        for name,shard in shards.items():
            self.assertTrue(shard['samples'])
            self.assertEqual(shard['fleet_parent_sha256'],digest_json(plan))
            self.assertEqual(shard['samples'],[plan['samples'][i] for i in assignments[name]])

    def test_duplicate_or_missing_work_is_rejected(self):
        plan={'samples':[{'sample_id':'a'},{'sample_id':'b'}]}
        for assignments in ({'a':[0],'b':[0]},{'a':[0]},{'a':[0,1,2]}):
            with self.assertRaises(ValueError): split_plan(plan,assignments)

    def test_transfer_paths_cannot_escape_dataset(self):
        root=Path(__file__).parent/'exports'
        for value in ('../passwords','images/../../passwords',str(root.parent/'outside')):
            with self.assertRaises(ValueError): inside(root,value)
        self.assertEqual(inside(root,'images/sample.png'),(root/'images/sample.png').resolve())

    def test_verified_deploy_is_repeatable_and_rejects_changed_job(self):
        with fixture() as root:
            (root/'incoming').mkdir()
            archive=root/'incoming'/'test-release.tgz'
            code=b'print("renderer")\n'
            import hashlib
            files={'render.py':hashlib.sha256(code).hexdigest()}
            with tarfile.open(archive,'w:gz') as package:
                for name,data in {'render.py':code,'release.json':json.dumps({'files':files}).encode()}.items():
                    member=tarfile.TarInfo(name); member.size=len(data)
                    package.addfile(member,io.BytesIO(data))
            request=dict(action='install',archive=archive.name,sha256=digest_file(archive),release='test-release')
            self.assertEqual(action(root,request),action(root,request))
            with self.assertRaises(ValueError): action(root,{**request,'sha256':'bad'})
            job=dict(action='prepare',job='test-job',config={'release':'test-release'},
                     plan={'classes':{'0':'Fold'},'samples':[]})
            action(root,job)
            self.assertTrue(action(root,job)['existing'])
            with self.assertRaises(FileExistsError): action(root,{**job,'config':{}})
            with lock(root/'worker.lock'):
                with self.assertRaises(RuntimeError): action(root,dict(action='pack',job='test-job'))
            action(root,dict(action='stop',job='test-job'))
            self.assertTrue((root/'jobs/test-job/cancel.flag').exists())

    def test_snapshot_includes_declared_non_python_renderer_assets(self):
        with fixture() as root:
            (root/'calibration.json').write_text('{"calibrated":false}')
            with patch.object(fleet,'ROOT',root), patch('generate_domain_dataset.CODE_FILES',('calibration.json',)):
                release,archive,digest=fleet.snapshot()
            with tarfile.open(archive) as package:
                self.assertIn('calibration.json',package.getnames())
                receipt=json.load(package.extractfile('release.json'))
            self.assertEqual(receipt['files']['calibration.json'],digest_file(root/'calibration.json'))

    def test_worker_failure_remains_status_not_connection_failure(self):
        state={'state':'failed','completed':7,'total':20,'error':'Render failed'}
        with patch.object(fleet,'run',return_value=json.dumps(state).encode()):
            self.assertEqual(fleet.node_call(dict(root='test',python='python',transport='local'),{'action':'status'}),state)


if __name__=='__main__': unittest.main()
