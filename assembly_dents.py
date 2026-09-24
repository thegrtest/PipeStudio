"""Small, shallow assembly dents in a physical surface chart (scene units)."""
import math
import random
import numpy as np
from geometry import radius_at


def dent_detail(seed,index,spec,base):
    rng=random.Random(seed ^ (0x71A9+index*104729))
    draw=rng.random()
    # Production examples include more than compact round dings. A common
    # miss is a shallow, circumferentially wide depression whose only cue is a
    # softly bent reflection band. Keep the old families, but reserve a
    # substantial share of new specimens for that hard case.
    family=('small_circular' if draw<.40 else
            'shallow_circular' if draw<.62 else
            'shallow_band' if draw<.88 else
            'large_varied')
    if family=='large_varied':return dict(dent_family=family)
    if family=='small_circular':
        radius=rng.uniform(.085,.19);aspect=rng.uniform(.92,1.10);rotation=rng.uniform(-math.pi,math.pi)
        depth=radius*rng.uniform(.055,.16)
    elif family=='shallow_circular':
        radius=rng.uniform(.20,.35);aspect=rng.uniform(.85,1.15);rotation=rng.uniform(-math.pi,math.pi)
        depth=rng.uniform(.004,.014)
    else:
        # aspect < 1 shortens the axial footprint while leaving a broader
        # circumferential footprint. Small rotation keeps the deformation
        # band-like instead of turning it into another long axial crease.
        radius=rng.uniform(.16,.30);aspect=rng.uniform(.48,.78);rotation=rng.uniform(-.28,.28)
        depth=rng.uniform(.007,.022)
    # Depth is independent of footprint; shallow does not mean simply scaled
    # down from a deep crater. No complete raised rim or sharp cut edge.
    detail=dict(radius=radius,depth=depth,aspect=aspect,
                rotation=rotation,asymmetry=rng.uniform(0,.075),phase=rng.uniform(0,math.tau))
    local_radius=radius_at(spec['position'],base)
    spec.update(width=max(.01,radius/base.length),arc=max(8,math.degrees(radius/local_radius)),
                depth=depth/local_radius,defect_style='DEFAULT',irregularity=.03,defect_rotation=0)
    return dict(dent_family=family,round_dent=detail)


def round_dent_field(t,angles,item,base):
    """Compact C2 bowl; geometry and support use the exact same field."""
    d=item['round_dent'];p=item['spec']
    u=(np.asarray(t)-p['position'])*base.length
    da=np.arctan2(np.sin(np.asarray(angles)-math.radians(p['angle'])),np.cos(np.asarray(angles)-math.radians(p['angle'])))
    v=da*radius_at(p['position'],base)
    co,si=math.cos(d['rotation']),math.sin(d['rotation'])
    x=(co*u+si*v)/(d['radius']*d['aspect']);y=(-si*u+co*v)/d['radius']
    q=x*x+y*y
    bowl=np.maximum(0,1-q)**3
    bowl*=1+d['asymmetry']*np.tanh(x*math.cos(d['phase'])+y*math.sin(d['phase']))
    field=-d['depth']*bowl
    return field,(bowl>=.03).astype(np.float32)


def refine_dent_grid(ts,angles,item,base):
    d=item['round_dent'];p=item['spec'];span=d['radius']*max(1,d['aspect'])*1.15
    half=span/base.length;center=math.radians(p['angle'])
    ts.extend(np.linspace(max(0,p['position']-half),min(1,p['position']+half),45).tolist())
    arc=span/radius_at(p['position'],base)
    angles.extend((center+v)%math.tau for v in np.linspace(-arc,arc,49))
