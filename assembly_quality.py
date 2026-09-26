"""Strict assembly visibility at detector input scale, independent of class."""
from copy import deepcopy
import hashlib
import json
import math
import random
import numpy as np
from defect_visibility import resize,assess

VERSION='assembly-yolox-visibility-2'
MODEL_SIZE=640
LIMITS=dict(min_short_side=5.,min_long_side=9.,min_support=36,
            min_mean_width=3.,min_median_luma=45.,min_p90_luma=65.,
            max_dark_fraction=.30,max_glare_fraction=.12,min_luma_span=12.)


def inspect_support(rgb,mask,model_size=MODEL_SIZE,legacy_box=False):
    """Necessary image-space conditions; box-only checks cannot prove a defect."""
    h,w=mask.shape;scale=min(1.,model_size/max(h,w))
    hh,ww=round(h*scale),round(w*scale)
    pixels=resize(rgb,hh,ww);support=resize(mask,hh,ww)>.35
    yy,xx=np.nonzero(support);n=len(xx);reasons=[]
    if n:
        width=int(xx.max()-xx.min()+1);height=int(yy.max()-yy.min()+1)
        luma=(pixels@np.array([.2126,.7152,.0722]))*255
        values=luma[support];median=float(np.median(values));p90=float(np.percentile(values,90))
        dark=float(np.mean(values<30));glare=float(np.mean(values>235))
        span=float(np.percentile(values,95)-np.percentile(values,5))
    else:width=height=0;median=p90=span=0.;dark=1.;glare=0.
    if min(width,height)<LIMITS['min_short_side']:reasons.append('too_small_or_thin')
    if max(width,height)<LIMITS['min_long_side']:reasons.append('too_short')
    if n<LIMITS['min_support']:reasons.append('too_few_model_pixels')
    if n/max(width,height,1)<LIMITS['min_mean_width']:reasons.append('thin_visible_support')
    if median<LIMITS['min_median_luma'] or p90<LIMITS['min_p90_luma'] or dark>LIMITS['max_dark_fraction']:reasons.append('too_dark')
    if glare>LIMITS['max_glare_fraction']:reasons.append('glare_obscured')
    if span<LIMITS['min_luma_span']:reasons.append('nearly_flat_patch')
    return dict(passed=not reasons,reasons=reasons,model_size=model_size,model_box=[width,height],
                support_pixels=n,median_luma=round(median,2),p90_luma=round(p90,2),
                dark_fraction=round(dark,4),glare_fraction=round(glare,4),luma_span=round(span,2),
                method='bounding_box_screen' if legacy_box else 'visible_mask_screen',thresholds=LIMITS)


def axial_texture(clean,shell):
    """Estimate grain without treating long straight reflection bars as grain.

    Smooth along the projected shell axis, inferred from its visible mask. A
    straight bar survives this filter; stochastic surface texture does not.
    Shell-weighted bilinear samples avoid averaging the background into a part.
    This measures texture only: all counterfactual change/noise gates still run.
    """
    yy,xx=np.nonzero(shell)
    if len(xx)<3:return np.full_like(clean,255.)
    coords=np.stack((xx,yy),axis=1)
    _,vectors=np.linalg.eigh(np.cov(coords,rowvar=False))
    axis=vectors[:,-1]
    h,w=clean.shape;y,x=np.mgrid[:h,:w]
    numerator=np.zeros_like(clean);denominator=np.zeros_like(clean)
    for offset in range(-8,9):
        sx=np.clip(x+offset*axis[0],0,w-1);sy=np.clip(y+offset*axis[1],0,h-1)
        x0=sx.astype(int);y0=sy.astype(int)
        x1=np.minimum(x0+1,w-1);y1=np.minimum(y0+1,h-1)
        fx=sx-x0;fy=sy-y0;weight=np.exp(-.5*(offset/3.)**2)
        for iy,ix,f in ((y0,x0,(1-fy)*(1-fx)),(y0,x1,(1-fy)*fx),
                        (y1,x0,fy*(1-fx)),(y1,x1,fy*fx)):
            weighted=f*weight*shell[iy,ix]
            numerator+=weighted*clean[iy,ix];denominator+=weighted
    return np.abs(clean-numerator/np.maximum(denominator,1e-8))


def counterfactual_assessment(beauty,control,mask,shell,others=()):
    result=assess(beauty,control,mask,shell,others,config=dict(model_size=MODEL_SIZE,
        min_pixels=36,min_p90_codes=7.5,min_changed_fraction=.25,min_component_pixels=12,
        noise_multiplier=3.,min_change_codes=3.,min_texture_ratio=1.5))
    mh,mw=result['model_dimensions'][1],result['model_dimensions'][0]
    support=resize(mask,mh,mw)>.35;pipe=resize(shell,mh,mw)>.5
    clean=resize(control,mh,mw)@np.array([.2126,.7152,.0722])*255
    texture=axial_texture(clean,pipe)
    level=float(np.percentile(texture[support],90)) if support.any() else 255.
    ratio=result['shape_p90_change_codes']/max(level,1.)
    result['isotropic_texture_diagnostic']={key:result[key] for key in
        ('clean_texture_p90_codes','shape_to_texture_ratio')}
    reasons=[r for r in result['reasons'] if r!='cue_buried_in_surface_texture']
    if ratio<result['thresholds']['min_texture_ratio']:reasons.append('cue_buried_in_surface_texture')
    result.update(version=VERSION,texture_method='shell-axis grain residual; signed coherent shading cue',
                  clean_texture_p90_codes=round(level,3),shape_to_texture_ratio=round(ratio,3),
                  reasons=reasons,passed=not reasons)
    return result


def strict_recipe(recipe):
    recipe=deepcopy(recipe);recipe['quality_profile']=VERSION
    rng=random.Random(f"assembly-strict:{recipe['seed']}")
    for item in recipe['instances']:
        spec=item['spec']
        elevation=42 if recipe['look']=='WARM_TRACK' else 36
        spec['angle']=(elevation+rng.uniform(-22,22)-math.degrees(recipe['initial_roll']))%360
        spec['width']=max(.075,spec['width']);spec['arc']=max(28,spec['arc'])
        spec['depth']=max(.11,spec['depth'])
        if 'round_dent' in item:
            d=item['round_dent'];d['radius']=max(.25,d['radius']);d['depth']=max(.022,d['depth'])
        if 'scratch' in item:
            item['scratch']['width']=max(.07,item['scratch']['width'])
            item['scratch']['depth']=max(.02,item['scratch']['depth'])
    return recipe


def repair_row(row,attempt):
    """Bounded shape/angle repair, keeping class, lighting, finish and location."""
    result=deepcopy(row);recipe=result['recipe']
    rng=random.Random(f"assembly-repair:{recipe['seed']}:{attempt}")
    for item in recipe['instances']:
        spec=item['spec'];spec['width']=min(.18,spec['width']*1.22)
        spec['arc']=min(65,spec['arc']*1.2);spec['depth']=min(.25,spec['depth']*1.45)
        elevation=42 if recipe['look']=='WARM_TRACK' else 36
        spec['angle']=(elevation+rng.uniform(-17,17)-math.degrees(recipe['initial_roll']))%360
        if 'round_dent' in item:
            d=item['round_dent'];d['radius']=min(.45,d['radius']*1.2);d['depth']=min(.065,d['depth']*1.5)
        if 'scratch' in item:
            d=item['scratch'];d['width']=min(.13,d['width']*1.25);d['depth']=min(.045,d['depth']*1.4)
    return result


def row_digest(row):
    return hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class AssemblyRejected(ValueError):
    def __init__(self,report):
        self.report=report
        super().__init__('Assembly failed strict visibility: '+str(report.get('sample_id')))
