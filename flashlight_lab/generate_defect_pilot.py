"""Blender: generate a balanced 24-row/72-image exterior defect pilot.

Run with Blender --background <workspace.blend> --python this_file -- --output DIR.
Completed matching rows are reused on rerun. All views of a row share one split.
"""
from pathlib import Path
import argparse,json,sys,time
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
from app_model import validate_settings
from flashlight_capture import varied_settings

args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
parser=argparse.ArgumentParser()
parser.add_argument('--output',default=str(root/'exports/shell_defects_pilot_v1'))
parser.add_argument('--resolution',type=int,default=1024)
parser.add_argument('--samples',type=int,default=48)
opt=parser.parse_args(args)
folder=Path(opt.output).resolve();folder.mkdir(parents=True,exist_ok=True)
studio.register();scene=bpy.context.scene;base=studio.settings_dict(scene.pipe_studio)
configuration=folder/'generation_settings.json'
if configuration.exists():base=json.loads(configuration.read_text())['base_settings']
else:studio.atomic_json(configuration,dict(base_settings=base,rows=24,recipe_version=track.RECIPE_VERSION))
families=[('clean','NONE','BODY'),('plastic_dent','DENT','BODY'),('metal_dent','DENT','TOP'),
    ('metal_scratch','SCRATCH','TOP'),('plastic_scratch','SCRATCH','BODY'),
    ('open_center','OPEN_CENTER','PLASTIC_FACE'),('protruding_crimp','PROTRUDING_CRIMP','PLASTIC_FACE'),
    ('body_twist','TWIST','BODY')]
infos=[];started=time.perf_counter()
for family_index,(family,kind,region) in enumerate(families):
    for variant in range(3):
        row=family_index*3+variant;split='val' if variant==2 else 'train'
        p=varied_settings({**base,'product_mode':'FLASHLIGHT','environment':'BUTTON_TRACK',
            'seed':7300,'defect':'DENT','depth':.1,'flashlight_layout':'MIXED','flashlight_count':6,
            'flashlight_index':1,'flashlight_capture':'ALL','resolution':opt.resolution,'samples':opt.samples},row)
        p=validate_settings({**p,'seed':7300+row,'defect':'NONE' if kind=='NONE' else 'DENT'})
        spec=track.make_recipe(p)
        if kind!='NONE':
            primary={**p,'defect':kind,'flashlight_layout':'SINGLE','flashlight_index':1,'flashlight_region':region,
                'depth':(.012,.035,.09)[variant] if kind=='DENT' else (.07,.11,.16)[variant],
                'width':(.12,.14,.1)[variant],'position':(.36,.5,.62)[variant],'angle':90.,'arc':35.,
                'defect_style':('DEFAULT','ELONGATED','OBLIQUE')[variant],
                'body_twist':(8.,-35.,105.)[variant],'body_twist_span':.7,
                'crimp_opening':(.04,.13,.27)[variant],'crimp_lift':(.02,.07,.15)[variant]}
            spec['items'][1]['defect']=track.make_recipe(primary)['items'][1]['defect']
            spec['defects']=[item['defect'] for item in spec['items'] if item['defect']]
            assert len(spec['defects'])>len(spec['items'])/2
        spec.update(pilot_family=family,pilot_variant=variant,dataset_split=split)
        stem=f'pilot_{row:03}'
        paths=[folder/'metadata'/f'{stem}_{cam.lower()}.json' for cam in track.CAMERAS]
        cached=[json.loads(path.read_text()) for path in paths] if all(path.exists() for path in paths) else []
        def complete(info):
            required=[info['image'],info['mask']]
            required.extend(a['mask'] for a in info['annotations']+info['region_annotations'])
            required.extend(c['image'] for c in info.get('crops',[]))
            name=Path(info['image']).stem+'.txt'
            required.extend(['labels/'+name,'regions/labels/'+name])
            return all((folder/path).exists() for path in required)
        if cached and all(i['recipe']==spec and i['parameters']==p and complete(i) for i in cached):
            current=cached
        else:
            button_row.remember(scene,p,spec)
            studio.apply_settings(scene,p)
            assert json.loads(scene['flashlight_recipe'])==spec,'Settings round-trip reset the planned specimen'
            current=track.export_views(scene,folder,stem,p)
        for info,path in zip(current,paths):
            info['split']=split;info['pilot_family']=family;info['pilot_variant']=variant
            studio.atomic_json(path,info)
        if kind=='NONE':assert all(not i['annotations'] for i in current)
        else:
            expected=track.CLASSES.index(family)
            assert any(a['class_id']==expected and a['flashlight_id']==1 and a['visible_pixels'] for i in current for a in i['annotations'])
        infos.extend(current)
        studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=infos,samples=infos,
            calibrated=False,purpose='Pilot for pipeline verification and visual review; geometric severity is not a measured acceptance threshold.'))
        studio.atomic_json(folder/'status.json',dict(completed_rows=row+1,total_rows=24,images=len(infos),elapsed_seconds=time.perf_counter()-started))
        print(f'PILOT_ROW {row+1}/24 {family} variant={variant} split={split}',flush=True)
track.write_region_dataset(folder,infos)
for target,classes in [(folder,track.CLASSES),(folder/'regions',track.REGIONS)]:
    for split in ('train','val'):
        (target/f'{split}.txt').write_text(''.join('./'+i['image']+'\n' for i in infos if i['split']==split))
    (target/'dataset.yaml').write_text('path: '+target.as_posix()+'\ntrain: train.txt\nval: val.txt\nnames:\n'+''.join(f'  {i}: {json.dumps(n)}\n' for i,n in enumerate(classes)))
    (target/'classes.txt').write_text('\n'.join(classes)+'\n')
if json.loads(scene.get('flashlight_recipe','{}'))!=spec:
    button_row.remember(scene,p,spec);studio.apply_settings(scene,p)
studio.save_blend(folder/'last_scene.blend')
print('DEFECT_PILOT_COMPLETE',flush=True)
