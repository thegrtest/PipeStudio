"""Small native-resolution render regions for controlled surface ablations."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from assembly_plan import make_specimen,capture_pose
from assembly_scene import build_scene,pose_scene,PREFIX

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
p.add_argument('--detail',action='store_true')
p.add_argument('--baseline-only',action='store_true')
p.add_argument('--neutral-floor',action='store_true')
p.add_argument('--part-reflections-only',action='store_true')
p.add_argument('--full-frame',action='store_true')
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=True)
r=make_specimen(361000,'good');scene,rig,body=build_scene(r,96);pose_scene(scene,rig,body,r,capture_pose(r,1))
if args.neutral_floor:
    bpy.data.objects[PREFIX+'Teal bed'].visible_glossy=False
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.25
scene.render.use_border=not args.full_frame;scene.render.use_crop_to_border=False
scene.render.border_min_x=900/1920;scene.render.border_max_x=1160/1920
scene.render.border_min_y=1-845/1200;scene.render.border_max_y=1-695/1200
lights=[o for o in scene.objects if o.type=='LIGHT']
if args.part_reflections_only:
    for light in lights:
        if 'reflection_bar_index' in light:light.light_linking.receiver_collection=bpy.data.collections[scene['assembly_fill_receiver']]
visibility={o:o.visible_glossy for o in lights}
print('LIGHTS',[(o.name,o.data.energy,o.data.specular_factor,getattr(o,'visible_glossy',None)) for o in lights],flush=True)
for mode in (('baseline',) if args.baseline_only else (('bar0','bar1','bar2','bar3','oxide_noglossy','corrected') if args.detail else ('baseline','bars','rail','ambient','oxide'))):
    for o in lights:
        enabled=mode in ('baseline','corrected') or (mode=='bars' and 'reflection_bar_index' in o) or (mode.startswith('bar') and mode[-1].isdigit() and o.get('reflection_bar_index')==int(mode[-1])) or (mode=='rail' and o.name==PREFIX+'Rail bounce') or (mode=='ambient' and o.name==PREFIX+'Ambient fill') or (mode.startswith('oxide') and o.name==PREFIX+'Soft oxide fill')
        o.hide_render=not enabled
        o.visible_glossy=False if mode in ('oxide_noglossy','corrected') and o.name==PREFIX+'Soft oxide fill' else visibility[o]
    scene.render.filepath=str(args.output/(mode+'.png'));bpy.ops.render.render(write_still=True)
    print('SURFACE_PROBE',mode,flush=True)
