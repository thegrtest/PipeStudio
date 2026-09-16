"""Photometric export gate, measured on final display RGB and visible masks.

This detects near-clipped white/yellow highlights, not general visibility or
model accuracy. Keep ordinary metallic reflections and non-clipped soap residue.
"""
import numpy as np

VERSION = 'defect-glare-1'
LIMITS = dict(defect_fraction=.10, context_fraction=.22, pipe_fraction=.035)
# Fixed candidates preserve specimen identity and nuisance random seeds.
LIGHT_STEPS = ((1., 1., 0.), (.60, .90, 0.), (.35, .78, 0.),
               (.20, .65, -.15), (.11, .50, -.35), (.06, .35, -.60))


def assess(rgb, masks, pipe_mask=None):
    """RGB floats in display space [0,1]; boolean masks in image coordinates."""
    rgb = np.asarray(rgb, dtype=np.float32)
    if rgb.ndim != 3 or rgb.shape[2] < 3 or not np.isfinite(rgb).all():
        raise ValueError('Invalid RGB raster for glare assessment')
    rgb = rgb[:, :, :3]
    if rgb.min() < 0 or rgb.max() > 1.00001:
        raise ValueError('Glare assessment requires display RGB in [0,1]')
    hot = ((rgb.min(axis=2) > .94) |
           ((rgb[:, :, 0] > .98) & (rgb[:, :, 1] > .98) & (rgb[:, :, 2] > .60)))
    silhouette = np.ones(hot.shape, bool) if pipe_mask is None else np.asarray(pipe_mask, bool)
    if silhouette.shape != hot.shape or not silhouette.any():
        raise ValueError('Missing or mismatched pipe mask')
    checks = []
    for index, support in enumerate(masks):
        support = np.asarray(support, bool)
        if support.shape != hot.shape or not support.any():
            raise ValueError('Missing or mismatched defect mask')
        ys, xs = np.nonzero(support)
        # Nearby brass must retain detail too; a tiny dark fold within a white
        # hotspot is unacceptable even when the fold pixels themselves are dark.
        pad = max(2, round(min(xs.max()-xs.min()+1, ys.max()-ys.min()+1)*.5))
        x0,x1 = max(0,xs.min()-pad), min(hot.shape[1],xs.max()+pad+1)
        y0,y1 = max(0,ys.min()-pad), min(hot.shape[0],ys.max()+pad+1)
        context = silhouette[y0:y1,x0:x1]
        overlap = float(hot[support].mean())
        nearby = float(hot[y0:y1,x0:x1][context].mean()) if context.any() else 0.
        checks.append(dict(instance_index=index, clipped_fraction=round(overlap,6),
                           context_clipped_fraction=round(nearby,6),
                           passed=overlap<=LIMITS['defect_fraction'] and nearby<=LIMITS['context_fraction']))
    total = float(hot[silhouette].mean()) if pipe_mask is not None else None
    passed = all(c['passed'] for c in checks) and (total is None or total<=LIMITS['pipe_fraction'])
    return dict(version=VERSION, passed=passed, limits=dict(LIMITS), instances=checks,
                pipe_clipped_fraction=None if total is None else round(total,6))
