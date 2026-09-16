"""Blender worker: one beauty image and an occlusion-aware mask per instance."""
import argparse
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path,value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        for attempt in range(10):
            try:
                temporary.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
                os.replace(temporary,path)
                return
            except PermissionError:
                if attempt==9: raise
                time.sleep(min(.05*2**attempt,.8))
    finally:
        temporary.unlink(missing_ok=True)


def refine_brass(mat,p):
    """Use the same idempotent surface response as the native Blender UI."""
    from brass_realism import configure_drawn_finish
    configure_drawn_finish(mat,p)


def deposit(mesh,spot,index):
    import numpy as np
    co=np.empty(len(mesh.vertices)*3,dtype=np.float32)
    mesh.vertices.foreach_get('co',co)
    co=co.reshape(-1,3)
    # Shared mesh outer half followed by inner half. Never paint the empty bore.
    outer=np.arange(len(co))<len(co)//2
    length=float(mesh['pipe_length'])
    u=(co[:,0]/length+.5-spot['position'])/spot['axial_size']
    da=np.arctan2(co[:,2],co[:,1])-math.radians(spot['angle'])
    v=np.arctan2(np.sin(da),np.cos(da))/math.radians(spot['angular_size'])
    turn=math.radians(spot.get('rotation',0))
    u,v=u*math.cos(turn)+v*math.sin(turn),-u*math.sin(turn)+v*math.cos(turn)
    phase=(spot['seed']%997)*.217
    radius=np.hypot(u,v)
    irregularity=spot.get('irregularity',.3)
    edge=1+irregularity*(.25*np.sin(5*np.arctan2(v,u)+phase)+.18*np.sin(9*u+7*v))
    coverage=np.clip((edge-radius)*7,0,1)
    if spot['subtype']=='ring':
        coverage*=.15+.85*np.exp(-((radius-.74)/.15)**2)
    if spot['subtype']=='speckled_residue':
        coverage*=.25+.75*(np.sin(15*u+phase)*np.sin(19*v)>.0)
    grain=.76+.24*np.sin(13*u+phase)*np.sin(17*v-phase)
    alpha=(coverage*grain*spot['strength']*outer).astype(np.float32)
    # Coverage, never image brightness, defines residue labels.
    support=(alpha>.08).astype(np.float32)
    alpha*=support
    attr=mesh.attributes.new('domain_stain_'+str(index),'FLOAT','POINT')
    attr.data.foreach_set('value',alpha)
    return support


def stain_material(mat,instances):
    nodes=mat.node_tree.nodes
    link=mat.node_tree.links.new
    output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL')
    # Rebuild only owned deposit nodes; old links otherwise compound per frame.
    for n in list(nodes):
        if n.name.startswith('DomainStain_'): nodes.remove(n)
    base=nodes['DullOxide']
    # Save the actual original final shader, which includes polish and rim blends.
    source_name=mat.get('domain_base_node')
    socket_name=mat.get('domain_base_socket')
    if source_name:
        socket=nodes[source_name].outputs[socket_name]
    else:
        socket=output.inputs['Surface'].links[0].from_socket
        mat['domain_base_node']=socket.node.name
        mat['domain_base_socket']=socket.name
    for index,instance in enumerate(instances):
        if 'spot' not in instance: continue
        spot=instance['spot']
        mix=nodes.new('ShaderNodeMixShader');mix.name='DomainStain_Mix_'+str(index)
        attr=nodes.new('ShaderNodeAttribute');attr.name='DomainStain_Attr_'+str(index)
        attr.attribute_name='domain_stain_'+str(index)
        coat=nodes.new('ShaderNodeBsdfPrincipled');coat.name='DomainStain_Coat_'+str(index)
        soap=instance['kind']=='SOAP_STAIN'
        acid=spot['subtype']=='acid_burn'
        coat.inputs['Base Color'].default_value=(.60,.63,.57,1) if soap else (.045,.026,.009,1) if acid else (.010,.008,.004,1)
        coat.inputs['Roughness'].default_value=.78 if soap or acid else .25
        coat.inputs['Metallic'].default_value=.18 if acid else 0
        brass=nodes['BrassShader']
        if brass.inputs['Normal'].is_linked: link(brass.inputs['Normal'].links[0].from_socket,coat.inputs['Normal'])
        link(attr.outputs['Fac'],mix.inputs[0]);link(socket,mix.inputs[1]);link(coat.outputs[0],mix.inputs[2])
        socket=mix.outputs[0]
    link(socket,output.inputs['Surface'])


def mask_array(path):
    import bpy
    import numpy as np
    im=bpy.data.images.load(str(path),check_existing=False)
    try:
        width,height=im.size
        pixels=np.empty(width*height*4,dtype=np.float32)
        im.pixels.foreach_get(pixels)
        mask=pixels.reshape(height,width,4)[::-1,:,0]>.5
        rgba=np.ones((height,width,4),dtype=np.float32)
        rgba[:,:,:3]=mask[::-1,:,None]
        im.pixels.foreach_set(rgba.ravel())
        im.filepath_raw=str(path);im.file_format='PNG';im.save()
        yy,xx=np.where(mask)
        box=None if not len(xx) else [int(xx.min()),int(yy.min()),int(xx.max()-xx.min()+1),int(yy.max()-yy.min()+1)]
        return width,height,box,int(mask.sum())
    finally:
        bpy.data.images.remove(im)


def projected_pipe_bounds(scene):
    """Record the actual mesh's pixel footprint, including crop outside the frame."""
    import bpy
    import numpy as np
    obj=bpy.data.objects['PS_Pipe']
    co=np.empty(len(obj.data.vertices)*3,dtype=np.float32)
    obj.data.vertices.foreach_get('co',co)
    co=co.reshape(-1,3)[:len(obj.data.vertices)//2]
    width,height=scene.render.resolution_x,scene.render.resolution_y
    projection=scene.camera.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(),x=width,y=height)
    transform=np.array(projection @ scene.camera.matrix_world.inverted() @ obj.matrix_world,dtype=np.float64)
    clip=np.column_stack((co,np.ones(len(co)))) @ transform.T
    visible=clip[:,3]>0
    ndc=clip[visible,:2]/clip[visible,3:4]
    x=(ndc[:,0]+1)*width/2
    y=(1-ndc[:,1])*height/2
    return [round(float(x.min()),3),round(float(y.min()),3),round(float(x.max()-x.min()),3),round(float(y.max()-y.min()),3)]


def read_display_raster(path):
    """Read encoded RGB values, not Blender's scene-linear texture samples."""
    import bpy
    import numpy as np
    im=bpy.data.images.load(str(path),check_existing=False)
    try:
        im.colorspace_settings.name='Non-Color'
        w,h=im.size
        pixels=np.empty(w*h*4,dtype=np.float32)
        im.pixels.foreach_get(pixels)
        return pixels.reshape(h,w,4)[::-1,:,:3].copy()
    finally: bpy.data.images.remove(im)


def render_beauty(scene,path):
    import bpy
    import numpy as np
    scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    p=scene.pipe_studio
    if p.sensor_noise:
        im=bpy.data.images.load(str(path),check_existing=False)
        try:
            arr=np.empty(len(im.pixels),dtype=np.float32);im.pixels.foreach_get(arr);arr=arr.reshape(-1,4)
            from sensor_response import apply_sensor_noise
            apply_sensor_noise(arr,p)
            im.pixels.foreach_set(arr.ravel());im.filepath_raw=str(path);im.file_format='PNG';im.save()
        finally: bpy.data.images.remove(im)


def correct_glare(scene,path,folder,annotations,pipe_mask):
    """Reuse geometry/masks; rerender RGB only. Never export a failed candidate."""
    import bpy
    from glare_guard import assess,LIGHT_STEPS
    masks=[read_display_raster(folder/a['mask'])[:,:,0]>.5 for a in annotations]
    silhouette=read_display_raster(pipe_mask)[:,:,0]>.5
    lights=[obj for obj in scene.objects if obj.type=='LIGHT' and not obj.hide_render]
    initial={obj.name:float(obj.data.energy) for obj in lights}
    exposure=scene.view_settings.exposure
    history=[]
    try:
        for index,(direct,fill,ev) in enumerate(LIGHT_STEPS):
            if index:
                for obj in lights:
                    scale=fill if obj.name in ('PS_Fill','PS_Bounce') else direct
                    obj.data.energy=initial[obj.name]*scale
                scene.view_settings.exposure=exposure+ev
                bpy.context.view_layer.update()
                render_beauty(scene,path)
            report=assess(read_display_raster(path),masks,silhouette)
            history.append(dict(attempt=index, direct_scale=direct, fill_scale=fill,
                                exposure_offset=ev, **report))
            if report['passed']:
                return dict(**report,retries=index,attempts=history,
                            actual_lights_watts={obj.name:float(obj.data.energy) for obj in lights},
                            actual_exposure=float(scene.view_settings.exposure))
            print('GLARE_RETRY',path.stem,index,report['pipe_clipped_fraction'],flush=True)
        raise ValueError('Glare still obscures specimen after bounded lighting retries: '+path.stem)
    finally:
        for obj in lights: obj.data.energy=initial[obj.name]
        scene.view_settings.exposure=exposure


def render_sample(studio,scene,row,folder):
    import bpy
    import numpy as np
    from domain_geometry import build_instances
    from geometry import PipeSpec,yolo_box
    instances=row['instances']
    spec=PipeSpec(**{k:row['settings'][k] for k in PipeSpec.__dataclass_fields__})
    # Scene geometry is rebuilt once using the union of every local refinement grid.
    original=studio.build_mesh
    supports=[]
    def build(*args,**kwargs):
        vertices,faces,union,regions,masks=build_instances(spec,instances,axial=kwargs.get('axial',144),radial=kwargs.get('radial',128))
        supports[:] = masks
        return vertices,faces,union,regions
    try:
        studio.build_mesh=build
        studio.apply_settings(scene,row['settings'])
    finally:
        studio.build_mesh=original
    fixture_state=None
    if row.get('fixture_parameters'):
        from eval_generation import apply_fixture_parameters
        fixture_state=apply_fixture_parameters(scene,row['fixture_parameters'])
    mesh=bpy.data.objects['PS_Pipe'].data
    mesh['pipe_length']=spec.length
    if len(supports)!=len(instances):
        raise ValueError('Every planned instance requires an aligned support mask.')
    for i,item in enumerate(instances):
        if 'spot' in item: supports[i]=deposit(mesh,item['spot'],i)
    mat=bpy.data.materials['PS_Brass']
    refine_brass(mat,scene.pipe_studio)
    stain_material(mat,instances)
    studio.set_mask_mode(scene,False)
    bpy.context.view_layer.update()
    stem=row['sample_id']
    for sub in ('images','labels','masks','metadata'): (folder/sub).mkdir(parents=True,exist_ok=True)
    path=folder/'images'/(stem+'.png')
    render_beauty(scene,path)
    p=scene.pipe_studio
    state=(scene.view_settings.view_transform,scene.view_settings.exposure,scene.cycles.samples,scene.cycles.use_denoising,scene.camera.data.dof.use_dof)
    annotations=[];lines=[]
    try:
        studio.set_mask_mode(scene,True)
        scene.view_settings.view_transform='Standard';scene.view_settings.exposure=0
        scene.cycles.samples=4;scene.cycles.use_denoising=False;scene.camera.data.dof.use_dof=False
        for i,(item,support) in enumerate(zip(instances,supports)):
            mesh.attributes['defect_mask'].data.foreach_set('value',np.asarray(support,dtype=np.float32))
            mesh.update();bpy.context.view_layer.update()
            mask=folder/'masks'/f'{stem}_{i:02d}.png'
            scene.render.filepath=str(mask)
            bpy.ops.render.render(write_still=True)
            w,h,box,pixels=mask_array(mask)
            if box is None or pixels<8:
                persistent=scene.render.use_persistent_data
                try:
                    scene.render.use_persistent_data=False
                    bpy.ops.render.render(write_still=True)
                    w,h,box,pixels=mask_array(mask)
                finally:
                    scene.render.use_persistent_data=persistent
            if box is None or pixels<8:
                raise ValueError(f'Insufficient visible support for {stem} instance {i}: {pixels}')
            from yolox_profile import projected_sizes
            annotation={**item,'mask':str(mask.relative_to(folder)).replace('\\','/'),'bbox_xywh':box,'visible_mask_pixels':pixels,
                        'yolox_input_sizes':projected_sizes(box,w,h)}
            annotations.append(annotation)
            lines.append(str(item['class_id'])+' '+' '.join(f'{v:.8f}' for v in yolo_box(box,w,h)))
        # Measure glare only on the pipe, excluding bright machine fixtures.
        # Also gates good specimens, avoiding class-dependent lighting shortcuts.
        mesh.attributes['defect_mask'].data.foreach_set('value',np.ones(len(mesh.vertices),dtype=np.float32))
        mesh.update();bpy.context.view_layer.update()
        pipe_mask=folder/'masks'/f'{stem}_pipe.png'
        scene.render.filepath=str(pipe_mask)
        bpy.ops.render.render(write_still=True)
        mask_array(pipe_mask)
    finally:
        scene.view_settings.view_transform,scene.view_settings.exposure,scene.cycles.samples,scene.cycles.use_denoising,scene.camera.data.dof.use_dof=state
        studio.set_mask_mode(scene,False)
    glare=correct_glare(scene,path,folder,annotations,pipe_mask)
    (folder/'labels'/(stem+'.txt')).write_text('\n'.join(lines)+('\n' if lines else ''),encoding='utf-8')
    info={k:v for k,v in row.items() if k not in ('settings','instances')}
    info.update(image='images/'+stem+'.png',width=scene.render.resolution_x,height=scene.render.resolution_y,
        projected_pipe_bbox_xywh=projected_pipe_bounds(scene),
        parameters=studio.settings_dict(p),instances=annotations,appearance_version=row.get('generation_revision','domain-2-glare-1'),
        fixture_response=fixture_state,
        material_response_version=mat.get('domain_material_version','unknown'),
        material_detail_audit=json.loads(mat.get('detail_audit','null')),
        fixture_response_version=scene.get('pipe_fixture_response_version') if p.inspection_camera!='ORIGINAL' and p.environment=='GODSLIGHT' else None,
        inspection_light_version=scene.get('pipe_inspection_light_version') if p.inspection_camera!='ORIGINAL' and p.environment=='GODSLIGHT' else None,
        glare_guard=glare,pipe_mask=pipe_mask.relative_to(folder).as_posix(),
        renderer=bpy.app.version_string,render_device=scene.get('pipe_device'),
        camera_response_sigma_px=scene.get('pipe_camera_response_sigma_px'),
        camera_softness_px=scene.get('pipe_camera_softness_px'),
        background_representation=scene.get('pipe_background_representation','Procedural 3D fixtures'),
        sensor_response_version='inspection-channel-noise-2' if p.environment=='GODSLIGHT' and p.inspection_camera!='ORIGINAL' else 'linear-signal-dependent',
        mask_definition='Each visible instance uses its own geometric support or residue-coverage mask; background is occluding black.',
        calibrated=False)
    atomic_json(folder/'metadata'/(stem+'.json'),info)
    files=[info['image'],'labels/'+stem+'.txt','metadata/'+stem+'.json',info['pipe_mask']]+[a['mask'] for a in annotations]
    info['output_sha256']={rel:file_hash(folder/rel) for rel in files}
    return info


def _worker(root,limit,verified_prefix=0):
    import bpy
    import pipe_studio as studio
    from fast_pipeline import install
    from generate_domain_dataset import source_signature, plan_hash, read_json, check_committed
    root=Path(root).resolve()
    plan=read_json(root/'render_plan.json')
    folder=root/'all';folder.mkdir(exist_ok=True)
    signature=source_signature()
    manifest=read_json(folder/'manifest.json',{'classes':plan['classes'],'samples':[],
        'plan_sha256':plan_hash(plan),'renderer_sources':signature,'blender_runtime':bpy.app.version_string})
    if manifest['plan_sha256']!=plan_hash(plan) or manifest['renderer_sources']!=signature or manifest['blender_runtime']!=bpy.app.version_string:
        raise ValueError('Renderer or plan changed: use a new output folder.')
    check_committed(root,plan,manifest,hash_from=verified_prefix)
    install(studio)
    studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
    scratch=Path(tempfile.gettempdir())/'PipeStudioDomain'/f'worker_{os.getpid()}'
    scratch.mkdir(parents=True,exist_ok=True)
    done=len(manifest['samples'])
    for row in plan['samples'][done:done+limit]:
        if (root/'cancel.flag').exists(): break
        started=time.perf_counter()
        record=render_sample(studio,scene,row,scratch)
        record['generation_seconds']=round(time.perf_counter()-started,3)
        # Publish label/masks/metadata before RGB; manifest is the commit marker.
        for rel in sorted(record['output_sha256'],key=lambda s:s.startswith('images/')):
            source=scratch/rel;target=folder/rel;target.parent.mkdir(parents=True,exist_ok=True)
            for attempt in range(10):
                try:
                    import shutil
                    temporary=target.with_suffix(target.suffix+'.partial')
                    shutil.copyfile(source,temporary)
                    if file_hash(temporary)!=record['output_sha256'][rel]: raise ValueError('Copy hash mismatch: '+rel)
                    os.replace(temporary,target);source.unlink();break
                except PermissionError:
                    if attempt==9:raise
                    time.sleep(min(.05*2**attempt,.8))
        manifest['samples'].append(record)
        atomic_json(folder/'manifest.json',manifest)
        atomic_json(root/'progress.json',{'state':'rendering','completed':len(manifest['samples']),
            'total':len(plan['samples']),'worker_pid':os.getpid(),'last_image':str(folder/record['image'])})
        print('DOMAIN_PROGRESS',len(manifest['samples']),len(plan['samples']),record['sample_id'],record['generation_seconds'],flush=True)


def worker(root,limit,verified_prefix=0):
    from generate_domain_dataset import exclusive
    with exclusive(Path(root).resolve(),'.domain-worker.lock'):
        _worker(root,limit,verified_prefix)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--chunk',type=int,default=20)
    ap.add_argument('--verified-prefix',type=int,default=0)
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    worker(args.output,args.chunk,args.verified_prefix)
