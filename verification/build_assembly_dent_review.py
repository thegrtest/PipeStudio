"""Render a small/shallow dent review with native images and real label export."""
import argparse
import copy
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from assembly_plan import make_specimen,capture_pose,DEFECT_CLASSES,PART_CLASSES
from assembly_scene import build_scene,make_assembly,pose_scene
from assembly_generate import export_row,write_schema,finalize
from domain_render import atomic_json,file_hash
from pipe_studio import save_blend

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--draft',action='store_true')
p.add_argument('--look',default='REFINED',choices=('REFINED','CAMERA_MATCHED'))
p.add_argument('--frame',type=int,default=1,choices=(0,1,2))
p.add_argument('--coverage',action='store_true',help='Include two moving frames and paired alternate lights on the good specimen')
args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
if (out/'plan.json').exists():raise RuntimeError('Use a fresh review folder.')
wanted={'small_circular':3,'shallow_circular':2,'large_varied':1};recipes=[]
for seed in range(361000,361100):
    r=make_specimen(seed,'dent',look=args.look,allowed_defects=('dent',));family=r['instances'][0]['dent_family']
    if wanted[family]:recipes.append(r);wanted[family]-=1
    if not any(wanted.values()):break
recipes += [make_specimen(362001,'deformity',look=args.look,allowed_defects=('deformity',)),make_specimen(362002,'good',look=args.look)]
if args.draft:recipes=recipes[:1]
rows=[]
for recipe in recipes:
    companion=make_specimen(recipe['seed']+100000,'good',look=args.look)
    rows.append(dict(sample_id=recipe['specimen_id']+f'_f{args.frame:03d}',split_group=recipe['specimen_id'],recipe=recipe,companions=[companion],pose=capture_pose(recipe,args.frame)))
if args.coverage and not args.draft:
    for index in (0,2):
        row=copy.deepcopy(rows[0]);row['sample_id']=row['recipe']['specimen_id']+f'_f{index:03d}'
        row['pose']=capture_pose(row['recipe'],index);rows.append(row)
    for lighting in ('CURRENT','FOUR_LINES'):
        row=copy.deepcopy(rows[7]);row['sample_id']+='_'+lighting.lower()
        for r in [row['recipe']]+row['companions']:r['lighting']=lighting
        rows.append(row)
plan=dict(settings=dict(review=True,samples=96,renderer_sha256={name:file_hash(ROOT/name) for name in ('assembly_plan.py','assembly_dents.py','assembly_environment_detail.py','assembly_geometry.py','assembly_scene.py','assembly_realism.py','assembly_camera_match.py','assembly_finish.py','assembly_generate.py')}),rows=rows)
atomic_json(out/'plan.json',plan)
if not args.draft:write_schema(out,DEFECT_CLASSES);write_schema(out/'tracking',PART_CLASSES)
for row in rows:
    scene,rig,body=build_scene(row['recipe'],48 if args.draft else 96)
    companions=[(*make_assembly(scene,r),r) for r in row['companions']]
    if args.draft:
        pose_scene(scene,rig,body,row['recipe'],row['pose'])
        from assembly_realism import companion_offset
        for cr,cb,recipe in companions:
            t=companion_offset(recipe);pose_scene(scene,cr,cb,recipe,dict(travel=t,roll=recipe['initial_roll']+t/recipe['base']['radius']))
        scene.render.filepath=str(out/'draft.png');bpy.ops.render.render(write_still=True)
    else:export_row(scene,rig,body,row,out,1,companions)
    print('DENT_REVIEW',row['sample_id'],flush=True)
save_blend(str(out/'assembly_track.blend'))
if not args.draft:finalize(out,plan);atomic_json(out/'status.json',dict(state='complete',completed=len(rows),total=len(rows)))
