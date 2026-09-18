"""Command-line launcher and resumable Blender worker for the assembly track."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from assembly_plan import make_plan, DEFECT_CLASSES, PART_CLASSES, NATIVE_SIZE, VERSION, visible_box, yolo_line
from domain_render import atomic_json, file_hash


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'exports'/('assembly_track_'+datetime.now().strftime('%Y%m%d_%H%M%S')))
    p.add_argument('--count',type=int,default=15,help='Total frames; 15 frames cover all five primary conditions')
    p.add_argument('--seed',type=int,default=260915)
    p.add_argument('--look',choices=('ORIGINAL','REFINED','CAMERA_MATCHED'),default='CAMERA_MATCHED')
    p.add_argument('--lighting',choices=('CURRENT','FOUR_LINES','BALANCED'),default='BALANCED')
    p.add_argument('--defect-set',choices=('ALL','DENTS_FOLDS'),default='ALL',help='DENTS_FOLDS: 45%% dents, 45%% folds (deformity class), 10%% good')
    p.add_argument('--samples',type=int,default=96)
    p.add_argument('--scale',type=int,choices=(1,2),default=1,help='1 = native 1920x1200; 2 = 3840x2400')
    p.add_argument('--open',action='store_true',help='Open the editable Blender scene instead of exporting')
    p.add_argument('--resume',action='store_true',help='Resume the identical saved plan and clear its pause marker')
    p.add_argument('--beauty-only',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--fleet-plan',type=Path,help=argparse.SUPPRESS)
    p.add_argument('--chunk',type=int,default=0,help=argparse.SUPPRESS)
    p.add_argument('--verified-prefix',type=int,default=0,help=argparse.SUPPRESS)
    p.add_argument('--blender',default=os.environ.get('BLENDER_EXE',r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe'))
    return p


def write_schema(root,names):
    root.mkdir(parents=True,exist_ok=True)
    (root/'classes.txt').write_text('\n'.join(names)+'\n',encoding='utf-8')
    (root/'dataset.yaml').write_text('path: '+json.dumps(str(root.resolve()).replace('\\','/'))+'\n'
        +'train: train.txt\nval: val.txt\n# Entire specimen sequences stay in one split.\nnames:\n'
        +''.join(f'  {i}: {v}\n' for i,v in enumerate(names)),encoding='utf-8')


def split_rows(rows):
    groups=sorted({r['split_group'] for r in rows})
    ordered=sorted(groups,key=lambda s:hashlib.sha256(s.encode()).hexdigest())
    nval=max(1,round(len(groups)*.2)) if len(groups)>1 else 0
    val=set(ordered[:nval])
    return {'train':[r for r in rows if r['split_group'] not in val],
            'val':[r for r in rows if r['split_group'] in val]}


def finalize(root,plan):
    infos=[json.loads((root/'metadata'/(r['sample_id']+'.json')).read_text()) for r in plan['rows']]
    for name,rows in split_rows(plan['rows']).items():
        content=''.join('./all/images/'+r['sample_id']+'.png\n' for r in rows)
        for directory in (root,root/'tracking'):(directory/(name+'.txt')).write_text(content,encoding='utf-8')
    from collections import Counter
    summary=dict(frames=len(infos),resolution=[infos[0]['width'],infos[0]['height']],
        primary_conditions=dict(Counter(i['recipe']['condition'] for i in infos)),
        visible_defects=dict(Counter(a['name'] for i in infos for a in i['annotations'])),
        visible_parts=dict(Counter(a['name'] for i in infos for a in i['parts'])),
        unique_image_hashes=len({i['sha256'][i['image']] for i in infos}),
        note='Ratios describe primary conditions; mixed defects, hidden surfaces and cropped components alter visible annotation totals.')
    atomic_json(root/'summary.json',summary)
    if summary['unique_image_hashes']!=len(infos):raise ValueError('Duplicate beauty images detected')
    review(root)


def copy_or_link(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():target.unlink()
    try:os.link(source,target)
    except OSError:shutil.copy2(source,target)


def complete(root,row):
    path=root/'metadata'/(row['sample_id']+'.json')
    if not path.exists():return False
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        return data['sample_id']==row['sample_id'] and all((root/k).is_file() and file_hash(root/k)==v for k,v in data['sha256'].items())
    except (ValueError,KeyError,OSError):return False


def export_row(scene,rig,body,row,root,scale,companions=()):
    import bpy
    import numpy as np
    from assembly_scene import pose_scene,render_masks
    from domain_render import read_display_raster
    recipe=row['recipe'];stem=row['sample_id'];pose=dict(row['pose'])
    pose_scene(scene,rig,body,recipe,pose)
    objects=[(rig,body,recipe,pose)]
    for other_rig,other_body,other_recipe in companions:
        from assembly_realism import companion_offset
        travel=pose['travel']+companion_offset(other_recipe)
        other_pose=dict(pose,travel=travel,
                        roll=other_recipe['initial_roll']+travel/other_recipe['base']['radius'])
        pose_scene(scene,other_rig,other_body,other_recipe,other_pose)
        objects.append((other_rig,other_body,other_recipe,other_pose))
    scratch=root/'.staging'/stem;scratch.mkdir(parents=True,exist_ok=True)
    path=scratch/(stem+'.png')
    bpy.context.view_layer.update()
    from assembly_camera_match import sync_plate_view
    sync_plate_view(scene)
    scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    masks={};per_specimen=[]
    for obj_index,(_,obj_body,obj_recipe,obj_pose) in enumerate(objects):
        prefix=f'part{obj_index}_'
        measured=render_masks(scene,obj_body,obj_recipe,scratch,stem+'_'+prefix.rstrip('_'))
        masks.update({prefix+k:v for k,v in measured.items()})
        per_specimen.append((obj_recipe,obj_pose,prefix,measured))
    # Bound excessive clipping without moving defects or changing mask geometry.
    history=[]
    for attempt in range(4):
        rgb=read_display_raster(path);shell=np.logical_or.reduce([m for k,m in masks.items() if k.endswith('_shell')])
        clipped=(rgb.min(axis=2)>.975)
        fraction=float(clipped[shell].mean()) if shell.any() else 0.0
        defect_fraction=max([float(clipped[m].mean()) for k,m in masks.items() if '_defect_' in k and m.any()]+[0.0])
        history.append(dict(exposure=float(scene.view_settings.exposure),shell_clipped=fraction,defect_clipped=defect_fraction))
        if fraction<=.035 and defect_fraction<=.12:break
        if attempt==3:raise ValueError('Specimen remains overexposed after bounded corrections: '+stem)
        scene.view_settings.exposure-=.4;sync_plate_view(scene);scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    # Subtle camera noise is applied to beauty only and varies per capture.
    image=bpy.data.images.load(str(path),check_existing=False)
    try:
        pixels=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(pixels)
        rgba=pixels.reshape(-1,4)
        rng=np.random.default_rng(recipe['seed']*101+pose['frame_index'])
        noise=rng.normal(0,recipe['environment']['noise'],rgba[:,:3].shape)*np.sqrt(np.maximum(rgba[:,:3],.015))
        if scene.get('assembly_background_source'):
            foreground=np.logical_or.reduce([m for k,m in masks.items() if k.endswith(('_shell','_ferrule'))])
            noise*=foreground[::-1].reshape(-1,1)
        rgba[:,:3]=np.clip(rgba[:,:3]+noise,0,1)
        image.pixels.foreach_set(rgba.ravel());image.filepath_raw=str(path);image.file_format='PNG';image.save()
    finally:bpy.data.images.remove(image)
    width,height=NATIVE_SIZE[0]*scale,NATIVE_SIZE[1]*scale
    annotations=[];part_annotations=[];hidden=[]
    for obj_recipe,obj_pose,prefix,measured in per_specimen:
        for i,item in enumerate(obj_recipe['instances']):
            binary=measured[f'defect_{i}'];box=visible_box(binary,minimum=1)
            if box is None:hidden.append(f"{obj_recipe['specimen_id']}:{item['instance_id']}");continue
            annotations.append(dict(class_id=item['class_id'],name=item['kind'],instance_id=item['instance_id'],bbox_xywh=box,
                visible_pixels=int(binary.sum()),specimen_id=obj_recipe['specimen_id'],mask=f'masks/{stem}_{prefix}defect_{i}.png',
                track_id=f"{obj_recipe['specimen_id']}:defect:{item['instance_id']}"))
        for i,name in enumerate(PART_CLASSES):
            box=visible_box(measured[name],minimum=1)
            if box is None:continue  # Component can be fully outside the frame.
            part_annotations.append(dict(class_id=i,name=name,bbox_xywh=box,visible_pixels=int(measured[name].sum()),
                specimen_id=obj_recipe['specimen_id'],mask=f'masks/{stem}_{prefix}{name}.png',track_id=f"{obj_recipe['specimen_id']}:{name}"))
    if not part_annotations:raise ValueError('No assembly parts visible in frame')
    relative_image=Path('all/images')/(stem+'.png')
    target=root/relative_image;target.parent.mkdir(parents=True,exist_ok=True);os.replace(path,target)
    copy_or_link(target,root/'tracking'/relative_image)
    for sub,values in (('all/labels',annotations),('tracking/all/labels',part_annotations)):
        p=root/sub/(stem+'.txt');p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(''.join(yolo_line(a['class_id'],a['bbox_xywh'],width,height)+'\n' for a in values),encoding='utf-8')
    for name in masks:
        source=scratch/f'{stem}_{name}.png';dest=root/'masks'/source.name;dest.parent.mkdir(parents=True,exist_ok=True);os.replace(source,dest)
    files=[relative_image,Path('tracking')/relative_image,Path('all/labels')/(stem+'.txt'),Path('tracking/all/labels')/(stem+'.txt')]
    info=dict(sample_id=stem,version=VERSION,split_group=row['split_group'],width=width,height=height,
              image=relative_image.as_posix(),pose=pose,recipe=recipe,annotations=annotations,parts=part_annotations,
              specimens=[dict(recipe=r,pose=p) for r,p,_,_ in per_specimen],
              hidden_defects=hidden,glare_checks=history,
              mask_convention='Visible geometric support; opaque fixtures occlude; clear guide transmits. No reflection ghost labels.',
              sha256={p.as_posix():file_hash(root/p) for p in files})
    if scene.get('assembly_background_source'):
        source=Path(scene['assembly_background_source'])
        info['background']=dict(mode=scene['assembly_background_mode'],source=str(source),sha256=file_hash(source))
        info['camera']=dict(elevation_deg=float(scene['assembly_camera_elevation_deg']),fit=scene['assembly_camera_fit'])
        material=body.data.materials[0]
        if material.get('assembly_finish_parameters'):
            info['surface_finish']=json.loads(material['assembly_finish_parameters'])
    atomic_json(root/'metadata'/(stem+'.json'),info)
    scratch.rmdir()
    return info


def review(root):
    import html
    rows=[]
    for path in sorted((root/'metadata').glob('*.json')):
        info=json.loads(path.read_text(encoding='utf-8'))
        boxes=[]
        for a in info['parts']+info['annotations']:
            x,y,w,h=a['bbox_xywh'];color='#54ccff' if a in info['parts'] else '#ff7659'
            boxes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{color}" stroke-width="1.5"/><text x="{x}" y="{max(12,y-4)}" fill="{color}" font-size="12">{a["name"]}</text>')
        rows.append(f'<article><div class="frame"><img src="{info["image"]}"><svg viewBox="0 0 {info["width"]} {info["height"]}">{"".join(boxes)}</svg></div><p>{html.escape(info["sample_id"])} · {info["recipe"]["condition"]} · {len(info["annotations"])} visible defects</p></article>')
    (root/'index.html').write_text('''<!doctype html><meta charset="utf-8"><title>Assembly track · Pipe Studio</title>
<style>body{background:#101719;color:#e2e7e6;font:15px system-ui;margin:28px}h1{font-size:27px}p{color:#a9b6b7}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(450px,1fr));gap:20px}article{background:#1b2529;padding:12px;border-radius:10px}img{width:100%;display:block}.frame{position:relative}svg{position:absolute;inset:0;width:100%;height:100%}.hide svg{display:none}button{padding:10px;margin-bottom:20px;cursor:pointer}</style>
<h1>Inert assembly · Four-bar inspection track</h1><p>Native 1920 × 1200 framing. Procedural brass, copper insert, clear guide and four physical reflection bars. Blue: component tracking. Coral: visible surface defects.</p>
<button onclick="document.body.classList.toggle('hide')">Show / hide labels</button><div class="grid">'''+''.join(rows)+'</div>',encoding='utf-8')


def render_settings(args):
    source_files=('assembly_plan.py','assembly_geometry.py','assembly_scene.py','assembly_generate.py','assembly_realism.py','assembly_dents.py','assembly_environment_detail.py','assembly_camera_match.py','assembly_finish.py',
                  'geometry.py','domain_geometry.py','brass_material.py','brass_realism.py','brass_spectrum.py','brass_microdetail.py',
                  'camera_response.py','reference_brass_spectrum.json')
    if args.look=='CAMERA_MATCHED':
        from assembly_camera_match import PLATES
        source_files+=tuple('assets/assembly_cam3936/'+name for name in PLATES)+('assets/assembly_cam3936/provenance.json',)
    return dict(version=VERSION,count=args.count,seed=args.seed,samples=args.samples,scale=args.scale,look=args.look,lighting=args.lighting,defect_set=args.defect_set,
                   renderer_sha256={name:file_hash(ROOT/name) for name in source_files})


def _worker(args):
    import bpy
    from assembly_scene import build_scene,pose_scene,make_assembly
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    requested=render_settings(args)
    plan_path=root/'plan.json'
    if args.fleet_plan:
        plan=json.loads(args.fleet_plan.read_text(encoding='utf-8'))
        if plan['settings']!=requested or len(plan['rows'])!=args.count:
            raise ValueError('Fleet plan settings or renderer differ')
        if plan_path.exists() and json.loads(plan_path.read_text(encoding='utf-8'))!=plan:
            raise ValueError('Saved fleet plan changed')
        if not 0 <= args.verified_prefix <= len(plan['rows']):raise ValueError('Invalid verified prefix')
        if not plan_path.exists():atomic_json(plan_path,plan)
    elif plan_path.exists():
        if not args.resume and not args.open:raise ValueError('Output already has a plan. Use --resume or a new output folder.')
        plan=json.loads(plan_path.read_text(encoding='utf-8'))
        if plan['settings']!=requested:raise ValueError('Existing output has a different plan. Choose a new output folder.')
    else:
        plan=dict(settings=requested,rows=make_plan(args.count,args.seed,args.look,args.lighting,args.defect_set));atomic_json(plan_path,plan)
    if args.open:
        row=plan['rows'][0];scene,rig,body=build_scene(row['recipe'],args.samples,args.scale)
        pose_scene(scene,rig,body,row['recipe'],row['pose'])
        import assembly_ui
        assembly_ui.register(root,row['recipe'])
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=='VIEW_3D':
                    space=area.spaces.active
                    space.region_3d.view_perspective='CAMERA';space.show_region_ui=True
                    space.shading.type='MATERIAL';space.shading.use_scene_lights=True;space.shading.use_scene_world=True
        return
    write_schema(root,DEFECT_CLASSES);write_schema(root/'tracking',PART_CLASSES)
    cached=None;scene=rig=body=None;companions=[];rendered=0
    try:
        for index,row in enumerate(plan['rows']):
            if (root/'STOP').exists() or (args.fleet_plan and (root/'cancel.flag').exists()):
                atomic_json(root/'status.json',dict(state='paused',completed=sum(complete(root,r) for r in plan['rows']),total=args.count));return
            if args.fleet_plan and index < args.verified_prefix:continue
            if complete(root,row):continue
            recipe=row['recipe']
            if cached != recipe['seed']:
                scene,rig,body=build_scene(recipe,args.samples,args.scale);cached=recipe['seed']
                companions=[(*make_assembly(scene,r),r) for r in row.get('companions',[])]
            scene.view_settings.exposure=recipe['environment']['exposure']
            if args.beauty_only:
                pose_scene(scene,rig,body,recipe,row['pose'])
                for other_rig,other_body,other_recipe in companions:
                    from assembly_realism import companion_offset
                    travel=row['pose']['travel']+companion_offset(other_recipe)
                    p=dict(row['pose'],travel=travel,roll=other_recipe['initial_roll']+travel/other_recipe['base']['radius'])
                    pose_scene(scene,other_rig,other_body,other_recipe,p)
                scene.render.filepath=str(root/(row['sample_id']+'.png'));bpy.ops.render.render(write_still=True)
                from pipe_studio import save_blend
                save_blend(str(root/'assembly_track.blend'));return
            export_row(scene,rig,body,row,root,args.scale,companions)
            atomic_json(root/'status.json',dict(state='running',completed=index+1,total=args.count,last_sample=row['sample_id']))
            if args.fleet_plan:
                atomic_json(root/'progress.json',dict(state='running',completed=index+1,total=args.count,
                    last_image=str(root/'all/images'/(row['sample_id']+'.png'))))
            print(f'ASSEMBLY_PROGRESS {index+1}/{args.count}',flush=True)
            rendered+=1
            if args.chunk and rendered>=args.chunk:return
        from pipe_studio import save_blend
        if scene is not None:save_blend(str(root/'assembly_track.blend'))
        finalize(root,plan)
        atomic_json(root/'status.json',dict(state='complete',completed=args.count,total=args.count))
    except Exception as error:
        atomic_json(root/'status.json',dict(state='failed',error=str(error),completed=sum(complete(root,r) for r in plan['rows']),total=args.count));raise


def worker(args):
    if args.open:return _worker(args)
    from generate_domain_dataset import exclusive
    args.output.mkdir(parents=True,exist_ok=True)
    with exclusive(args.output,'.assembly.lock'):
        if args.resume and not args.fleet_plan:(args.output/'STOP').unlink(missing_ok=True)
        return _worker(args)


def main():
    inside='bpy' in sys.modules or Path(sys.executable).stem.lower()=='blender'
    argv=sys.argv[sys.argv.index('--')+1:] if inside and '--' in sys.argv else sys.argv[1:]
    args=parser().parse_args(argv)
    if args.samples < 8 or args.count < 1:raise ValueError('At least 8 samples and 1 frame required')
    if inside:return worker(args)
    command=[args.blender,'--factory-startup']
    if not args.open:command.append('--background')
    command += ['--python-exit-code','1','--python',str(Path(__file__).resolve()),'--',
                '--output',str(args.output.resolve()),'--count',str(args.count),'--seed',str(args.seed),
                '--samples',str(args.samples),'--scale',str(args.scale),'--look',args.look,'--lighting',args.lighting,'--defect-set',args.defect_set]
    if args.open:command.append('--open')
    if args.resume:command.append('--resume')
    if args.beauty_only:command.append('--beauty-only')
    return subprocess.call(command,cwd=ROOT)


if __name__=='__main__':
    result=main()
    # Keep the interactive Blender window alive after --open. Background
    # Blender exits naturally after this script; the outer CLI forwards status.
    if 'bpy' not in sys.modules:sys.exit(result)
