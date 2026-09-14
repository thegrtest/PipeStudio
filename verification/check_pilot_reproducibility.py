from pathlib import Path
import sys,json
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from flashlight_capture import varied_settings
from app_model import validate_settings
folder=root/'exports/shell_defects_pilot_v1'
base=json.loads((folder/'generation_settings.json').read_text())['base_settings']
count=0
for path in (folder/'metadata').glob('pilot_*.json'):
    info=json.loads(path.read_text());row=int(path.stem.split('_')[1]);actual=info['parameters']
    p=varied_settings({**base,'product_mode':'FLASHLIGHT','environment':'BUTTON_TRACK',
        'seed':7300,'defect':'DENT','depth':.1,'flashlight_layout':'MIXED','flashlight_count':6,
        'flashlight_index':1,'flashlight_capture':'ALL','resolution':actual['resolution'],'samples':actual['samples']},row)
    p=validate_settings({**p,'seed':7300+row,'defect':'NONE' if row<3 else 'DENT'})
    assert p==actual,(path,{k:(p[k],actual.get(k)) for k in p if p[k]!=actual.get(k)})
    count+=1
print('PILOT_SETTINGS_REPRODUCIBLE',count)
