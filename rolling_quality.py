"""Repeatable sharp-exposure rendering and restrained rib definition."""
PRODUCTION=dict(resolution=2400,samples=192,adaptive_threshold=.003,minimum_samples=64,
                filter_width=1.,groove_definition=1.4,inspection_softness=.30,inspection_scatter=.045,
                sensor_noise=.003,plastic_roughness=.265,plastic_specular=.40,plastic_coat=.035)


def configure(scene,job):
    from camera_response import configure_camera_response
    import pipe_studio as studio
    scene.cycles.samples=job['samples']
    scene.cycles.adaptive_threshold=job.get('adaptive_threshold',.012)
    scene.cycles.adaptive_min_samples=min(job['samples'],job.get('minimum_samples',0))
    scene.cycles.filter_width=job.get('filter_width',1.5)
    scene.cycles.denoiser='OPENIMAGEDENOISE'
    scene.cycles.denoising_prefilter='ACCURATE'
    scene.cycles.denoising_quality='HIGH'
    scene.render.resolution_x=job['resolution'];scene.render.resolution_y=round(job['resolution']/2)
    scene.render.resolution_percentage=100
    scene.render.use_motion_blur=False
    p=studio.settings_dict(scene.pipe_studio)
    p.update(resolution=job['resolution'])
    for key in ('inspection_softness','inspection_scatter','sensor_noise','groove_definition',
                'plastic_roughness','plastic_specular','plastic_coat'):
        if key in job:p[key]=job[key]
    configure_camera_response(scene,p)
    scene.render.use_compositing=True
    return p


def finish_existing(scene,p):
    """Adjust existing materials without rebuilding any defect geometry."""
    seen=set()
    for obj in scene.objects:
        if not obj.get('inspection_region'):continue
        for slot in obj.material_slots:
            mat=slot.material
            if not mat or mat in seen or not mat.name.startswith('Inspection burgundy'):continue
            seen.add(mat)
            nodes=mat.node_tree.nodes
            shader=nodes.get('Principled BSDF')
            if not shader.inputs['Specular IOR Level'].is_linked:shader.inputs['Specular IOR Level'].default_value=p['plastic_specular']
            if not shader.inputs['Coat Weight'].is_linked:shader.inputs['Coat Weight'].default_value=p['plastic_coat']
            groove=nodes.get('Fine groove shoulder normals')
            if groove:groove.inputs['Distance'].default_value=.0007*p.get('groove_definition',1.)
            if groove:
                rough=nodes.get('Polymer base roughness')
                amount=p['plastic_finish_variation'];base=p['plastic_roughness']
                rough.inputs['To Min'].default_value=max(.12,base-.045*amount)
                rough.inputs['To Max'].default_value=min(.8,base+.07*amount)
                for node_name,key,scale in [('Matte reference ink reflection','plastic_specular',.7),('Stamp interrupts glossy coating','plastic_coat',1.)]:
                    node=nodes.get(node_name)
                    if node:
                        node.inputs[1].default_value=-scale*p[key]
                        node.inputs[2].default_value=p[key]
                for key in ('plastic_roughness','plastic_specular','plastic_coat'):mat[key]=p[key]
                mat['groove_definition']=p.get('groove_definition',1.)


def scene_view(scene):
    import bpy
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                shading=area.spaces.active.shading
                shading.type='RENDERED';shading.use_scene_lights=True;shading.use_scene_world=True
                area.spaces.active.region_3d.view_perspective='CAMERA'
