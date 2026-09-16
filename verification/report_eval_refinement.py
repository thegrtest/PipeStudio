"""Validate the bounded render check and explain what changed in its gallery."""
import json
from pathlib import Path
import sys
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from domain_review import validate_dataset,write_gallery

def main():
    root=ROOT/'verification/eval_refinement'
    records=json.loads((root/'results.json').read_text())
    plan=json.loads((root/'review_plan.json').read_text())
    (root/'render_plan.json').write_text(json.dumps(plan,indent=2))
    (root/'all/manifest.json').write_text(json.dumps(dict(classes={'0':'Fold','1':'Dent','2':'Soap stain','3':'Oil stain'},samples=records),indent=2))
    report,_=validate_dataset(root)
    left,right=[r for r in records if r.get('pair_role')=='lighting_variant']
    def pixels(row):return np.asarray(Image.open(root/'all'/row['instances'][0]['mask']))
    # PNG hashes can differ because Blender embeds file metadata. Compare the
    # actual binary masks to test stable labels under lighting changes.
    paired=dict(same_specimen=left['specimen_id']==right['specimen_id'],
                same_geometry=left['instances'][0]['spec']==right['instances'][0]['spec'],
                same_mask_pixels=np.array_equal(pixels(left),pixels(right)),
                same_labels=(root/'all/labels'/f"{left['sample_id']}.txt").read_bytes()==(root/'all/labels'/f"{right['sample_id']}.txt").read_bytes(),
                different_images=left['output_sha256'][left['image']]!=right['output_sha256'][right['image']])
    report['paired_lighting_check']=paired
    (root/'validation.json').write_text(json.dumps(report,indent=2))
    if not report['valid'] or not all(paired.values()):raise RuntimeError('Render verification failed; see validation.json')
    write_gallery(root,report,records)
    page=root/'index.html';html=page.read_text(encoding='utf-8')
    note='''<section style="padding:24px;background:#20362d;border:1px solid #627b69;margin-bottom:24px">
<h2>Changes from the real-image evaluation</h2>
<p><strong>21 reference-sized previews, all eight environments.</strong> Broad shallow sweeps cover the smooth dents missed by the model. Soft buckles add rounded neck and silhouette folds. Legacy shapes remain available.</p>
<p>Two images show the same small fold under different moderate light directions: geometry, mask pixels and labels are identical while RGB changes. Two sound-part controls include stronger hardware reflections. One image has two separately labeled dents plus soap residue.</p>
<p>The production recipe retains 10% good, 720 primary images per defect class and 400 images per environment in a 3,200-image cycle. It includes 1,152 mixed images, of which 288 contain three instances. Lighting and fixture conditions are stratified across classes, including good parts.</p>
<p><strong>Development previews only.</strong> These repeated controls are kept out of training bundles. Native dimensions, label alignment, file integrity and glare checks passed. This does not establish better real-model accuracy; compare the next trained model on a fixed real development set.</p>
</section>'''
    html=html.replace('</header>','</header>'+note,1)
    assert 'Changes from the real-image evaluation' in html
    page.write_text(html,encoding='utf-8')
    print(json.dumps(dict(valid=report['valid'],images=report['image_count'],unique=report['unique_image_hash_count'],paired=paired)))

if __name__=='__main__':main()
