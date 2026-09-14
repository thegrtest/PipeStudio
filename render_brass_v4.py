"""Reference-sized material samples and the updated native workspace."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as s
from scene_presets import SCENE_PRESETS
from brass_finishes import finish_settings
from lighting_profiles import lighting_settings
s.register();scene=s.fresh_scene();s.setup_scene(scene)
folder=ROOT/'examples'/'brass-v4';folder.mkdir(parents=True,exist_ok=True)
append_satin='--satin-only' in sys.argv
reports=json.loads((folder/'manifest.json').read_text())['samples'] if append_satin else []
for env in ('MACHINE','GODSLIGHT'):
    variants=[('SATIN','REFERENCE')] if append_satin else [('REFERENCE','REFERENCE'),('DRAWN','REFERENCE'),('MOTTLED','REFERENCE'),('SATIN','REFERENCE'),('REFERENCE','RIGHT_RAKE')]
    for finish,lighting in variants:
        values={**SCENE_PRESETS[env],**finish_settings(env,finish),**lighting_settings(env,lighting)}
        s.apply_settings(scene,values)
        info=s.export_frame(scene,folder,env.lower()+'_'+finish.lower()+'_'+lighting.lower())
        info.update(sample_id=env.lower()+'_'+finish.lower()+'_'+lighting.lower(),
                    specimen_id=env.lower()+'_material_study',split='test',finish_recipe=finish,
                    lighting_profile=lighting,scenario_id=env.lower()+'_brass_surface')
        reports=[r for r in reports if r['sample_id']!=info['sample_id']]+[info]
        s.atomic_json(folder/'manifest.json',{'appearance_version':4,'calibrated':False,'classes':{'0':'Fold','1':'Dent'},'samples':reports,
            'purpose':'Brass surface review. Material varies within each specimen; this is not a lighting-only challenge.'})
        print('BRASS_V4_SAMPLE',info['sample_id'],flush=True)
s.apply_settings(scene,SCENE_PRESETS['MACHINE'])
scene.pipe_studio.last_export=str(folder)
scene['pipe_surface_notes']='Brass surface V4: active anisotropy, exposed brass / oxide patches, burnished tracks and cut rims.'
s.arrange_view()
for relative in s.REFERENCE_PATHS.values():
    ref=bpy.data.images.load(str(ROOT/relative),check_existing=True);ref.pack()
s.save_blend(folder/'Brass Surface V4.blend')
s.atomic_json(folder/'status.json',{'state':'complete','completed':len(reports),'total':len(reports),
    'last_image':str(folder/reports[0]['image'])})
print('BRASS_V4_READY '+str(folder),flush=True)
