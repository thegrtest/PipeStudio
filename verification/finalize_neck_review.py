"""Collect the two reviewed camera batches without mixing their provenance."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent/'crescent_neck_20260923'

def main():
    batches=[]
    for name,count in (('final',6),('side',1)):
        folder=ROOT/name
        assert 'VISIBILITY_REVIEW_COMPLETE' in (folder/'render.log').read_text()
        data=json.loads((folder/'all/manifest.json').read_text())
        assert len(data['samples'])==count and not data.get('rejected')
        for row in data['samples']:
            assert row['glare_guard']['passed'] and row['visibility_guard']['passed']
            for rel,digest in row['output_sha256'].items():
                assert hashlib.sha256((folder/'all'/rel).read_bytes()).hexdigest()==digest
        batches.append(dict(folder=name,count=count,revision=sorted({r['generation_revision'] for r in data['samples']}),
                            audit=json.loads((folder/'audit.json').read_text())))
    side=json.loads((ROOT/'side/all/manifest.json').read_text())['samples'][0]
    stem=side['sample_id']
    results=dict(accepted=7,native_dimensions=[640,640],class_id=1,class_name='Dent',
        batches=batches,earlier_iteration='pass1',real_images_in_training_folder=False,
        fleet_jobs_modified=False,render_device='CPU (6 threads)',
        limitations=['Rolled mouth is a continuous wall, not missing/torn metal.',
                     'Visibility checks are not detector accuracy measurements.'])
    (ROOT/'RESULTS.json').write_text(json.dumps(results,indent=2))
    (ROOT/'index.html').write_text(f'''<!doctype html><meta charset="utf-8"><title>Neck defect comparison</title>
    <style>body{{font:17px system-ui;background:#0c141e;color:#dce9f4;max-width:1320px;margin:40px auto;padding:0 24px}}h1,h2{{color:#fff}}p{{line-height:1.6}}img{{max-width:100%;border-radius:8px}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}a{{color:#9cdaff}}section{{background:#14202c;border-radius:12px;padding:22px;margin:24px 0}}</style>
    <h1>Crescent creases and uneven mouth edges</h1>
    <p>Seven labeled synthetic examples at native 640 × 640. All retain <b>Dent (class 1)</b>, matching your supplied annotations, and pass the existing glare and matched-control visibility checks.</p>
    <section><h2>Crescent toward the side of the neck</h2><div class="pair">
    <div><p>Real camera reference</p><img src="side/assets/20260905_012931_613_cam1130.jpg"></div>
    <div><p>New synthetic side-angle example</p><img src="side/assets/{stem}.jpg"></div></div>
    <p><a href="side/index.html">Inspect labels, enlarged detail and the same scene with the defect removed</a></p></section>
    <section><h2>Size, lighting and camera variation</h2><a href="final/index.html"><img src="final/contact_sheet.jpg"></a>
    <p><a href="final/index.html">Open all six detailed comparisons</a></p></section>
    <p>The first iteration produced an overly tall U. The revised crescent is flatter, has a weaker raised edge and appears at varied angles.
    The rolled-mouth version changes the rim silhouette as well as the neck surface. It remains smoother than the torn-looking edge in the real photograph; no missing metal is modeled.</p>
    <p>The general fleet ratios are unchanged. These are targeted development examples; actual YOLOX improvement still needs evaluation.
    The two batches retain their individual plans and source fingerprints. Real references stay outside the synthetic image folders.</p>
    <p><a href="pass1/index.html">Earlier shape iteration</a> · <a href="RESULTS.json">Verification record</a></p>''',encoding='utf-8')
    print(json.dumps(dict(accepted=7,labels=7,native_dimensions=[640,640])))

if __name__=='__main__':main()
