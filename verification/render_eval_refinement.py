"""Bounded reference-sized render check; never starts or modifies a fleet job."""
import argparse
from copy import deepcopy
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_model import validate_settings
from domain_plan import make_plan,SETUPS
from eval_generation import fixture_parameters


def review_rows():
    plan=make_plan(seed=915210000,quality='full',preview=True,profile='yolox')
    rows=[]
    for setup in SETUPS:
        group=[r for r in plan['samples'] if r['setup']==setup]
        for style in ('SOFT_BUCKLE','SHALLOW_SWEEP'):
            row=deepcopy(next(r for r in group if r['instances'] and r['instances'][0].get('spec',{}).get('defect_style')==style and len(r['instances'])==1))
            row['settings']['samples']=48
            rows.append(row)
    # Same camera/body/finish under two moderate light directions. These are
    # review controls, not independent specimens to mix across train/val.
    fold=deepcopy(next(r for r in plan['samples'] if r['setup']=='CAM5080' and len(r['instances'])==1 and r['instances'][0].get('spec',{}).get('defect_style')=='AXIAL_PINCH'))
    for label,azimuth,fill in (('left',-9,.90),('right',9,1.10)):
        row=deepcopy(fold);row['sample_id']+='_'+label
        row['pair_role']='lighting_variant';row['split']='development'
        row['settings']=validate_settings({**row['settings'],'samples':48,
                                         'light_azimuth':row['settings']['light_azimuth']+azimuth,
                                         'fill_power':row['settings']['fill_power']*fill})
        rows.append(row)
    for setup in ('CAM2534','MACHINE'):
        row=deepcopy(next(r for r in plan['samples'] if r['setup']==setup and r['primary_kind']=='NONE'))
        row['reflection_context']='reflective';row['fixture_parameters']=fixture_parameters(row['settings']['seed'],'reflective')
        row['settings']['samples']=48
        rows.append(row)
    row=deepcopy(next(r for r in plan['samples'] if r['setup']=='CAM7650' and len(r['instances'])==3))
    row['settings']['samples']=48;rows.append(row)
    return rows


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'verification/eval_refinement')
    parser.add_argument('--limit',type=int,default=100)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    import bpy
    import pipe_studio as studio
    from domain_render import render_sample,atomic_json
    from fast_pipeline import install
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'REVIEW_ONLY.txt').write_text('Generator development previews, including repeated lighting controls. Keep out of training/evaluation bundles.\n')
    rows=review_rows()
    atomic_json(args.output/'review_plan.json',dict(samples=rows,purpose='Bounded review, not a production dataset'))
    install(studio);studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
    records=[]
    for row in rows[:args.limit]:
        started=time.perf_counter()
        try:
            record=render_sample(studio,scene,row,args.output/'all')
            record['seconds']=round(time.perf_counter()-started,2)
            records.append(record)
            atomic_json(args.output/'results.json',records)
            print('EVAL_REFINEMENT',len(records),row['setup'],row['sample_id'],record['seconds'],flush=True)
        except Exception as exc:
            atomic_json(args.output/'failure.json',dict(sample_id=row['sample_id'],error=repr(exc)))
            raise
    print('EVAL_REFINEMENT_COMPLETE',len(records),flush=True)


if __name__=='__main__':main()
