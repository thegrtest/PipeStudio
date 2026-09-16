import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fast_pipeline import install
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'remote'))
from fleet_node import action, cache_runtime_compatible
from fleet_common import write_json, read_json, digest_json, digest_file
from test_domain_runtime import fixture
from enable_render_cache import verify_trial


class Scene(dict):
    def __init__(self):
        super().__init__(pipe_device='test GPU')
        self.render=SimpleNamespace(use_persistent_data=False)
        self.cycles=SimpleNamespace(device='GPU',denoiser='OPENIMAGEDENOISE',denoising_use_gpu=False)


class RenderCacheTests(unittest.TestCase):
    def studio(self,observed):
        return SimpleNamespace(configure_renderer=lambda scene: None,
            set_mask_mode=lambda scene,active: observed.append((active,scene.render.use_persistent_data)),
            export_frame=lambda *args: None)

    def test_beauty_cache_is_disabled_before_every_mask_transition(self):
        observed=[]; studio=self.studio(observed); scene=Scene()
        with patch.dict(os.environ,{'PIPESTUDIO_RENDER_CACHE':'beauty'}): install(studio)
        studio.configure_renderer(scene)
        self.assertTrue(scene.render.use_persistent_data)
        for _ in range(2):
            studio.set_mask_mode(scene,True)
            self.assertFalse(scene.render.use_persistent_data)
            studio.set_mask_mode(scene,False)
            self.assertTrue(scene.render.use_persistent_data)
        self.assertEqual(observed,[(True,False),(False,True)]*2)

    def test_default_off_and_invalid_modes_fail_closed(self):
        studio=self.studio([]); scene=Scene()
        with patch.dict(os.environ,{'PIPESTUDIO_RENDER_CACHE':'off'}): install(studio)
        studio.configure_renderer(scene)
        studio.set_mask_mode(scene,True); studio.set_mask_mode(scene,False)
        self.assertFalse(scene.render.use_persistent_data)
        with patch.dict(os.environ,{'PIPESTUDIO_RENDER_CACHE':'all'}):
            with self.assertRaises(ValueError): install(self.studio([]))

    def test_handoff_permits_only_known_cache_policy_change(self):
        old=dict(release='old',threads=6,chunk=2,env={'PIPESTUDIO_CYCLES_BACKEND':'CUDA'})
        new={**old,'release':'new','env':{**old['env'],'PIPESTUDIO_RENDER_CACHE':'beauty'}}
        self.assertTrue(cache_runtime_compatible(old,new))
        self.assertFalse(cache_runtime_compatible(old,{**new,'threads':12}))
        self.assertFalse(cache_runtime_compatible(old,{**new,'chunk':20}))
        self.assertFalse(cache_runtime_compatible(old,{**new,'env':{**new['env'],'PIPESTUDIO_RENDER_CACHE':'all'}}))
        self.assertFalse(cache_runtime_compatible(old,{**new,'env':{**new['env'],'PIPESTUDIO_CYCLES_BACKEND':'OPTIX'}}))
        self.assertNotIn('PIPESTUDIO_RENDER_CACHE',old['env'])

    def test_cache_handoff_preserves_committed_outputs_and_records_runtime(self):
        with fixture() as root:
            plan=dict(classes={'0':'Fold'},samples=[dict(sample_id=s,primary_kind='FOLD',instances=[{}])
                                                  for s in ('first','next')])
            old=dict(release='old',blender=['test'],threads=6,env={'PIPESTUDIO_CYCLES_BACKEND':'CUDA'})
            action(root,dict(action='prepare',job='parent',plan=plan,config=old))
            parent=root/'jobs/parent'
            image=parent/'all/images/first.png';image.parent.mkdir();image.write_bytes(b'committed image')
            record=dict(sample_id='first',image='images/first.png',output_sha256={'images/first.png':digest_file(image)})
            write_json(parent/'all/manifest.json',dict(samples=[record],plan_sha256=digest_json(plan),
                renderer_sources={'render.py':'oldhash'},blender_runtime='5.1'))
            release=root/'releases/new';release.mkdir(parents=True)
            (release/'generate_domain_dataset.py').write_text("CODE_FILES=('render.py',)\n")
            (release/'render.py').write_text('# RGB-only cache\n')
            write_json(release/'release.json',dict(files={p.name:digest_file(p) for p in release.iterdir()}))
            updated={**old,'release':'new','env':{**old['env'],'PIPESTUDIO_RENDER_CACHE':'beauty'}}
            action(root,dict(action='continue_release',job='child',parent_job='parent',completed=1,
                             plan=plan,config=updated,paused=True))
            child=root/'jobs/child'
            manifest=read_json(child/'all/manifest.json')
            self.assertEqual(manifest['samples'],[record])
            self.assertEqual((child/'all/images/first.png').read_bytes(),image.read_bytes())
            self.assertEqual(manifest['source_segments'][-1]['runtime_config']['env']['PIPESTUDIO_RENDER_CACHE'],'beauty')
            self.assertEqual(read_json(child/'fleet_job.json'),updated)
            self.assertEqual(read_json(parent/'fleet_job.json'),old)

    def test_deployment_gate_rejects_label_changes_or_missing_speed_gain(self):
        with fixture() as root:
            path=root/'comparison.json'
            report=dict(release='tested',candidate='beauty_only',samples=4,
                        all_labels_exact=True,all_masks_exact=True,all_metadata_exact=True,
                        time_saved_percent=4,samples_detail=[dict(mean_abs_rgb_difference=.00002,max_rgb_difference=2)]*4)
            write_json(path,report)
            self.assertEqual(verify_trial(path,'tested'),report)
            for changes in ({'all_labels_exact':False},{'all_masks_exact':False},{'time_saved_percent':0}):
                write_json(path,{**report,**changes})
                with self.assertRaises(ValueError): verify_trial(path,'tested')


if __name__=='__main__': unittest.main()
