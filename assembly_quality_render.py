"""Blender counterfactual QA; failed renders never enter the image dataset."""
import numpy as np
from assembly_quality import VERSION,AssemblyRejected,inspect_support,counterfactual_assessment


def camera_noise(scene,path,recipe,pose,masks):
    import bpy
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


def evaluate(scene,objects,masks,path,scratch,stem):
    import bpy
    from assembly_geometry import build_assembly_body
    from domain_render import read_display_raster,file_hash
    beauty=read_display_raster(path);checks=[]
    report=dict(version=VERSION,sample_id=stem,passed=True,instances=checks,beauty_sha256=file_hash(path))
    primary=objects[0]
    for number,(_,body,recipe,pose) in enumerate(objects):
        prefix=f'part{number}_';shell=masks[prefix+'shell']
        for index,item in enumerate(recipe['instances']):
            mask=masks[prefix+f'defect_{index}']
            screen=inspect_support(beauty,mask)
            entry=dict(specimen_id=recipe['specimen_id'],instance_id=item['instance_id'],screen=screen,passed=screen['passed'])
            checks.append(entry)
            if not screen['passed']:report['passed']=False;continue
            vertices,_,_=build_assembly_body(recipe,omit_instances=(index,))
            if len(vertices)!=len(body.data.vertices):raise ValueError('Counterfactual changed topology')
            coords=np.empty(len(body.data.vertices)*3,dtype=np.float32);body.data.vertices.foreach_get('co',coords)
            attribute=body.data.attributes[f'defect_{index}']
            support=np.empty(len(attribute.data),dtype=np.float32);attribute.data.foreach_get('value',support)
            control_path=scratch/f'{stem}_control_{number}_{index}.png'
            original_path=scene.render.filepath
            try:
                body.data.vertices.foreach_set('co',np.asarray(vertices,dtype=np.float32).ravel())
                attribute.data.foreach_set('value',np.zeros_like(support));body.data.update()
                bpy.context.view_layer.update();scene.render.filepath=str(control_path)
                bpy.ops.render.render(write_still=True)
                camera_noise(scene,control_path,primary[2],primary[3],masks)
                other=[m for k,m in masks.items() if '_defect_' in k and k!=prefix+f'defect_{index}']
                check=counterfactual_assessment(beauty,read_display_raster(control_path),mask,shell,other)
                entry['counterfactual']=check;entry['control_sha256']=file_hash(control_path)
                entry['passed']=check['passed'];report['passed'] &= check['passed']
            finally:
                body.data.vertices.foreach_set('co',coords);attribute.data.foreach_set('value',support)
                body.data.update();bpy.context.view_layer.update();scene.render.filepath=original_path
                control_path.unlink(missing_ok=True)
    if not report['passed']:raise AssemblyRejected(report)
    return report
