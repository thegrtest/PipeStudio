"""Shared pipe deformation fields with a thin diagnostic scratch extension."""
import math
import numpy as np

from domain_geometry import instance_grid, _bounded_sum
from geometry import PipeSpec, radius_at, displacement


def build_assembly_body(recipe,omit_instances=()):
    base=PipeSpec(**recipe['base'])
    items=recipe['instances']
    proxies=[dict(kind=i['spec']['defect'], spec=i['spec']) for i in items]
    ts,angles,specs=instance_grid(base,proxies,axial=160,radial=160)
    # Fine angular/axial samples keep subpixel scratches from becoming
    # triangles. Grid refinement has no screen- or light-dependent placement.
    for item in items:
        if 'round_dent' in item:
            from assembly_dents import refine_dent_grid
            refine_dent_grid(ts,angles,item,base)
        if item['kind'] != 'scratch': continue
        s=item['scratch']; p=item['spec']
        half=(s['length']*.7+s['width']*4)/base.length
        ts += np.linspace(max(0,p['position']-half),min(1,p['position']+half),85).tolist()
        span=min(math.pi,s['length'] / base.radius)
        center=math.radians(p['angle'])
        angles += [(center+x) % math.tau for x in np.linspace(-span,span,150)]
    ts=sorted(set(ts)); angles=sorted(set(angles))
    nr=len(angles); nt=len(ts)
    t,a=np.meshgrid(ts,angles,indexing='ij'); t=t.ravel(); a=a.ravel()
    nominal=np.asarray([radius_at(v,base) for v in t])
    total=np.zeros_like(t); supports=[]
    for index,(item,spec) in enumerate(zip(items,specs)):
        if index in omit_instances:
            supports.append(np.zeros_like(t,dtype=np.float32));continue
        if 'round_dent' in item:
            from assembly_dents import round_dent_field
            field,support=round_dent_field(t,a,item,base)
            total+=field;supports.append(support)
        elif item['kind']=='scratch':
            s=item['scratch']
            u=(t-spec.position)*base.length
            da=np.arctan2(np.sin(a-math.radians(spec.angle)),np.cos(a-math.radians(spec.angle)))
            v=da*radius_at(spec.position,base)
            turn=math.radians(spec.defect_rotation)
            x=u*math.cos(turn)+v*math.sin(turn)
            y=-u*math.sin(turn)+v*math.cos(turn)
            y -= s['curvature'] * np.sin(x/max(.01,s['length'])*4)
            end=np.clip(1-(x/(s['length']*.5))**2,0,1)**2
            groove=np.exp(-.5*(y/s['width'])**2)*end
            total -= s['depth']*groove
            supports.append((groove>.12).astype(np.float32))
        else:
            field=np.asarray([displacement(float(u),float(v),spec) for u,v in zip(t,a)])
            total+=field[:,0]; supports.append(field[:,1].astype(np.float32))
    total=np.asarray([_bounded_sum(d,r) for d,r in zip(total,nominal)])
    r=nominal+total
    outer=np.column_stack(((t-.5)*base.length,r*np.cos(a),r*np.sin(a)))
    inner=outer.copy(); factor=(r-base.radius*base.wall_ratio)/r
    inner[:,1:] *= factor[:,None]
    vertices=np.concatenate((outer,inner)).tolist(); half=len(outer)
    faces=[]
    for j in range(nt-1):
        for k in range(nr):
            q=(k+1)%nr
            aa,bb,cc,dd=j*nr+k,(j+1)*nr+k,(j+1)*nr+q,j*nr+q
            faces.extend(((aa,dd,cc,bb),(aa+half,bb+half,cc+half,dd+half)))
    for k in range(nr):
        q=(k+1)%nr; aa=(nt-1)*nr+k;bb=(nt-1)*nr+q
        faces.extend(((k,k+half,q+half,q),(aa,bb,bb+half,aa+half)))
    supports=[np.concatenate((s,np.zeros(half,dtype=np.float32))) for s in supports]
    return vertices,faces,supports
