import io
from pathlib import Path
import sys
import unittest
from contextlib import redirect_stdout

from PIL import Image

sys.path.insert(0,str(Path(__file__).parent/'remote'))
from collect_fleet import collect, checked_labels
from fleet_export import inventory, source_path
from fleet_common import write_json, digest_file
from test_domain_runtime import fixture


class LiveCollectionTests(unittest.TestCase):
    def test_live_collection_ignores_uncommitted_files_deduplicates_and_preserves_source(self):
        with fixture() as root:
            node=root/'node'
            classes={'0':'Fold','1':'Dent','2':'Soap stain','3':'Oil stain'}
            originals=[]
            for job in ('old','new'):
                base=node/'jobs'/job/'all'
                (base/'images').mkdir(parents=True); (base/'labels').mkdir()
                image=base/'images/sample.png'; label=base/'labels/sample.txt'
                Image.new('RGB',(16,12),'#aa9873').save(image); label.write_text('1 0.5 0.5 0.25 0.25\n')
                row=dict(sample_id='sample',image='images/sample.png',primary_kind='DENT',instances=[{}],
                         width=16,height=12,setup='STUDIO',output_sha256={'images/sample.png':digest_file(image),'labels/sample.txt':digest_file(label)})
                write_json(base/'manifest.json',dict(classes=classes,samples=[row]))
                (base/'images/uncommitted.png').write_bytes(b'incomplete')
                originals.append((image,image.read_bytes()))
            self.assertEqual(len(inventory(node)['samples']),2)
            filtered=inventory(node,'new')
            self.assertEqual(len(filtered['samples']),1)
            self.assertEqual(filtered['samples'][0]['job'],'new')
            config=root/'nodes.json'; write_json(config,dict(nodes={'desktop':dict(transport='local',root=str(node),python=sys.executable)}))
            output=root/'collected'
            with redirect_stdout(io.StringIO()):
                result=collect(config,output)
                repeated=collect(config,output)
                selected=collect(config,root/'selected','new')
            self.assertEqual((result['images'],result['labels']),(1,1))
            self.assertEqual(repeated['transfer']['desktop']['files'],0)
            self.assertEqual(selected['job_filter'],'new')
            self.assertEqual(selected['images'],1)
            self.assertEqual(len(list((output/'images').glob('*.png'))),1)
            for path,original in originals: self.assertEqual(path.read_bytes(),original)
            (output/'images/sample.png').write_bytes(b'edited')
            with self.assertRaisesRegex(ValueError,'differs'):
                collect(config,output)

    def test_export_path_and_label_checks_reject_invalid_inputs(self):
        with fixture() as root:
            with self.assertRaises(ValueError): inventory(root,'../private')
            for relative in ('../private.png','jobs/test/all/images/../../secret.png','jobs/test/all/metadata/secret.json'):
                with self.assertRaises(ValueError): source_path(root,relative)
            label=root/'bad.txt'; label.write_text('1 0.99 0.5 0.5 0.1\n')
            with self.assertRaisesRegex(ValueError,'leaves image'):
                checked_labels(label,{'instances':1},{0,1,2,3})


if __name__=='__main__': unittest.main()
