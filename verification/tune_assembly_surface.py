"""Compare patch-scale interventions without changing generator defaults."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
import math
from assembly_plan import make_specimen,capture_pose
from assembly_scene import build_scene,pose_scene,PREFIX
from pipe_studio import aim

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
r=make_specimen(361000,'good');scene,rig,body=build_scene(r,128);pose_scene(scene,rig,body,r,capture_pose(r,1))
scene.render.use_border=True;scene.render.use_crop_to_border=False
scene.render.border_min_x=900/1920;scene.render.border_max_x=1160/1920
scene.render.border_min_y=1-845/1200;scene.render.border_max_y=1-695/1200
lights=[o for o in scene.objects if 'reflection_bar_index' in o]
oxide=bpy.data.objects[PREFIX+'Soft oxide fill'];oxide.visible_glossy=False
view=math.atan2(scene.camera.location.z-.62,scene.camera.location.y)
for o in lights:
 i=o['reflection_bar_index'];incoming=view-2*math.asin((.60,.28,-.02,-.32)[i])
 o.location=(0,math.cos(incoming)*110+r['environment']['light_shift'],.62+math.sin(incoming)*110);aim(o,(0,0,.62))
 o.data.energy=45000*r['environment']['light_scale']*r['environment']['bar_balance'][i]*(1.8,.30,.23,.17)[i]
n=body.data.materials[0].node_tree.nodes
steps=('lighting','grain','film')
for step in steps:
 if step in ('grain','film'):
  n['Inspection statistical grain multiplier'].inputs['To Min'].default_value=-.60
  n['Inspection statistical grain multiplier'].inputs['To Max'].default_value=2.60
  for shader in ('BrassShader','PolishedBrass','DullOxide'):n['Inspection measured grain '+shader].inputs[0].default_value=1
 if step=='film':
  n['Thin oxide film'].inputs[1].default_value=.60
  ramp=n['OxideColors'].color_ramp;ramp.elements[0].color=(.13,.095,.05,1);ramp.elements[1].color=(.32,.24,.13,1)
 scene.render.filepath=str(out/(step+'.png'));bpy.ops.render.render(write_still=True)
 print('SURFACE_STEP',step,flush=True)
