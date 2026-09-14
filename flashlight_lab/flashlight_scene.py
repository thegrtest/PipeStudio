"""Standalone procedural flashlight inspection scene. Run with Blender's Python."""
import argparse
import hashlib
import json
import math
import os
import random
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

VERSION = 1
CLASSES = ['plastic_dent', 'metal_dent', 'metal_scratch']
TAU = math.tau


def write_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temporary.replace(path)


def material(name, color, metal=0, roughness=.4, grain=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metal
    bsdf.inputs['Roughness'].default_value = roughness
    if metal == 0:
        bsdf.inputs['Specular IOR Level'].default_value = .23
    if grain:
        coords = nodes.new('ShaderNodeTexCoord')
        scale = nodes.new('ShaderNodeVectorMath')
        scale.operation = 'MULTIPLY'
        scale.inputs[1].default_value = (90, 1.5, 90)
        links.new(coords.outputs['Generated'], scale.inputs[0])
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 5
        noise.inputs['Detail'].default_value = 2
        links.new(scale.outputs[0], noise.inputs['Vector'])
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = .17
        bump.inputs['Distance'].default_value = .0012
        links.new(noise.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs[0], bsdf.inputs['Normal'])
        mottle = nodes.new('ShaderNodeTexNoise')
        mottle.inputs['Scale'].default_value = 26 if metal else 8
        mottle.inputs['Detail'].default_value = 5
        links.new(coords.outputs['Generated'], mottle.inputs['Vector'])
        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = .25
        ramp.color_ramp.elements[0].color = (*(v * (.3 if metal else .82) for v in color), 1)
        ramp.color_ramp.elements[1].position = .73
        ramp.color_ramp.elements[1].color = (*color, 1)
        links.new(mottle.outputs['Fac'], ramp.inputs[0])
        links.new(ramp.outputs[0], bsdf.inputs['Base Color'])
        if not metal:
            flecks = nodes.new('ShaderNodeTexNoise')
            flecks.inputs['Scale'].default_value = 155
            flecks.inputs['Detail'].default_value = 2
            links.new(coords.outputs['Generated'], flecks.inputs['Vector'])
            cutoff = nodes.new('ShaderNodeMath')
            cutoff.operation = 'GREATER_THAN'
            cutoff.inputs[1].default_value = .79
            links.new(flecks.outputs['Fac'], cutoff.inputs[0])
            wear = nodes.new('ShaderNodeMixRGB')
            links.new(cutoff.outputs[0], wear.inputs[0])
            links.new(ramp.outputs[0], wear.inputs[1])
            wear.inputs[2].default_value = (.53,.42,.32,1)
            links.new(wear.outputs[0], bsdf.inputs['Base Color'])
        rough = nodes.new('ShaderNodeMapRange')
        rough.inputs['To Min'].default_value = roughness - .12
        rough.inputs['To Max'].default_value = roughness + .15
        links.new(mottle.outputs['Fac'], rough.inputs['Value'])
        links.new(rough.outputs[0], bsdf.inputs['Roughness'])
    return mat


def emission(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    emit = nodes.new('ShaderNodeEmission')
    emit.inputs['Color'].default_value = (*color, 1)
    mat.node_tree.links.new(emit.outputs[0], out.inputs[0])
    return mat


def mesh_object(name, vertices, faces, mat):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    mesh.materials.append(mat)
    mesh.polygons.foreach_set('use_smooth',np.ones(len(mesh.polygons),dtype=np.bool_))
    return obj


def box(name, position, scale, mat, bevel=.015):
    bpy.ops.mesh.primitive_cube_add(size=1, location=position)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Rounded rail edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        obj.modifiers.new('Rail normals', 'WEIGHTED_NORMAL')
    return obj


def deformation(theta, y, defect):
    if not defect:
        return 0.
    a = math.atan2(math.sin(theta - defect['angle']), math.cos(theta - defect['angle']))
    if defect['kind'] == 'metal_scratch':
        total = 0.
        for line in defect['lines']:
            t = (y - line['y']) / line['length']
            if abs(t) < 1:
                across = a - line['offset'] - line['slope'] * t
                total += defect['depth'] * math.exp(-.5 * (across / line['width']) ** 2) * (1 - t*t)**2
        return total
    # Smooth compact support, oblique elongated depression with asymmetric lip.
    a -= defect['tilt'] * (y - defect['y'])
    q = (a / defect['arc'])**2 + ((y - defect['y']) / defect['length'])**2
    return defect['depth'] * (1 - q)**3 if q < 1 else 0.


def shell(name, profile, inner_radius, mat, x, flip, roll=0, defect=None, ribs=False):
    """Closed annular shell: deform both walls; label only affected exterior faces."""
    segments = 384
    verts, faces, support = [], [], []
    rings = len(profile)
    samples = []
    for inside in (False, True):
        for y, radius in profile:
            for j in range(segments):
                theta = TAU * j / segments
                d = deformation(theta, y, defect)
                r = inner_radius if inside else radius
                r -= d
                if ribs and not inside:
                    r += .00065 * math.cos(theta * 128)
                verts.append((r*math.cos(theta), y, r*math.sin(theta)))
                samples.append(d)
    side = rings * segments
    for inside in (False, True):
        offset = side if inside else 0
        for i in range(rings-1):
            for j in range(segments):
                face = (offset+i*segments+j, offset+i*segments+(j+1)%segments,
                        offset+(i+1)*segments+(j+1)%segments, offset+(i+1)*segments+j)
                faces.append(tuple(reversed(face)) if not inside else face)
                support.append(bool(not inside and defect and max(samples[k] for k in face) >= defect['depth']*.12))
    for i in (0, rings-1):
        for j in range(segments):
            face = (i*segments+j, i*segments+(j+1)%segments, side+i*segments+(j+1)%segments, side+i*segments+j)
            faces.append(face if i == 0 else tuple(reversed(face)))
            support.append(bool(defect and max(samples[k] for k in face) >= defect['depth']*.12))
    obj = mesh_object(name, verts, faces, mat)
    obj.location = (x, 0, .505)
    obj.scale.y = 1.25
    # Roll around the product axis; alternate end direction around world Z.
    obj.rotation_euler = (0, roll, math.pi if flip else 0)
    obj['defect_id'] = defect['id'] if defect else 0
    if defect:
        obj.data.materials.append(mat)
        for face, marked in zip(obj.data.polygons, support):
            face.material_index = int(marked)
    return obj


def cylinder(name, radius, depth, y, mat, x, flip):
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=depth,
                                      location=(x, (-y if flip else y)*1.25, .505), rotation=(math.pi/2, 0, 0))
    obj = bpy.context.object
    obj.name = name
    obj.scale.z = 1.25
    obj.data.materials.append(mat)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def recipe(seed, demo=False, count=6, clean_probability=.3, roll_degrees=0):
    rng = random.Random(seed)
    items = []
    for i in range(count):
        kind = (['clean','metal_scratch','plastic_dent','clean','metal_dent','plastic_dent'][i%6]
                if demo else ('clean' if rng.random() < clean_probability else rng.choice(CLASSES)))
        roll = math.radians(rng.uniform(-roll_degrees, roll_degrees))
        # Demo has unsupported dented shells; random batches retain both causal possibilities.
        battery = (kind != 'plastic_dent') if demo else rng.random() > .25
        d = None
        if kind != 'clean':
            d = dict(id=i+1, kind=kind, angle=math.pi/2+rng.uniform(-.32,.32),
                     y=rng.uniform(-.45,.65) if kind=='plastic_dent' else rng.uniform(-1.35,-1.10),
                     depth=rng.uniform(.04,.09) if kind=='plastic_dent' else rng.uniform(.025,.06),
                     arc=rng.uniform(.36,.58), length=rng.uniform(.22,.38), tilt=rng.uniform(-.5,.5))
            if kind == 'metal_scratch':
                d['depth'] = .003
                d['lines'] = [dict(y=rng.uniform(-1.31,-1.12), length=rng.uniform(.05,.14),
                                   offset=rng.uniform(-.3,.3), slope=rng.uniform(-.35,.35),
                                   width=rng.uniform(.015,.027)) for _ in range(5)]
            elif kind == 'metal_dent':
                d.update(y=-1.39, length=.15)
            elif demo and i == 2:
                d.update(depth=.145,arc=.62,length=.24,tilt=-1.4)
        items.append(dict(index=i, x=i-(count-1)/2, bulb_end='top' if i%2 else 'bottom',
                          battery_installed=battery, roll=roll, defect=d,
                          plastic_color=[.33*rng.uniform(.96,1.04), .10*rng.uniform(.96,1.04), .065]))
    return dict(version=VERSION, seed=seed, units='illustrative; nominal diameter 1, length 3.5625; axial model coordinates scaled by 1.25',
                items=items, light_gain=1 if demo else rng.uniform(.85,1.15),
                exposure=0 if demo else rng.uniform(-.15,.15))


def build_scene(spec, width=1536, samples=64, reset=True, preserve_objects=False):
    cache = Path(__file__).resolve().parent/'output'/'.optix-cache'
    cache.mkdir(parents=True,exist_ok=True)
    os.environ['OPTIX_CACHE_PATH'] = str(cache)
    if reset:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    elif not preserve_objects:
        # Interactive rebuilding is restricted to this dedicated lab scene.
        for obj in list(bpy.context.scene.objects):
            bpy.data.objects.remove(obj,do_unlink=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.seed = spec['seed']
    scene['flashlight_recipe'] = json.dumps(spec)
    scene['flashlight_generator_version'] = VERSION
    scene['dimensions_note'] = spec['units']
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for backend in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
            devices = [d for d in prefs.devices if d.type == backend]
            if devices:
                for device in prefs.devices:
                    device.use = device in devices
                scene.cycles.device = 'GPU'
                break
        except Exception:
            continue
    scene.render.resolution_x = width
    scene.render.resolution_y = round(width * 2/3)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = spec['exposure']
    scene.world = bpy.data.worlds.new('Inspection ambient')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.6,.65,.7,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .12
    steel = material('Tarnished nickel bulb housing', (.58,.57,.49), .92, .3, True)
    rail = material('Brushed steel rails', (.32,.35,.36), .85, .32, True)
    dark = material('Matte track', (.023,.028,.029), .1, .72, True)
    black = material('Battery wrapper', (.024,.025,.027), .25, .45)
    lens = material('Unlit lens', (.14,.17,.18), .4, .16)
    for item in spec['items']:
        idx, x = item['index'], item['x']
        flip = item['bulb_end'] == 'top'
        defect = item['defect']
        plastic = material(f'Plastic {idx:02}', item['plastic_color'], 0, .43, True)
        # Fine, rounded ends; constant cylindrical envelope preserves tight contact.
        body = []
        for k in range(201):
            y = -1.025 + 2.405*k/200
            end = min(y+1.025, 1.38-y)
            radius = .5 - .018*max(0, 1-end/.055)**2
            body.append((y,radius))
        shell(f'Flashlight {idx:02} | hollow plastic', body, .465, plastic, x, flip, item['roll'],
              defect if defect and defect['kind']=='plastic_dent' else None, True)
        metal_profile = []
        for k in range(81):
            y = -1.425+.405*k/80
            radius = .484 + .016*math.exp(-((y+1.4)/.012)**2) + .006*math.exp(-((y+1.03)/.012)**2)
            metal_profile.append((y,radius))
        shell(f'Flashlight {idx:02} | bulb housing', metal_profile, .455, steel, x, flip, item['roll'],
              defect if defect and defect['kind']!='plastic_dent' else None)
        cylinder(f'Flashlight {idx:02} | rear cap', .482, .035, 1.395, steel, x, flip)
        cylinder(f'Flashlight {idx:02} | front lens', .454, .008, -1.416, lens, x, flip)
        if item['battery_installed']:
            cylinder(f'Flashlight {idx:02} | installed battery', .345, 2.16, .10, black, x, flip)
    count = spec.get('layout_count',len(spec['items']))
    box('Continuous track UNDER touching products', (0,0,-.065), (count+2,4.2,.12), dark)
    for y in (-1.84,1.84):
        box('Edge guide rail', (0,y,.35), (count+2,.085,.25), rail)
    camera_data = bpy.data.cameras.new('Overhead inspection camera')
    camera = bpy.data.objects.new('Overhead inspection camera',camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0,0,10)
    camera.rotation_euler = (0,0,0)
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = count-.22
    scene.camera = camera
    for name, position, power, size, size_y in [
            ('Broad inspection softbox',(-2,-.5,4),500,4,4),
            ('Right grazing strip',(3,.3,2),200,1,4),
            ('Top edge reflection',(0,3,2.5),300,5,1)]:
        data = bpy.data.lights.new(name,'AREA')
        data.energy = power*spec['light_gain']
        data.shape = 'RECTANGLE'
        data.size, data.size_y = size, size_y
        obj = bpy.data.objects.new(name,data)
        scene.collection.objects.link(obj)
        obj.location = position
        obj.rotation_euler = (Vector((0,0,.4))-obj.location).to_track_quat('-Z','Y').to_euler()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
    return scene


def save_binary(path, mask):
    h,w = mask.shape
    image = bpy.data.images.new('Binary mask export', width=w,height=h,alpha=False)
    image.colorspace_settings.name = 'Non-Color'
    rgba = np.ones((h,w,4),dtype=np.float32)
    rgba[:,:,:3] = mask[::-1,:,None]
    image.pixels.foreach_set(rgba.ravel())
    image.filepath_raw = str(path)
    image.file_format = 'PNG'
    image.save()
    bpy.data.images.remove(image)


def export_frame(scene, spec, folder, stem, save_blend=False):
    for sub in ('images','masks','labels','metadata'):
        (folder/sub).mkdir(exist_ok=True)
    scene.render.filepath = str(folder/'images'/f'{stem}.png')
    bpy.ops.render.render(write_still=True)
    if save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=str(folder/'Flashlight Inspection.blend'))
    defects = [item['defect'] for item in spec['items'] if item['defect']]
    annotations = []
    if defects:
        # Isolate one affected surface per pass: no palette ambiguity, occlusion is ray traced.
        originals = [(obj, list(obj.data.materials)) for obj in scene.objects if obj.type=='MESH']
        zero, one = emission('Mask black',(0,0,0)), emission('Mask white',(1,1,1))
        state = (scene.cycles.samples, scene.cycles.use_denoising, scene.view_settings.view_transform,
                 scene.view_settings.exposure, scene.world.node_tree.nodes['Background'].inputs[1].default_value)
        try:
            scene.cycles.samples = 1
            scene.cycles.use_denoising = False
            scene.view_settings.view_transform = 'Standard'
            scene.view_settings.exposure = 0
            scene.world.node_tree.nodes['Background'].inputs[1].default_value = 0
            for defect in defects:
                for obj, materials in originals:
                    # Preserve material indices while swapping references in existing slots.
                    for i in range(len(materials)):
                        obj.data.materials[i] = one if i==1 and obj.get('defect_id')==defect['id'] else zero
                path = folder/'masks'/f'{stem}_{defect["id"]:02}.png'
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True)
                im = bpy.data.images.load(str(path),check_existing=False)
                w,h = im.size
                pixels = np.empty(w*h*4,dtype=np.float32)
                im.pixels.foreach_get(pixels)
                mask = pixels.reshape(h,w,4)[::-1,:,0] > .5
                bpy.data.images.remove(im)
                save_binary(path,mask)
                ys,xs = np.where(mask)
                bbox = [int(xs.min()),int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)] if len(xs) else None
                annotations.append(dict(defect_id=defect['id'], class_id=CLASSES.index(defect['kind']),
                                        class_name=defect['kind'], bbox_xywh=bbox, visible_pixels=int(mask.sum()),
                                        mask=f'masks/{path.name}'))
        finally:
            for obj, materials in originals:
                for i,mat in enumerate(materials):
                    obj.data.materials[i] = mat
            (scene.cycles.samples,scene.cycles.use_denoising,scene.view_settings.view_transform,
             scene.view_settings.exposure,scene.world.node_tree.nodes['Background'].inputs[1].default_value) = state
            bpy.data.materials.remove(zero)
            bpy.data.materials.remove(one)
    w,h = scene.render.resolution_x,scene.render.resolution_y
    labels = []
    for annotation in annotations:
        if annotation['bbox_xywh']:
            x,y,bw,bh = annotation['bbox_xywh']
            labels.append(f'{annotation["class_id"]} {(x+bw/2)/w:.8f} {(y+bh/2)/h:.8f} {bw/w:.8f} {bh/h:.8f}')
    (folder/'labels'/f'{stem}.txt').write_text('\n'.join(labels)+('\n' if labels else ''),encoding='utf-8')
    info = dict(image=f'images/{stem}.png',width=w,height=h,annotations=annotations,recipe=spec,
                split='test', specimen_group=f'seed_{spec["seed"]}',
                mask_definition='Visible mesh faces with sampled radial deformation >=12% of nominal peak; physical support, not perceptual detectability. Scratch groups share one instance mask.')
    write_json(folder/'metadata'/f'{stem}.json',info)
    return info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--count',type=int,default=1)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--width',type=int,default=1536)
    parser.add_argument('--samples',type=int,default=64)
    parser.add_argument('--demo',action='store_true')
    parser.add_argument('--clean-probability',type=float,default=.3)
    parser.add_argument('--roll-degrees',type=float,default=0)
    parser.add_argument('--resume',action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.count<1 or args.width<128 or args.samples<1 or not 0<=args.clean_probability<=1 or not 0<=args.roll_degrees<=180:
        parser.error('Invalid count, resolution, samples, probability, or roll range.')
    folder = args.output.resolve()
    folder.mkdir(parents=True,exist_ok=True)
    config = {key:str(value) if isinstance(value,Path) else value for key,value in vars(args).items() if key not in ('resume','output')}
    config.update(generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),blender=bpy.app.version_string)
    plan_path = folder/'job.json'
    if args.resume:
        if not plan_path.exists() or json.loads(plan_path.read_text()) != config:
            raise ValueError('Resume requires identical job settings, Blender version, and generator source.')
    elif any(folder.iterdir()):
        raise ValueError('Use a new empty output directory, or --resume for the same job.')
    else:
        write_json(plan_path,config)
    lock = folder/'render.lock'
    with lock.open('x') as handle:
        handle.write(str(__import__('os').getpid()))
    try:
        manifest = []
        for index in range(args.count):
            stem = f'flashlight_{index:06}'
            metadata = folder/'metadata'/f'{stem}.json'
            if args.resume and metadata.exists() and 'sha256' in json.loads(metadata.read_text()):
                info = json.loads(metadata.read_text())
                for relative,digest in info['sha256'].items():
                    if hashlib.sha256((folder/relative).read_bytes()).hexdigest()!=digest:
                        raise ValueError(f'Output changed: {relative}')
            else:
                spec = recipe(args.seed+index,args.demo,clean_probability=args.clean_probability,roll_degrees=args.roll_degrees)
                scene = build_scene(spec,args.width,args.samples)
                info = export_frame(scene,spec,folder,stem,save_blend=index==0)
                files = [info['image'],f'labels/{stem}.txt']+[a['mask'] for a in info['annotations']]
                info['sha256'] = {p:hashlib.sha256((folder/p).read_bytes()).hexdigest() for p in files}
                write_json(metadata,info)
            manifest.append(info)
            write_json(folder/'manifest.json',dict(classes=CLASSES,images=manifest))
            write_json(folder/'status.json',dict(state='complete' if index+1==args.count else 'running',completed=index+1,total=args.count))
            if (folder/'stop.flag').exists():
                write_json(folder/'status.json',dict(state='stopped',completed=index+1,total=args.count))
                break
        (folder/'classes.txt').write_text('\n'.join(CLASSES)+'\n')
        (folder/'dataset.yaml').write_text('path: .\ntest: images\nnames:\n'+''.join(f'  {i}: {name}\n' for i,name in enumerate(CLASSES)))
        print(f'FLASHLIGHT_EXPORT_COMPLETE {folder}',flush=True)
    except Exception as exc:
        write_json(folder/'status.json',dict(state='failed',error=str(exc)))
        raise
    finally:
        lock.unlink(missing_ok=True)


if __name__=='__main__':
    main()
