from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).parent/'remote'))
from fleet_node import action
from fleet_common import read_json,write_json,digest_file,digest_json
from domain_plan import make_plan,defects_only_plan
from roll_fleet_update import merged_plan
from test_domain_runtime import fixture


class RendererRolloutTests(unittest.TestCase):
    def test_new_sources_keep_old_commit_provenance_and_pause_without_rendering(self):
        with fixture() as root:
            old=defects_only_plan(make_plan(320,seed=977))
            latest=defects_only_plan(make_plan(320,seed=977,profile='yolox'))
            config=dict(release='old',blender=['test'])
            action(root,dict(action='prepare',job='parent',plan=old,config=config))
            parent=root/'jobs/parent'; sid=old['samples'][0]['sample_id']
            path=parent/'all/images'/f'{sid}.png'; path.parent.mkdir(); path.write_bytes(b'old committed image')
            record=dict(sample_id=sid,image=f'images/{sid}.png',output_sha256={f'images/{sid}.png':digest_file(path)})
            original=dict(samples=[record],plan_sha256=digest_json(old),renderer_sources={'render.py':'oldhash'},blender_runtime='5.1')
            write_json(parent/'all/manifest.json',original)
            release=root/'releases/new'; release.mkdir(parents=True)
            (release/'generate_domain_dataset.py').write_text("CODE_FILES=('render.py',)\n")
            (release/'render.py').write_text('# new rendering code\n')
            write_json(release/'release.json',dict(files={p.name:digest_file(p) for p in release.iterdir()}))
            plan=merged_plan(old,latest,1)
            action(root,dict(action='continue_release',job='child',parent_job='parent',completed=1,
                             plan=plan,config={**config,'release':'new'},paused=True))
            result=read_json(root/'jobs/child/all/manifest.json')
            self.assertEqual(result['samples'],original['samples'])
            self.assertEqual(read_json(parent/'all/manifest.json'),original)
            self.assertEqual(result['renderer_sources'],{'render.py':digest_file(release/'render.py')})
            self.assertEqual(result['source_segments'][0]['renderer_sources'],original['renderer_sources'])
            self.assertEqual((result['source_segments'][0]['start'],result['source_segments'][0]['end']),(0,1))
            self.assertEqual((result['source_segments'][1]['start'],result['source_segments'][1]['end']),(1,None))
            state=action(root,dict(action='status'))
            self.assertEqual((state['job'],state['state'],state['completed']),('child','paused',1))
            self.assertFalse(state['running'])


if __name__=='__main__': unittest.main()
