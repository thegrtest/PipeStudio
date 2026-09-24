"""Sparse object-space handling detail, independent of diagnostic defects.

R/G/B encode reflectance multiplier, roughness offset and shallow normal detail.
These are newly sampled physical-scale fields, not copies of reference pixels.
"""
import json
import math
import numpy as np

VERSION = 'inspection-forming-detail-6'
WIDTH, HEIGHT = 1536, 1024


def synthesize_details(seed, width=WIDTH, height=HEIGHT, length=8., radius=.9,
                       wear=.35, finish_marks=.3, taper_start=.8, taper_end=.88,
                       end_ratio=.68):
    """Return bounded RGBA data and a small audit of the sampled finish.

    Sparse marks cluster around randomly sampled contact areas. Quiet areas
    remain between them. Angular wrapping keeps the cylindrical seam continuous.
    Color contrast is deliberately modest: conspicuous oil/soap patches still
    belong to the separate labeled defect generator.
    """
    if width < 32 or height < 32 or length <= 0 or radius <= 0:
        raise ValueError('Positive physical dimensions and at least 32 texels are required.')
    if not 0 <= taper_start < taper_end <= 1 or not 0 < end_ratio <= 1:
        raise ValueError('Invalid tapered surface proportions.')
    wear = float(np.clip(wear, 0, 1))
    marks = float(np.clip(finish_marks, 0, 1))
    rng = np.random.default_rng([int(seed), 915051])
    circumference = math.tau * radius
    dx, dy = length / width, circumference / height
    planes = np.zeros((height, width, 3), dtype=np.float32)
    contacts = [(rng.uniform(.08, .92)*length, rng.uniform(0, circumference))
                for _ in range(int(rng.integers(3, 7)))]

    def location(clustered=True):
        if clustered and rng.random() < .68:
            cx, cy = contacts[int(rng.integers(len(contacts)))]
            return (float(np.clip(cx+rng.normal(0, .40)*radius, .01, length-.01)),
                    float((cy+rng.normal(0, .24)*radius) % circumference))
        return rng.uniform(.01, length-.01), rng.uniform(0, circumference)

    def stamp(cx, cy, a, b, angle, amplitudes, stroke=False, curve=0.):
        # Bound work to the mark's footprint, with periodic angular indices.
        ca, sa = math.cos(angle), math.sin(angle)
        a, b = max(a, dx*.55), max(b, dy*.55)
        ex = min(length, 2.2*(abs(ca)*a+abs(sa)*b))
        ey = min(circumference*.49, 2.2*(abs(sa)*a+abs(ca)*b))
        ix = np.arange(max(0, int((cx-ex)/dx)), min(width, int((cx+ex)/dx)+1))
        iy = np.arange(int(math.floor((cy-ey)/dy)), int(math.ceil((cy+ey)/dy))+1)
        if not len(ix) or not len(iy):
            return
        x = (ix[None, :]+.5)*dx-cx
        y = (iy[:, None]+.5)*dy-cy
        u = (x*ca+y*sa)/a
        v = (-x*sa+y*ca)/b-curve*u*u
        field = np.exp(-2*(u**4 if stroke else u*u)-2*v*v).astype(np.float32)
        wrapped = iy % height
        for channel, amount in enumerate(amplitudes):
            planes[wrapped[:, None], ix[None, :], channel] += field*amount

    # Soft local polishing patches change the reflected light more than color.
    # Their shape, extent and sign differ; no all-over equally strong mottling.
    patch_count = int(rng.integers(10, 19))
    for _ in range(patch_count):
        x, y = location()
        sign = rng.choice([-1., 1.])
        stamp(x, y, rng.uniform(.18, .95)*radius, rng.uniform(.07, .32)*radius,
              rng.normal(0, .18), (sign*rng.uniform(.025, .075),
              -sign*rng.uniform(.045, .15)*(.65+wear*.5), rng.uniform(-.06, .06)))

    # Distinct short drawing/contact traces, with rounded uneven ends and a
    # minority of crossing angles. No Voronoi network or full-length stripes.
    trace_count = int(rng.integers(45, 75)+marks*120)
    for _ in range(trace_count):
        x, y = location()
        angle = rng.normal(0, .055) if rng.random() < .8 else rng.uniform(-.65, .65)
        a = float(np.exp(rng.uniform(math.log(.025), math.log(.62))))*radius
        b = rng.uniform(.0018, .0065)*radius
        stamp(x, y, a, b, angle, (rng.uniform(.10, .27)*(.6+marks),
              -rng.uniform(.045, .13), -rng.uniform(.035, .11)), True, rng.uniform(-.35, .35))

    # A few low-contrast irregular pinpricks at approximately 1–4 native camera
    # pixels. They are surface finish variation, never crater displacement.
    speck_count = int(rng.integers(8, 19)+marks*65)
    for _ in range(speck_count):
        x, y = location()
        a = rng.uniform(.006, .020)*radius
        stamp(x, y, a, a*rng.uniform(.55, 1.4), rng.uniform(0, math.tau),
              (-rng.uniform(.25, .60), rng.uniform(.02, .07), -.015))

    # Intermittent cut-rim burnishing: finite arcs rather than a perfect ring.
    for _ in range(int(rng.integers(4, 9))):
        x = rng.choice([0., length])
        stamp(x, rng.uniform(0, circumference), rng.uniform(.012, .035)*radius,
              rng.uniform(.06, .30)*radius, 0, (.06, -.12, .02))

    # Forming history is distinct from handling damage. Development crops show
    # interrupted axial tracks, then finer circumferential rubs on the neck.
    # Sample them in physical surface coordinates so a camera rotation does not
    # rotate the finish relative to the part. Separate RNG preserves handling
    # identity when proportions change; defect class never enters this field.
    forming = np.random.default_rng([int(seed), 619032])
    track_count = int(forming.integers(24, 39))
    track_segments = 0
    for _ in range(track_count):
        y = forming.uniform(0, circumference)
        center = forming.uniform(.12, .86)*length
        extent = forming.uniform(.85, 2.25)*radius
        b = forming.uniform(.009, .035)*radius
        contrast = forming.uniform(.035, .095)*forming.choice([-1., 1.])
        slope = forming.normal(0, .009)
        # Unequal finite fragments share a drawing direction, not identical
        # parallel stripes extending from end to end.
        for _ in range(int(forming.integers(2, 5))):
            x = float(np.clip(center+forming.normal(0, extent*.65), 0, length))
            stamp(x, y+forming.normal(0, b*.35), extent*forming.uniform(.30, .75),
                  b*forming.uniform(.6, 1.3), slope,
                  (contrast, -contrast*.45, contrast*.10), False, forming.uniform(-.3, .3))
            track_segments += 1

    # A weak continuous draw field ties those sparse marks together. Use a
    # periodic angular spectrum and physical correlation lengths, rather than
    # stripes or isotropic cloud noise. Fade it over the shoulder into the neck.
    fx = np.fft.rfftfreq(width, d=dx)[None, :]
    fy = np.fft.fftfreq(height, d=dy)[:, None]
    spectrum = np.exp(-.5*((math.tau*.65*radius*fx)**2+(math.tau*.028*radius*fy)**2))
    spectrum *= 1-np.exp(-(np.abs(fy)*radius/2.)**4)
    field = np.fft.irfft2(np.fft.rfft2(forming.normal(size=(height, width)))*spectrum,
                         s=(height, width))
    field = np.clip(field/max(float(field.std()), 1e-8), -2.5, 2.5)
    axial = (np.arange(width)+.5)/width
    fade = np.clip((taper_end-axial)/(taper_end-taper_start), 0, 1)
    field *= (.3+.7*fade[None, :])
    planes[..., 0] += field*.032
    planes[..., 1] -= field*.050

    # Shoulder burnishing is irregular around the circumference. This is a
    # shallow material response, not a new dent or an unlabelled stain.
    shoulder_center = (taper_start+taper_end)*length*.5
    shoulder_half = (taper_end-taper_start)*length*.55
    for _ in range(9):
        stamp(shoulder_center+forming.normal(0, shoulder_half*.20),
              forming.uniform(0, circumference), max(dx, shoulder_half),
              forming.uniform(.12, .45)*radius, 0, (.018, -.045, 0.))
    neck_rubs = int(forming.integers(6, 12)) if taper_end < .99 else 0
    for _ in range(neck_rubs):
        stamp(forming.uniform(taper_end, 1)*length, forming.uniform(0, circumference),
              forming.uniform(.0025, .007)*radius,
              forming.uniform(.12, .44)*radius/end_ratio, 0,
              (forming.uniform(.015, .045), -.035, -.008))

    # Only slightly shift the background grain's local strength. Broad color
    # fields and sparse marks have separate effects in the shader.
    result = np.ones((height, width, 4), dtype=np.float32)
    result[..., 0] = np.clip(1.+planes[..., 0], .44, 1.32)/1.5
    result[..., 1] = np.clip(.5+planes[..., 1], .25, .75)
    result[..., 2] = np.clip(.5+planes[..., 2], .30, .70)
    audit = dict(version=VERSION, seed=int(seed), contacts=len(contacts),
                 traces=trace_count, specks=speck_count, patches=patch_count,
                 physical_length=length, physical_radius=radius,
                 forming_tracks=track_count, forming_segments=track_segments,
                 neck_rubs=neck_rubs, taper_start=taper_start, taper_end=taper_end,
                 end_ratio=end_ratio,
                 draw_correlation_scene_units=[.65*radius, .028*radius],
                 draw_reflectance_amplitude=.032, draw_roughness_amplitude=.050,
                 finish_marks=marks, wear=wear, texture_size=[width, height])
    return result, audit


def configure_local_details(material, settings):
    import bpy
    def value(k, d):
        return settings.get(k, d) if isinstance(settings, dict) else getattr(settings, k, d)
    if value('product_mode', 'PIPE') != 'PIPE':
        return
    nodes = material.node_tree.nodes
    link = material.node_tree.links.new
    def node(kind, name):
        n = nodes.get(name)
        if n is None:
            n = nodes.new(kind); n.name = n.label = name
        return n
    params = dict(seed=int(value('seed', 42)), length=float(value('length', 8)),
                  radius=float(value('radius', .9)), wear=float(value('wear', .35)),
                  finish_marks=float(value('finish_marks', .3)),
                  taper_start=float(value('taper_start', .8)),
                  taper_end=float(value('taper_end', .88)),
                  end_ratio=float(value('end_ratio', .68)))
    signature = json.dumps(dict(version=VERSION, **params), sort_keys=True)
    tex = node('ShaderNodeTexImage', 'Inspection local detail maps')
    if tex.image is None:
        tex.image = bpy.data.images.new('PS_LocalBrassDetails', width=WIDTH, height=HEIGHT, float_buffer=True)
        tex.image.colorspace_settings.name = 'Non-Color'
    im = tex.image
    if im.get('detail_signature') != signature:
        pixels, audit = synthesize_details(**params)
        im.pixels.foreach_set(pixels.ravel()); im.update(); im.pack()
        im['detail_signature'] = signature
        im['detail_audit'] = json.dumps(audit, sort_keys=True)
    tex.interpolation = 'Linear'; tex.extension = 'REPEAT'
    link(nodes['Inspection cylindrical grain coordinates'].outputs[0], tex.inputs['Vector'])
    channels = node('ShaderNodeSeparateColor', 'Inspection local detail channels'); channels.mode = 'RGB'
    link(tex.outputs['Color'], channels.inputs[0])

    multiplier = node('ShaderNodeMath', 'Inspection localized reflectance'); multiplier.operation = 'MULTIPLY'
    multiplier.inputs[1].default_value = 1.5
    link(channels.outputs['Red'], multiplier.inputs[0])
    offset = node('ShaderNodeMath', 'Inspection localized roughness'); offset.operation = 'SUBTRACT'
    offset.inputs[1].default_value = .5
    link(channels.outputs['Green'], offset.inputs[0])
    bump = node('ShaderNodeBump', 'Inspection localized normal detail')
    bump.inputs['Strength'].default_value = .32
    bump.inputs['Distance'].default_value = .012*params['radius']/.9
    link(channels.outputs['Blue'], bump.inputs['Height'])
    link(nodes['GrainBump'].outputs['Normal'], bump.inputs['Normal'])

    # Burnishing also quiets the fine grain in that contact patch. This varies
    # local detail density instead of overlaying the same noise everywhere.
    activity = node('ShaderNodeMapRange', 'Inspection grain activity'); activity.clamp = True
    activity.inputs['From Min'].default_value = .30; activity.inputs['From Max'].default_value = .65
    activity.inputs['To Min'].default_value = .35; activity.inputs['To Max'].default_value = 1.5
    link(channels.outputs['Green'], activity.inputs['Value'])
    centered = node('ShaderNodeMath', 'Inspection centered statistical grain'); centered.operation = 'SUBTRACT'
    centered.inputs[1].default_value = .5
    link(nodes['Inspection statistical grain'].outputs['Color'], centered.inputs[0])
    local_grain = node('ShaderNodeMath', 'Inspection local grain activity'); local_grain.operation = 'MULTIPLY_ADD'
    local_grain.inputs[2].default_value = .5
    link(centered.outputs[0], local_grain.inputs[0]); link(activity.outputs[0], local_grain.inputs[1])
    link(local_grain.outputs[0], nodes['Inspection statistical grain multiplier'].inputs['Value'])

    for shader in ('BrassShader', 'PolishedBrass', 'DullOxide'):
        mixed = node('ShaderNodeMixRGB', 'Inspection localized color '+shader); mixed.blend_type = 'MULTIPLY'
        mixed.inputs[0].default_value = 1.
        link(nodes['Inspection measured grain '+shader].outputs[0], mixed.inputs[1])
        link(multiplier.outputs[0], mixed.inputs[2]); link(mixed.outputs[0], nodes[shader].inputs['Base Color'])
        rough = node('ShaderNodeMath', 'Inspection local roughness '+shader); rough.operation = 'ADD'; rough.use_clamp = True
        if shader == 'BrassShader':
            link(nodes['Inspection varied roughness'].outputs[0], rough.inputs[0])
        elif shader == 'PolishedBrass':
            rough.inputs[0].default_value = max(.25, value('roughness', .45)*.76+.035)
        else:
            rough.inputs[0].default_value = .60+.18*params['wear']
        link(offset.outputs[0], rough.inputs[1]); link(rough.outputs[0], nodes[shader].inputs['Roughness'])
        link(bump.outputs['Normal'], nodes[shader].inputs['Normal'])
    # Sparse analytic traces supersede the previous equal-density cellular
    # scratch web. Keep fine statistical grain underneath the local details.
    nodes['Inspection trace amount'].inputs[1].default_value = 0.
    material['domain_material_version'] = VERSION
    material['detail_audit'] = im['detail_audit']
