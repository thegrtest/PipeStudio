"""Check local geometry reuse, persistent edited recipes, and exact worker export."""
from pathlib import Path
import sys,json,time,statistics,math
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
studio.register();scene=bpy.context.scene
original_output=scene.pipe_studio.output_dir
folder=root/'examples'/'local-shell-updates';folder.mkdir(exist_ok=True)
started=time.perf_counter()
studio.apply_settings(scene,dict(defect='DENT',flashlight_layout='MIXED',flashlight_count=6,flashlight_index=0,
    flashlight_camera='FRONT_45',flashlight_capture='ALL',resolution=1200,samples=48,seed=42,depth=.12,width=.12))
full_seconds=time.perf_counter()-started
p=studio.settings_dict(scene.pipe_studio)
for count in range(2,13):
    for seed in range(10):
        spec=track.make_recipe({**p,'flashlight_count':count,'seed':seed})
        assert sum(bool(i['defect']) for i in spec['items'])>count/2
assert len(json.loads(scene['flashlight_recipe'])['defects'])==5
assert all(abs(track.brass_rim_face_height(r)+1.442)<1e-9 for r in (.490,.497,.505,.509))
before=track.export_views(scene,folder/'before','row',p)
track.write_region_dataset(folder/'before',before)
studio.atomic_json(folder/'before'/'manifest.json',dict(images=before,samples=before,classes=dict(enumerate(track.CLASSES))))
times=[];updates=[];demo=None
for step in range(8):
    old=json.loads(scene['flashlight_recipe'])
    next_index=old.get('next_shell_index',0)
    unchanged={o.name:(o.as_pointer(),o.data.as_pointer() if o.data else 0) for o in scene.objects
               if o.get('flashlight_id')!=next_index}
    world=scene.world.as_pointer();camera=scene.camera.as_pointer()
    assert bpy.ops.pipe.randomize()=={'FINISHED'}
    new=json.loads(scene['flashlight_recipe'])
    changed=[i for i,(a,b) in enumerate(zip(old['items'],new['items'])) if a!=b]
    assert changed==[next_index],changed
    assert scene.pipe_studio.seed==42
    for name,ptrs in unchanged.items():
        obj=scene.objects[name]
        assert (obj.as_pointer(),obj.data.as_pointer() if obj.data else 0)==ptrs,name
    assert scene.world.as_pointer()==world and scene.camera.as_pointer()==camera
    for index,item in enumerate(new['items']):
        regions=[o for o in scene.objects if o.get('inspection_region') and o.get('flashlight_id')==index]
        assert len(regions)==4
        for obj in regions:
            d=item['defect']
            assert obj['defect_id']==(d['id'] if d and d['region']==obj['inspection_region'] else 0)
    times.append(scene['button_row_last_update_seconds'])
    updates.append(dict(index=next_index,rebuilt_regions=scene['button_row_rebuilt_regions']))
    if step==0:
        demo=new
        after=track.export_views(scene,folder/'after','row',p)
        track.write_region_dataset(folder/'after',after)
        studio.atomic_json(folder/'after'/'manifest.json',dict(images=after,samples=after,classes=dict(enumerate(track.CLASSES))))
# Restore the first-click demonstration; appearance/camera changes retain edits.
button_row.remember(scene,p,demo)
studio.apply_settings(scene,dict(flashlight_camera='REAR_45',resolution=480,samples=8))
assert json.loads(scene['flashlight_recipe'])==demo
studio.apply_settings(scene,dict(flashlight_camera='FRONT_45'))
scene.pipe_studio.output_dir=str(folder/'worker')
job=studio.launch_job(scene,False)
assert studio.ACTIVE_JOB['process'].wait(timeout=180)==0,(job/'render.log').read_text()[-3000:]
results=json.loads((job/'manifest.json').read_text())['samples']
assert len(results)==3 and all(i['recipe']==demo for i in results),'Worker reset edited row'
assert statistics.median(times)<full_seconds
studio.apply_settings(scene,dict(resolution=1200,samples=48))
# Clean close-up isolates the planar lip without resetting the saved defect row.
saved=json.loads(scene['flashlight_recipe']);clean=json.loads(json.dumps(saved))
for item in clean['items']:item['defect']=None
clean['defects']=[]
button_row.remember(scene,studio.settings_dict(scene.pipe_studio),clean)
studio.refresh(scene,True)
r=scene.render;r.use_border=True;r.use_crop_to_border=True
r.border_min_x=.02;r.border_max_x=.205;r.border_min_y=0;r.border_max_y=.325
r.filepath=str(folder/'flat_lip.png');bpy.ops.render.render(write_still=True)
r.use_border=False;r.use_crop_to_border=False
button_row.remember(scene,studio.settings_dict(scene.pipe_studio),saved)
studio.refresh(scene,True)
scene.pipe_studio.output_dir=original_output
studio.arrange_view();studio.save_blend(root/'examples'/'button-track'/'Brass Button Track.blend')
studio.atomic_json(folder/'checks.json',dict(passed=True,initial_defective_shells=5,one_shell_per_click=True,
    unchanged_shells_and_environment_reused=True,updates=updates,full_rebuild_seconds=full_seconds,
    local_update_median_seconds=statistics.median(times),local_update_seconds=times,
    worker_preserved_edited_recipe=True,worker=str(job),flat_lip=True))
print('LOCAL_SHELL_UPDATES_VERIFIED',flush=True)
