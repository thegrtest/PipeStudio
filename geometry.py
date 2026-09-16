"""Deterministic, dimensionless hollow pipe geometry. No Blender dependency."""
from dataclasses import dataclass, asdict
import math
import random


DENT_STYLES = ("DEFAULT", "ELONGATED", "DOUBLE", "OBLIQUE", "WRINKLED", "BRANCHED")
FOLD_STYLES = DENT_STYLES + ("AXIAL_PINCH",)
DEFECT_STYLES = FOLD_STYLES + ("SHALLOW_SWEEP", "SOFT_BUCKLE")
# Real shoulder/neck folds are usually short axial pinches. Retain every older
# family, including diagonal and branching folds, as a substantial minority.
FOLD_STYLE_WEIGHTS = (0.072, 0.080, 0.064, 0.056, 0.064, 0.064, 0.600)


def _weighted_choice(rng, values, weights):
    total = sum(weights)
    threshold = rng.random() * total
    for value, weight in zip(values, weights):
        threshold -= weight
        if threshold <= 0:
            return value
    return values[-1]


def _sample_fold_rotation(rng, defect_style):
    """Return a fold rotation with stronger angular and shape diversity."""
    roll = rng.random()
    if defect_style == "AXIAL_PINCH":
        # This profile is axial at zero rotation; legacy fold profiles are
        # circumferential at zero. Do not rotate a pinch through another 90°.
        return rng.uniform(-14, 14) if roll < 0.85 else rng.choice((-1, 1)) * rng.uniform(14, 28)
    if roll < 0.20:
        angle = rng.uniform(36, 74)
    elif roll < 0.40:
        angle = rng.uniform(-74, -38)
    elif roll < 0.58:
        angle = rng.uniform(8, 30)
    elif roll < 0.76:
        angle = rng.uniform(-30, -8)
    elif roll < 0.90:
        angle = rng.uniform(-12, 12)
    else:
        angle = rng.uniform(-55, 55)
    if defect_style == "OBLIQUE":
        angle -= 28
    return max(-75.0, min(75.0, angle))


@dataclass
class PipeSpec:
    length: float = 6.0
    radius: float = 0.72
    end_ratio: float = 0.66
    wall_ratio: float = 0.10
    taper_start: float = 0.48
    taper_end: float = 0.88
    body_taper: float = 0.0
    shoulder_roundness: float = 1.0
    defect: str = "DENT"
    position: float = 0.60
    angle: float = 155.0
    depth: float = 0.13
    width: float = 0.075
    arc: float = 25.0
    irregularity: float = 0.24
    seed: int = 42
    defect_style: str = "DEFAULT"
    defect_rotation: float = 0.0
    secondary_strength: float = 0.5

    def validate(self):
        if not 2.0 <= self.length <= 12.0:
            raise ValueError("Length must be between 2 and 12 scene units")
        if not 0.3 <= self.radius <= 1.5:
            raise ValueError("Radius must be between 0.3 and 1.5 scene units")
        if not 0.35 <= self.end_ratio <= 1.0:
            raise ValueError("Outlet ratio must be between 0.35 and 1")
        if not 0.03 <= self.wall_ratio <= 0.22:
            raise ValueError("Wall ratio must be between 0.03 and 0.22")
        if not 0.0 <= self.taper_start < self.taper_end <= 1.0:
            raise ValueError("Taper start must precede taper end")
        if not 0.0 <= self.body_taper <= 0.12:
            raise ValueError("Body taper must be between 0 and 0.12")
        if not 0.0 <= self.shoulder_roundness <= 1.0:
            raise ValueError("Shoulder roundness must be between 0 and 1")
        if self.defect not in {"NONE", "DENT", "FOLD"}:
            raise ValueError("Unknown defect type")
        if not 0.03 <= self.position <= 0.97:
            raise ValueError("Defect position must be between 0.03 and 0.97")
        if not 0.0 <= self.depth <= 0.25:
            raise ValueError("Depth must be between 0 and 0.25")
        if not 0.01 <= self.width <= 0.18 or not 8 <= self.arc <= 65:
            raise ValueError("Defect footprint is outside supported limits")
        if not 0 <= self.irregularity <= 0.65:
            raise ValueError("Irregularity must be between 0 and 0.65")
        if self.defect_style not in DEFECT_STYLES:
            raise ValueError("Unknown defect style")
        if not -75 <= self.defect_rotation <= 75:
            raise ValueError("Defect rotation must be between -75 and 75 degrees")
        if not 0 <= self.secondary_strength <= 1:
            raise ValueError("Secondary strength must be between 0 and 1")
        return self


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def rounded_cone(t):
    """Linear center with quadratic toe/heel over 10% at either end (C1)."""
    t = max(0.0, min(1.0, t))
    edge = 0.10
    if t < edge:
        return t * t / (2 * edge * (1 - edge))
    if t > 1 - edge:
        return 1 - (1 - t) ** 2 / (2 * edge * (1 - edge))
    return (t - edge / 2) / (1 - edge)


def body_reduction(t):
    """Mostly linear reduction, easing its final 10% into the shoulder."""
    t = max(0.0, min(1.0, t))
    edge = 0.10
    # Flatten the final slope so the body and shoulder normals meet smoothly.
    eased = t - max(0.0, t - (1 - edge)) ** 2 / (2 * edge)
    return eased / (1 - edge / 2)


def radius_at(t, spec):
    if t < spec.taper_start:
        reduction = body_reduction(t / spec.taper_start)
        return spec.radius * (1 - spec.body_taper * reduction)
    u = (t - spec.taper_start) / (spec.taper_end - spec.taper_start)
    blend = (spec.shoulder_roundness * smoothstep(u)
             + (1 - spec.shoulder_roundness) * rounded_cone(u))
    body_end_ratio = 1 - spec.body_taper
    return spec.radius * (body_end_ratio - (body_end_ratio - spec.end_ratio) * blend)


def _base_form(u, v, spec, phase):
    """Original dimple/crease profile, reused as a smooth cluster primitive."""
    # A slightly meandering center gives repeatable, non-perfectly oval defects.
    u += spec.irregularity * 0.40 * math.sin(2.5 * v + phase)
    envelope = math.exp(-2.0 * (u*u + v*v))
    if spec.defect == "DENT":
        form = -envelope * (1 + spec.irregularity * 0.25 * math.sin(4*u + phase))
        form += 0.13 * math.exp(-1.2 * (u*u + v*v)) * (u*u + v*v)
    else:
        # A narrow trough and adjacent raised lip extend around part of the tube.
        form = (-math.exp(-12 * u*u) + 0.42 * math.exp(-22 * (u - 0.36)**2))
        form *= math.exp(-1.8 * v*v)
        form *= 1 + spec.irregularity * 0.22 * math.sin(5*v + phase)
    return form


def _style_form(u, v, spec, phase):
    """Smooth geometric lobes; secondary strength changes the cluster's structure."""
    base = lambda x, y: _base_form(x, y, spec, phase)
    strength = spec.secondary_strength
    if spec.defect_style == "DEFAULT":
        return base(u, v)
    if spec.defect_style == "AXIAL_PINCH":
        # An axial depression with a rounded, pinched trough and an unequal
        # displaced lip. In the references the highlight widens on one side
        # of a short dark crease; a symmetric triangular groove misses this.
        # All terms deform the skin and participate in its geometric mask.
        side = 1.0 if math.sin(phase + 0.4) >= 0 else -1.0
        longitudinal = u * (1.0 if math.cos(phase) >= 0 else -1.0)
        longitudinal += 0.10 * math.sin(phase)
        center = spec.irregularity * 0.10 * math.sin(1.8 * longitudinal + phase)
        center += strength * 0.045 * math.sin(phase) * math.tanh(1.8 * longitudinal)
        transverse = side * (v - center)
        # Smoothly changing aperture gives narrow slits at low strength and
        # broader pinched pockets at high strength, with rounded tapered ends.
        aperture = (0.15 + 0.16 * strength) * (0.86 + 0.20 * math.tanh(-1.6 * longitudinal))
        envelope = math.exp(-1.6 * longitudinal**2 - 0.18 * longitudinal**4)
        core = -math.exp(-0.5 * (transverse / aperture)**2)
        lip_width = 0.15 + 0.06 * strength
        lip_center = aperture * 1.65 + 0.06
        lip = (0.30 + 0.12 * strength) * math.exp(-0.5 * ((transverse - lip_center) / lip_width)**2)
        lip *= 0.80 + 0.20 * math.tanh(-1.3 * longitudinal)
        far_lip = 0.065 * math.exp(-0.5 * ((transverse + aperture * 1.75) / 0.19)**2)
        pocket = -0.24 * strength * math.exp(-2.1 * (longitudinal + 0.28)**2 - 3.2 * (transverse + 0.08)**2)
        form = envelope * (core + lip + far_lip) + pocket
        # Compact C1 support prevents imperceptible tails joining a rim or
        # covering a much larger label than the localized physical defect.
        form *= smoothstep((2.10 - abs(u)) / 0.55) * smoothstep((1.60 - abs(v)) / 0.45)
        if spec.defect == "DENT":
            # A manually selected pinch remains a smooth pocket; dent
            # randomization continues to use only its original six families.
            form = 0.72 * form - 0.22 * math.exp(-2.0 * (u*u + v*v))
    elif spec.defect_style == "SHALLOW_SWEEP":
        # A wide, shallow press with rounded ends and no circular crater rim.
        # Compact C1 support labels the complete deformed area, including the
        # gently sloped center which can disappear under a grazing highlight.
        x = (u + .16 * spec.irregularity * v * math.sin(phase)) / 1.65
        y = (v + .13 * spec.irregularity * math.sin(1.7*u + phase)) / .95
        bowl = max(0., 1-x*x)**2 * max(0., 1-y*y)**2
        form = -bowl * (.86 + .14 * math.tanh(-x + .4*math.sin(phase)))
        side = 1 if math.cos(phase) >= 0 else -1
        # Small displaced shoulder on one side, never a complete raised ring.
        form += (.025 + .035*strength) * math.exp(-5*(x+.22)**2-28*(y-.75*side)**2)
        form *= smoothstep((2.0-abs(u))/.35) * smoothstep((1.3-abs(v))/.30)
    elif spec.defect_style == "SOFT_BUCKLE":
        # Rounded shoulder/neck collapse seen at the silhouette: a soft trough
        # beside an unequal lip, without a triangular or razor-like apex.
        side = 1 if math.sin(phase) >= 0 else -1
        longitudinal = u + .10*math.sin(phase)
        transverse = side*v + .10*spec.irregularity*math.sin(2*u+phase)
        envelope = math.exp(-1.6*longitudinal**2-.25*longitudinal**4)
        core = -math.exp(-((transverse+.06)/(.43+.09*strength))**2)
        lip = (.20+.12*strength)*math.exp(-((transverse-.62)/.32)**2)
        form = envelope*(core+lip)
        form *= smoothstep((2.-abs(u))/.45)*smoothstep((1.65-abs(v))/.4)
    elif spec.defect_style == "ELONGATED":
        if spec.defect == "DENT":
            form = base(u / 1.65 + strength * 0.16 * math.tanh(1.8*v), v / 0.72)
        else:
            form = base(u / 0.86 + strength * 0.13 * math.tanh(1.4*v), v / 1.65)
    elif spec.defect_style == "DOUBLE":
        primary = base((u + 0.47) / 0.78, (v + 0.27) / 0.82)
        secondary = base((u - 0.47) / 0.82, (v - 0.27) / 0.88)
        form = (primary + strength * secondary) / (1 + 0.20 * strength)
    elif spec.defect_style == "OBLIQUE":
        # The chart has already been rotated in the physical tangent plane.
        form = base(u / 0.70 + strength * 0.12 * math.tanh(1.5*v), v / 1.50)
    elif spec.defect_style == "WRINKLED":
        form = 0.58 * base(u / 0.70, v / 1.10)
        form += strength * 0.38 * (base((u - 0.65) / 0.60, (v + 0.13) / 1.05)
                                   + base((u + 0.65) / 0.60, (v - 0.15) / 0.85))
    else:  # BRANCHED: one trunk smoothly separates into two unequal troughs.
        branch = 0.28 * (v + math.sqrt(v*v + 0.12))
        trunk_gate = 0.5 * (1 - math.tanh(2.4 * (v - 0.15)))
        arms_gate = 0.5 * (1 + math.tanh(2.4 * (v + 0.15)))
        form = trunk_gate * base(u / 0.64, v / 1.20)
        form += strength * arms_gate * (base((u - branch) / 0.56, (v - 0.48) / 0.85)
                                        + 0.76 * base((u + branch) / 0.50, (v - 0.44) / 0.80))
    # Smooth saturation preserves the nominal unit peak and bounds every sum
    # below 1/tanh(1.5) = 1.105. No clipping plateau or discontinuous edge.
    return math.tanh(1.5 * form) / math.tanh(1.5)


def displacement(t, theta, spec):
    """A bounded local radial displacement; no mechanics/strain simulation."""
    if spec.defect == "NONE" or spec.depth == 0:
        return 0.0, 0.0
    phase = (spec.seed % 997) * 0.217
    da = math.atan2(math.sin(theta - math.radians(spec.angle)),
                    math.cos(theta - math.radians(spec.angle)))
    rotation = spec.defect_rotation + (28 if spec.defect_style == "OBLIQUE" else 0)
    if rotation == 0:
        # Preserve DEFAULT bit-for-bit, including its historic footprint.
        u = (t - spec.position) / spec.width
        v = da / math.radians(spec.arc)
    else:
        # Rotate physical axial/circumferential distances before normalizing.
        # Thus the angle is meaningful even for very long or narrow footprints.
        local_radius = radius_at(spec.position, spec)
        axial_distance = (t - spec.position) * spec.length
        tangent_distance = da * local_radius
        turn = math.radians(rotation)
        co, si = math.cos(turn), math.sin(turn)
        u = (co * axial_distance + si * tangent_distance) / (spec.width * spec.length)
        v = (-si * axial_distance + co * tangent_distance) / (math.radians(spec.arc) * local_radius)
    form = _style_form(u, v, spec, phase)
    if spec.defect_style != "DEFAULT" or spec.defect_rotation != 0:
        # The local angular chart meets itself at the far side of the tube.
        # A C1 fade only in its final 20% removes the antipodal branch cut,
        # including wide, rotated footprints, without cutting off mask support.
        form *= smoothstep((math.pi - abs(da)) / (math.pi * 0.20))
    amount = spec.depth * radius_at(t, spec) * form
    # Geometric support mask: >= 3% of the nominal peak displacement.
    # This is explicitly not a human visibility/defect acceptance threshold.
    mask = 1.0 if abs(form) >= 0.03 else 0.0
    return amount, mask


def sampling_grid(spec, axial=144, radial=128, adaptive=False):
    """Shared skin grid, optionally refined over the rotated defect footprint.

    Existing uniform knots are retained. Additional axial and angular knots
    follow the local physical crease/dimple scale and keep a tensor-product
    wall topology. Refinement is limited to about 200,000 paired-skin vertices;
    an explicitly denser base grid is never reduced.
    """
    spec.validate()
    if axial < 16 or radial < 16:
        raise ValueError("Mesh sampling is too low")
    ts = [i / axial for i in range(axial + 1)]
    angles = [2 * math.pi * j / radial for j in range(radial)]
    if not adaptive or spec.defect == "NONE" or spec.depth == 0:
        return ts, angles

    local_radius = radius_at(spec.position, spec)
    sx, sy = spec.width * spec.length, math.radians(spec.arc) * local_radius
    rotation = math.radians(spec.defect_rotation + (28 if spec.defect_style == 'OBLIQUE' else 0))
    co, si = abs(math.cos(rotation)), abs(math.sin(rotation))
    # Approximate three-sigma support including raised lips and meandering.
    # Multiple lobes enlarge the support but retain a finer individual trough.
    extent_u, extent_v, narrow_u, narrow_v = {
        'DEFAULT': (1.55, 1.60, 1.0, 1.0),
        'ELONGATED': (2.85, 1.20, 1.65, .72) if spec.defect == 'DENT' else (1.40, 2.80, .86, 1.65),
        'DOUBLE': (1.85, 1.80, .78, .82),
        'OBLIQUE': (1.10, 2.50, .70, 1.50),
        'WRINKLED': (1.90, 1.95, .60, .85),
        'BRANCHED': (2.00, 2.10, .50, .80),
        'AXIAL_PINCH': (2.10, 1.60, 1.00, .28),
        'SHALLOW_SWEEP': (2.00, 1.30, 1.20, .80),
        'SOFT_BUCKLE': (2.00, 1.65, 1.00, .43),
    }[spec.defect_style]
    half_x = co * sx * extent_u + si * sy * extent_v
    half_y = si * sx * extent_u + co * sy * extent_v
    low, high = max(0.0, spec.position-half_x/spec.length), min(1.0, spec.position+half_x/spec.length)
    half_angle = min(math.pi, half_y/local_radius)
    # The fold's one-sided Gaussian lip is narrower than its envelope. Aim
    # for six samples per narrow physical sigma (more across the full trough).
    sigma_u = sx * narrow_u * (.15 if spec.defect == 'FOLD' else .42)
    sigma_v = sy * narrow_v * .42
    if spec.defect_style == 'AXIAL_PINCH':
        # The narrow feature is circumferential here, not axial. Resolve the
        # smallest aperture and lip, even when the pinch is nearly horizontal.
        sigma_u, sigma_v = sx * .40, sy * .09
    elif spec.defect_style == 'SOFT_BUCKLE':
        sigma_u, sigma_v = sx * .40, sy * .20
    step_x = 1 / (6 * math.hypot(co/sigma_u, si/sigma_v))
    step_y = 1 / (6 * math.hypot(si/sigma_u, co/sigma_v))
    step_t, step_angle = step_x/spec.length, step_y/local_radius
    budget = max(100000, len(ts)*len(angles))
    for _ in range(32):
        extra_t = max(1, math.ceil((high-low)/step_t))
        extra_angle = max(1, math.ceil(2*half_angle/step_angle))
        # Conservative upper bound counts all old knots, new interval ends,
        # and exact defect centers even where some coincide after merging.
        estimate = (len(ts)+extra_t+2)*(len(angles)+extra_angle+2)
        if estimate <= budget:
            break
        multiplier = 1.02 * math.sqrt(estimate/budget)
        step_t *= multiplier
        step_angle *= multiplier

    def merge(values):
        result = []
        for value in sorted(values):
            if not result or value-result[-1] > 1e-10:
                result.append(value)
        return result

    ts = merge(ts + [low+(high-low)*i/extra_t for i in range(extra_t+1)] + [spec.position])
    center = math.radians(spec.angle) % math.tau
    additions = [(center-half_angle+2*half_angle*j/extra_angle) % math.tau
                 for j in range(extra_angle+1)] + [center]
    additions = [0.0 if min(a, math.tau-a) < 1e-10 else a for a in additions]
    angles = merge(angles+additions)
    return ts, angles


def build_mesh(spec, axial=144, radial=128, adaptive=False):
    """Closed wall volume with two open bores, outward winding, no seam duplicates."""
    ts, angles = sampling_grid(spec, axial, radial, adaptive)
    vertices, masks, faces, face_regions = [], [], [], []
    rings, radial = len(ts), len(angles)
    axial = rings - 1
    for inner in (False, True):
        for t in ts:
            nominal = radius_at(t, spec)
            for theta in angles:
                delta, mask = displacement(t, theta, spec)
                # Apply the same displacement to both skins, retaining radial wall thickness.
                r = nominal + delta - (spec.radius * spec.wall_ratio if inner else 0)
                vertices.append(((t - 0.5) * spec.length, r * math.cos(theta), r * math.sin(theta)))
                masks.append(mask if not inner else 0.0)
    offset = rings * radial
    for i in range(axial):
        for j in range(radial):
            k = (j + 1) % radial
            a, b, c, d = i*radial+j, (i+1)*radial+j, (i+1)*radial+k, i*radial+k
            faces.append((a, d, c, b)); face_regions.append("outer")
            faces.append((a+offset, b+offset, c+offset, d+offset)); face_regions.append("inner")
    for j in range(radial):
        k = (j + 1) % radial
        faces.append((j, j+offset, k+offset, k)); face_regions.append("rim")
        a, b = axial*radial+j, axial*radial+k
        faces.append((a, b, b+offset, a+offset)); face_regions.append("rim")
    return vertices, faces, masks, face_regions


def random_spec(base, seed, visible_angle=None):
    """The same base + seed always reproduces the same geometric specimen."""
    rng = random.Random(seed)
    values = asdict(base)
    values.update(seed=seed, defect=rng.choice(["DENT", "FOLD"]),
                  position=rng.uniform(0.18, 0.82), depth=rng.uniform(0.055, 0.21),
                  width=rng.uniform(0.035, 0.105), arc=rng.uniform(15, 42),
                  angle=rng.uniform(0, 360) if visible_angle is None else (visible_angle+rng.uniform(-35, 35)) % 360,
                  irregularity=rng.uniform(0.1, 0.5))
    # Append draws so existing seed-to-position/depth/width mappings stay stable.
    # The observed folds now cover a wider angular spread and a broader shape mix.
    values["defect_style"] = rng.choice(DENT_STYLES) if values["defect"] == "DENT" else _weighted_choice(rng, FOLD_STYLES, FOLD_STYLE_WEIGHTS)
    if values["defect"] == "FOLD":
        values["defect_rotation"] = _sample_fold_rotation(rng, values["defect_style"])
    else:
        values["defect_rotation"] = 0.0 if rng.random() < 0.20 else rng.uniform(-75, 75)
    values["secondary_strength"] = rng.uniform(0.25, 1.0)
    return PipeSpec(**values).validate()


def mask_bbox(pixels, width, height, threshold=0.5):
    """Bounding box in top-left pixel coordinates from a Blender RGBA mask."""
    xs, ys = [], []
    for y in range(height):
        for x in range(width):
            if pixels[(y*width+x)*4] > threshold:
                xs.append(x); ys.append(height-1-y)
    if not xs:
        return None
    x0, y0, x1, y1 = min(xs), min(ys), max(xs)+1, max(ys)+1
    return x0, y0, x1-x0, y1-y0


def yolo_box(box, width, height):
    x, y, w, h = box
    return (x+w/2)/width, (y+h/2)/height, w/width, h/height
