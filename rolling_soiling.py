"""Seeded normal contamination, independent of the geometric defect recipe."""
import random


def assign(items, options, seed):
    if not options.get('mix_soiling', False):
        return
    dirty = max(0., min(1., options.get('dirty_fraction', .5)))
    strength = options.get('dirt_strength', 1.)
    rng = random.Random(seed + 836917)
    # Stratify each group so a normal row contains both appearance extremes.
    for offset in range(0, len(items), 6):
        group = items[offset:offset + 6]
        count = len(group)
        heavy = min(count, round(count * dirty))
        clean = round((count - heavy) * .67)
        states = ['heavy'] * heavy + ['clean'] * clean + ['light'] * (count - heavy - clean)
        rng.shuffle(states)
        for item, state in zip(group, states):
            item['normal_appearance'] = dict(version=1, category=state, seed=rng.randrange(1, 100000000),
                strength=strength * rng.uniform(.82, 1.18),
                palette=rng.choice(['dry_dust', 'dark_grime', 'mixed']), label_policy='normal_not_defect')


def material_parameters(base, item):
    appearance = item.get('normal_appearance')
    if not appearance:
        return base
    p = dict(base)
    category = appearance['category']
    p['dust_amount'] = {'clean': .008, 'light': .22, 'heavy': .95}[category]
    p['groove_residue'] = {'clean': .08, 'light': .5, 'heavy': 1.}[category]
    return p


def apply(mat, appearance):
    """Object-space matte soil preserves ribs; label passes replace this shader."""
    if not appearance:
        return
    mat['normal_soiling'] = appearance['category']
    mat['normal_soiling_seed'] = appearance['seed']
    mat['normal_soiling_label_policy'] = 'normal_not_defect'
    if appearance['category'] == 'clean':
        return
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    # Matte particles need one diffuse lobe, not another layered Principled
    # shader. Keep the already layered brass below Cycles' closure limit.
    existing_dust = nodes.get('Matte normal dust and debris')
    if existing_dust and existing_dust.type == 'BSDF_PRINCIPLED':
        diffuse_dust = nodes.new('ShaderNodeBsdfDiffuse'); diffuse_dust.name = 'Normal diffuse dust grains'
        diffuse_dust.inputs['Color'].default_value = existing_dust.inputs['Base Color'].default_value
        diffuse_dust.inputs['Roughness'].default_value = .65
        if existing_dust.inputs['Normal'].is_linked:
            links.new(existing_dust.inputs['Normal'].links[0].from_socket, diffuse_dust.inputs['Normal'])
        for link in list(existing_dust.outputs[0].links): links.new(diffuse_dust.outputs[0], link.to_socket)
        nodes.remove(existing_dust)
    coords = nodes.new('ShaderNodeTexCoord'); coords.name = 'Soil moves with this shell'
    shift = nodes.new('ShaderNodeVectorMath'); shift.operation = 'ADD'
    rng = random.Random(appearance['seed'])
    shift.inputs[1].default_value = tuple(rng.uniform(-100, 100) for _ in range(3))
    links.new(coords.outputs['Object'], shift.inputs[0])

    def math(name, operation, a, b):
        node = nodes.new('ShaderNodeMath'); node.name = name; node.operation = operation
        for value, socket in ((a, node.inputs[0]), (b, node.inputs[1])):
            if isinstance(value, (float, int)): socket.default_value = value
            else: links.new(value, socket)
        return node.outputs[0]

    def noise(name, scale, vector=None):
        node = nodes.new('ShaderNodeTexNoise'); node.name = name
        node.inputs['Scale'].default_value = scale; node.inputs['Detail'].default_value = 3
        links.new(vector if vector is not None else shift.outputs[0], node.inputs['Vector'])
        return node.outputs['Fac']

    def remap(name, value, start, end, low, high):
        node = nodes.new('ShaderNodeMapRange'); node.name = name; node.clamp = True
        for key, val in [('From Min', start), ('From Max', end), ('To Min', low), ('To Max', high)]:
            node.inputs[key].default_value = val
        links.new(value, node.inputs['Value'])
        return node.outputs[0]

    stretch = nodes.new('ShaderNodeVectorMath'); stretch.operation = 'MULTIPLY'
    stretch.inputs[1].default_value = (1.5, .48, 1.5)
    links.new(shift.outputs[0], stretch.inputs[0])
    broad = noise('Uneven handled soil patches', 4.2, stretch.outputs[0])
    breakup = noise('Broken clumps and flecks', 38)
    grains = noise('Fine adhered soil grains', 185)
    heavy = appearance['category'] == 'heavy'
    patch = remap('Patchy normal dirt coverage', broad, .37 if heavy else .59, .65 if heavy else .76, 0, 1)
    patch = math('Broken patch boundaries', 'MULTIPLY', patch,
                 remap('Clump breakup', breakup, .25, .68, .18, 1.))
    valley = nodes.get('Fine residue channel')
    if valley:
        trapped = math('More dirt trapped in grooves', 'MULTIPLY', valley.outputs[0],
                       remap('Interrupted trapped dirt', broad, .38, .63, 0, .33 if heavy else .08))
        patch = math('Patches and groove deposits', 'ADD', patch, trapped)
    coverage = math('Soiling intensity', 'MULTIPLY', patch, appearance['strength'] * (1.3 if heavy else .6))
    coverage = math('Keep exposed substrate between clumps', 'MINIMUM', coverage, .93)
    colors = {
        'dry_dust': ((.095, .064, .033, 1), (.43, .34, .21, 1)),
        'dark_grime': ((.015, .011, .007, 1), (.16, .115, .065, 1)),
        'mixed': ((.032, .019, .009, 1), (.34, .255, .14, 1)),
    }
    color = nodes.new('ShaderNodeMixRGB'); color.name = 'Natural soil color variation'
    color.inputs[1].default_value, color.inputs[2].default_value = colors[appearance['palette']]
    links.new(breakup, color.inputs[0])
    soil = nodes.new('ShaderNodeBsdfDiffuse'); soil.name = 'Normal matte soil, not a defect'
    links.new(color.outputs[0], soil.inputs['Color'])
    soil.inputs['Roughness'].default_value = .65
    bump = nodes.new('ShaderNodeBump'); bump.name = 'Microscopic soil relief over the existing ribs'
    bump.inputs['Strength'].default_value = .22; bump.inputs['Distance'].default_value = .0007
    links.new(grains, bump.inputs['Height'])
    ribs = nodes.get('Fine groove shoulder normals')
    if ribs: links.new(ribs.outputs[0], bump.inputs['Normal'])
    links.new(bump.outputs[0], soil.inputs['Normal'])
    output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
    original = output.inputs['Surface'].links[0].from_socket
    mix = nodes.new('ShaderNodeMixShader'); mix.name = 'Normal dirt excluded from all defect labels'
    links.new(coverage, mix.inputs[0]); links.new(original, mix.inputs[1]); links.new(soil.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs['Surface'])
