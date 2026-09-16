"""Blender checks for material/lighting reuse and polymer isolation."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as studio
from brass_material import update_brass
from brass_realism import configure_drawn_finish
from domain_profiles import camera_settings
studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
def fingerprint(mat):
    nodes=mat.node_tree.nodes
    values=[]
    for node in nodes:
        for socket in node.inputs:
            value=getattr(socket,'default_value',None)
            if value is None:continue
            try:value=tuple(value)
            except TypeError:pass
            values.append((node.name,socket.name,value))
    links=sorted((x.from_node.name,x.from_socket.name,x.to_node.name,x.to_socket.name) for x in mat.node_tree.links)
    return values,links
checks=[]
for camera in ('CAM2534','CAM5080','CAM7650'):
    p=camera_settings(camera,seed=2571)
    studio.apply_settings(scene,p);mat=bpy.data.materials['PS_Brass']
    p={key:getattr(scene.pipe_studio,key) for key in studio.settings_dict(scene.pipe_studio)}
    expected=fingerprint(mat);count=len(mat.node_tree.nodes)
    detail=mat.node_tree.nodes.get('Inspection local detail maps')
    detail_image=detail.image if detail else None
    detail_signature=detail_image.get('detail_signature') if detail_image else None
    image_count=len(bpy.data.images)
    for _ in range(5):
        update_brass(mat,scene.pipe_studio);configure_drawn_finish(mat,scene.pipe_studio)
        assert fingerprint(mat)==expected
        assert len(mat.node_tree.nodes)==count
        if detail_image:
            assert detail.image==detail_image and len(bpy.data.images)==image_count
            assert detail_image['detail_signature']==detail_signature
    # Different illumination and classes cannot select a different finish.
    for kind in ('NONE','FOLD','DENT'):
        update_brass(mat,{**p,'defect':kind,'key_power':999})
        assert fingerprint(mat)==expected
        if detail_image:assert detail_image['detail_signature']==detail_signature
    before=tuple(mat.node_tree.nodes['Seeded finish coordinates'].inputs[1].default_value)
    update_brass(mat,{**p,'seed':2572})
    assert tuple(mat.node_tree.nodes['Seeded finish coordinates'].inputs[1].default_value)!=before
    if detail_image:
        assert detail_image['detail_signature']!=detail_signature
        assert detail.image==detail_image and len(bpy.data.images)==image_count
    key=bpy.data.objects['PS_Key'];reference=(tuple(key.location),key.data.energy,key.data.size,key.data.size_y)
    for _ in range(3):
        studio.refresh(scene,geometry=False)
        assert (tuple(key.location),key.data.energy,key.data.size,key.data.size_y)==reference
    before=fingerprint(mat);configure_drawn_finish(mat,{'product_mode':'BUTTON'})
    assert fingerprint(mat)==before
    checks.append(dict(camera=camera,nodes=count,repeated_refresh=True,class_independent=True,unique_seed=True,polymer_bypass=True))
ap=argparse.ArgumentParser()
ap.add_argument('--output',type=Path,default=ROOT/'verification/realism_20260915/shader_validation.json')
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
out=args.output;out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(dict(valid=True,checks=checks),indent=2))
print('MICROFINISH_SHADER_CHECKS_PASSED',flush=True)
