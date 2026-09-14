"""Smooth, bounded asymmetric exterior indentations; no material failure claims."""
import math
import random

def parameters(seed):
    rng=random.Random(seed)
    return dict(phase=rng.uniform(-math.pi,math.pi),skew=rng.uniform(-.45,.45),
                offset=rng.uniform(-.42,.42),hand=rng.choice((-1,1)),profile=seed%3)

def field(u,v,d):
    p=d['shape_parameters'];phase=p['phase'];a=.8+.5*d.get('irregularity',.2)
    u+=a*.30*math.sin(v*2.1+phase)*math.exp(-v*v*.5)
    v=v*(1+p['skew']*.30*math.tanh(u))+a*.20*math.sin(u*2.4+phase)
    def lobe(x,y):
        q=x*x+y*y
        return max(0,1-q)**2*(1+.5*min(q,1))
    main=lobe(u*(1+p['skew']*.2),v)
    if p.get('profile')==1:
        main=lobe((u+.35*v)*1.75,v*.72)
    elif p.get('profile')==2:
        main=max(0,1-abs(u)**2.8)**2*max(0,1-abs(v)**2.3)**2
    displaced=lobe((u+p['offset'])*1.2,(v-.25*p['hand'])*.85)
    crease=lobe((u-.28*p['hand']+.25*v)*3.5,v*.78)
    secondary=.55 if d.get('style')=='DOUBLE' else .28
    if d.get('style')=='BRANCHED':crease=max(crease,lobe((u+.28*p['hand']-.4*v)*3.5,v*.78))
    value=(main+secondary*a*displaced+.17*a*crease)/(1+(secondary+.17)*a)
    if d.get('style')=='WRINKLED':value*=.9+.1*math.sin(5*u+3*v+phase)
    # A localized displaced shoulder, not a complete circular raised ring.
    shoulder=lobe((u-.78*p['hand'])*3.6,(v+.35)*1.7)
    return d['depth']*(value-.075*a*shoulder)

def upgrade(spec):
    for item in spec.get('items',[]):
        d=item.get('defect')
        if d and d['kind']=='plastic_dent' and d['region']=='BODY':
            d.setdefault('shape_parameters',parameters(spec['seed']*104729+item['index']*7919))
            d['shape_model']='asymmetric_press_v2'
    spec['defects']=[item['defect'] for item in spec.get('items',[]) if item.get('defect')]
    return spec
