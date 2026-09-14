"""Inspect export completeness and schemas without modifying source datasets."""
from pathlib import Path
import json
import sys
root = Path(__file__).resolve().parents[1]
reports = []
for manifest in sorted((root/'exports').rglob('manifest.json')):
    folder = manifest.parent
    data = json.loads(manifest.read_text(encoding='utf-8'))
    samples = data.get('samples', data.get('images', []))
    if isinstance(samples, dict): samples = list(samples.values())
    first = samples[0] if samples else {}
    metadata = sorted((folder/'metadata').glob('*.json'))
    if isinstance(first, dict) and first.get('metadata'):
        first = json.loads((folder/first['metadata']).read_text())
    elif metadata:
        first = json.loads(metadata[0].read_text())
    images = list((folder/'images').glob('*'))
    report = dict(folder=str(folder.relative_to(root)), manifest_mb=round(manifest.stat().st_size/1e6,2),
        top_keys=list(data), samples=len(samples), metadata=len(metadata), images=len(images),
        folders=[p.name for p in folder.iterdir() if p.is_dir()],
        classes=data.get('classes'), status=json.loads((folder/'status.json').read_text()) if (folder/'status.json').exists() else None,
        sample_keys=list(first) if isinstance(first,dict) else str(first)[:100])
    if isinstance(first, dict):
        report['sample_summary']={k:first.get(k) for k in ('image','width','height','camera_id','sequence_id','split_group','specimen_group','appearance_version','source_variant_count')}
        report['sample_annotation']=first.get('annotations',[])[:1]
        report['sample_crop']=first.get('crops',[])[:1]
        report['recipe_keys']=list(first.get('recipe',{}))
        report['recipe_seed']=first.get('recipe',{}).get('seed')
        report['first_item']=first.get('recipe',{}).get('items',[])[:1]
    reports.append(report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('sample_crop','first_item','sample_annotation')},ensure_ascii=False),flush=True)
(root/'verification/training-source-inventory.json').write_text(json.dumps(reports,indent=2))
