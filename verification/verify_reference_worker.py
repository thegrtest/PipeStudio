from pathlib import Path
import sys,json
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
studio.register();scene=bpy.context.scene
studio.apply_settings(scene,{'resolution':480,'samples':8,'flashlight_camera':'REFERENCE','flashlight_capture':'CURRENT'})
for r in (.488,.492,.500,.507,.510):assert abs(track.brass_rim_face_height(r)+1.442)<1e-6
for obj in scene.objects:
    if obj.get('inspection_region')=='PLASTIC_FACE' and not obj.get('defect_id'):
        assert max(v.co.y for v in obj.data.vertices)<=track.PLASTIC_RIM_Y+1e-6
spec=json.loads(scene['flashlight_recipe'])
scene.pipe_studio.output_dir=str(root/'verification/reference-worker')
job=studio.launch_job(scene,False)
assert studio.ACTIVE_JOB['process'].wait(timeout=120)==0,(job/'render.log').read_text()[-3000:]
infos=json.loads((job/'manifest.json').read_text())['samples']
assert len(infos)==1 and infos[0]['camera_id']=='REFERENCE'
assert infos[0]['recipe']==spec
assert infos[0]['appearance_version']==4
assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in infos[0]['recipe']['defects'])==4
studio.atomic_json(root/'verification/reference-worker/result.json',dict(passed=True,job=str(job),
    reference_camera_exported=True,edited_recipe_preserved=True,flat_brass_lip=True,clean_crimp_flush=True))
print('REFERENCE_WORKER_VERIFIED',flush=True)
