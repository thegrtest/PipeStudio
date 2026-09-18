import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from PIL import Image

sys.path.insert(0,str(Path(__file__).parent/'remote'))
from collect_fleet import collect, checked_labels
from fleet_export import inventory, source_path
from fleet_common import write_json, digest_file,read_json
from test_domain_runtime import fixture


class LiveCollectionTests(unittest.TestCase):
    def test_archive_mixed_labels_and_incremental_collection_cannot_restore_exclusions(self):
        from split_surface_dataset import split,verified_copy
        with fixture() as root:
            node=root/'node'; base=node/'jobs/run/all'
            (base/'images').mkdir(parents=True); (base/'labels').mkdir()
            classes={'0':'Fold','1':'Dent','2':'Soap stain','3':'Oil stain'}
            records=[]
            combinations=((0,1),(1,2),(0,3),(2,3))
            for index,ids in enumerate(combinations):
                sid='sample_'+str(index)
                image=base/'images'/f'{sid}.png'; label=base/'labels'/f'{sid}.txt'
                Image.new('RGB',(16,12),(100,index*40,75)).save(image)
                label.write_text(''.join(f'{k} 0.5 0.5 0.25 0.25\n' for k in ids))
                records.append(dict(sample_id=sid,image='images/'+image.name,primary_kind=('FOLD','DENT','SOAP_STAIN','OIL_STAIN')[ids[0]],
                    instances=[{'class_id':k} for k in ids],width=16,height=12,setup='STUDIO',
                    output_sha256={'images/'+image.name:digest_file(image),'labels/'+label.name:digest_file(label)}))
            write_json(base/'manifest.json',dict(classes=classes,samples=records))
            config=root/'nodes.json';write_json(config,dict(nodes={'desktop':dict(transport='local',root=str(node),python=sys.executable)}))
            output=root/'collected';soap=root/'Soap Dataset';stain=root/'Stain Dataset'
            with redirect_stdout(io.StringIO()):
                collect(config,output)
                def interrupted_copy(source,target,expected):
                    if target.is_relative_to(stain): raise OSError('Simulated archive interruption')
                    return verified_copy(source,target,expected)
                with patch('split_surface_dataset.verified_copy',side_effect=interrupted_copy):
                    with self.assertRaisesRegex(OSError,'interruption'):split(output,soap,stain)
                self.assertEqual(len(list((output/'images').glob('*.png'))),4)
                self.assertEqual(len(list((output/'labels').glob('*.txt'))),4)
                with self.assertRaisesRegex(RuntimeError,'pending dataset split'):collect(config,output)
                result=split(output,soap,stain)
                repeated=split(output,soap,stain)
                refreshed=collect(config,output)
            self.assertEqual([result[k]['images'] for k in (2,3,'retained')],[2,2,1])
            self.assertEqual(refreshed['images'],1)
            self.assertEqual(refreshed['transfer']['desktop']['files'],0)
            self.assertEqual(read_json(output/'.collection/receipt.json')['excluded_class_ids'],[2,3])
            self.assertEqual((output/'classes.txt').read_text(),'Fold\nDent\n')
            for folder,sids in ((soap,(1,3)),(stain,(2,3)),(output,(0,))):
                self.assertEqual({p.stem for p in (folder/'images').glob('*.png')},{'sample_'+str(i) for i in sids})
                for i in sids:
                    self.assertEqual((folder/'labels'/f'sample_{i}.txt').read_bytes(),(base/'labels'/f'sample_{i}.txt').read_bytes())

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
                row=dict(sample_id='sample',image='images/sample.png',primary_kind='DENT',instances=[{'class_id':1}],
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
