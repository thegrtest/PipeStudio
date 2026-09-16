"""Analytic distant-radiance surfaces fitted to reference background regions.

All near-field hardware and the specimen are full geometry. This distant
background approximation contains only smooth basis functions, no photos.
"""
from functools import lru_cache
import json
from pathlib import Path

@lru_cache(maxsize=1)
def profiles():
    return json.loads((Path(__file__).with_name('reference_environment_fields.json')).read_text())['fields']

def sample_field(profile,width=512,height=320):
    """Evaluate smooth basis functions into a small GPU lookup, never photo pixels."""
    import numpy as np
    centers=np.asarray(profile['centers']);sigma=np.asarray(profile['sigma'])
    coefficients=np.asarray(profile['coefficients'])
    result=np.ones((height,width,4),dtype=np.float32)
    for first in range(0,height,16):
        end=min(height,first+16)
        u,v=np.meshgrid((np.arange(width)+.5)/width,(np.arange(first,end)+.5)/height)
        xy=np.stack((u,v),axis=-1)
        weight=np.exp(-.5*np.sum(((xy[:,:,None,:]-centers)/sigma)**2,axis=-1))
        rgb=(weight@coefficients)/weight.sum(axis=-1,keepdims=True)
        result[first:end,:,:3]=np.clip(rgb,0,3)
    return result

def build_material(camera,session):
    import bpy
    key=camera+'_'+session
    name='PS_EnvGods_Radiance_'+key
    material=bpy.data.materials.get(name)
    if material:return material
    profile=profiles()[key]
    material=bpy.data.materials.new(name);material.use_nodes=True
    nodes=material.node_tree.nodes;nodes.clear();link=material.node_tree.links.new
    field=sample_field(profile)
    image=bpy.data.images.new('PS_AnalyticRadiance_'+key,width=field.shape[1],height=field.shape[0],alpha=True,float_buffer=True)
    image.colorspace_settings.name='Non-Color';image.pixels.foreach_set(field.ravel());image.pack()
    lookup=nodes.new('ShaderNodeTexImage');lookup.image=image;lookup.interpolation='Cubic';lookup.extension='EXTEND'
    lookup.label='GPU lookup of fitted analytic field, not a photograph'
    emit=nodes.new('ShaderNodeEmission');emit.name='Reference background radiance'
    link(lookup.outputs['Color'],emit.inputs['Color']);emit.inputs['Strength'].default_value=1
    output=nodes.new('ShaderNodeOutputMaterial');link(emit.outputs[0],output.inputs['Surface'])
    material['reference_background_fit']=key
    return material

def configure_background(scene,settings):
    import bpy
    from mathutils import Vector
    def value(key,default):
        return settings.get(key,default) if isinstance(settings,dict) else getattr(settings,key,default)
    camera=value('inspection_camera','ORIGINAL');session=value('capture_session','AUG19')
    material=build_material(camera,session)
    name='PS_EnvGods_'+camera+'RadianceField'
    obj=bpy.data.objects.get(name)
    if obj is None:
        mesh=bpy.data.meshes.new(name);mesh.from_pydata([(0,0,0)]*4,[],[(0,1,2,3)])
        obj=bpy.data.objects.new(name,mesh);bpy.data.collections['PS_Studio'].objects.link(obj)
        mesh.uv_layers.new(name='Reference field coordinates');mesh.materials.append(material)
        obj['inspection_cameras']=[camera];obj['pipe_studio_fixture']=True
    obj.data.materials[0]=material;obj['pipe_beauty_materials']=[material.name]
    # Place the far radiance surface on the current camera frustum. This is a
    # distant-field approximation, not a measured 3D reconstruction of the plant.
    frame=scene.camera.data.view_frame(scene=scene)
    xmin,xmax=min(p.x for p in frame),max(p.x for p in frame)
    ymin,ymax=min(p.y for p in frame),max(p.y for p in frame)
    for index,corner in enumerate(frame):
        obj.data.vertices[index].co=scene.camera.matrix_world @ (corner*(48/-corner.z))
        obj.data.uv_layers.active.data[index].uv=((corner.x-xmin)/(xmax-xmin),1-(corner.y-ymin)/(ymax-ymin))
    obj.data.update();obj.hide_render=False;obj.hide_set(False)
    # Match reference brightness at baseline exposure while retaining user and
    # dataset exposure changes. Front lighting cannot flatten this far field.
    from domain_profiles import camera_recipe
    exposure=camera_recipe(camera)['settings']['exposure']
    material.node_tree.nodes['Reference background radiance'].inputs['Strength'].default_value=2**(-exposure)
    for other in bpy.data.collections['PS_Studio'].objects:
        if other.name.startswith('PS_EnvGods_'+camera) and other!=obj:
            if any(token in other.name for token in ('Enclosure','RearPost','RearCrossBeam','Reflection','DiagonalRearBeam')):
                other.hide_render=True;other.hide_set(True)
    scene['pipe_background_representation']='Analytic radiance field fitted to masked development backgrounds; generated GPU lookup, not a source photograph.'
