"""Seeded, thin dried-soap films in pipe surface coordinates.

Reference: August 12/13 camera captures supplied from TestDataset. Shape and
color are procedural; no real image or cut-out is used as a render texture.
"""
import math
import random

VERSION = 'soap-dried-film-3'
SUBTYPES = ('dried_island', 'faint_film', 'coalesced_residue')


def sample_parameters(seed, subtype):
    if subtype not in SUBTYPES:
        raise ValueError('Unsupported dried-soap subtype: ' + subtype)
    rng = random.Random(f'soap-film-material:{seed}:{subtype}')
    # A thin pale ochre/cream deposit, illuminated by the machine's existing
    # lamps. The partially mixed base shader preserves metallic drawing marks.
    tint = rng.uniform(.88, 1.08)
    return dict(color=[.89*tint, .82*tint, .205*tint, 1.0],
                roughness=rng.uniform(.47, .61), metallic=.48,
                edge_width=rng.uniform(.055, .105) if subtype != 'faint_film' else rng.uniform(.15, .24))


def coverage(u, v, spot):
    """Return material alpha and its conservative visible-support mask.

    Inputs are normalized surface coordinates (not screen pixels), so spots
    wrap and foreshorten with the same mesh and camera as the brass.
    """
    import numpy as np
    subtype = spot['subtype']
    params = sample_parameters(spot['seed'], subtype)
    rng = random.Random(f'soap-film-shape:{spot["seed"]}:{subtype}')
    u, v = np.asarray(u), np.asarray(v)
    field = np.zeros(np.broadcast_shapes(u.shape, v.shape), dtype=np.float64)
    lobes = 3 if subtype == 'coalesced_residue' else 1
    for index in range(lobes):
        cx = (index-1)*.43 if lobes > 1 else 0.
        cy = rng.uniform(-.15, .15) if lobes > 1 else 0.
        sx = rng.uniform(.51, .67) if lobes > 1 else rng.uniform(.78, .94)
        sy = rng.uniform(.57, .82) if lobes > 1 else rng.uniform(.77, .98)
        x, y = (u-cx)/sx, (v-cy)/sy
        theta = np.arctan2(y, x)
        radius = np.hypot(x, y)
        amplitude = .035 if subtype == 'faint_film' else .11
        edge = np.ones_like(radius)
        for frequency, gain in ((3, 1.), (5, .65), (9, .26), (15, .09)):
            edge += amplitude*gain*np.sin(frequency*theta+rng.uniform(0, math.tau))
        # Broad menisci with locally ragged edges, without checkerboard speckles.
        t = np.clip((edge-radius)/params['edge_width']+.5, 0, 1)
        patch = t*t*(3-2*t)
        field = np.maximum(field, patch)
    # Nonperiodic-looking, low-contrast thickness changes inside the film.
    thickness = np.full_like(field, .90)
    for frequency, gain in ((2.1, .055), (4.8, .032), (10.7, .014)):
        phi, phase = rng.uniform(0, math.tau), rng.uniform(0, math.tau)
        thickness += gain*np.sin((u*math.cos(phi)+v*math.sin(phi))*frequency+phase)
    alpha = np.clip(field*thickness*spot['strength'], 0, .85).astype(np.float32)
    # Keep a soft optical boundary; exclude nearly transparent fringe from
    # the label. The renderer later clips this support by actual visibility.
    support = (alpha >= .11).astype(np.float32)
    return alpha, support
