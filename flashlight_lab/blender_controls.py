"""Load with --python to register the standalone Flashlight Lab sidebar."""
import json
import sys
from datetime import datetime
from pathlib import Path
import bpy
from bpy.props import IntProperty, FloatProperty, BoolProperty, PointerProperty

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import flashlight_scene as lab


class FL_Settings(bpy.types.PropertyGroup):
    seed: IntProperty(name='Seed',default=42,min=0)
    demo: BoolProperty(name='Reference defect arrangement',default=True)
    clean: FloatProperty(name='Clean probability per flashlight',default=.3,min=0,max=1)
    roll: FloatProperty(name='Random roll range (degrees)',default=0,min=0,max=180)
    width: IntProperty(name='Image width',default=1536,min=128,max=8192)
    samples: IntProperty(name='Cycles samples',default=64,min=1,max=4096)
    gain: FloatProperty(name='Lighting multiplier',default=1,min=.05,max=4)


class FL_Rebuild(bpy.types.Operator):
    bl_idname='flashlight.rebuild'
    bl_label='Build / update scene'
    bl_options={'REGISTER','UNDO'}

    def execute(self,context):
        p=context.scene.flashlight_lab
        spec=lab.recipe(p.seed,p.demo,clean_probability=p.clean,roll_degrees=p.roll)
        spec['light_gain'] *= p.gain
        lab.build_scene(spec,p.width,p.samples,reset=False)
        return {'FINISHED'}


class FL_Export(bpy.types.Operator):
    bl_idname='flashlight.export'
    bl_label='Export current image + defect masks'

    def execute(self,context):
        scene=context.scene
        if 'flashlight_recipe' not in scene:
            self.report({'ERROR'},'Build the flashlight scene first.')
            return {'CANCELLED'}
        folder=ROOT/'output'/datetime.now().strftime('manual_%Y%m%d_%H%M%S_%f')
        folder.mkdir(parents=True)
        info=lab.export_frame(scene,json.loads(scene['flashlight_recipe']),folder,'flashlight_000000',True)
        lab.write_json(folder/'manifest.json',dict(classes=lab.CLASSES,images=[info]))
        self.report({'INFO'},f'Saved to {folder}')
        return {'FINISHED'}


class FL_Panel(bpy.types.Panel):
    bl_label='Flashlight Lab — standalone'
    bl_idname='FL_PT_lab'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='Flashlight Lab'

    def draw(self,context):
        layout=self.layout
        p=context.scene.flashlight_lab
        for key in ('seed','demo','clean','roll','width','samples','gain'):
            layout.prop(p,key)
        layout.operator('flashlight.rebuild')
        layout.operator('render.render',text='Render preview (F12)')
        layout.operator('flashlight.export')
        layout.label(text='Rebuild replaces this lab scene.')
        layout.label(text='Batch export: Generate Dataset.ps1')
        layout.label(text='Dimensions are illustrative.')


for cls in (FL_Settings,FL_Rebuild,FL_Export,FL_Panel):
    bpy.utils.register_class(cls)
bpy.types.Scene.flashlight_lab=PointerProperty(type=FL_Settings)
if 'flashlight_recipe' in bpy.context.scene:
    spec=json.loads(bpy.context.scene['flashlight_recipe'])
    bpy.context.scene.flashlight_lab.seed=spec['seed']
    bpy.context.scene.flashlight_lab.width=bpy.context.scene.render.resolution_x
    bpy.context.scene.flashlight_lab.samples=bpy.context.scene.cycles.samples
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.show_region_ui=True
            area.spaces.active.region_3d.view_perspective='CAMERA'
