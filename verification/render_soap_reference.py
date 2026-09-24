"""Small CPU-only soap comparison batch; does not touch fleet jobs or datasets."""
import argparse
from collections import Counter
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def preview_plan():
    from app_model import DEFAULTS, front_angle, validate_settings
    from domain_plan import CLASSES, _instance
    from domain_profiles import camera_settings
    from scene_presets import SCENE_PRESETS
    from soap_residue import VERSION
    rows=[]
    scenarios=(('CAM7650','dried_island',3),('CAM5080','faint_film',1),
               ('CAM2534','coalesced_residue',2),('CAM7650','coalesced_residue',2),
               ('CAM5080','dried_island',2),('CAM2534','faint_film',3))
    for index,(camera,subtype,count) in enumerate(scenarios):
        seed=923600100+index
        settings={**DEFAULTS,**SCENE_PRESETS['GODSLIGHT'],
                  **camera_settings(camera,seed=seed,variation=.35,session='AUG19')}
        settings.update(seed=seed,product_mode='PIPE',defect='NONE',depth=0,
                        resolution=1936,frame_aspect=1936/1216,samples=32,
                        roughness=.49,oxide_amount=.44,texture_strength=.45,
                        finish_marks=.28,wear=.31,polish_amount=.26)
        # The supplied Aug13 dark-camera frames place the pipe ~200 px to
        # the left of the older Aug19 recipe; keep the same object scale.
        if camera=='CAM7650': settings['camera_shift_x']+=.105
        settings=validate_settings(settings)
        instances=[]
        positions={1:(.66,),2:(.48,.72),3:(.43,.64,.78)}[count]
        for j,position in enumerate(positions):
            size='small' if subtype=='faint_film' or j==0 and count==3 else 'medium'
            item=_instance(settings,'SOAP_STAIN',size,j,subtype=subtype)
            # Normalized half-extents give circular spots after accounting
            # for the pipe length/radius, with larger connected spill marks.
            radius=(.010+.002*j) if size=='small' else (.031+.002*j)
            item['spot'].update(position=position,angle=(front_angle(settings)+(-27,4,-23)[j])%360,
                                axial_size=radius,angular_size=radius*settings['length']/settings['radius']*57.2958,
                                rotation=(-12,20,7)[j])
            item.update(region='body')
            instances.append(item)
        stem=f'domain_{seed:010d}_{camera.lower()}_soap_reference'
        rows.append(dict(sample_id=stem,specimen_id=stem,split='review',setup=camera,
                         primary_kind='SOAP_STAIN',size_bin='mixed',surface_condition='handled',
                         lighting_regime='mild',settings=settings,instances=instances,
                         generation_revision=VERSION,reference_session='AUG12_AUG13',
                         synthetic_only=True))
    return dict(classes=CLASSES,samples=rows,preview=True,
                expected_instance_counts=dict(Counter(i['kind'] for r in rows for i in r['instances'])))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--indices',type=int,nargs='+',default=list(range(6)))
    p.add_argument('--samples',type=int,default=32)
    p.add_argument('--check-visibility',action='store_true')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    from domain_render import atomic_json,render_sample,render_beauty,stain_material,read_display_raster
    import bpy
    import numpy as np
    import pipe_studio as studio
    configure=studio.configure_renderer
    def cpu_preview(scene):
        configure(scene)
        scene.cycles.device='CPU';scene['pipe_device']='CPU preview (desktop GPU reserved)'
        scene.cycles.denoising_use_gpu=False
        scene.render.compositor_device='CPU'
        scene.cycles.adaptive_threshold=.035
    studio.configure_renderer=cpu_preview
    studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
    folder=args.output.resolve();folder.mkdir(parents=True,exist_ok=True)
    plan=preview_plan()
    for row in plan['samples']:row['settings']['samples']=args.samples
    atomic_json(folder/'render_plan.json',plan)
    (folder/'REVIEW_ONLY.txt').write_text('Synthetic development previews; do not add to held-out real evaluation.\n')
    records=[]
    for index in args.indices:
        row=plan['samples'][index];start=time.perf_counter()
        record=render_sample(studio,scene,row,folder/'all')
        coat_nodes=[n for n in bpy.data.materials['PS_Brass'].node_tree.nodes if n.name=='DomainStain_Coat']
        assert len(coat_nodes)==1, 'Multiple residue BSDFs can exceed the brass closure budget.'
        if args.check_visibility and index in (0,1,2):
            # Same scene/camera/finish/noise seed, but no soap: isolates the
            # mark's actual RGB effect from unrelated brass texture and glare.
            controls=folder/'controls';controls.mkdir(exist_ok=True)
            clean=controls/(row['sample_id']+'_without_soap.png')
            stain_material(bpy.data.materials['PS_Brass'],[])
            for name,watts in record['glare_guard']['actual_lights_watts'].items():
                bpy.data.objects[name].data.energy=watts
            scene.view_settings.exposure=record['glare_guard']['actual_exposure']
            render_beauty(scene,clean)
            beauty=read_display_raster(folder/'all'/record['image'])
            control=read_display_raster(clean)
            delta=np.mean(np.abs(beauty-control),axis=2)*255
            checks=[]
            for annotation in record['instances']:
                mask=read_display_raster(folder/'all'/annotation['mask'])[:,:,0]>.5
                checks.append(dict(instance_id=annotation['instance_id'],
                    mean_rgb_change_8bit=round(float(delta[mask].mean()),3),
                    fraction_changed_over_3_codes=round(float((delta[mask]>3).mean()),4)))
            atomic_json(controls/(row['sample_id']+'_visibility.json'),dict(same_seed_control=True,instances=checks))
        record['generation_seconds']=round(time.perf_counter()-start,3)
        records.append(record)
        atomic_json(folder/'all/manifest.json',dict(classes=plan['classes'],samples=records))
        print('SOAP_PREVIEW',index,row['sample_id'],record['generation_seconds'],flush=True)
    (folder/'all/classes.txt').write_text('Fold\nDent\nSoap stain\nOil stain\n')
    (folder/'all/data.yaml').write_text('path: '+(folder/'all').as_posix()+'\ntrain: images\nnames:\n  0: Fold\n  1: Dent\n  2: Soap stain\n  3: Oil stain\n')
    print('SOAP_PREVIEW_COMPLETE',flush=True)


if __name__=='__main__':main()
