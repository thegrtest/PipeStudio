"""Labeled snapshots of the rolling scene, with unique identities per instance."""
import copy
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import uuid
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Matrix

ROOT=Path(__file__).resolve().parent
ACTIVE=None


def poll():
    if not ACTIVE:return None
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type=='VIEW_3D':area.tag_redraw()
    if ACTIVE['process'].poll() is not None:
        from rolling_supervisor import is_active
        if is_active(ACTIVE['folder']):return None
        import pipe_studio as studio
        status=studio.read_status(ACTIVE['folder'])
        if status.get('state') not in ('complete','cancelled','failed','exhausted'):
            studio.atomic_json(ACTIVE['folder']/'status.json',dict(state='failed',saved=status.get('saved',0),
                error='Capture worker exited unexpectedly. See render.log.'))
        return None
    return 1.


def prepare(scene):
    """Remap shared source-shell IDs to stable IDs for the individual moving rigs."""
    import button_track as track
    source=json.loads(scene.get('rolling_source_recipe',scene['flashlight_recipe']))
    scene['rolling_source_recipe']=json.dumps(source)
    by_source={item['index']:item for item in source['items']}
    rigs=sorted((obj for obj in scene.objects if 'rolling_index' in obj),key=lambda obj:obj['rolling_index'])
    if not rigs:raise ValueError('Open the rolling shell scene before starting capture.')
    if scene.get('rolling_randomized_recipe'):
        spec=json.loads(scene['rolling_randomized_recipe'])
        scene['flashlight_recipe']=json.dumps(spec)
        return rigs,spec,spec
    originals=[obj for obj in scene.objects if obj.type=='MESH' and (obj.get('inspection_region') or obj.get('annotation_only'))
               and not (obj.parent and 'rolling_index' in obj.parent)]
    for obj in originals:obj['inspection_label_exclude']=True
    items=[]
    for shell_id,rig in enumerate(rigs):
        item=copy.deepcopy(by_source[rig['source_shell']])
        item.update(index=shell_id,source_shell=rig['source_shell'],rolling_index=rig['rolling_index'])
        defect=item['defect']
        if defect:
            defect.update(id=shell_id*4+track.REGION_KEYS.index(defect['region'])+1,flashlight_id=shell_id)
        rig['capture_shell_id']=shell_id
        # Older animation files omitted aperture diagnostic surfaces from the stream.
        if not any(child.get('annotation_only') for child in rig.children):
            for original in originals:
                if original.get('annotation_only') and original.get('flashlight_id')==rig['source_shell']:
                    proxy=original.copy()
                    next(iter(rig.users_collection)).objects.link(proxy)
                    proxy.parent=rig;proxy.matrix_parent_inverse=Matrix.Identity(4);proxy.location=(0,0,0)
        for obj in rig.children:
            if obj.type!='MESH':continue
            obj['inspection_label_exclude']=False
            obj['flashlight_id']=shell_id
            region=obj.get('inspection_region')
            obj['region_instance_id']=shell_id*4+track.REGION_KEYS.index(region)+1 if region else 0
            obj['defect_id']=defect['id'] if defect and (obj.get('annotation_only') or defect['region']==region) else 0
        items.append(item)
    spec={**source,'items':items,'defects':[item['defect'] for item in items if item['defect']],
          'rolling_capture':True,'source_variant_count':len(by_source)}
    # Four dents are a source-row rule, not an assertion about every moving camera crop.
    spec.pop('required_body_dents',None)
    scene['flashlight_recipe']=json.dumps(spec)
    return rigs,source,spec


def headers(folder):
    import button_track as track
    for relative,names in (('',track.CLASSES),('regions',track.REGIONS),('shells',('shell',))):
        dest=folder/relative;dest.mkdir(parents=True,exist_ok=True)
        (dest/'classes.txt').write_text('\n'.join(names)+'\n')
        (dest/'dataset.yaml').write_text('path: '+dest.resolve().as_posix()+'\ntest: images\nnames:\n'+
            ''.join(f'  {i}: {json.dumps(name)}\n' for i,name in enumerate(names)))


def compact_info(info):
    result={key:value for key,value in info.items() if key not in ('recipe','parameters','shell_poses','lighting','camera')}
    for key in ('annotations','region_annotations','shell_annotations'):
        result[key]=[a for a in info[key] if a['bbox_xywh']]
    return result


def checkpoint_manifest(folder,infos,skipped,sequences,randomized):
    import pipe_studio as studio
    import button_track as track
    groups=sorted({s['split_group'] for s in sequences.values()})
    studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=infos,samples=infos,
        sequence_id=folder.name,sequences=sequences,split_groups=groups,
        split_group=groups[0] if len(groups)==1 and not randomized else None,
        source_variant_count=sum(s['source_variant_count'] for s in sequences.values()),skipped=skipped,
        randomized_defects=randomized,split_policy='Keep each sequence and its source variants in the same split.'))


def run_job(path):
    import pipe_studio as studio
    import button_track as track
    path=Path(path);folder=path.parent;job=json.loads(path.read_text())
    scene=bpy.context.scene
    transform=scene.view_settings.view_transform
    studio.configure_renderer(scene)
    scene.view_settings.view_transform=transform
    from rolling_quality import configure
    p=configure(scene,job)
    # Label passes temporarily swap many per-instance materials. Release the
    # render engine between passes instead of retaining those temporary shaders.
    scene.render.use_persistent_data=False
    scene.render.use_motion_blur=False
    p.update(resolution=job['resolution'],samples=job['samples'],flashlight_crops='ON',
             capture_complete_shell_crops=job['complete_crops'],
             capture_minimum_defect_pixels=job['minimum_pixels'] if job['trigger']=='DEFECT' else 0,
             capture_visible_only=job.get('autonomous',False),rolling_quality_version=job.get('quality_version',0))
    headers(folder)
    frames=list(range(job['start'],job['end']+1,job['step']))
    randomized=job.get('randomize_defects',False)
    passes=job.get('passes',1) if randomized else 1
    if job.get('autonomous') and (folder/'progress.json').exists():
        progress=json.loads((folder/'progress.json').read_text())
        checkpoint=dict(images=[compact_info(json.loads((folder/path).read_text())) for path in progress['captures']],
                        skipped=progress['skipped'],sequences=progress['sequences'])
    else:checkpoint=json.loads((folder/'manifest.json').read_text()) if (folder/'manifest.json').exists() else {}
    infos=checkpoint.get('images',[]);skipped=checkpoint.get('skipped',[])
    sequences=checkpoint.get('sequences',{})
    done={(info.get('pass_index',0),info['frame'],info['camera_id']) for info in infos+skipped}
    attempted=len(done)
    total=passes*len(frames)*len(job['cameras'])
    target=job.get('target_images',0);passes_built=0
    try:
        for pass_index in range(passes):
            if target and len(infos)>=target:break
            if job.get('worker_pass_limit') and passes_built>=job['worker_pass_limit']:break
            if (folder/'cancel.flag').exists():break
            if all((pass_index,frame,camera) in done for frame in frames for camera in job['cameras']):continue
            sequence=f'{folder.name}:pass{pass_index:04d}' if randomized else folder.name
            studio.atomic_json(folder/'status.json',dict(state='building shells',attempted=attempted,total=total,
                saved=len(infos),skipped=len(skipped),pass_index=pass_index,passes=passes))
            if randomized:
                import rolling_randomization
                recipe_path=folder/'recipes'/f'pass_{pass_index:04d}.json'
                saved_recipe=json.loads(recipe_path.read_text()) if recipe_path.exists() else None
                rigs,source,spec=rolling_randomization.randomize(scene,p,job,pass_index,recipe=saved_recipe)
                recipe_path.parent.mkdir(exist_ok=True)
                studio.atomic_json(recipe_path,spec)
            else:
                rigs,source,spec=prepare(scene)
                from rolling_quality import finish_existing
                finish_existing(scene,p)
            passes_built+=1
            group=source.get('split_group',f'button_seed_{source["seed"]}')
            sequences[sequence]=dict(pass_index=pass_index,split_group=group,seed=source['seed'],
                source_variant_count=len(source['items']),recipe_sha256=source.get('recipe_sha256'))
            for frame in frames:
                scene.frame_set(frame)
                poses={obj['capture_shell_id']:[list(row) for row in obj.matrix_world] for obj in rigs}
                for camera in job['cameras']:
                    if target and len(infos)>=target:break
                    if (folder/'cancel.flag').exists():break
                    if (pass_index,frame,camera) in done:continue
                    scene.camera=next(obj for obj in scene.objects if obj.get('inspection_camera')==camera)
                    current={**p,'seed':source['seed']+frame*7919}
                    prefix=f'rolling_p{pass_index:04d}' if randomized else 'rolling'
                    stem=f'{prefix}_{frame:05d}_{camera.lower()}'
                    info=track.export_frame(scene,folder,stem,current)
                    attempted+=1
                    if info is None:
                        skipped.append(dict(pass_index=pass_index,sequence_id=sequence,frame=frame,camera_id=camera,
                            reason='below visible defect threshold'))
                    else:
                        info.update(sequence_id=sequence,pass_index=pass_index,frame=frame,
                            timestamp_seconds=(frame-1)/scene.render.fps,specimen_group=group,split_group=group,
                            source_variant_count=len(source['items']),randomized_defects=randomized,
                            recipe_sha256=source.get('recipe_sha256'),motion_blur=False,
                            exposure_policy='Frozen frame; RGB and masks use the same geometry and time',shell_poses=poses)
                        info['metadata']=f'metadata/{stem}.json'
                        info['render_quality']={key:job.get(key) for key in ('quality_version','resolution','samples',
                            'adaptive_threshold','minimum_samples','filter_width','groove_definition')}
                        by_id={item['index']:item for item in spec['items']}
                        for key in ('annotations','region_annotations','shell_annotations'):
                            for annotation in info[key]:
                                shell_id=annotation['flashlight_id'];item=by_id[shell_id]
                                annotation.update(track_id=f'{sequence}:{shell_id}',source_variant_id=item['source_shell'])
                                box=annotation['bbox_xywh']
                                annotation['edge_truncated']=bool(box and (box[0]==0 or box[1]==0 or
                                    box[0]+box[2]>=info['width'] or box[1]+box[3]>=info['height']))
                        for crop in info['crops']:
                            crop.update(sequence_id=sequence,pass_index=pass_index,frame=frame,specimen_group=group,
                                track_id=f'{sequence}:{crop["flashlight_id"]}')
                            track.write_yolo((folder/crop['image']).with_suffix('.txt'),crop['annotations'],
                                             crop['source_bbox_xywh'][2],crop['source_bbox_xywh'][3])
                        studio.atomic_json(folder/'metadata'/f'{stem}.json',info)
                        infos.append(compact_info(info) if job.get('autonomous') else info)
                    if job.get('autonomous'):
                        studio.atomic_json(folder/'progress.json',dict(captures=[info['metadata'] for info in infos],
                            skipped=skipped,sequences=sequences))
                    else:checkpoint_manifest(folder,infos,skipped,sequences,randomized)
                    studio.atomic_json(folder/'status.json',dict(state='rendering',attempted=attempted,total=total,
                        saved=len(infos),skipped=len(skipped),frame=frame,camera=camera,pass_index=pass_index,passes=passes,target_images=target))
                if target and len(infos)>=target:break
                if (folder/'cancel.flag').exists():break
            if (folder/'cancel.flag').exists():break
        checkpoint_manifest(folder,infos,skipped,sequences,randomized)
        cancelled=(folder/'cancel.flag').exists()
        finished=attempted>=total or bool(target and len(infos)>=target)
        if not finished and not cancelled:
            studio.atomic_json(folder/'status.json',dict(state='checkpoint',attempted=attempted,total=total,
                saved=len(infos),skipped=len(skipped),target_images=target))
            return
        track.write_region_dataset(folder,infos)
        coco=dict(images=[],annotations=[],categories=[dict(id=i,name=name) for i,name in enumerate(track.CLASSES)])
        for image_id,info in enumerate(infos,1):
            coco['images'].append(dict(id=image_id,file_name=info['image'],width=info['width'],height=info['height'],
                sequence_id=info['sequence_id'],frame=info['frame'],camera_id=info['camera_id'],split_group=info['split_group']))
            for annotation in info['annotations']:
                if annotation['bbox_xywh']:
                    coco['annotations'].append(dict(id=len(coco['annotations'])+1,image_id=image_id,
                        category_id=annotation['class_id'],bbox=annotation['bbox_xywh'],area=annotation['visible_pixels'],
                        iscrowd=0,track_id=annotation['track_id']))
        studio.atomic_json(folder/'annotations.coco.json',coco)
        state='cancelled' if cancelled else ('exhausted' if target and len(infos)<target else 'complete')
        studio.atomic_json(folder/'status.json',dict(state=state,attempted=attempted,total=total,
            saved=len(infos),skipped=len(skipped),target_images=target))
    except Exception as exc:
        studio.atomic_json(folder/'status.json',dict(state='failed',error=str(exc),attempted=attempted,saved=len(infos)))
        raise


def start_supervisor(folder,blender):
    from rolling_supervisor import is_active
    if is_active(folder):raise RuntimeError('This collection is already running.')
    python=ROOT/'.venv/Scripts/python.exe'
    if not python.exists():raise RuntimeError('The collection Python runtime is missing.')
    with (folder/'supervisor.log').open('a',encoding='utf-8') as log:
        return subprocess.Popen([str(python),str(ROOT/'rolling_supervisor.py'),str(folder),'--blender',blender],
            cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def launch(scene,autonomous=False):
    global ACTIVE
    import pipe_studio as studio
    import button_track as track
    if ACTIVE and ACTIVE['process'].poll() is None:raise RuntimeError('A rolling capture is already running.')
    config=scene.rolling_capture
    if config.end<config.start:raise ValueError('End frame must be after the start frame.')
    if config.start<scene.frame_start or config.end>scene.frame_end:
        raise ValueError('Capture frames must stay inside the animation range; repeated loops duplicate training views.')
    cameras=list(track.CAMERAS) if config.camera=='ALL' else [scene.camera.get('inspection_camera','FRONT_45')]
    folder=Path(bpy.path.abspath(config.output_dir))/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    folder.mkdir(parents=True,exist_ok=False)
    job=dict(start=config.start,end=config.end,step=config.step,cameras=cameras,trigger=config.trigger,
        minimum_pixels=config.minimum_pixels,complete_crops=config.complete_crops,
        samples=config.samples,resolution=config.resolution,**random_options(config),**quality_options(config))
    if autonomous:
        job.update(autonomous=True,randomize_defects=True,passes=config.collection_pass_limit,
            target_images=config.collection_target,worker_pass_limit=1,worker_timeout_seconds=7200)
    studio.atomic_json(folder/'job.json',job)
    studio.atomic_json(folder/'status.json',dict(state='starting',saved=0))
    prefs=bpy.context.preferences.filepaths;previous=prefs.file_preview_type
    try:
        prefs.file_preview_type='NONE'
        bpy.ops.wm.save_as_mainfile(filepath=str(folder/'source.blend'),copy=True,check_existing=False)
    finally:prefs.file_preview_type=previous
    if autonomous:process=start_supervisor(folder,bpy.app.binary_path)
    else:
        with (folder/'render.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen([bpy.app.binary_path,'--background',str(folder/'source.blend'),'--python-exit-code','1',
                '--python',str(Path(__file__).resolve()),'--',str(folder/'job.json')],cwd=str(ROOT),
                stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    ACTIVE=dict(process=process,folder=folder)
    if not bpy.app.timers.is_registered(poll):bpy.app.timers.register(poll,first_interval=1.)
    config.last_capture=str(folder)
    studio.atomic_json(folder.parent/'active_job.json',dict(folder=str(folder),pid=process.pid,job=job))
    return folder


class ROLL_Settings(bpy.types.PropertyGroup):
    production_quality: BoolProperty(name='Production quality',default=True)
    groove_definition: FloatProperty(name='Groove definition',default=1.4,min=.5,max=2.)
    collection_target: IntProperty(name='Images to collect',default=3000,min=1,max=100000)
    collection_pass_limit: IntProperty(name='Maximum collection passes',default=1000,min=1,max=1000)
    randomize_defects: BoolProperty(name='Randomize defects',default=True,description='Unique incoming shells, rebuilt once per pass and held fixed throughout that pass')
    passes: IntProperty(name='Passes',default=3,min=1,max=1000)
    random_seed: IntProperty(name='Defect seed',default=41000,min=1,max=1000000000)
    body_dents: IntProperty(name='Body dents per six',default=4,min=0,max=6)
    defect_strength: FloatProperty(name='Defect strength',default=1.,min=.25,max=1.5)
    twist_limit: IntProperty(name='Maximum twist (degrees)',default=12,min=0,max=25)
    mix_soiling: BoolProperty(name='Mix clean and dirty shells',default=False,description='Normal dirt is independent of defects and excluded from defect labels')
    dirty_fraction: FloatProperty(name='Heavily dirty fraction',default=.5,min=0,max=1,subtype='FACTOR')
    dirt_strength: FloatProperty(name='Dirt intensity',default=1.,min=.25,max=1.5)
    start: IntProperty(name='First frame',default=1,min=1)
    end: IntProperty(name='Last frame',default=144,min=1)
    step: IntProperty(name='Every N frames',default=12,min=1,max=144)
    camera: EnumProperty(name='Cameras',items=[('CURRENT','Current camera','Capture the selected view'),('ALL','All three cameras','Front 45, rear 45 and overhead')],default='CURRENT')
    trigger: EnumProperty(name='Save',items=[('DEFECT','Visible defects','Skip views below the visible defect threshold'),('ALL','Every sampled frame','Include clean and hidden-defect views as negatives')],default='DEFECT')
    minimum_pixels: IntProperty(name='Minimum defect pixels',default=16,min=1,max=10000)
    complete_crops: BoolProperty(name='Only full-shell crops',default=True,description='Exclude full-shell crops touching an image edge; partial shells remain labeled in the source frame')
    resolution: IntProperty(name='Image width',default=2400,min=320,max=4096)
    samples: IntProperty(name='Render samples',default=192,min=4,max=512)
    output_dir: StringProperty(name='Output folder',subtype='DIR_PATH',default=str(ROOT/'exports/rolling_shell_captures'))
    last_capture: StringProperty(default='')


class ROLL_OT_capture(bpy.types.Operator):
    bl_idname='rolling.capture';bl_label='Capture rolling images'
    def execute(self,context):
        try:folder=launch(context.scene)
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        self.report({'INFO'},'Capture started: '+str(folder))
        return {'FINISHED'}


def random_options(config):
    return {key:getattr(config,key) for key in ('randomize_defects','passes','random_seed','body_dents','defect_strength','twist_limit',
        'mix_soiling','dirty_fraction','dirt_strength')}


def quality_options(config):
    from rolling_quality import PRODUCTION
    values={key:value for key,value in PRODUCTION.items() if key not in ('resolution','samples')} if config.production_quality else {}
    return {**values,'groove_definition':config.groove_definition,'quality_version':1 if config.production_quality else 0}


class ROLL_OT_autonomous(bpy.types.Operator):
    bl_idname='rolling.autonomous';bl_label='Start autonomous collection'
    def execute(self,context):
        try:folder=launch(context.scene,autonomous=True)
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        self.report({'INFO'},'Unattended collection started: '+str(folder))
        return {'FINISHED'}


class ROLL_OT_randomize(bpy.types.Operator):
    bl_idname='rolling.randomize';bl_label='New random defects'
    bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        import pipe_studio as studio
        import rolling_randomization
        config=context.scene.rolling_capture
        config.random_seed+=1
        try:rolling_randomization.randomize(context.scene,{**studio.settings_dict(context.scene.pipe_studio),**quality_options(config)},random_options(config))
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        self.report({'INFO'},'New shell defects generated. Capture uses this seed for its first pass.')
        return {'FINISHED'}


class ROLL_OT_stop(bpy.types.Operator):
    bl_idname='rolling.stop';bl_label='Stop after current image'
    def execute(self,context):
        path=context.scene.rolling_capture.last_capture
        if path:(Path(path)/'cancel.flag').write_text('User requested stop')
        return {'FINISHED'}


class ROLL_OT_resume(bpy.types.Operator):
    bl_idname='rolling.resume';bl_label='Resume last capture'
    def execute(self,context):
        global ACTIVE
        if ACTIVE and ACTIVE['process'].poll() is None:
            self.report({'ERROR'},'A rolling capture is already running.');return {'CANCELLED'}
        folder=Path(context.scene.rolling_capture.last_capture)
        if not (folder/'job.json').exists() or not (folder/'source.blend').exists():
            self.report({'ERROR'},'No saved rolling capture to resume.');return {'CANCELLED'}
        (folder/'cancel.flag').unlink(missing_ok=True)
        job=json.loads((folder/'job.json').read_text())
        if job.get('autonomous'):
            try:process=start_supervisor(folder,bpy.app.binary_path)
            except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}
        else:
            with (folder/'render.log').open('a',encoding='utf-8') as log:
                process=subprocess.Popen([bpy.app.binary_path,'--background',str(folder/'source.blend'),
                    '--python-exit-code','1','--python',str(Path(__file__).resolve()),'--',str(folder/'job.json')],
                    cwd=str(ROOT),stdout=log,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        ACTIVE=dict(process=process,folder=folder)
        if not bpy.app.timers.is_registered(poll):bpy.app.timers.register(poll,first_interval=1.)
        self.report({'INFO'},'Resuming from completed images.')
        return {'FINISHED'}


class ROLL_PT_capture(bpy.types.Panel):
    bl_idname='ROLL_PT_capture';bl_label='Rolling image capture'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Rolling Capture'
    @classmethod
    def poll(cls,context):return bool(context.scene.get('animation_loop'))
    def draw(self,context):
        layout=self.layout;settings=context.scene.rolling_capture
        layout.prop(settings,'randomize_defects')
        if settings.randomize_defects:
            for key in ('passes','random_seed','body_dents','defect_strength','twist_limit'):layout.prop(settings,key)
            layout.prop(settings,'mix_soiling')
            if settings.mix_soiling:
                layout.prop(settings,'dirty_fraction');layout.prop(settings,'dirt_strength')
            layout.operator('rolling.randomize',icon='FILE_REFRESH')
            layout.label(text='Defects stay fixed within each pass')
        layout.separator()
        for key in ('start','end','step','camera','trigger'):
            layout.prop(settings,key)
        if settings.trigger=='DEFECT':layout.prop(settings,'minimum_pixels')
        layout.prop(settings,'production_quality');layout.prop(settings,'groove_definition')
        for key in ('complete_crops','resolution','samples','output_dir'):layout.prop(settings,key)
        count=max(0,(settings.end-settings.start)//settings.step+1)*(3 if settings.camera=='ALL' else 1)
        if settings.randomize_defects:count*=settings.passes
        layout.label(text=f'Up to {count} images with tracked labels')
        layout.label(text='Sharp exposure; RGB + masks + crops')
        layout.operator('rolling.capture',icon='RENDER_ANIMATION')
        box=layout.box();box.label(text='Unattended collection')
        box.prop(settings,'collection_target');box.prop(settings,'collection_pass_limit')
        box.label(text='Fresh worker per pass; automatic recovery')
        box.operator('rolling.autonomous',icon='PLAY')
        layout.operator('rolling.stop',icon='CANCEL')
        if settings.last_capture:
            layout.operator('rolling.resume',icon='PLAY')
            try:
                status=json.loads((Path(settings.last_capture)/'status.json').read_text())
                layout.label(text=f'{status["state"]}: {status.get("saved",0)} images saved')
            except (OSError,ValueError):pass


CLASSES=(ROLL_Settings,ROLL_OT_capture,ROLL_OT_autonomous,ROLL_OT_randomize,ROLL_OT_stop,ROLL_OT_resume,ROLL_PT_capture)


def register():
    if hasattr(bpy.types.Scene,'rolling_capture'):return
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.Scene.rolling_capture=PointerProperty(type=ROLL_Settings)


def unregister():
    if not hasattr(bpy.types.Scene,'rolling_capture'):return
    if bpy.app.timers.is_registered(poll):bpy.app.timers.unregister(poll)
    del bpy.types.Scene.rolling_capture
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)


if __name__=='__main__':
    sys.path.insert(0,str(ROOT))
    import pipe_studio as studio
    studio.register()
    run_job(sys.argv[sys.argv.index('--')+1])
