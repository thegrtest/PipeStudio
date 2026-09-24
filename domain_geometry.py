"""One watertight pipe mesh carrying separately labeled defect instances."""
import math

from geometry import PipeSpec, displacement, axial_displacement, radius_at, sampling_grid


BODY_KEYS = ('length','radius','end_ratio','wall_ratio','taper_start','taper_end',
             'body_taper','shoulder_roundness','seed')


def _merge(values):
    merged=[]
    for value in sorted(values):
        if not merged or value-merged[-1]>1e-10:
            merged.append(value)
    return merged


def _bounded_sum(delta, nominal):
    # Leave isolated small/medium defects exactly unchanged. Above 20% of
    # local radius, a C1 shoulder smoothly approaches a strict 24.9% bound.
    # This retains a positive inner bore even for overlapping extreme defects.
    magnitude=abs(delta)
    onset=.20*nominal
    if magnitude<=onset:
        return delta
    return math.copysign(onset+.049*nominal*math.tanh((magnitude-onset)/(.049*nominal)),delta)


def instance_grid(base_spec, instances, axial=144, radial=128):
    """Union local grids so each narrow feature retains its own refinement.

    A typical two-instance mesh remains near 400k paired-skin vertices. No
    hard decimation is applied when a complex rotated pair needs more; local
    crease sampling takes precedence over an arbitrary mesh budget.
    """
    base=base_spec if isinstance(base_spec,PipeSpec) else PipeSpec(**base_spec)
    base.validate()
    ts,angles=sampling_grid(base,axial,radial,adaptive=False)
    specs=[]
    for instance in instances:
        if instance['kind'] in ('FOLD','DENT'):
            spec=PipeSpec(**instance['spec']).validate()
            if any(getattr(spec,key)!=getattr(base,key) for key in BODY_KEYS):
                raise ValueError('All instances must deform the same body and use its specimen seed.')
            if spec.defect!=instance['kind']:
                raise ValueError('Geometric instance kind does not match its specification.')
            added_t,added_angles=sampling_grid(spec,axial,radial,adaptive=True)
            specs.append(spec)
        elif instance['kind'] in ('SOAP_STAIN','OIL_STAIN'):
            spot=instance['spot']
            if (not .03<=spot['position']<=.97 or not 0<=spot['angle']<=360
                    or not .003<=spot['axial_size']<=.12 or not 3<=spot['angular_size']<=65):
                raise ValueError('Invalid stain surface coordinates.')
            # Stains have no displaced geometry. Use a virtual dimple only to
            # resolve the attribute field on the shared visible pipe surface.
            values={key:getattr(base,key) for key in PipeSpec.__dataclass_fields__}
            values.update(defect='DENT',defect_style='DEFAULT',depth=.05,
                          position=spot['position'],angle=spot['angle'],
                          width=max(.01,spot['axial_size']),arc=max(8,spot['angular_size']),
                          defect_rotation=0)
            added_t,added_angles=sampling_grid(PipeSpec(**values),axial,radial,adaptive=True)
            half_t=spot['axial_size']*1.8
            low,high=max(0,spot['position']-half_t),min(1,spot['position']+half_t)
            # Additional local rings resolve thin soap-ring rims and speckles.
            added_t += [low+(high-low)*i/108 for i in range(109)]
            center=math.radians(spot['angle'])
            half_angle=math.radians(spot['angular_size'])*1.8
            added_angles += [(center-half_angle+2*half_angle*i/108)%math.tau for i in range(109)]
            specs.append(None)
        else:
            raise ValueError('Unknown instance kind.')
        ts.extend(added_t)
        angles.extend(added_angles)
    angles=[0.0 if min(value,math.tau-value)<1e-10 else value for value in angles]
    return _merge(ts),_merge(angles),specs


def build_instances(base_spec, instances, axial=144, radial=128, omit_instance=None):
    """Return vertices, faces, union mask, face regions, instance masks.

    Instance masks are aligned to the input list, including all-zero entries
    for material stains. The render worker fills their independent spot
    masks. Inner skins never receive support labels. Both skins receive the
    identical combined radial displacement, preserving wall thickness.
    The base specification defines the body only; its own defect is ignored
    unless supplied explicitly in the instances list.
    """
    base=base_spec if isinstance(base_spec,PipeSpec) else PipeSpec(**base_spec)
    ts,angles,specs=instance_grid(base,instances,axial,radial)
    rim_specs=[s for s in specs if s is not None and s.defect_style=='ROLLED_LIP']
    if len(rim_specs)>1:
        raise ValueError('At most one rolled rim instance is supported per pipe; other defect styles may be mixed.')
    # Keep the FULL refinement grid when making a counterfactual. Removing an
    # instance before sampling changes topology/normals and invalidates RGB QA.
    if omit_instance is not None:
        if not isinstance(omit_instance,int) or not 0<=omit_instance<len(instances):
            raise ValueError('Counterfactual instance index is out of range')
        specs[omit_instance]=None
    rim=next((s for s in specs if s is not None and s.defect_style=='ROLLED_LIP'),None)
    vertices=[]
    masks=[]
    individual=[[] for _ in instances]
    for t in ts:
        nominal=radius_at(t,base)
        for theta in angles:
            values=[displacement(t,theta,spec) if spec is not None else (0.0,0.0) for spec in specs]
            delta=_bounded_sum(sum(value[0] for value in values),nominal)
            r=nominal+delta
            axial_offset=axial_displacement(t,theta,rim) if rim is not None else 0.
            vertices.append(((t-.5)*base.length+axial_offset,r*math.cos(theta),r*math.sin(theta)))
            masks.append(float(any(value[1] for value in values)))
            for target,value in zip(individual,values):
                target.append(value[1])
    half=len(vertices)
    thickness=base.radius*base.wall_ratio
    # Reuse the computed outer radial positions to avoid evaluating complex
    # displacement functions a second time for the unlabelled inner wall.
    for x,y,z in vertices[:half]:
        r=math.hypot(y,z)
        factor=(r-thickness)/r
        vertices.append((x,y*factor,z*factor))
    masks.extend([0.0]*half)
    for target in individual:
        target.extend([0.0]*half)
    radial=len(angles)
    axial=len(ts)-1
    faces=[]
    regions=[]
    for i in range(axial):
        for j in range(radial):
            k=(j+1)%radial
            a,b,c,d=i*radial+j,(i+1)*radial+j,(i+1)*radial+k,i*radial+k
            faces.append((a,d,c,b));regions.append('outer')
            faces.append((a+half,b+half,c+half,d+half));regions.append('inner')
    for j in range(radial):
        k=(j+1)%radial
        faces.append((j,j+half,k+half,k));regions.append('rim')
        a,b=axial*radial+j,axial*radial+k
        faces.append((a,b,b+half,a+half));regions.append('rim')
    return vertices,faces,masks,regions,individual
