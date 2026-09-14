"""Exterior-only brass-button reference, three cameras, region/defect ground truth."""
import json
import math
import os
import random
import shutil
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from flashlight_lab import flashlight_scene as lab
from flashlight_capture import STYLES
import flashlight_materials
import crimp_geometry
import shell_deformation
import plastic_dents

REGION_KEYS=('TOP','BODY','BRASS_FACE','PLASTIC_FACE')
REGIONS=('top','body','Brass Face','Plastic Face')
CLASSES=('plastic_dent','metal_dent','metal_scratch','plastic_scratch','open_center','protruding_crimp','body_twist')
RECIPE_VERSION=12
CAMERAS=('FRONT_45','REAR_45','OVERHEAD')
AVAILABLE_CAMERAS=CAMERAS+('REFERENCE',)
PLASTIC_RIM_Y=1.35
BRASS_RIM_RADIUS=.518
BRASS_RIM_JOIN_Y=-1.432
_stamp_pixels=None


def stamp_depth(x,z):
    global _stamp_pixels
    if _stamp_pixels is None:
        path=Path(__file__).parent/'flashlight_lab'/'assets'/'cap_stamp_v2.png'
        image=bpy.data.images.load(str(path),check_existing=False)
        image.colorspace_settings.name='Non-Color'
        _stamp_pixels=np.array(image.pixels[:],dtype=np.float32).reshape(image.size[1],image.size[0],4)[:,:,0]
        bpy.data.images.remove(image)
    n=_stamp_pixels.shape[0]
    u=max(0,min(n-2,(x+.5)*(n-1)));v=max(0,min(n-2,(z+.5)*(n-1)))
    i,j=int(u),int(v);a,b=u-i,v-j
    return .0055*((1-a)*(1-b)*_stamp_pixels[j,i]+a*(1-b)*_stamp_pixels[j,i+1]+(1-a)*b*_stamp_pixels[j+1,i]+a*b*_stamp_pixels[j+1,i+1])


def plastic_face_height(r,theta):
    # Six pressed folds lie behind the rim plane. Grooves go inward, never out.
    phase=3*theta+.24*(r/.48)**1.4
    fold=math.exp(-(math.sin(phase)/.10)**2)
    support=max(0,1-(r/.468)**8)
    y=PLASTIC_RIM_Y-.071-.006*fold*support*min(1,r/.05)
    y-=.012*math.exp(-(r/.042)**2)
    # Curved fold shoulders rise toward the rim but never cross its plane.
    y+=.066*(math.sin(phase)**2)*math.exp(-((r-.26)/.155)**2)*(1-math.exp(-(r/.035)**2))
    if r>.44:
        t=min(1,(r-.44)/.042)
        y+=(PLASTIC_RIM_Y-y)*t*t*(3-2*t)
    return min(PLASTIC_RIM_Y,y)


def make_recipe(p):
    rng=random.Random(p['seed'])
    items=[]; defects=[]
    region_order=list(REGION_KEYS)
    rng.shuffle(region_order)
    # Keep a small clean minority, retaining four-region coverage on larger rows.
    count=p['flashlight_count'];damaged_count=min(count,max(count//2+1,math.ceil(count*.8)))
    clean_indices=set(rng.sample(list(range(4,count)) if count>4 else list(range(count)),count-damaged_count))
    for i in range(p['flashlight_count']):
        region=region_order[i%4] if p['flashlight_layout']=='MIXED' else p['flashlight_region']
        crimp_kind={'OPEN_CENTER':'open_center','PROTRUDING_CRIMP':'protruding_crimp'}.get(p['defect'])
        if crimp_kind:region='PLASTIC_FACE'
        force_twist=p['defect']=='TWIST'
        if force_twist:region='BODY'
        d=None
        if p['defect']!='NONE' and (p['depth']>0 or crimp_kind or force_twist) and ((p['flashlight_layout']=='MIXED' and (i not in clean_indices or crimp_kind)) or (p['flashlight_layout']=='SINGLE' and i==p['flashlight_index'])):
            metal=region in ('TOP','BRASS_FACE')
            scratch=rng.random()<.4 if p['flashlight_layout']=='MIXED' else p['defect']=='SCRATCH'
            kind=('metal_' if metal else 'plastic_')+('scratch' if scratch else 'dent')
            if crimp_kind:kind=crimp_kind;scratch=False
            elif force_twist or (region=='BODY' and p['flashlight_layout']=='MIXED' and rng.random()<.35):
                kind='body_twist';scratch=False
            elif region=='PLASTIC_FACE' and p['flashlight_layout']=='MIXED':
                kind=rng.choice(('plastic_dent','plastic_scratch','open_center','protruding_crimp'))
                scratch=kind.endswith('scratch')
            d=dict(id=i*4+REGION_KEYS.index(region)+1,kind=kind,region=region,flashlight_id=i,
                   angle=math.radians(p['angle']),position=p['position'],
                   depth=p['depth']*(.025 if scratch else .5),arc=math.radians(p['arc']),
                   length=p['width']*(2.405 if region=='BODY' else .405),
                   tilt=math.tan(math.radians(p['defect_rotation']))*.4,
                   footprint=max(.025,p['width']*1.8),irregularity=p['irregularity'])
            d.update(opening=p['crimp_opening']*.482,lift=p['crimp_lift'],spread=p['crimp_spread'])
            d.update(twist_degrees=p['body_twist'],twist_span=p['body_twist_span'])
            d['style']=rng.choice(STYLES) if p['flashlight_layout']=='MIXED' else p['defect_style']
            if p['flashlight_layout']=='MIXED':
                d['depth']*=rng.choice((.08,.15,.25,.4,.65,1.))*rng.uniform(.85,1.15)
                if kind=='body_twist' and not force_twist:
                    d['twist_degrees']=rng.choice((-1,1))*rng.choice((3,5,8,12,18,25))
                d['angle']+=rng.uniform(-.22,.22)
                d['position']=rng.uniform(.08,.92)
            start=-1.055 if region=='BODY' else -1.425
            span=2.405 if region=='BODY' else .37
            d['y']=start+d['position']*span
            if scratch:
                d['lines']=[dict(y=d['y']+rng.uniform(-.04,.04),length=max(.02,d['length']*rng.uniform(.6,2.8)),
                    offset=rng.uniform(-d['arc']*.6,d['arc']*.6),slope=rng.uniform(-.2,.2),
                    width=rng.uniform(.008,.020)+p['irregularity']*.008) for _ in range(rng.randint(1,6))]
            if kind=='body_twist' and abs(d['twist_degrees'])<1e-6:d=None
            if d:defects.append(d)
        items.append(dict(index=i,x=i-(p['flashlight_count']-1)/2,flip=bool(i%2),roll=math.radians(p['flashlight_roll']),defect=d,
                          material_seed=p['seed']*101+i, rib_count=rng.randint(92,100),rib_phase=rng.uniform(0,math.tau),
                          crimp_twist=p['crimp_twist'],crimp_fold_depth=p['crimp_fold_depth'],crimp_tightness=p['crimp_tightness'],
                          crimp_phase=random.Random(p['seed']*347+i).uniform(-.32,.32)))
    return plastic_dents.upgrade(dict(version=RECIPE_VERSION,seed=p['seed'],items=items,defects=defects,exposure=p['exposure'],light_gain=1,
                body_twist_model='Smooth torsion with bounded ovalization/buckling; material coordinates follow the deformed plastic. Exterior approximation.',
                brass_rim_model='Planar front annulus with a small outer edge bevel and rear groove; reference appearance estimate.',
                button_model='Shallow continuous crown, recessed joint and rolled concentric seat; exterior appearance estimate.',
                crimp_model='Six thick flaps, twisted and pressed; geometric approximation, not a material solver. Protrusion cause is unspecified.',
                units='Illustrative diameter 1; exterior length controlled by length_scale. Exterior only.',
                region_mapping=dict(zip(REGION_KEYS,REGIONS))))


def force_body_dents(spec,p,count=4):
    """Production collection rule: exactly N distinct body-dented specimens."""
    rng=random.Random(p['seed']+83497)
    selected=set(rng.sample(range(len(spec['items'])),min(count,len(spec['items']))))
    for item in spec['items']:
        if item['index'] in selected:
            q={**p,'defect':'DENT','flashlight_layout':'SINGLE','flashlight_region':'BODY',
               'flashlight_index':item['index'],'depth':rng.uniform(.03,.10),'width':rng.uniform(.08,.15),
               'position':rng.uniform(.15,.85),'arc':rng.uniform(25,50),
               'angle':(90+p['flashlight_roll'])%360,'defect_style':rng.choice(('DEFAULT','ELONGATED','OBLIQUE'))}
            item['defect']=make_recipe(q)['items'][item['index']]['defect']
        elif item['defect'] and item['defect']['kind']=='plastic_dent' and item['defect']['region']=='BODY':
            item['defect']=None
    spec['defects']=[item['defect'] for item in spec['items'] if item['defect']]
    spec['required_body_dents']=len(selected)
    return spec


def tag_mesh(name,verts,faces,marks,mat,item,region,button_mat=None):
    obj=lab.mesh_object(name,verts,faces,mat)
    d=item['defect']
    damaged=mat
    if d and d['region']==region and d['kind'].endswith('scratch'):
        damaged=mat.copy();damaged.name=mat.name+' | freshly scraped surface'
        nodes=damaged.node_tree.nodes
        if damaged.get('pipe_brass_version'):
            nodes['OxideAmount'].outputs[0].default_value*=.15
            nodes['RoughnessBase'].outputs[0].default_value*=.75
        else:
            shader=nodes.get('Principled BSDF')
            if shader:
                for link in list(shader.inputs['Roughness'].links):damaged.node_tree.links.remove(link)
                shader.inputs['Roughness'].default_value=.48
    obj.data.materials.append(damaged)
    if button_mat: obj.data.materials.append(button_mat)
    indices=np.asarray(marks,dtype=np.int32)
    if button_mat:
        centers=np.empty((len(obj.data.polygons),3),dtype=np.float32)
        obj.data.polygons.foreach_get('center',centers.ravel())
        indices[(indices==0)&(np.hypot(centers[:,0],centers[:,2])<.115*1.12)]=2
    obj.data.polygons.foreach_set('material_index',indices)
    obj.location=(item['x'],0,.505)
    obj.rotation_euler=(0,item['roll'],math.pi if item['flip'] else 0)
    if region=='PLASTIC_FACE' and d and d['kind']=='body_twist':
        obj.rotation_euler.y-=math.radians(d['twist_degrees'])
    obj.scale.y=item.get('length_scale',1.)
    obj['inspection_region']=region
    obj['flashlight_id']=item['index']
    obj['region_instance_id']=item['index']*4+REGION_KEYS.index(region)+1
    d=item['defect']
    obj['defect_id']=d['id'] if d and d['region']==region else 0
    return obj


def dent_field(u,v,d):
    style=d.get('style','DEFAULT')
    if style=='ELONGATED':u*=1.5;v/=1.8
    if style=='OBLIQUE':u-=v*.65
    if d.get('shape_model')=='asymmetric_press_v2':
        return plastic_dents.field(u,v,d)
    def lobe(a,b):
        q=a*a+b*b
        return max(0,1-q)**3
    value=lobe(u,v)
    if style=='DOUBLE':value=(value+.65*lobe(u-.6,v-.65))/1.25
    elif style=='WRINKLED':value*=.78+.22*math.cos(10*u+2*v)
    elif style=='BRANCHED':value=max(lobe(u*2.2+.7*v,v*.6),.8*lobe(u*2.2-.7*v,v*.6))
    if style in ('OBLIQUE','WRINKLED','BRANCHED'):
        radius=math.hypot(u,v)
        value-=.11*math.exp(-((radius-.85)/.12)**2)*max(0,min(1,.5+u))
    return d['depth']*value


def side(item,region,mat):
    radial=384 if region=='BODY' else 768
    start,end=(-1.055,1.35) if region=='BODY' else (BRASS_RIM_JOIN_Y,-1.060)
    # Concentrate axial samples around the rolled lip and groove. The first
    # ring coincides exactly with the brass face's outer ring.
    ys=([start+(end-start)*k/160 for k in range(161)] if region=='BODY' else
        [start+(-1.378-start)*k/48 for k in range(49)]+
        [-1.378+(end+1.378)*k/64 for k in range(1,65)])
    rings=len(ys)
    verts=[]; faces=[]; displacements=[];rest=[]
    d=item['defect'] if item['defect'] and item['defect']['region']==region else None
    for k in range(rings):
        y=ys[k]
        for j in range(radial):
            theta=math.tau*j/radial
            if region=='BODY':
                r=.488+.00055*math.cos(theta*item['rib_count']+item['rib_phase']+.06*math.sin(y*4))
                r+=.00065*math.sin(theta*7+item['rib_phase'])*math.sin(y*3)
                r-=.006*max(0,1-min(y-start,end-y)/.035)**2
            else:
                r=brass_collar_radius(y)
                r+=.007*math.exp(-((y+1.066)/.01)**2)
            rest.append((r*math.cos(theta),y,r*math.sin(theta)))
            if d and d['kind']=='body_twist':
                r,theta,affected=shell_deformation.twist(y,theta,r,d)
                displacement=0
            elif d and not d['kind'].endswith('scratch'):
                a=math.atan2(math.sin(theta-d['angle']),math.cos(theta-d['angle']))
                displacement=dent_field((a-d['tilt']*(y-d['y']))/d['arc'],(y-d['y'])/d['length'],d)
            else:
                displacement=lab.deformation(theta,y,{**d,'kind':'metal_scratch'} if d else None)
            verts.append(((r-displacement)*math.cos(theta),y,(r-displacement)*math.sin(theta)))
            displacements.append(float(affected) if d and d['kind']=='body_twist' else displacement)
    marks=[]
    for k in range(rings-1):
        for j in range(radial):
            f=(k*radial+j,(k+1)*radial+j,(k+1)*radial+(j+1)%radial,k*radial+(j+1)%radial)
            faces.append(f)
            marks.append(bool(d and max(abs(displacements[v]) for v in f)>=(.5 if d['kind']=='body_twist' else d['depth']*.08)))
    obj=tag_mesh(f'Button flashlight {item["index"]:02} | {region}',verts,faces,marks,mat,item,region)
    if region=='BODY':
        attr=obj.data.attributes.new('inspection_rest_position','FLOAT_VECTOR','POINT')
        attr.data.foreach_set('vector',np.asarray(rest,dtype=np.float32).ravel())
    return obj


def face_displacement(x,z,d):
    if not d: return 0
    radius=d['position']*.38
    cx,cz=radius*math.cos(d['angle']),radius*math.sin(d['angle'])
    dx,dz=x-cx,z-cz
    if d['kind'].endswith('scratch'):
        total=0
        for line in d['lines']:
            across=dx-(d['tilt']+line['slope'])*dz-line['offset']*.25
            total+=math.exp(-.5*(across/(line['width']*.4))**2)*max(0,1-(dz/max(.04,line['length']))**2)**2
        return d['depth']*total
    return dent_field(dx/d['footprint'],dz/(d['footprint']*.8),d)


def end_face(item,region,mat,button_mat=None):
    if region=='PLASTIC_FACE':return crimp_face(item,mat)
    brass=region=='BRASS_FACE'
    n,rings=(768,192) if brass else (384,128)
    d=item['defect'] if item['defect'] and item['defect']['region']==region else None
    def point(r,theta):
        x,z=r*math.cos(theta),r*math.sin(theta)
        if brass:
            # Rolled perimeter and stamped face surround a continuous pressed seat.
            y=brass_rim_face_height(r)
            if r<.180*1.12:y=button_profile(r)
            else:y+=stamp_depth(x,z)
        else:
            y=plastic_face_height(r,theta+item.get('crimp_phase',0))
        displacement=face_displacement(x,z,d)
        y+=displacement if brass else -displacement
        return (x,y,z),displacement
    center,dc=point(0,0)
    verts=[center]; disp=[dc]; faces=[]
    for k in range(1,rings+1):
        for j in range(n):
            # The quarter-round lip needs angle-spaced samples at its tangent.
            radius=(.510*k/160 if k<=160 else .510+.008*math.sin(math.pi*.5*(k-160)/32)) if brass else .482*k/rings
            v,delta=point(radius,math.tau*j/n)
            verts.append(v); disp.append(delta)
    for j in range(n): faces.append((0,1+j,1+(j+1)%n))
    for k in range(rings-1):
        for j in range(n):
            a=1+k*n+j;b=1+k*n+(j+1)%n
            faces.append((a,a+n,b+n,b))
    # Consistent outward normals on opposite ends.
    for i,f in enumerate(faces):
        a,b,c=(Vector(verts[v]) for v in f[:3])
        if ((b-a).cross(c-a).y<0) != brass: faces[i]=tuple(reversed(f))
    marks=[bool(d and max(abs(disp[v]) for v in f)>=d['depth']*.08) for f in faces]
    return tag_mesh(f'Button flashlight {item["index"]:02} | {region}',verts,faces,marks,mat,item,region,button_mat)


def smooth_profile(value,knots):
    for (a,ya,ma),(b,yb,mb) in zip(knots,knots[1:]):
        if value<=b:
            t=max(0,(value-a)/(b-a));t2=t*t;t3=t2*t
            return (2*t3-3*t2+1)*ya+(t3-2*t2+t)*(b-a)*ma+(-2*t3+3*t2)*yb+(t3-t2)*(b-a)*mb
    return knots[-1][1]


def brass_collar_radius(y):
    return smooth_profile(y,((BRASS_RIM_JOIN_Y,BRASS_RIM_RADIUS,0.),
        (-1.422,.514,-1.),(-1.414,.497,-2.),(-1.407,.480,-.2),
        (-1.397,.479,.1),(-1.378,.484,0.)))


def brass_rim_face_height(r):
    if r>=.510:
        return BRASS_RIM_JOIN_Y-.010*math.sqrt(max(0,1-((r-.510)/.008)**2))
    return smooth_profile(r,((0.,-1.424,0.),(.476,-1.424,0.),
        (.488,-1.442,0.),(.510,-1.442,0.)))


def button_profile(r):
    """Continuous shallow crown, rounded edge, recessed joint and rolled seat.

    Hermite tangents keep the tiny bevels smooth without the former flat disk's
    height discontinuity. Negative Y faces the inspection camera. Dimensions
    are appearance estimates; the crown remains behind the outer face rim.
    """
    knots=((0.,-1.440,0.),(.060,-1.434,.20),(.090,-1.427,.36),
           (.108,-1.419,.55),(.119,-1.413,.20),(.130,-1.412,0.),(.140,-1.423,-1.1),
           (.155,-1.438,0.),(.166,-1.430,.9),(.180,-1.424,0.))
    return smooth_profile(r/1.12,knots)


def crimp_face(item,mat):
    d=item['defect'] if item['defect'] and item['defect']['region']=='PLASTIC_FACE' else None
    special=d if d and d['kind'] in ('open_center','protruding_crimp') else None
    verts,faces,marks,aperture=crimp_geometry.build(item,special)
    if d and not special:
        deltas=[face_displacement(x,z,d) for x,y,z in verts]
        verts=[(x,y-delta,z) for (x,y,z),delta in zip(verts,deltas)]
        marks=[max(abs(deltas[v]) for v in face)>=d['depth']*.08 for face in faces]
    obj=tag_mesh(f'Button flashlight {item["index"]:02} | PLASTIC_FACE',verts,faces,marks,mat,item,'PLASTIC_FACE')
    obj['crimp_flaps']=6;obj['nominal_rim_y']=PLASTIC_RIM_Y
    if aperture:
        # This surface exists only in the defect-ID pass. Beauty has an actual hole.
        center=tuple(sum(v[k] for v in aperture)/len(aperture) for k in range(3))
        av=[(center[0],center[1]-.001,center[2])]+[(x,y-.001,z) for x,y,z in aperture]
        af=[(0,j+1,(j+1)%len(aperture)+1) for j in range(len(aperture))]
        proxy=lab.mesh_object(f'Crimp aperture label {item["index"]:02}',av,af,mat)
        proxy.data.materials.append(mat)
        for poly in proxy.data.polygons:poly.material_index=1
        proxy.location=obj.location;proxy.rotation_euler=obj.rotation_euler;proxy.scale=obj.scale
        proxy['defect_id']=d['id'];proxy['region_instance_id']=0;proxy['annotation_only']=True
        proxy['flashlight_id']=item['index']
        proxy.hide_render=True;proxy.hide_set(True)
    return obj


def build_scene(spec,p):
    plastic_dents.upgrade(spec);spec['version']=RECIPE_VERSION
    empty={**spec,'items':[],'layout_count':len(spec['items'])}
    scene=lab.build_scene(empty,p['resolution'],p['samples'],reset=False,preserve_objects=True)
    for item in spec['items']:
        item['length_scale']=p['flashlight_length_scale']
        plastic=flashlight_materials.plastic(p,item['material_seed'],body=True,rib_spec=item)
        face_plastic=flashlight_materials.plastic(p,item['material_seed'])
        brass=flashlight_materials.brass(p,item['material_seed'])
        face_brass=flashlight_materials.brass(p,item['material_seed'],face=True)
        button=flashlight_materials.button(p,item['material_seed'])
        side(item,'BODY',plastic); side(item,'TOP',brass)
        end_face(item,'BRASS_FACE',face_brass,button); end_face(item,'PLASTIC_FACE',face_plastic)
    # Glossy black conveyor and low guides leave the end faces visible.
    for obj in scene.objects:
        if obj.name.startswith('Continuous track UNDER'):
            obj.dimensions.y=4.2
            shader=obj.data.materials[0].node_tree.nodes.get('Principled BSDF')
            for key in ('Base Color','Roughness'):
                for link in list(shader.inputs[key].links):obj.data.materials[0].node_tree.links.remove(link)
            shader.inputs['Base Color'].default_value=(.008,.011,.008,1)
            shader.inputs['Roughness'].default_value=.18
            flashlight_materials.track_finish(obj.data.materials[0],False)
        if obj.name.startswith('Edge guide rail'):
            obj.location.z=.095; obj.dimensions.z=.09
            shader=obj.data.materials[0].node_tree.nodes.get('Principled BSDF')
            for key in ('Base Color','Roughness'):
                for link in list(shader.inputs[key].links):obj.data.materials[0].node_tree.links.remove(link)
            shader.inputs['Base Color'].default_value=(.012,.018,.013,1)
            shader.inputs['Roughness'].default_value=.24
            flashlight_materials.track_finish(obj.data.materials[0],True)
    apron=lab.material('Polished worn conveyor apron',(.09,.075,.03),metal=.65,roughness=.17)
    apron.node_tree.nodes.get('Principled BSDF').inputs['Coat Weight'].default_value=.22
    for sign in (-1,1):
        lab.box(f'Inspection reflection apron {sign}',(0,sign*(1.43*p['flashlight_length_scale']+.26),-.035),
                (p['flashlight_count']+2,.58,.064),apron,bevel=.005)
    overhead=scene.camera
    overhead['inspection_camera']='OVERHEAD'
    for name,y in [('Face inspection front',-4),('Face inspection rear',4)]:
        data=bpy.data.lights.new(name,'AREA');data.shape='RECTANGLE';data.size=5;data.size_y=1.2
        obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj)
        obj.location=(0,y,1.9)
        obj.rotation_euler=(Vector((0,0,.4))-obj.location).to_track_quat('-Z','Y').to_euler()
    for facing in (-1,1):
        for slot in (-1,1):
            data=bpy.data.lights.new(f'Rib reflection {facing} {slot}','AREA');data.shape='RECTANGLE'
            obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj)
            obj['inspection_rib_light']=facing;obj['inspection_rib_slot']=slot
    for key,y in [('FRONT_45',-8),('REAR_45',8),('REFERENCE',-8)]:
        data=bpy.data.cameras.new(key)
        obj=bpy.data.objects.new(key,data); scene.collection.objects.link(obj)
        obj.location=(0,y,8.505)
        obj.rotation_euler=(Vector((0,0,.505))-obj.location).to_track_quat('-Z','Y').to_euler()
        obj['inspection_camera']=key
        data.type='ORTHO'
    scene['flashlight_recipe']=json.dumps(spec)
    return scene


def configure(scene,p):
    elevation=math.radians(p['key_angle'])
    # Close segmented bars produce a longitudinal falloff; preserve their
    # angular size and central illuminance when scaling the fixture distance.
    distance_scale=p.get('inspection_light_distance',1.)
    continuous=p.get('inspection_light_rig','SEGMENTED')=='CONTINUOUS'
    fixture_scale=.7*distance_scale
    light_y=4.8*fixture_scale*math.cos(elevation)
    light_z=.505+4.8*fixture_scale*math.sin(elevation)
    for obj in scene.objects:
        if obj.get('inspection_camera'):
            obj.data.ortho_scale=max(p['flashlight_count']-.18,3.9*p['frame_aspect'] if obj['inspection_camera']=='OVERHEAD' else 3.22*p['frame_aspect'])/p['camera_zoom']
            if obj['inspection_camera']!='OVERHEAD':
                perspective=p['flashlight_projection']=='PERSP'
                obj.data.type='PERSP' if perspective else 'ORTHO'
                distance=20. if perspective else math.sqrt(128)
                direction=1 if obj['inspection_camera']=='REAR_45' else -1
                angle=math.radians(p['flashlight_reference_elevation'] if obj['inspection_camera']=='REFERENCE' else 45)
                obj.location=(0,direction*distance*math.cos(angle),.505+distance*math.sin(angle))
                obj.rotation_euler=(Vector((0,0,.505))-obj.location).to_track_quat('-Z','Y').to_euler()
                obj.data.sensor_fit='HORIZONTAL';obj.data.sensor_width=36
                obj.data.lens=distance*36/(obj.data.ortho_scale*1.08)
            obj.data.shift_x=p['camera_shift_x']; obj.data.shift_y=p['camera_shift_y']
            if obj['inspection_camera']==p['flashlight_camera']: scene.camera=obj
        if obj.get('inspection_flashlight') and obj.type=='LIGHT':
            if obj.name.startswith('Face inspection'):
                obj.location.z=.25
                obj.data.size=6;obj.data.size_y=.22
                obj.data.energy=p['fill_power']*2.9
                obj.data.color=(.55,1,.70)
            if obj.name.startswith('Broad inspection'):
                obj.location=(0,-light_y,light_z)
                obj.data.size=5.55*p['key_span']*fixture_scale;obj.data.size_y=max(.2,p['light_softness']*2.4)*fixture_scale
                obj.data.color=(.35,.78,1);obj.data.energy=p['key_power']*.26*fixture_scale**2
            if obj.name.startswith('Top edge reflection'):
                obj.data.color=(.35,.78,1); obj.location=(0,light_y,light_z)
                obj.data.size=5.55*p['key_span']*fixture_scale;obj.data.size_y=max(.2,p['light_softness']*2.4)*fixture_scale
                obj.data.energy=p['rim_power']*.26*fixture_scale**2
            elif obj.name.startswith('Right grazing'):
                obj.data.color=(.48,.80,1);obj.data.size=.3;obj.data.size_y=4
            if obj.get('inspection_rib_light'):
                side=obj['inspection_rib_light'];x=obj['inspection_rib_slot']*p['flashlight_count']*(1.25/6)
                obj.location=(x,side*light_y,light_z)
                obj.data.size=max(.12,p['key_span']*.71)*fixture_scale;obj.data.size_y=max(.2,p['light_softness']*4.2)*fixture_scale
                obj.data.energy=p['key_power' if side<0 else 'rim_power']*.21*fixture_scale**2
                obj.data.color=(.35,.78,1)
            if continuous:
                if obj.name.startswith(('Broad inspection','Top edge reflection')):
                    front=obj.name.startswith('Broad inspection')
                    distance=3.55*distance_scale
                    obj.location=(0,(-1 if front else 1)*distance*math.cos(elevation),.505+distance*math.sin(elevation))
                    obj.data.size=(p['flashlight_count']+1.5)*(p['key_span']/.45)*distance_scale
                    obj.data.size_y=max(.12,p['light_softness']*2.4)*distance_scale
                    obj.data.energy=p['key_power' if front else 'rim_power']*.5*distance_scale**2*((p['flashlight_count']+1.5)/7.5)
                elif obj.get('inspection_rib_light'):
                    obj.data.energy=0
                elif obj.name.startswith('Right grazing'):
                    obj.data.energy=p['fill_power']*(25/145)
            warmth=(p['color_cast']-.35)*.25
            obj.data.color=(max(0,min(1,obj.data.color[0]+warmth)),obj.data.color[1],max(0,min(1,obj.data.color[2]-warmth)))
            aim_x=obj.location.x if obj.get('inspection_rib_light') else 0
            obj.rotation_euler=(Vector((aim_x,0,.505 if continuous else .4))-obj.location).to_track_quat('-Z','Y').to_euler()
        if obj.name.startswith('Inspection reflection apron'):
            shader=obj.data.materials[0].node_tree.nodes.get('Principled BSDF')
            dark=p.get('inspection_track_finish','METAL')=='DARK'
            shader.inputs['Base Color'].default_value=(.008,.011,.008,1) if dark else (.09,.075,.03,1)
            shader.inputs['Metallic'].default_value=0 if dark else .65
            shader.inputs['Roughness'].default_value=.15 if dark else .17
            shader.inputs['Coat Weight'].default_value=.10 if dark else .22
        if obj.get('inspection_region'):
            for mat in set(obj.data.materials):
                if not mat: continue
                shader=mat.node_tree.nodes.get('Principled BSDF')
                if shader and not mat.name.startswith('Inspection burgundy'):
                    for link in list(shader.inputs['Roughness'].links):mat.node_tree.links.remove(link)
                    shader.inputs['Roughness'].default_value=p['roughness']
    from camera_response import configure_camera_response
    if configure_camera_response(scene,p):scene.render.use_compositing=True


def mask_pass(scene,folder,stem,regions=False):
    objects=[o for o in scene.objects if o.type=='MESH']
    originals=[(o,[(slot.link,slot.material) for slot in o.material_slots]) for o in objects]
    visibility=[(o,o.hide_render) for o in objects if o.get('annotation_only') and not o.get('inspection_label_exclude')]
    ids=sorted({int(o.get('region_instance_id' if regions else 'defect_id',0)) for o in objects}-{0})
    radix=4
    while max(ids,default=0)>=radix**3:radix+=1
    colors={key:np.array((((key%radix)+1)/radix,((key//radix)%radix+1)/radix,
                         ((key//radix**2)%radix+1)/radix),dtype=np.float32) for key in ids}
    mats={key:lab.emission(f'Label {key}',color) for key,color in colors.items()}
    black=lab.emission('Label background',(0,0,0))
    state=(scene.cycles.samples,scene.cycles.use_denoising,scene.view_settings.view_transform,scene.view_settings.exposure,
           scene.world.node_tree.nodes['Background'].inputs[1].default_value,scene.render.use_compositing,
           scene.view_settings.look,scene.view_settings.gamma,scene.render.filepath,scene.render.use_motion_blur,
           scene.cycles.use_adaptive_sampling,scene.cycles.adaptive_min_samples)
    try:
        scene.cycles.samples=1; scene.cycles.use_denoising=False
        scene.cycles.use_adaptive_sampling=False;scene.cycles.adaptive_min_samples=0
        scene.view_settings.view_transform='Standard';scene.view_settings.exposure=0
        scene.view_settings.look='None';scene.view_settings.gamma=1
        scene.world.node_tree.nodes['Background'].inputs[1].default_value=0
        scene.render.use_compositing=False
        scene.render.use_motion_blur=False
        for obj,hidden in visibility:obj.hide_render=regions
        for obj,materials in originals:
            key=0 if obj.get('inspection_label_exclude') else int(obj.get('region_instance_id' if regions else 'defect_id',0))
            for i in range(len(materials)):
                # Linked mesh instances still need distinct object labels.
                obj.material_slots[i].link='OBJECT'
                obj.material_slots[i].material=mats.get(key,black) if regions or i==1 else black
        path=folder/f'{stem}.png';scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True)
        im=bpy.data.images.load(str(path),check_existing=False)
        im.colorspace_settings.name='Non-Color'
        w,h=im.size; pixels=np.empty(w*h*4,dtype=np.float32);im.pixels.foreach_get(pixels)
        pixels=pixels.reshape(h,w,4)[::-1,:,:3]
        bpy.data.images.remove(im)
        result=np.zeros((h,w),dtype=np.uint16)
        best=np.full((h,w),.0005,dtype=np.float32)
        for key,color in colors.items():
            encoded=np.where(color<=.0031308,color*12.92,1.055*np.power(color,1/2.4)-.055)
            distance=((pixels-encoded)**2).sum(axis=2)
            select=distance<best;result[select]=key;best[select]=distance[select]
        return result
    finally:
        for obj,hidden in visibility:obj.hide_render=hidden
        for obj,materials in originals:
            for i,(link,mat) in enumerate(materials):
                obj.material_slots[i].material=mat
                obj.material_slots[i].link=link
        (scene.cycles.samples,scene.cycles.use_denoising,scene.view_settings.view_transform,scene.view_settings.exposure,
         scene.world.node_tree.nodes['Background'].inputs[1].default_value,scene.render.use_compositing,
         scene.view_settings.look,scene.view_settings.gamma,scene.render.filepath,scene.render.use_motion_blur,
         scene.cycles.use_adaptive_sampling,scene.cycles.adaptive_min_samples)=state
        for mat in [black,*mats.values()]:bpy.data.materials.remove(mat)


def annotation(binary,path,class_id,name,**extra):
    ys,xs=np.where(binary)
    bbox=[int(xs.min()),int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)] if len(xs) else None
    lab.save_binary(path,binary)
    return dict(class_id=class_id,class_name=name,bbox_xywh=bbox,visible_pixels=int(binary.sum()),**extra)


def write_yolo(path,annotations,w,h):
    rows=[]
    for a in annotations:
        if a['bbox_xywh']:
            x,y,bw,bh=a['bbox_xywh']
            rows.append(f'{a["class_id"]} {(x+bw/2)/w:.8f} {(y+bh/2)/h:.8f} {bw/w:.8f} {bh/h:.8f}')
    path.write_text('\n'.join(rows)+('\n' if rows else ''))


def export_frame(scene,folder,stem,p):
    folder=Path(folder)
    for name in ('images','labels','metadata','masks','label_passes','region_masks','regions/images','regions/labels',
                 'shells/images','shells/labels','shells/masks'):
        (folder/name).mkdir(parents=True,exist_ok=True)
    spec=json.loads(scene['flashlight_recipe'])
    defect_ids=None
    if p.get('capture_minimum_defect_pixels',0)>0:
        defect_ids=mask_pass(scene,folder/'label_passes',stem+'_defects',False)
        if int((defect_ids>0).sum())<p['capture_minimum_defect_pixels']:
            return None
    scene.render.filepath=str(folder/'images'/f'{stem}.png')
    bpy.ops.render.render(write_still=True)
    if p['sensor_noise']>0:
        image=bpy.data.images.load(scene.render.filepath,check_existing=False)
        pixels=np.array(image.pixels[:],dtype=np.float32).reshape(-1,4)
        noise_seed=p['seed']+AVAILABLE_CAMERAS.index(scene.camera['inspection_camera'])*104729
        pixels[:,:3]=np.clip(pixels[:,:3]+np.random.default_rng(noise_seed).normal(0,p['sensor_noise'],pixels[:,:3].shape),0,1)
        image.pixels.foreach_set(pixels.ravel());image.filepath_raw=scene.render.filepath;image.save()
        bpy.data.images.remove(image)
    region_ids=mask_pass(scene,folder/'label_passes',stem+'_regions',True)
    if defect_ids is None:
        defect_ids=mask_pass(scene,folder/'label_passes',stem+'_defects',False)
    h,w=region_ids.shape
    annotations=[];region_annotations=[];shell_annotations=[]
    visible_only=p.get('capture_visible_only',False)
    for d in spec['defects']:
        binary=defect_ids==d['id']
        if visible_only and not binary.any():continue
        path=folder/'masks'/f'{stem}_{d["id"]:02}.png'
        a=annotation(binary,path,CLASSES.index(d['kind']),d['kind'],
                     defect_id=d['id'],flashlight_id=d['flashlight_id'],region=d['region'],mask=f'masks/{path.name}')
        annotations.append(a)
    for item in spec['items']:
        shell_id=item['index']
        shell_binary=(region_ids>=shell_id*4+1)&(region_ids<=shell_id*4+4)
        if visible_only and not shell_binary.any():continue
        shell_path=folder/'shells/masks'/f'{stem}_{shell_id:02}.png'
        shell_annotations.append(annotation(shell_binary,
            shell_path,0,'shell',flashlight_id=shell_id,mask=f'shells/masks/{shell_path.name}'))
        for class_id,(key,name) in enumerate(zip(REGION_KEYS,REGIONS)):
            instance_id=item['index']*4+class_id+1
            binary=region_ids==instance_id
            if visible_only and not binary.any():continue
            path=folder/'region_masks'/f'{stem}_{instance_id:02}.png'
            region_annotations.append(annotation(binary,path,class_id,name,
                instance_id=instance_id,flashlight_id=item['index'],region=key,mask=f'region_masks/{path.name}'))
    union=defect_ids>0
    combined=annotation(union,folder/'masks'/f'{stem}.png',0,'combined')
    write_yolo(folder/'labels'/f'{stem}.txt',annotations,w,h)
    write_yolo(folder/'regions/labels'/f'{stem}.txt',region_annotations,w,h)
    write_yolo(folder/'shells/labels'/f'{stem}.txt',shell_annotations,w,h)
    source=folder/'images'/f'{stem}.png'
    for dataset in ('regions','shells'):
        linked=folder/dataset/'images'/f'{stem}.png'
        if linked.exists():linked.unlink()
        try:os.link(source,linked)
        except OSError:shutil.copy2(source,linked)
    camera=scene.camera
    info=dict(image=f'images/{stem}.png',mask=f'masks/{stem}.png',width=w,height=h,
       annotations=annotations,region_annotations=region_annotations,shell_annotations=shell_annotations,recipe=spec,parameters=p,
       product_mode='FLASHLIGHT',environment='BUTTON_TRACK',appearance_version=9 if p.get('rolling_quality_version') else 8,defect_type=p['defect'],
       bbox_xywh=combined['bbox_xywh'],visible_mask_pixels=combined['visible_pixels'],
       has_visible_geometric_mask=bool(combined['bbox_xywh']),calibrated=False,split='test',
       specimen_group=f'button_seed_{p["seed"]}',camera_id=camera['inspection_camera'],
       camera=dict(matrix_world=[list(row) for row in camera.matrix_world],type=camera.data.type,
                   ortho_scale=camera.data.ortho_scale,lens_mm=camera.data.lens,sensor_width_mm=camera.data.sensor_width,
                   shift_x=camera.data.shift_x,shift_y=camera.data.shift_y,
                   projection_matrix=[list(row) for row in camera.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(),x=w,y=h,
                       scale_x=scene.render.pixel_aspect_x,scale_y=scene.render.pixel_aspect_y)]),
       lighting=[dict(name=o.name,matrix_world=[list(row) for row in o.matrix_world],
                      power_watts=o.data.energy,color=list(o.data.color),size=o.data.size,size_y=o.data.size_y)
                 for o in scene.objects if o.type=='LIGHT' and o.get('inspection_flashlight')],
       region_mapping=spec['region_mapping'],
       mask_definition='Visible deformed geometry; open-center masks include the visible aperture and withdrawn tips. Aperture diagnostic surfaces are hidden in beauty and region passes. Region labels follow actual visible surfaces. Same specimen identity across cameras.')
    info['crops']=export_crops(folder,stem,info,region_ids) if p.get('flashlight_crops','ON')=='ON' else []
    lab.write_json(folder/'metadata'/f'{stem}.json',info)
    return info


def export_crops(folder,stem,info,region_ids):
    """Lossless source-pixel crops; boxes and annotations use top-left coordinates."""
    image=bpy.data.images.load(str(folder/info['image']),check_existing=False)
    image.colorspace_settings.name='Non-Color'
    h,w=region_ids.shape
    pixels=np.array(image.pixels[:],dtype=np.float32).reshape(h,w,4)[::-1]
    bpy.data.images.remove(image)
    candidates=[]
    for item in info['recipe']['items']:
        i=item['index']
        mask=(region_ids>=i*4+1)&(region_ids<=i*4+4)
        ys,xs=np.where(mask)
        if len(xs):
            complete=xs.min()>0 and ys.min()>0 and xs.max()<w-1 and ys.max()<h-1
            if complete or not info['parameters'].get('capture_complete_shell_crops',False):
                candidates.append(('flashlight',i,[int(xs.min()),int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)]))
    for a in info['region_annotations']:
        box=a['bbox_xywh']
        if box and a['visible_pixels']>=64 and a['visible_pixels']/(box[2]*box[3])>=.1:
            candidates.append((a['region'],a['flashlight_id'],box))
    crops=[]
    for region,i,box in candidates:
        x,y,bw,bh=box
        path=folder/'crops'/region/f'{stem}_{i:02}.png'
        path.parent.mkdir(parents=True,exist_ok=True)
        crop=bpy.data.images.new('Inspection crop',width=bw,height=bh,alpha=True)
        crop.colorspace_settings.name='Non-Color'
        crop.pixels.foreach_set(np.ascontiguousarray(pixels[y:y+bh,x:x+bw][::-1]).ravel())
        crop.filepath_raw=str(path);crop.file_format='PNG';crop.save()
        bpy.data.images.remove(crop)
        defects=[]
        for a in info['annotations']:
            if a['flashlight_id']!=i or not a['bbox_xywh'] or (region!='flashlight' and a['region']!=region):continue
            ax,ay,aw,ah=a['bbox_xywh']
            left,top=max(x,ax),max(y,ay);right,bottom=min(x+bw,ax+aw),min(y+bh,ay+ah)
            if right>left and bottom>top:
                defects.append(dict(defect_id=a['defect_id'],class_id=a['class_id'],class_name=a['class_name'],
                                    bbox_xywh=[left-x,top-y,right-left,bottom-top]))
        crops.append(dict(image=path.relative_to(folder).as_posix(),source_image=info['image'],
                          source_bbox_xywh=box,flashlight_id=i,region=region,
                          specimen_group=info['specimen_group'],camera_id=info['camera_id'],annotations=defects))
    return crops


def export_views(scene,folder,stem,p):
    selected=scene.camera
    infos=[]
    try:
        cameras=CAMERAS if p['flashlight_capture']=='ALL' else (p['flashlight_camera'],)
        for key in cameras:
            scene.camera=next(o for o in scene.objects if o.get('inspection_camera')==key)
            infos.append(export_frame(scene,folder,f'{stem}_{key.lower()}',p))
    finally:scene.camera=selected
    return infos


def write_region_dataset(folder,infos):
    folder=Path(folder)
    lab.write_json(folder/'crops.json',dict(crops=[c for info in infos for c in info.get('crops',[])]))
    coco=dict(images=[],annotations=[],categories=[dict(id=i,name=n) for i,n in enumerate(REGIONS)])
    for image_id,info in enumerate(infos,1):
        coco['images'].append(dict(id=image_id,file_name=info['image'],width=info['width'],height=info['height'],
            specimen_group=info['specimen_group'],camera_id=info['camera_id']))
        for a in info['region_annotations']:
            if a['bbox_xywh']:
                coco['annotations'].append(dict(id=len(coco['annotations'])+1,image_id=image_id,category_id=a['class_id'],
                    bbox=a['bbox_xywh'],area=a['visible_pixels'],iscrowd=0,flashlight_id=a['flashlight_id']))
    lab.write_json(folder/'regions.coco.json',coco)
    (folder/'regions').mkdir(exist_ok=True)
    (folder/'regions/classes.txt').write_text('\n'.join(REGIONS)+'\n')
    (folder/'regions/dataset.yaml').write_text('path: '+(folder/'regions').resolve().as_posix()+'\ntest: images\nnames:\n'+''.join(f'  {i}: {json.dumps(n)}\n' for i,n in enumerate(REGIONS)))
    shells=dict(images=coco['images'],annotations=[],categories=[dict(id=0,name='shell')])
    for image_id,info in enumerate(infos,1):
        for a in info.get('shell_annotations',[]):
            if a['bbox_xywh']:
                shells['annotations'].append(dict(id=len(shells['annotations'])+1,image_id=image_id,category_id=0,
                    bbox=a['bbox_xywh'],area=a['visible_pixels'],iscrowd=0,flashlight_id=a['flashlight_id']))
    lab.write_json(folder/'shells.coco.json',shells)
    (folder/'shells').mkdir(exist_ok=True)
    (folder/'shells/classes.txt').write_text('shell\n')
    (folder/'shells/dataset.yaml').write_text('path: '+(folder/'shells').resolve().as_posix()+'\ntest: images\nnames:\n  0: shell\n')
