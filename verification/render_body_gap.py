"""Bounded native previews of the inverted-camera body-gap recipe."""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from body_gap_plan import make_plan
from domain_render import atomic_json,render_sample


def preview_plan(seed):
    plan=make_plan(3200,seed=seed)
    candidates=plan['samples']; selected=[]; used=set()
    def take(predicate):
        row=next(r for r in candidates if r['sample_id'] not in used and predicate(r))
        used.add(row['sample_id']); selected.append(deepcopy(row))
    for kind in ('DENT','FOLD'):
        for size in ('small','medium','large'):
            for finish in ('clean','dirty'):
                take(lambda r:r['primary_kind']==kind and r['size_bin']==size and r['gap_targeted']
                     and len(r['instances'])==1 and r['surface_condition']==finish)
    for count in (2,3):
        for kind in ('FOLD','DENT'):
            take(lambda r:len(r['instances'])==count and r['primary_kind']==kind and r['gap_targeted'])
    for kind in ('FOLD','DENT'):
        take(lambda r:r['primary_kind']==kind and not r['gap_targeted'])
    for row in selected: row['split']='test'
    plan.update(samples=selected,preview=True,
        expected_primary_counts=dict(Counter(r['primary_kind'] for r in selected)),
        expected_instance_counts=dict(Counter(i['kind'] for r in selected for i in r['instances'])),
        expected_setup_counts={'INVERTED':len(selected)})
    return plan


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    p.add_argument('--seed',type=int,default=923171000)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    plan=preview_plan(args.seed);atomic_json(out/'render_plan.json',plan)
    (out/'REVIEW_ONLY.txt').write_text('Development previews only. Not production training/holdout data.\n')
    import pipe_studio as studio
    from fast_pipeline import install
    install(studio);studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
    records=[]
    for row in plan['samples']:
        started=time.perf_counter()
        record=render_sample(studio,scene,row,out/'all')
        record['generation_seconds']=round(time.perf_counter()-started,3);records.append(record)
        atomic_json(out/'all/manifest.json',dict(classes=plan['classes'],samples=records))
        print('BODY_GAP_PREVIEW',len(records),len(plan['samples']),row['primary_kind'],row['size_bin'],flush=True)
    print('BODY_GAP_PREVIEW_COMPLETE',flush=True)


if __name__=='__main__':main()
