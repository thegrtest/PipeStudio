"""Check seeded recipes, save random-capture controls, and launch two short passes."""
from pathlib import Path
import json
import sys
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import rolling_capture as capture
import rolling_randomization as randomized
studio.register();scene=bpy.context.scene
config=scene.rolling_capture
config.randomize_defects=True;config.passes=3;config.random_seed=41000
config.body_dents=4;config.defect_strength=1.;config.twist_limit=12
p=studio.settings_dict(scene.pipe_studio)
options=capture.random_options(config);rigs=randomized.rigs_in(scene)
first=randomized.make_recipe(p,rigs,options,0)
assert first==randomized.make_recipe(p,rigs,options,0)
assert first['items']!=randomized.make_recipe(p,rigs,options,1)['items']
assert first['split_group']==randomized.make_recipe({**p,'resolution':640,'samples':8},rigs,options,0)['split_group']
classes=set()
for pass_index in range(16):
    spec=randomized.make_recipe(p,rigs,options,pass_index)
    for offset in range(0,len(spec['items'])-5,6):
        group=spec['items'][offset:offset+6]
        assert sum(bool(item['defect'] and item['defect']['kind']=='plastic_dent' and item['defect']['region']=='BODY') for item in group)==4
    for defect in spec['defects']:
        classes.add(defect['kind'])
        if defect['kind']=='body_twist':assert abs(defect['twist_degrees'])<=12
assert {'plastic_dent','metal_dent','metal_scratch','plastic_scratch','body_twist','open_center','protruding_crimp'}<=classes
studio.atomic_json(root/'verification/random-rolling-recipes.json',dict(passed=True,
    deterministic=True,new_recipes_each_pass=True,body_dents_per_six=4,twist_limit=12,classes=sorted(classes),tested_passes=16))
studio.save_blend(root/'examples/rolling-shells/Rolling shell capture.blend')
config.passes=2;config.start=1;config.end=25;config.step=24;config.camera='ALL'
config.trigger='ALL';config.resolution=800;config.samples=12
folder=capture.launch(scene)
studio.atomic_json(root/'examples/rolling-shells/random-capture-example.json',dict(folder=str(folder),
    pid=capture.ACTIVE['process'].pid,images=12,passes=2))
# Keep practical capture defaults in the editable workspace.
config.passes=3;config.end=144;config.step=12;config.camera='CURRENT'
config.trigger='DEFECT';config.resolution=1200;config.samples=32
studio.save_blend(root/'examples/rolling-shells/Rolling shell capture.blend')
print('RANDOM_ROLLING_CAPTURE_STARTED',folder,flush=True)
