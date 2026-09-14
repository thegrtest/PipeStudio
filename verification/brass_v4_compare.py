"""Matched-camera/material-only comparisons against the preserved V3 shader."""
from pathlib import Path
import sys,json,importlib.util
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as s
import brass_material as current
spec=importlib.util.spec_from_file_location('brass_v3_baseline',ROOT/'verification'/'brass-v4'/'baseline_material.py')
baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
s.register();scene=s.fresh_scene();s.setup_scene(scene)
out=ROOT/'verification'/'brass-v4'/'comparisons';out.mkdir(parents=True,exist_ok=True)
reports=[]
for env in ('machine','godslight'):
    values=json.loads((ROOT/'examples'/'realism-v3'/'metadata'/(env+'.json')).read_text())['parameters']
    for name,changes in [('v3',{}),('v4',dict(oxide_amount=.38,polish_amount=.42)),
                         ('v4_patched',dict(oxide_amount=.70,polish_amount=.65))]:
        s.update_brass=baseline.update_brass if name=='v3' else current.update_brass
        s.apply_settings(scene,{**values,**changes,'resolution':1120,'samples':96})
        info=s.export_frame(scene,out,env+'_'+name)
        info['comparison']=name;reports.append(info)
        print('BRASS_COMPARE',env,name,flush=True)
s.atomic_json(out/'manifest.json',{'classes':{'0':'Fold','1':'Dent'},'samples':reports})
