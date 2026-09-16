"""Unique surface detail sampled from aggregate development-image spectra."""
from functools import lru_cache
import json,math
from pathlib import Path
import numpy as np

@lru_cache(maxsize=1)
def _profile():
    return json.loads(Path(__file__).with_name('reference_brass_spectrum.json').read_text())

def synthesize(seed,width=1024,height=768,length=8.,radius=.9):
    """Periodic scalar field; random phase prevents repeating reference marks."""
    profile=_profile();axis=np.asarray(profile['axis_cycles_per_scene_unit'])
    spectrum=np.asarray(profile['log_power'])
    fx=np.abs(np.fft.rfftfreq(width,d=length/width))
    fy=np.abs(np.fft.fftfreq(height,d=math.tau*radius/height))
    along=np.array([np.interp(fx,axis,row,left=row[0],right=-20) for row in spectrum])
    log=np.array([np.interp(fy,axis,col,left=col[0],right=-20) for col in along.T]).T
    rng=np.random.default_rng(int(seed))
    white=rng.normal(size=(height,width))
    amplitude=np.exp(log*.5)
    # No material-scale illumination gradient is inferred from the photo.
    frequency=np.hypot(fy[:,None],fx[None,:])
    amplitude*=1-np.exp(-(frequency/3.0)**4)
    z=np.fft.irfft2(np.fft.rfft2(white)*amplitude,s=(height,width))
    z/=max(float(z.std()),1e-8)
    return np.clip(.5+.060*z,.04,.96).astype(np.float32)

def configure_spectral_grain(material,settings):
    import bpy
    def value(k,d):return settings.get(k,d) if isinstance(settings,dict) else getattr(settings,k,d)
    nodes=material.node_tree.nodes;link=material.node_tree.links.new
    def node(kind,name):
        n=nodes.get(name)
        if n is None:n=nodes.new(kind);n.name=n.label=name
        return n
    signature=f"{int(value('seed',42))}:{float(value('length',8)):.6f}:{float(value('radius',.9)):.6f}"
    tex=node('ShaderNodeTexImage','Inspection statistical grain')
    if tex.image is None:
        tex.image=bpy.data.images.new('PS_StatisticalBrassGrain',width=1024,height=768,float_buffer=True)
        tex.image.colorspace_settings.name='Non-Color'
    im=tex.image
    if im.get('grain_signature')!=signature:
        grain=synthesize(value('seed',42),length=value('length',8),radius=value('radius',.9))
        pixels=np.ones((768,1024,4),dtype=np.float32);pixels[...,:3]=grain[...,None]
        im.pixels.foreach_set(pixels.ravel());im.update();im.pack();im['grain_signature']=signature
    tex.interpolation='Linear';tex.extension='REPEAT'
    position=nodes['Local pipe position']
    axial=node('ShaderNodeMath','Inspection grain axial coordinate');axial.operation='MULTIPLY_ADD'
    axial.inputs[1].default_value=1/value('length',8);axial.inputs[2].default_value=.5
    link(position.outputs['X'],axial.inputs[0])
    angle=node('ShaderNodeMath','Inspection grain circumferential angle');angle.operation='ARCTAN2'
    link(position.outputs['Z'],angle.inputs[0]);link(position.outputs['Y'],angle.inputs[1])
    around=node('ShaderNodeMath','Inspection grain circumferential coordinate');around.operation='MULTIPLY'
    around.inputs[1].default_value=1/math.tau;link(angle.outputs[0],around.inputs[0])
    uv=node('ShaderNodeCombineXYZ','Inspection cylindrical grain coordinates')
    link(axial.outputs[0],uv.inputs['X']);link(around.outputs[0],uv.inputs['Y']);link(uv.outputs[0],tex.inputs['Vector'])
    remap=node('ShaderNodeMapRange','Inspection statistical grain multiplier')
    remap.inputs['To Min'].default_value=.30;remap.inputs['To Max'].default_value=1.70
    link(tex.outputs['Color'],remap.inputs['Value'])
    for shader,source in (('BrassShader','Inspection exposed trace colour'),('PolishedBrass','Inspection exposed trace colour'),('DullOxide','OxideColors')):
        mixed=node('ShaderNodeMixRGB','Inspection measured grain '+shader);mixed.blend_type='MULTIPLY'
        mixed.inputs[0].default_value=.48+value('texture_strength',.5)*.40
        link(nodes[source].outputs[0],mixed.inputs[1]);link(remap.outputs[0],mixed.inputs[2]);link(mixed.outputs[0],nodes[shader].inputs['Base Color'])
    # Generic isotropic noise is now a quiet supporting layer; the observed
    # grain spectrum supplies the visible scale and directional structure.
    nodes['Inspection grain reflectance'].inputs[0].default_value=.12
    nodes['Inspection mottled alloy'].inputs[0].default_value=.08
    nodes['Oxide island coverage'].inputs[1].default_value=.18
    material['domain_material_version']='inspection-statistical-finish-4'
    material['grain_signature']=signature
