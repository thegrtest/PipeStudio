"""RGB observability proxy, using one matched counterfactual per instance.

This is not a detector accuracy score. Thresholds are conservative engineering
defaults, recorded with every result; validate them against real annotations.
Only NumPy is required, including inside Blender's bundled Python.
"""
import numpy as np

VERSION='counterfactual-visibility-2'
DEFAULTS=dict(model_size=640,min_pixels=8,min_p90_codes=4.,min_changed_fraction=.15,
              min_component_pixels=6,noise_multiplier=3.,min_change_codes=2.,min_texture_ratio=1.5)


def resize(a,height,width):
    """Pixel-centre bilinear resize, with an area prefilter for downsampling."""
    a=np.asarray(a,dtype=np.float32)
    while a.shape[0]>=height*2 and a.shape[1]>=width*2:
        h,w=a.shape[:2];a=(a[:h//2*2:2,:w//2*2:2]+a[1:h//2*2:2,:w//2*2:2]
                          +a[:h//2*2:2,1:w//2*2:2]+a[1:h//2*2:2,1:w//2*2:2])*.25
    if a.shape[:2]==(height,width):return a.copy()
    ys=np.clip((np.arange(height)+.5)*a.shape[0]/height-.5,0,a.shape[0]-1)
    xs=np.clip((np.arange(width)+.5)*a.shape[1]/width-.5,0,a.shape[1]-1)
    y0=ys.astype(int);x0=xs.astype(int);y1=np.minimum(y0+1,a.shape[0]-1);x1=np.minimum(x0+1,a.shape[1]-1)
    fy=(ys-y0)[:,None];fx=(xs-x0)[None,:]
    if a.ndim==3:fy=fy[...,None];fx=fx[...,None]
    return ((a[y0[:,None],x0]*(1-fx)+a[y0[:,None],x1]*fx)*(1-fy)
            +(a[y1[:,None],x0]*(1-fx)+a[y1[:,None],x1]*fx)*fy)


def smooth(a):
    b=np.pad(a,((1,1),(1,1)),mode='edge')
    return (b[:-2,:-2]+2*b[:-2,1:-1]+b[:-2,2:]+2*b[1:-1,:-2]
            +4*b[1:-1,1:-1]+2*b[1:-1,2:]+b[2:,:-2]+2*b[2:,1:-1]+b[2:,2:])/16


def dilate(mask,radius=1):
    out=mask.copy()
    for _ in range(radius):
        b=np.pad(out,1)
        out=np.logical_or.reduce([b[y:y+mask.shape[0],x:x+mask.shape[1]] for y in range(3) for x in range(3)])
    return out


def largest_component(mask):
    # Limit flood-fill to the small support bounding box, not the full frame.
    ys,xs=np.nonzero(mask)
    if not len(xs):return 0
    todo=mask[ys.min():ys.max()+1,xs.min():xs.max()+1].copy();best=0
    h,w=todo.shape
    for y,x in zip(*np.nonzero(todo)):
        if not todo[y,x]:continue
        todo[y,x]=False;stack=[(y,x)];size=0
        while stack:
            yy,xx=stack.pop();size+=1
            for dy,dx in ((-1,0),(1,0),(0,-1),(0,1)):
                ny,nx=yy+dy,xx+dx
                if 0<=ny<h and 0<=nx<w and todo[ny,nx]:
                    todo[ny,nx]=False;stack.append((ny,nx))
        best=max(best,size)
    return best


def assess(beauty,control,mask,pipe_mask,other_masks=(),config=None):
    cfg={**DEFAULTS,**(config or {})}
    if set(cfg)!=set(DEFAULTS):raise ValueError('Unknown visibility control')
    for key,value in cfg.items():
        if not np.isfinite(value) or value<=0:raise ValueError('Invalid visibility control: '+key)
    if cfg['min_changed_fraction']>1:raise ValueError('Changed fraction must be <= 1')
    beauty=np.asarray(beauty);control=np.asarray(control);mask=np.asarray(mask,dtype=bool)
    if beauty.shape!=control.shape or beauty.shape[:2]!=mask.shape or beauty.shape[2]!=3:
        raise ValueError('Counterfactual and support dimensions differ')
    if not np.isfinite(beauty).all() or not np.isfinite(control).all():
        raise ValueError('Non-finite counterfactual pixels')
    h,w=mask.shape;scale=min(1.,cfg['model_size']/max(h,w));mh,mw=round(h*scale),round(w*scale)
    mask=resize(mask,mh,mw)>.35;pipe=resize(pipe_mask,mh,mw)>.5
    occupied=mask.copy()
    for other in other_masks:occupied|=resize(other,mh,mw)>.25
    luma=np.array([.2126,.7152,.0722])
    clean=resize(control,mh,mw)@luma*255
    delta=smooth(resize(beauty,mh,mw)@luma*255-clean)
    absolute=np.abs(delta);ys,xs=np.nonzero(mask)
    roi=np.zeros_like(mask)
    if len(xs):roi[max(0,ys.min()-16):min(mh,ys.max()+17),max(0,xs.min()-16):min(mw,xs.max()+17)]=True
    context=roi&pipe&~dilate(occupied,4)
    if context.sum()<32:context=pipe&~dilate(occupied,4)
    noise=absolute[context]
    baseline=float(np.median(noise)) if noise.size else 0.
    mad=float(np.median(np.abs(noise-baseline)))*1.4826 if noise.size else 0.
    threshold=baseline+max(cfg['min_change_codes'],cfg['noise_multiplier']*mad)
    changed=mask&(absolute>=threshold);count=int(mask.sum())
    p90=float(np.percentile(absolute[mask],90)) if count else 0.
    fraction=float(changed.sum()/count) if count else 0.
    component=largest_component(changed)
    # Geometry can shift grain without making its shape recognizable. Require
    # the low-frequency signed shading cue to beat the clean surface's local
    # texture at a comparable scale. This is separate from render-noise QA.
    low_clean=clean.copy();shape_delta=delta.copy()
    for _ in range(16):low_clean=smooth(low_clean)
    for _ in range(7):shape_delta=smooth(shape_delta)
    texture=float(np.percentile(np.abs(clean-low_clean)[mask],90)) if count else 0.
    shape_p90=float(np.percentile(np.abs(shape_delta[mask]),90)) if count else 0.
    texture_ratio=shape_p90/max(texture,1.)
    reasons=[]
    if count<cfg['min_pixels']:reasons.append('too_few_model_pixels')
    if p90<max(cfg['min_p90_codes'],threshold):reasons.append('weak_rgb_change')
    if fraction<cfg['min_changed_fraction']:reasons.append('insufficient_changed_support')
    if component<cfg['min_component_pixels']:reasons.append('no_coherent_local_cue')
    if texture_ratio<cfg['min_texture_ratio']:reasons.append('cue_buried_in_surface_texture')
    if noise.size<32:reasons.append('insufficient_noise_reference')
    return dict(version=VERSION,passed=not reasons,reasons=reasons,thresholds=cfg,
                model_dimensions=[mw,mh],support_pixels=count,p90_change_codes=round(p90,3),
                changed_fraction=round(fraction,4),largest_changed_component=component,
                shape_p90_change_codes=round(shape_p90,3),clean_texture_p90_codes=round(texture,3),
                shape_to_texture_ratio=round(texture_ratio,3),
                context_noise_median_codes=round(baseline,3),context_noise_mad_codes=round(mad,3),
                actual_change_threshold_codes=round(threshold,3))


class VisibilityRejected(ValueError):
    def __init__(self,report):
        self.report=report
        super().__init__('Defect has insufficient rendered evidence: '+str(report.get('sample_id')))


def repair_instances(row,failed_indices):
    """Bounded depth repair, preserving identity, class, footprint and nuisance.

    Deliberately do not brighten only positive frames or remove failed labels.
    """
    from copy import deepcopy
    candidate=deepcopy(row)
    for index in failed_indices:
        spec=candidate['instances'][index]['spec']
        spec['depth']=min(.25,max(spec['depth']*1.5,spec['depth']+.012))
    return candidate


def reposition_eval_gap(row, attempt):
    """Reproducible angle-only retry for the opt-in square-camera recipe."""
    from copy import deepcopy
    import random
    if row.get('sampling_profile')!='eval-gap' or row['settings']['environment']!='MACHINE' or not 1<=attempt<=3:
        raise ValueError('Invalid eval-gap visibility reposition')
    result=deepcopy(row);center=(180+row['settings']['camera_yaw'])%360
    for index,item in enumerate(result['instances']):
        rng=random.Random(f"brass-domain-v1:{row['settings']['seed']}:eval-gap-20260924-v1:reposition:{attempt}:{index}")
        item['spec']['angle']=(center+rng.uniform(-23,23))%360
    result['visibility_reposition_attempt']=attempt
    return result


def replay_visibility_repairs(planned, record):
    """Reconstruct only permitted recorded repairs for strict dataset validation."""
    from copy import deepcopy
    result=deepcopy(planned)
    reposition=record.get('visibility_reposition_attempt',0)
    histories=record.get('visibility_reposition_history',[])
    if not isinstance(reposition,int) or not 0<=reposition<=planned.get('visibility_reposition_limit',0) or len(histories)!=reposition:
        raise ValueError('Invalid reposition history')
    if reposition:
        for index,entry in enumerate(histories):
            if entry.get('attempt')!=index or entry.get('report',{}).get('passed') is not False:
                raise ValueError('Reposition history must document failed candidates')
        result=reposition_eval_gap(result,reposition)
    repairs=record.get('visibility_repair_history',[])
    if len(repairs)>2:raise ValueError('Too many depth repairs')
    for index,entry in enumerate(repairs):
        if entry.get('attempt')!=index or entry.get('instances')!=result['instances']:
            raise ValueError('Depth repair history disagrees with planned geometry')
        report=entry.get('report',{})
        if report.get('passed') is not False:raise ValueError('Depth repair requires a failed visibility report')
        failed=[r['instance_index'] for r in report['instances'] if not r['passed']]
        if not failed or any(not isinstance(i,int) or not 0<=i<len(result['instances']) for i in failed):
            raise ValueError('Invalid failed instance indices')
        result=repair_instances(result,failed)
    if result.get('instances') and 'spec' in result['instances'][0]:
        result['settings'].update(result['instances'][0]['spec'])
    return result
