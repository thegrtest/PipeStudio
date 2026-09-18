"""Blender: paired, labeled 1920x1200 lighting comparison on fixed specimens."""
import json
from pathlib import Path
import sys
import argparse

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from assembly_plan import make_plan,DEFECT_CLASSES,PART_CLASSES
from assembly_scene import build_scene,make_assembly
from assembly_generate import export_row,write_schema,finalize
from domain_render import atomic_json,file_hash
from pipe_studio import save_blend

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,default=ROOT/'verification'/'assembly_realism_v2_final')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.output.resolve()
OUT.mkdir(parents=True,exist_ok=True)
for lighting in ('CURRENT','BALANCED','FOUR_LINES'):
    folder=OUT/lighting.lower();folder.mkdir(exist_ok=True)
    rows=[make_plan(15,260915,'REFINED',lighting)[i] for i in (1,4,10)]
    plan=dict(settings=dict(review=True,lighting=lighting,look='REFINED',samples=96,
             renderer_sha256={n:file_hash(ROOT/n) for n in ('assembly_realism.py','assembly_scene.py','assembly_plan.py','assembly_generate.py')}),rows=rows)
    if (folder/'plan.json').exists():raise RuntimeError('Choose a fresh review directory; do not overwrite an earlier review.')
    atomic_json(folder/'plan.json',plan);write_schema(folder,DEFECT_CLASSES);write_schema(folder/'tracking',PART_CLASSES)
    for row in rows:
        scene,rig,body=build_scene(row['recipe'],96,1)
        companions=[(*make_assembly(scene,r),r) for r in row['companions']]
        export_row(scene,rig,body,row,folder,1,companions)
        print('REVIEW_FRAME',lighting,row['sample_id'],flush=True)
    save_blend(str(folder/'assembly_track.blend'));finalize(folder,plan)
    atomic_json(folder/'status.json',dict(state='complete',completed=len(rows),total=len(rows)))
