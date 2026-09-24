"""CPU-only development review; never interrupts fleet jobs or desktop training."""
import argparse
from collections import Counter
from copy import deepcopy
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def preview_plan():
    from body_gap_plan import make_plan
    from app_model import front_angle
    plan=make_plan(320,seed=923800000);rows=plan['samples'];selected=[];used=set()
    def take(kind,size,style=None,count=1):
        choices=[r for r in rows if r['primary_kind']==kind and r['size_bin']==size
                 and len(r['instances'])==count and r['sample_id'] not in used]
        row=deepcopy(next((r for r in choices if r['gap_targeted']),choices[0]))
        used.add(row['sample_id'])
        if style:row['instances'][0]['spec']['defect_style']=style
        row['review_scenario']=f'{size} {kind.lower()} / '+row['instances'][0]['spec']['defect_style']
        row['keep_visibility_controls']=True;row['split']='review'
        row['settings']['samples']=48;selected.append(row)
        return row
    a=take('DENT','small','DEFAULT');a['review_scenario']='Small round dent in body shadow'
    a['instances'][0]['spec'].update(position=.66,angle=front_angle(a['settings'])-8,depth=.026)
    a=take('DENT','small','DOUBLE');a['review_scenario']='Paired small dimples above shoulder'
    a['instances'][0]['spec'].update(position=.73,angle=front_angle(a['settings'])+12,depth=.040)
    take('DENT','medium','ELONGATED')
    a=take('DENT','medium','SHALLOW_SWEEP');a['review_scenario']='Broad shallow dent visibility challenge'
    a['instances'][0]['spec'].update(width=.07,arc=16,depth=.008,angle=front_angle(a['settings']),position=.63)
    take('FOLD','small','BODY_BUCKLE')
    a=take('FOLD','large','WRINKLED');a['review_scenario']='Larger uneven shoulder buckle (closed surface)'
    a['instances'][0]['spec'].update(position=a['settings']['taper_start']+.025,
                                   depth=.22,width=.045,arc=35,angle=front_angle(a['settings'])+15)
    take('DENT','medium',count=2)
    take('FOLD','medium',count=3)
    for source in selected[:2]:
        row=deepcopy(source);row['sample_id']+='_clean';row['specimen_id']=row['sample_id']
        row.update(instances=[],primary_kind='NONE',review_scenario='Clean negative control / same nuisance recipe')
        row['settings'].update(defect='NONE',depth=0);selected.append(row)
    plan['samples']=selected;plan['preview']=True
    plan['expected_primary_counts']=dict(Counter(r['primary_kind'] for r in selected))
    plan['expected_instance_counts']=dict(Counter(i['kind'] for r in selected for i in r['instances']))
    plan['expected_setup_counts']={'INVERTED':len(selected)}
    plan['generation_policy']=dict(defects_only=False,allowed_defects=['FOLD','DENT'])
    plan['ratio_definition']='Curated development cases including matched clean negatives; production ratios are separate.'
    return plan


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
    p.add_argument('--indices',type=int,nargs='+');p.add_argument('--samples',type=int,default=48)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    import pipe_studio as studio
    from domain_render import atomic_json,render_sample
    from defect_visibility import VisibilityRejected
    configure=studio.configure_renderer
    def cpu_preview(scene):
        configure(scene);scene.cycles.device='CPU';scene.cycles.denoising_use_gpu=False
        scene.render.compositor_device='CPU';scene.cycles.adaptive_threshold=.02
        scene['pipe_device']='CPU preview; desktop GPU reserved'
        scene.cycles.use_animated_seed=False
    studio.configure_renderer=cpu_preview
    studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    plan=preview_plan()
    from generate_domain_dataset import source_signature
    plan['renderer_sources']=source_signature()
    for row in plan['samples']:row['settings']['samples']=args.samples
    plan['selected_indices']=args.indices if args.indices is not None else list(range(len(plan['samples'])))
    atomic_json(out/'render_plan.json',plan)
    (out/'REVIEW_ONLY.txt').write_text('Synthetic development review. Real photos are references only. No training accuracy claim.\n')
    records=[];rejected=[]
    for index in (args.indices if args.indices is not None else range(len(plan['samples']))):
        row=plan['samples'][index];start=time.perf_counter()
        try:
            record=render_sample(studio,scene,row,out/'all')
            # Exercise idempotence in a real Blender scene: repeated absolute
            # nuisance application may not walk fixtures or compound colors.
            import bpy
            from capture_variation import apply_variation
            def snapshot():
                locations={o.name:tuple(o.location) for o in scene.objects if o.name.startswith('PS_Capture_Inverse')}
                colors={m.name:tuple(tuple(e.color) for n in m.node_tree.nodes if n.type=='VALTORGB' for e in n.color_ramp.elements)
                        for m in bpy.data.materials if m.name.startswith('PS_EnvMachine_Capture') and m.use_nodes}
                return locations,colors
            before=snapshot();apply_variation(scene,row.get('background_variation'));assert before==snapshot()
            record['generation_seconds']=round(time.perf_counter()-start,3);records.append(record)
        except VisibilityRejected as exc:
            rejected.append(dict(sample_id=row['sample_id'],review_scenario=row['review_scenario'],report=exc.report))
        atomic_json(out/'all/manifest.json',dict(classes=plan['classes'],samples=records,rejected=rejected))
        print('VISIBILITY_REVIEW_PROGRESS',index+1,len(plan['samples']),len(records),len(rejected),flush=True)
    (out/'all/classes.txt').write_text('Fold\nDent\nSoap stain\nOil stain\n')
    (out/'all/data.yaml').write_text('path: '+(out/'all').as_posix()+'\ntrain: images\nnames:\n  0: Fold\n  1: Dent\n  2: Soap stain\n  3: Oil stain\n')
    print('VISIBILITY_REVIEW_COMPLETE',flush=True)


if __name__=='__main__':main()
