"""Portable training views that omit the earlier heavy-soiling run."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
folder=root/'datasets/Shell_Defects_Training_20260913'
report={}
for relative in ('','crops/whole_shell','crops/regions'):
    base=folder/relative
    rows=[json.loads(line) for line in (base/'index.jsonl').read_text().splitlines()]
    counts={}
    for split in ('train','val','test'):
        kept=[row for row in rows if row['split']==split and not row['heavy_dirt']]
        lines=['./'+row['image'] for row in kept]
        assert all((base/line[2:]).is_file() for line in lines)
        (base/f'{split}_without_heavy_dirt.txt').write_text('\n'.join(lines)+'\n')
        counts[split]=len(lines)
    config=(base/'data.yaml').read_text()
    for split in ('train','val','test'):
        config=config.replace(f'{split}: images/{split}',f'{split}: {split}_without_heavy_dirt.txt')
    (base/'without_heavy_dirt.yaml').write_text(config)
    report[relative or 'frames']=counts
readme=folder/'README.md'
text=readme.read_text(encoding='utf-8')
text+='\n## Exclude earlier heavy dirt\n\nUse **without_heavy_dirt.yaml** instead of data.yaml to omit captures from the earlier heavily soiled run. Each crop dataset has the same option. These portable image lists preserve the original splits and keep every source file. This excludes heavy dirt, not the subtle normal finish present in older reference renders.\n'
readme.write_text(text,encoding='utf-8')
(folder/'no_heavy_dirt_counts.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
