"""Blender integration checks for transforms, environment visibility and masks."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as studio
from scene_presets import SCENE_PRESETS

studio.register(); scene=studio.fresh_scene(); studio.setup_scene(scene)
folder=ROOT/'verification'/'reference-scenes'
folder.mkdir(parents=True,exist_ok=True)
reports=[]
cases=[('machine_dent','MACHINE','DENT',180,True),('machine_clean','MACHINE','NONE',180,False),
       ('machine_hidden','MACHINE','DENT',0,False),('godslight_dent','GODSLIGHT','DENT',160,True)]
for name,environment,defect,angle,visible in cases:
    values={**SCENE_PRESETS[environment],'defect':defect,'angle':angle,'resolution':640,'samples':16}
    studio.apply_settings(scene,values)
    report=studio.export_frame(scene,folder,name); reports.append(report)
    assert bool(report['bbox_xywh'])==visible,(name,report['bbox_xywh'])
    assert report['height']==round(640/values['frame_aspect'])
    assert scene.view_settings.view_transform=='Standard'
    assert bpy.data.objects['PS_Floor'].hide_render
    if environment=='MACHINE':
        assert abs(studio.visible_angle(scene)-180)<.01
    for obj in bpy.data.collections['PS_Studio'].objects:
        if obj.name.startswith('PS_EnvMachine_'):
            assert obj.hide_render==(environment!='MACHINE')
        elif obj.name.startswith('PS_EnvGods_'):
            assert obj.hide_render==(environment!='GODSLIGHT')
studio.apply_settings(scene,SCENE_PRESETS['STUDIO'])
assert abs(bpy.data.objects['PS_Pipe'].rotation_euler.y)<.001
assert not bpy.data.objects['PS_Floor'].hide_render
assert scene.view_settings.view_transform=='AgX'
studio.atomic_json(folder/'result.json',{'passed':True,'samples':reports})
print('REFERENCE_CHECKS_PASSED',flush=True)
