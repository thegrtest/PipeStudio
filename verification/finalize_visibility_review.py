"""Finish a stopped development preview, then verify every accepted pair/hash."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from domain_render import atomic_json
from defect_visibility import assess


def main(folder):
    folder=Path(folder).resolve();all_dir=folder/'all'
    if 'VISIBILITY_REVIEW_COMPLETE' not in (folder/'render.log').read_text():
        raise ValueError('Preview has not completed; do not modify a running manifest')
    manifest=json.loads((all_dir/'manifest.json').read_text());plan=json.loads((folder/'render_plan.json').read_text())
    # The first preview script named its review-only negatives GOOD. Normalize
    # that metadata to the production NONE spelling; no pixels/labels change.
    for record in manifest['samples']:
        if record['primary_kind']=='GOOD' and not record['instances']:
            record['primary_kind']='NONE'
            path=all_dir/'metadata'/(record['sample_id']+'.json')
            metadata=json.loads(path.read_text());metadata['primary_kind']='NONE'
            metadata['review_metadata_normalization']='GOOD renamed to NONE; pixels and labels unchanged'
            record['review_metadata_normalization']=metadata['review_metadata_normalization']
            atomic_json(path,metadata)
            record['output_sha256'][path.relative_to(all_dir).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    for row in plan['samples']:
        if not row['instances']:row['primary_kind']='NONE'
    plan['expected_primary_counts']=dict(Counter(r['primary_kind'] for r in plan['samples']))
    plan['expected_instance_counts']=dict(Counter(i['kind'] for r in plan['samples'] for i in r['instances']))
    plan['expected_setup_counts']={'INVERTED':len(plan['samples'])}
    plan['generation_policy']=dict(defects_only=False,allowed_defects=['FOLD','DENT'])
    plan['ratio_definition']='Curated development review, including matched negative controls; not production allocation.'
    plan['rendered_sample_ids']=[r['sample_id'] for r in manifest['samples']]
    plan['rejected_sample_ids']=[r['sample_id'] for r in manifest.get('rejected',[])]
    atomic_json(folder/'render_plan.json',plan);atomic_json(all_dir/'manifest.json',manifest)
    hashes=set();boxes=0;visibility=[]
    def raster(path):
        with Image.open(path) as im:return np.array(im.convert('RGB'),dtype=np.float32)/255
    for record in manifest['samples']:
        for rel,digest in record['output_sha256'].items():
            assert hashlib.sha256((all_dir/rel).read_bytes()).hexdigest()==digest,rel
        rgb=raster(all_dir/record['image']);assert rgb.shape==(640,640,3)
        digest=hashlib.sha256((all_dir/record['image']).read_bytes()).hexdigest()
        assert digest not in hashes,'Duplicate accepted RGB';hashes.add(digest)
        lines=(all_dir/'labels'/(record['sample_id']+'.txt')).read_text().splitlines()
        assert len(lines)==len(record['instances'])
        for line,instance in zip(lines,record['instances']):
            cls,*coords=map(float,line.split());assert cls==instance['class_id'];assert len(coords)==4
            assert all(0<=v<=1 for v in coords) and coords[2]>0 and coords[3]>0
            boxes+=1
        silhouette=raster(all_dir/record['pipe_mask'])[:,:,0]>.5
        masks=[raster(all_dir/i['mask'])[:,:,0]>.5 for i in record['instances']]
        for check in record['visibility_guard']['instances']:
            index=check['instance_index']
            result=assess(rgb,raster(all_dir/check['control_image']),masks[index],silhouette,
                          [m for j,m in enumerate(masks) if j!=index],check['thresholds'])
            assert result['passed'],(record['sample_id'],index,result)
            visibility.append(dict(sample_id=record['sample_id'],instance_index=index,**result))
    for rejected in manifest.get('rejected',[]):
        assert not (all_dir/'images'/(rejected['sample_id']+'.png')).exists()
        assert not (all_dir/'labels'/(rejected['sample_id']+'.txt')).exists()
    assert len(list((all_dir/'images').glob('*.png')))==len(hashes)
    audit=dict(accepted_images=len(hashes),defect_boxes=boxes,
               clean_controls=sum(not r['instances'] for r in manifest['samples']),
               rejected_candidates=len(manifest.get('rejected',[])),dimensions=[640,640],
               all_hashes_verified=True,unique_rgb=True,all_visibility_rechecks_passed=True,
               visibility=visibility)
    atomic_json(folder/'verification.json',audit)
    print({k:v for k,v in audit.items() if k!='visibility'})


if __name__=='__main__':main(sys.argv[1])
