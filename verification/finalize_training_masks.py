"""Keep optional binary instance masks outside the auto-detected semantic path."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
folder=(root/'datasets/Shell_Defects_Training_20260913').resolve()
assert folder.is_relative_to(root.resolve())
assert json.loads((folder/'build-status.json').read_text())['state']=='packaged'
old=(folder/'masks').resolve();new=(folder/'instance_masks').resolve()
assert old.parent==folder and new.parent==folder
if old.exists():
    assert not new.exists()
    old.rename(new)
path=folder/'index.jsonl';temporary=folder/'index.updated.jsonl'
with path.open(encoding='utf-8') as src,temporary.open('w',encoding='utf-8') as out:
    for line in src:
        item=json.loads(line)
        for a in item['annotations']:
            if a['mask'].startswith('masks/'):a['mask']='instance_'+a['mask']
        out.write(json.dumps(item,separators=(',',':'))+'\n')
temporary.replace(path)
readme=folder/'README.md'
text=readme.read_text(encoding='utf-8').replace('in `masks/`','in `instance_masks/`')
text+='\nThe layout was checked against the [Ultralytics dataset loader](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/data/utils.py). Optional instance masks are stored separately from its automatic semantic-mask directory.\n'
readme.write_text(text,encoding='utf-8')
assert not old.exists() and new.exists()
print('INSTANCE_MASK_LAYOUT_READY',flush=True)
