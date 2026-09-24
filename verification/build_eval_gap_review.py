"""Build a local visual review from saved evaluation outputs; no inference or dataset edits."""
import csv
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'eval_gap_20260923_232143'
SOURCE = Path(r'C:\Users\daugh\EvalReports\eval_20260923_232143')

EXAMPLES = [
    ('Body', '20260905_013112_470_cam2829.jpg', 'Broad, shallow body dent',
     'All three checkpoints miss the labeled dent; latest produces no detection. The depression has a soft dark center and weak highlight transition. Generate these alongside small circular dimples; stronger depth alone would change the target appearance.'),
    ('Body', '20260905_014217_432_cam2829.jpg', 'Dent close to the silhouette',
     'All three checkpoints miss this frame. Move visible defects toward the left and right sides of the cylindrical body, varying reflection direction and roll while retaining a readable cue.'),
    ('Neck', '20260905_013510_819_cam1130.jpg', 'Thin neck fold beside an obvious body dent',
     'The large body dent is detected, but the narrow neck fold is missed. Extend the new crescent family with long axial creases and rim/sidewall deformations.'),
    ('Neck', '20260905_013510_819_cam2829.jpg', 'A second view of the neck-fold gap',
     'The body dent is detected confidently while a thin fold along the neck edge is missed. This is a useful paired-view failure, not two independent physical defects.'),
    ('Labels', '20260905_013112_470_cam1489.jpg', 'Detected region, wrong defect class',
     'The mouth label is Fold, but the overlapping prediction is Dent at 0.75. Audit class boundaries and generate consistent Fold/Dent examples. More visual contrast by itself does not address this error.'),
    ('Clusters', '20260905_013443_838_cam1489.jpg', 'Mixed visibility and a background response',
     'Two of four labeled defects are missed, and an extra prediction appears off the part. Include one strong defect with smaller nearby defects, plus matching fixture backgrounds without defects.'),
    ('Clusters', '19691231_182526_548_cam0.jpg', 'Several adjacent dents',
     'Only one of five labeled defects is matched. Prioritize clusters with different sizes and contrast, checking visibility for every annotation after the camera effect and model resize.'),
    ('Scale', '20260819_162328_497_cam5080.jpg', 'Small defect in a full-resolution frame',
     'The frame is resized to a 640-pixel long edge before inference. Evaluate the defect at that scale; native render resolution alone does not guarantee that the model sees enough detail.'),
    ('Negatives', 'TEST_cam1_20251209_113607_341.jpg', 'Neck-transition false alarm',
     'This frame has no ground-truth boxes, but the model responds near the neck/shoulder transition. Verify that the region is acceptable before using it as a clean counterexample.'),
    ('Labels', '20260812_174502_805_cam5080.jpg', 'Soap reference has an empty evaluation label',
     'This is one of the user-supplied soap examples, yet the evaluated label file is empty. This run cannot measure soap recall. If soap is a reject class, review these labels before treating the frames as good parts.'),
    ('Labels', '20260819_091242_596_cam7650.jpg', 'A label floating in the background',
     'One tiny Fold box is above and left of the part. Review that annotation separately from the three on-part Dent labels. Do not create synthetic defects to imitate a misplaced box.'),
]


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th>' + html.escape(str(x)) + '</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + html.escape(str(x)) + '</td>' for x in r) + '</tr>' for r in rows) + '</tbody></table></div>'


def main():
    OUT.mkdir(exist_ok=True)
    assets = OUT / 'examples'
    assets.mkdir(exist_ok=True)
    a = json.loads((OUT / 'analysis.json').read_text())
    run = json.loads((SOURCE / 'run.json').read_text())
    rows = list(csv.DictReader((SOURCE / 'per_image.csv').open(encoding='utf-8-sig', newline='')))
    per_image = {(r['model'], r['image']): r for r in rows}
    model_rows = []
    corrected = []
    for m in run['models']:
        v = m['metrics']; totals = m['image_totals']; pc = m['per_class']
        model_rows.append([m['model_name'], f"{v['precision']:.1%}", f"{v['recall']:.1%}", totals['fn'], totals['kick_misses'], f"{totals['kick_false']}/401"])
        for cid, name in [(0, 'Fold'), (1, 'Dent')]:
            tp, fn, fp = pc[f'class_{cid}']['tp'], pc[f'class_{cid}']['fn'], pc[name]['fp']
            corrected.append(dict(model=m['model_name'], class_name=name, tp=tp, fp=fp, fn=fn, recall=tp/(tp+fn), precision=tp/(tp+fp)))
    (OUT / 'corrected_classes.json').write_text(json.dumps(corrected, indent=2))
    cameras = a['cameras']['latest_ckpt']
    assert sum(v['gt'] for v in cameras.values()) == 1875
    assert sum(v['fn'] for v in cameras.values()) == 264
    target = [cameras[c] for c in ['1130', '2829', '1489']]
    assert sum(v['tp'] for v in target) == 64 and sum(v['gt'] for v in target) == 108
    camera_rows = [[c, cameras[c]['images'], f"{cameras[c]['tp']}/{cameras[c]['gt']}", f"{cameras[c]['tp']/cameras[c]['gt']:.1%}", cameras[c]['negative']] for c in ['2829', '1489', '1130']]
    camera_rows.append(['All other cameras', 1744, '1547/1767', '87.5%', 400])
    gallery = []
    manifest = []
    for i, (tag, name, title, note) in enumerate(EXAMPLES):
        annotated = SOURCE / 'annotated' / 'latest_ckpt' / name
        r = per_image['latest_ckpt', name]
        original = Path(r['image_path'])
        assert annotated.is_file() and original.is_file(), name
        ann_name, raw_name = f'{i:02d}_annotated.jpg', f'{i:02d}_original.jpg'
        shutil.copy2(annotated, assets / ann_name)
        shutil.copy2(original, assets / raw_name)
        stats = f"GT {r['gt_count']} · TP {r['tp']} · FP {r['fp']} · FN {r['fn']}"
        gallery.append(f'''<article data-tag="{tag}"><div class="cardhead"><span>{tag}</span><b>{html.escape(title)}</b></div>
          <a href="examples/{ann_name}" target="_blank"><img loading="lazy" src="examples/{ann_name}" alt="{html.escape(title)}"></a>
          <div class="body"><strong>{stats}</strong><p>{html.escape(note)}</p><small>{html.escape(name)}</small>
          <p class="links"><a href="examples/{ann_name}" target="_blank">Full annotation</a> · <a href="examples/{raw_name}" target="_blank">Original pixels</a></p></div></article>''')
        manifest.append(dict(category=tag, image=name, title=title, observation=note, counts={k:int(r[k]) for k in ('gt_count','tp','fp','fn')}, annotated=str(annotated), original=str(original)))
    (OUT / 'review_examples.json').write_text(json.dumps(manifest, indent=2))
    size_rows = []
    for group in ['<16', '16-31', '32-63', '64+']:
        v = a['single_gt_size']['latest_ckpt'][group]
        size_rows.append([group, v['images'], f"{v['tp']}/{v['gt']}", f"{v['tp']/v['gt']:.1%}"])
    class_rows = [[c['class_name'], c['tp'], c['fp'], c['fn'], f"{c['precision']:.1%}", f"{c['recall']:.1%}"] for c in corrected if c['model']=='latest_ckpt']
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Pre-change evaluation · failure patterns</title><style>
    :root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#111a23;color:#edf2f6;font:16px/1.55 system-ui,sans-serif}main{max-width:1380px;margin:auto;padding:40px 26px}h1{font-size:36px;line-height:1.15;margin:10px 0 18px}h2{margin-top:36px;font-size:23px}p{max-width:1060px}a{color:#91d3ff}small,.muted{color:#b5c1cc} .eyebrow{color:#e6b978;text-transform:uppercase;font-size:13px;letter-spacing:.13em}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:26px 0}.stat{background:#1c2a36;border:1px solid #31434e;border-radius:12px;padding:22px}.stat strong{display:block;font-size:31px;color:#ffe0aa}.stat span{color:#c6d1d8}.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;background:#182530}td,th{text-align:left;padding:11px 15px;border-bottom:1px solid #31404b}th{color:#e9c791;font-size:14px}.note{border-left:3px solid #e6b978;background:#1d2932;padding:14px 19px;margin:22px 0}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{border:1px solid #34444f;background:#17232e;border-radius:12px;overflow:hidden}article img{width:100%;height:470px;object-fit:contain;background:#080c10;display:block}.cardhead,.body{padding:16px 20px}.cardhead span{display:block;color:#eac58f;font-size:12px;text-transform:uppercase;letter-spacing:.1em}.cardhead b{font-size:20px}.body p{margin:8px 0 12px}.body small{overflow-wrap:anywhere}.links{font-size:14px}button{border:1px solid #4c6473;border-radius:20px;padding:7px 16px;background:#172530;color:#e5eff5;font:inherit;cursor:pointer}button.active{background:#e6b978;color:#18222a;border-color:#e6b978}.filters{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}li{margin:12px 0;max-width:1090px}[hidden]{display:none!important}details{margin:18px 0}summary{cursor:pointer;color:#a7d9f7}footer{border-top:1px solid #3b4a54;margin-top:38px;padding-top:18px;font-size:13px;color:#afbec9}@media(max-width:800px){main{padding:25px 16px}.grid,.stats{grid-template-columns:1fr}h1{font-size:28px}article img{height:auto;max-height:620px}}
    </style><main><div class="eyebrow">Saved baseline · September 23, 2026 · 23:21:43</div>
    <h1>Target the subtle defects in the weak camera views</h1>
    <p>The dominant observed gaps are broad shallow dents, small edge defects, thin neck folds, and less obvious defects beside a strong one. The newly added crescent and rolled-mouth styles address part of this; this saved evaluation does not measure their effect yet.</p>
    <div class="stats"><div class="stat"><strong>59.3%</strong><span>Defect recall in cameras 1130 / 2829 / 1489<br>64 of 108 labels · 76 frames</span></div><div class="stat"><strong>87.5%</strong><span>Defect recall in the other camera groups<br>1,547 of 1,767 labels</span></div><div class="stat"><strong>44 / 401</strong><span>Label-negative frames flagged by latest<br>11.0% false-alarm rate under existing labels</span></div></div>
    <p class="muted">Camera, size, and multiplicity breakdowns below use latest_ckpt at confidence 0.25 with class-aware center matching. These are descriptive recall measurements, not AP. Camera cohorts differ in defect composition, so the gap does not prove lighting alone is responsible.</p>
    <h2>Where the failures concentrate</h2>CAMERA_TABLE
    <p>The three weak cameras contribute 16.7% of all missed labels while containing 5.8% of ground-truth labels. Each has only 25–26 images, and together they have just one negative frame. The exact rates need a larger camera-specific holdout. Best_ap50_95 also struggles here: 68/108 labels matched (63.0%).</p>
    <h2>Generation targets, in priority order</h2><ol>
    <li><b>Shallow body dents and silhouette dents in these three views.</b> Include small round dimples, broader pressed-in ovals, asymmetric depressions, and edge placements. Match the dark grainy brass, soft highlight/shadow transitions, neighboring part occlusion, and fixture reflections. Vary lighting within each real camera setup. Retain shallow but visible examples rather than making every defect deep.</li>
    <li><b>Thin neck and mouth folds alongside the new crescent defects.</b> Add axial creases, edge wrinkles, rolled rims and subtle shoulder interruptions. Maintain consistent Fold/Dent definitions; several apparent misses already have a prediction of the wrong class.</li>
    <li><b>Multiple defects with unequal visibility.</b> Latest recall is 90.7% on single-defect frames, 85.0% on two-defect frames, and 64.4% on frames with three or more labels. Generate one obvious defect plus smaller adjacent ones, sometimes combining body and neck defects. Apply the visibility check separately to every label.</li>
    <li><b>Verified difficult negatives under the same lighting.</b> Normal shoulder transitions, bright edges, draw lines and surface mottling attract false positives. Add intact counterparts with the same nuisance appearance. First check that existing empty-label images are actually acceptable for the intended classes.</li>
    <li><b>Preserve cues at the model's input size.</b> Measure defect size and contrast after the 640-pixel preprocessing step. Test a part crop or a larger model input separately if tiny defects remain unresolved. Generating a higher-resolution full frame alone does not change the size seen by a model still resizing to 640.</li>
    </ol>
    <h2>Examples to guide the next generation pass</h2><p class="muted">Orange = unmatched ground truth; red = unmatched prediction; green = matched. class_0 means Fold and class_1 means Dent. Click an image for full resolution, or open the original pixels without boxes.</p>
    <div class="filters">FILTERS</div><div class="grid">GALLERY</div>
    <h2>The very small defects need special attention</h2>SIZE_TABLE
    <p class="muted">Only single-label frames are used here so the missed box is unambiguous. Size is sqrt(box width × box height), measured after long-edge resize to 640; it is not literal defect diameter. The smallest group has just 27 examples. The size effect is descriptive and intertwined with camera and defect type.</p>
    <h2>Checkpoint differences are smaller than the recurring gaps</h2>MODEL_TABLE
    <p>Best_ap50_95 catches 11 more labels than latest and leaves 71 rather than 77 positive frames completely unflagged, at the cost of 19 extra unmatched predictions and one extra negative-frame false alarm. All three checkpoints miss at least one label on the same 173 frames; all three produce no prediction on the same 44 positive frames.</p>
    <div class="note"><b>Do not interpret the 94.6% pickout figure as full defect coverage.</b> That metric counts any prediction anywhere in a positive frame as a successful reject. Latest has 34 such positive frames with zero correctly matched defects. Its label-level recall is 85.9%, and this run uses the lenient center rule: either box's center inside the other box counts as a spatial match.</div>
    <h2>Annotation and reporting issues to resolve</h2><ul>
    <li>The evaluation loaded no class names. It separates Fold/Dent false positives from class_0/class_1 true positives and misses, producing misleading per-class precision rows. Matching itself uses class IDs, so aggregate counts remain usable. The corrected latest table below combines IDs 0/1 with the dataset's Fold/Dent names.</li>
    <li>At least one off-part Fold annotation needs review. Some neck errors are class confusion, which should be separated from defects with no detection at all.</li>
    <li>There are no Soap or Stain ground-truth boxes in this run. A supplied soap reference is present with an empty label. If these are intended reject categories, the validation labels need completing before judging those classes.</li>
    <li>Evaluate the next model on a versioned copy of the same baseline with the same threshold and matching rule, plus a strict IoU diagnostic. Keep an additional real holdout that was not used to tune generation. When correcting labels, rescore both models against the same corrected version.</li>
    </ul>CLASS_TABLE
    <details><summary>Method and source files</summary><p>Read all 1,820 per-image records for each of three checkpoints, reconciled label counts, inspected selected annotated failures at full resolution and camera contact sheets. No inference was rerun. Multi-label image counts cannot identify exactly which boxes failed without the saved predictions; box-level size analysis is restricted to single-label images. Camera IDs are filename-derived and may cover several collection sessions. Counts are per frame, not independent tracked physical parts.</p>
    <p><a href="SOURCE_REPORT">Original evaluation report</a> · <a href="analysis.json">Full breakdown and source hashes</a> · <a href="corrected_classes.json">Corrected class counts</a> · <a href="review_examples.json">Example manifest</a></p></details>
    <footer>Source: C:\\Users\\daugh\\EvalReports\\eval_20260923_232143. Read-only review: generation jobs, training, evaluation outputs and dataset labels were not changed.</footer></main>
    <script>document.querySelectorAll('.filters button').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.filters button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('article[data-tag]').forEach(x=>x.hidden=b.dataset.filter!=='All'&&x.dataset.tag!==b.dataset.filter)}));</script></html>'''
    replacements = {
        'CAMERA_TABLE': table(['Camera','Frames','Matched / GT','Recall','Negative frames'], camera_rows),
        'SIZE_TABLE': table(['Box-equivalent pixels','Single-label frames','Matched / GT','Recall'], size_rows),
        'MODEL_TABLE': table(['Checkpoint','Precision','Recall','Missed labels','Unflagged positive frames','Flagged negative frames'], model_rows),
        'CLASS_TABLE': table(['Class','TP','FP','FN','Precision','Recall'], class_rows),
        'GALLERY': ''.join(gallery),
        'FILTERS': ''.join(f'<button class="{"active" if t=="All" else ""}" data-filter="{t}">{t}</button>' for t in ['All','Body','Neck','Clusters','Scale','Negatives','Labels']),
        'SOURCE_REPORT': (SOURCE / 'report.html').as_uri(),
    }
    for token, value in replacements.items():
        assert token in document, token
        document = document.replace(token, value)
    (OUT / 'index.html').write_text(document, encoding='utf-8')
    print(json.dumps({'report': str(OUT / 'index.html'), 'examples': len(EXAMPLES), 'source_images_modified': 0}, indent=2))


if __name__ == '__main__':
    main()
