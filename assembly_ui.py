"""Blender sidebar for the isolated four-bar assembly inspection scene."""
import json
from pathlib import Path
import subprocess
import sys

import bpy
from bpy.props import EnumProperty,FloatProperty,IntProperty,PointerProperty,StringProperty

from assembly_plan import make_specimen,capture_pose,CONDITIONS
from assembly_scene import build_scene,pose_scene,PREFIX
from assembly_realism import companion_offset,configure_lights,configure_surface

ROOT=Path(__file__).resolve().parent
ACTIVE_PROCESS=None


def change_roll(self,context):
    rig=bpy.data.objects.get(PREFIX+'Rolling specimen');body=bpy.data.objects.get(PREFIX+'Shell')
    if rig and body:
        recipe=json.loads(context.scene['assembly_recipe_json'])
        pose=dict(travel=self.travel,roll=recipe['initial_roll']+self.travel/recipe['base']['radius'],guide_clearance=0,frame_index=0)
        pose_scene(context.scene,rig,body,recipe,pose)
    for other in context.scene.objects:
        if other.get('assembly_companion_recipe'):
            recipe=json.loads(other['assembly_companion_recipe'])
            body=next(o for o in other.children if o.get('part_class_id')==0 and o.name.startswith(PREFIX+'Shell') and 'end' not in o.name)
            travel=self.travel+companion_offset(recipe)
            pose=dict(travel=travel,roll=recipe['initial_roll']+travel/recipe['base']['radius'],guide_clearance=0,frame_index=0)
            pose_scene(context.scene,other,body,recipe,pose)


def add_companion(scene,recipe,travel):
    from assembly_scene import make_assembly
    condition='good' if recipe['condition']=='good' else 'dent'
    other=make_specimen(recipe['seed']+100000,condition,recipe.get('look','REFINED'),recipe.get('lighting','BALANCED'))
    rig,body=make_assembly(scene,other);rig['assembly_companion_recipe']=json.dumps(other)
    t=travel+companion_offset(other)
    p=dict(travel=t,roll=other['initial_roll']+t/other['base']['radius'],guide_clearance=0,frame_index=0)
    pose_scene(scene,rig,body,other,p)


def change_lighting(self,context):
    recipe=json.loads(context.scene['assembly_recipe_json'])
    env=recipe['environment']
    recipe['lighting']=self.lighting
    configure_lights(context.scene,recipe,self.light_scale)
    context.scene['assembly_recipe_json']=json.dumps(recipe)
    for o in context.scene.objects:
        if o.type=='MESH' and o.get('part_class_id')==0 and 'end' not in o.name:
            own=json.loads(o.parent['assembly_companion_recipe']) if o.parent and o.parent.get('assembly_companion_recipe') else dict(recipe)
            own['lighting']=self.lighting
            configure_surface(o.data.materials[0],own)
            if o.parent and o.parent.get('assembly_companion_recipe'):o.parent['assembly_companion_recipe']=json.dumps(own)
    context.scene.view_settings.exposure=env['exposure']+self.exposure
    from assembly_camera_match import sync_plate_view
    sync_plate_view(context.scene)


class ASSEMBLY_Settings(bpy.types.PropertyGroup):
    seed:IntProperty(name='Specimen seed',default=260916,min=0,max=2000000000)
    condition:EnumProperty(name='Primary condition',items=[(v,v.title(),'') for v in CONDITIONS],default='dent')
    look:EnumProperty(name='Scene version',items=[('ORIGINAL','Original — preserved',''),('REFINED','Refined procedural environment',''),('CAMERA_MATCHED','Elevated camera / real empty track','Rendered parts and shadows over verified empty camera frames')],default='CAMERA_MATCHED')
    lighting:EnumProperty(name='Lighting preset',items=[('CURRENT','Current lighting',''),('FOUR_LINES','Four crisp reflection lines',''),('BALANCED','Balanced / in between','')],default='BALANCED',update=change_lighting)
    travel:FloatProperty(name='Roll along guide',default=0,min=-8,max=8,update=change_roll)
    count:IntProperty(name='Frames to export',default=120,min=1,max=100000)
    samples:IntProperty(name='Render samples',default=96,min=8,max=512)
    output:StringProperty(name='Export folder',subtype='DIR_PATH')
    light_scale:FloatProperty(name='Four-bar brightness',default=1,min=.6,max=1.4,update=change_lighting)
    exposure:FloatProperty(name='Exposure adjustment',default=0,min=-1,max=1,update=change_lighting)


class ASSEMBLY_OT_build(bpy.types.Operator):
    bl_idname='assembly.build';bl_label='Build / randomize specimen'
    def execute(self,context):
        p=context.scene.assembly_studio
        recipe=make_specimen(p.seed,p.condition,p.look,p.lighting)
        scene,rig,body=build_scene(recipe,p.samples)
        scene['assembly_recipe_json']=json.dumps(recipe)
        pose_scene(scene,rig,body,recipe,dict(travel=p.travel,roll=recipe['initial_roll']+p.travel/recipe['base']['radius'],guide_clearance=0,frame_index=0))
        add_companion(scene,recipe,p.travel)
        change_lighting(p,context)
        return {'FINISHED'}


class ASSEMBLY_OT_export(bpy.types.Operator):
    bl_idname='assembly.export';bl_label='Start balanced dataset'
    def execute(self,context):
        global ACTIVE_PROCESS
        p=context.scene.assembly_studio
        root=Path(bpy.path.abspath(p.output)).resolve()
        root.mkdir(parents=True,exist_ok=True)
        if ACTIVE_PROCESS is not None and ACTIVE_PROCESS.poll() is None:
            self.report({'WARNING'},'Export already running from this editor');return {'CANCELLED'}
        command=[bpy.app.binary_path,'--background','--factory-startup','--python-exit-code','1',
                 '--python',str(ROOT/'assembly_generate.py'),'--','--output',str(root),
                 '--count',str(p.count),'--seed',str(p.seed),'--samples',str(p.samples),'--look',p.look,'--lighting',p.lighting]
        if (root/'plan.json').exists():command.append('--resume')
        with (root/'worker.log').open('ab') as log:
            child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        ACTIVE_PROCESS=child
        context.scene['assembly_export_pid']=child.pid
        self.report({'INFO'},f'Export started: {p.count} frames. See worker.log and status.json.')
        return {'FINISHED'}


class ASSEMBLY_OT_stop(bpy.types.Operator):
    bl_idname='assembly.stop';bl_label='Pause after current frame'
    def execute(self,context):
        root=Path(bpy.path.abspath(context.scene.assembly_studio.output))
        root.mkdir(parents=True,exist_ok=True);(root/'STOP').touch()
        self.report({'INFO'},'This assembly export will pause after its current frame')
        return {'FINISHED'}


class ASSEMBLY_PT_main(bpy.types.Panel):
    bl_label='Four-bar assembly inspection';bl_idname='ASSEMBLY_PT_main'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='Assembly Studio'
    def draw(self,context):
        p=context.scene.assembly_studio;l=self.layout
        l.label(text='Inert brass body + copper ferrule')
        l.prop(p,'seed');l.prop(p,'condition');l.prop(p,'look');l.operator('assembly.build')
        l.prop(p,'travel');l.operator('render.render',text='Render camera preview')
        l.prop(p,'lighting');l.label(text='Preview brightness / exposure')
        l.prop(p,'light_scale');l.prop(p,'exposure')
        l.separator();l.label(text='1920 x 1200 | separate tracking labels')
        l.prop(p,'output');l.prop(p,'count');l.prop(p,'samples')
        l.operator('assembly.export');l.operator('assembly.stop')
        try:
            status=json.loads((Path(bpy.path.abspath(p.output))/'status.json').read_text())
            l.label(text=f"{status['state'].title()}: {status['completed']} / {status['total']}")
            if status.get('error'):l.label(text=status['error'][:70],icon='ERROR')
        except (OSError,ValueError,KeyError):pass


CLASSES=(ASSEMBLY_Settings,ASSEMBLY_OT_build,ASSEMBLY_OT_export,ASSEMBLY_OT_stop,ASSEMBLY_PT_main)


def register(root,recipe=None):
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.Scene.assembly_studio=PointerProperty(type=ASSEMBLY_Settings)
    from assembly_plan import make_specimen
    scene=bpy.context.scene
    scene.assembly_studio.seed=scene['assembly_recipe_seed']
    scene.assembly_studio.output=str(Path(root)/'dataset')
    # Launcher starts on a good specimen; UI follows the actual current scene.
    recipe=recipe or make_specimen(scene['assembly_recipe_seed'],'good')
    scene.assembly_studio.condition=recipe['condition']
    scene['assembly_recipe_json']=json.dumps(recipe)
    scene.assembly_studio.look=recipe.get('look','REFINED')
    scene.assembly_studio.lighting=recipe.get('lighting','BALANCED')
    recipe=json.loads(scene['assembly_recipe_json'])
    scene.assembly_studio.travel=-3
    add_companion(scene,recipe,-3)
    def redraw():
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=='VIEW_3D':area.tag_redraw()
        return 1.0
    bpy.app.timers.register(redraw,first_interval=1.0)
