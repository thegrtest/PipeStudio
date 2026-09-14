import math
import unittest
from collections import Counter
from dataclasses import replace
from geometry import (DEFECT_STYLES, PipeSpec, build_mesh, displacement,
                      random_spec, mask_bbox, yolo_box, radius_at, sampling_grid)


def original_displacement(t, theta, spec):
    """Frozen previous-release formula: existing saved scenes must reproduce."""
    phase = (spec.seed % 997) * 0.217
    da = math.atan2(math.sin(theta - math.radians(spec.angle)),
                    math.cos(theta - math.radians(spec.angle)))
    u = (t - spec.position) / spec.width
    v = da / math.radians(spec.arc)
    u += spec.irregularity * 0.40 * math.sin(2.5 * v + phase)
    envelope = math.exp(-2.0 * (u*u + v*v))
    if spec.defect == 'DENT':
        form = -envelope * (1 + spec.irregularity * 0.25 * math.sin(4*u + phase))
        form += 0.13 * math.exp(-1.2 * (u*u + v*v)) * (u*u + v*v)
    else:
        form = (-math.exp(-12 * u*u) + 0.42 * math.exp(-22 * (u - 0.36)**2))
        form *= math.exp(-1.8 * v*v)
        form *= 1 + spec.irregularity * 0.22 * math.sin(5*v + phase)
    return spec.depth * radius_at(t, spec) * form, float(abs(form) >= 0.03)


class GeometryTests(unittest.TestCase):
    def test_wall_is_watertight_but_bores_are_open(self):
        vertices, faces, masks, regions = build_mesh(PipeSpec(), 24, 32)
        edges = Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f, f[1:]+f[:1]))
        self.assertTrue(all(n == 2 for n in edges.values()))
        self.assertEqual(regions.count('rim'), 64)
        # No vertex lies on either bore axis, including both end rings.
        self.assertGreater(min(math.hypot(v[1], v[2]) for v in vertices), 0)
        # Every paired skin point retains its radial wall thickness.
        half = len(vertices)//2
        for a,b in zip(vertices[:half], vertices[half:]):
            self.assertAlmostEqual(math.hypot(a[1],a[2])-math.hypot(b[1],b[2]), 0.072, places=7)

    def test_clean_and_zero_depth_have_no_mask_or_deformation(self):
        for s in (PipeSpec(defect='NONE'), PipeSpec(depth=0)):
            self.assertEqual(displacement(0.6, math.radians(155), s), (0.0, 0.0))
            self.assertFalse(any(build_mesh(s, 16, 16)[2]))

    def test_deformation_wraps_continuously_at_seam(self):
        s=PipeSpec(angle=359, irregularity=0)
        a=displacement(0.6, -0.000001, s)[0]
        b=displacement(0.6, 2*math.pi-0.000001, s)[0]
        self.assertAlmostEqual(a,b,places=12)

    def test_default_defects_exactly_reproduce_previous_release(self):
        for kind in ('DENT', 'FOLD'):
            for seed in (0, 42, 237):
                s = PipeSpec(defect=kind, seed=seed, irregularity=0.65, arc=65)
                for t in (0, 0.3, 0.54, 0.6, 0.64, 0.9, 1):
                    for theta in (0, 1.2, 2.7, 4.8, 2*math.pi):
                        self.assertEqual(displacement(t, theta, s), original_displacement(t, theta, s))

    def test_every_style_is_periodic_and_smooth_across_far_side_chart(self):
        for style in DEFECT_STYLES:
            for kind in ('DENT', 'FOLD'):
                s = PipeSpec(defect=kind, defect_style=style, defect_rotation=75,
                             angle=359, width=0.18, arc=65, secondary_strength=1)
                for t in (0.15, 0.6, 0.92):
                    for theta in (-0.1, 0, 1.5, 4.0):
                        self.assertAlmostEqual(displacement(t, theta, s)[0],
                                               displacement(t, theta + 2*math.pi, s)[0], places=12)
                    antipode = math.radians(s.angle) + math.pi
                    left = displacement(t, antipode - 1e-7, s)[0]
                    right = displacement(t, antipode + 1e-7, s)[0]
                    self.assertLess(abs(left), 1e-12)
                    self.assertLess(abs(right), 1e-12)
                    self.assertLess(abs(left-right), 1e-12)

    def test_rotation_uses_physical_tangent_plane(self):
        for style in ('DEFAULT', 'ELONGATED', 'DOUBLE', 'WRINKLED', 'BRANCHED'):
            s = PipeSpec(defect_style=style, irregularity=0.35, width=0.06, arc=20)
            r = radius_at(s.position, s)
            # An off-center sample is rotated geometrically, not re-indexed in
            # normalized ellipse coordinates; dividing by nominal radius
            # removes the intentional local pipe-radius amplitude scaling.
            x, y = 0.11, 0.035
            t0, theta0 = s.position + x/s.length, math.radians(s.angle) + y/r
            original = displacement(t0, theta0, s)[0] / radius_at(t0, s)
            for turn in (-65, 47):
                co, si = math.cos(math.radians(turn)), math.sin(math.radians(turn))
                tx = s.position + (co*x-si*y)/s.length
                theta = math.radians(s.angle) + (si*x+co*y)/r
                rotated = replace(s, defect_rotation=turn)
                actual = displacement(tx, theta, rotated)[0] / radius_at(tx, rotated)
                self.assertAlmostEqual(original, actual, places=12)

    def test_styles_change_geometry_and_seeds_remain_deterministic(self):
        for kind in ('DENT', 'FOLD'):
            fingerprints = []
            for style in DEFECT_STYLES:
                s = PipeSpec(defect=kind, defect_style=style, secondary_strength=0.8)
                points = [(s.position+u*s.width, math.radians(s.angle+v*s.arc))
                          for u in (-1, -0.45, 0, 0.45, 1) for v in (-0.9, -0.3, 0.3, 0.9)]
                values = tuple(displacement(t, theta, s) for t, theta in points)
                self.assertEqual(values, tuple(displacement(t, theta, replace(s)) for t, theta in points))
                self.assertNotEqual(values, tuple(displacement(t, theta, replace(s, seed=101))
                                                 for t, theta in points))
                fingerprints.append(tuple(round(v[0], 8) for v in values))
            self.assertEqual(len(set(fingerprints)), len(DEFECT_STYLES))

    def test_secondary_strength_changes_cluster_support(self):
        for kind in ('DENT', 'FOLD'):
            for style in ('DOUBLE', 'WRINKLED', 'BRANCHED'):
                s = PipeSpec(defect=kind, defect_style=style, secondary_strength=0)
                strong = replace(s, secondary_strength=1)
                points = [(s.position+u*s.width, math.radians(s.angle+v*s.arc))
                          for u in (-1.2, -0.8, -0.4, 0, 0.4, 0.8, 1.2)
                          for v in (-1, -0.5, 0, 0.5, 1)]
                weak_values = [displacement(t, theta, s) for t, theta in points]
                strong_values = [displacement(t, theta, strong) for t, theta in points]
                self.assertTrue(any(abs(a[0]-b[0]) > 0.001 for a, b in zip(weak_values, strong_values)))
                self.assertTrue(any(a[1] != b[1] for a, b in zip(weak_values, strong_values)))

    def test_all_style_extremes_preserve_nested_open_bores_and_wall_volume(self):
        for style in DEFECT_STYLES:
            for kind in ('DENT', 'FOLD'):
                for turn in (-75, 75):
                    s = PipeSpec(radius=0.3, end_ratio=0.35, wall_ratio=0.22, depth=0.25,
                                 defect=kind, defect_style=style, defect_rotation=turn,
                                 position=0.97, irregularity=0.65, body_taper=0.12,
                                 width=0.18, arc=65, secondary_strength=1)
                    vertices, faces, masks, regions = build_mesh(s, 24, 32)
                    edges = Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f, f[1:]+f[:1]))
                    self.assertTrue(all(n == 2 for n in edges.values()))
                    self.assertEqual(regions.count('rim'), 64)
                    half = len(vertices)//2
                    self.assertFalse(any(masks[half:]))
                    for index, point in enumerate(vertices):
                        self.assertTrue(all(math.isfinite(v) for v in point))
                        self.assertLessEqual(abs(point[0]), s.length/2)
                        self.assertLess(math.hypot(point[1],point[2]), s.radius*1.3)
                        theta = 2*math.pi*(index%32)/32
                        signed_radius = point[1]*math.cos(theta)+point[2]*math.sin(theta)
                        self.assertGreater(signed_radius, 0.005)
                    for outer, inner in zip(vertices[:half], vertices[half:]):
                        self.assertAlmostEqual(math.hypot(outer[1],outer[2])-math.hypot(inner[1],inner[2]),
                                               s.radius*s.wall_ratio, places=12)

    def test_styles_are_bounded_and_masks_cover_geometric_displacement(self):
        for style in DEFECT_STYLES:
            for kind in ('DENT', 'FOLD'):
                s = PipeSpec(defect_style=style, defect=kind, depth=0.25, irregularity=0.65,
                             secondary_strength=1, width=0.01, arc=8, position=0.03)
                for u in (-2, -1, -0.5, 0, 0.5, 1, 2):
                    for v in (-2, -1, -0.5, 0, 0.5, 1, 2):
                        t, theta = s.position+u*s.width, math.radians(s.angle+v*s.arc)
                        amount, mask = displacement(t, theta, s)
                        form = amount/(s.depth*radius_at(t, s))
                        self.assertLessEqual(abs(form), 1.163)
                        self.assertEqual(mask, float(abs(form) >= 0.03))
                for clean in (replace(s, defect='NONE'), replace(s, depth=0)):
                    self.assertFalse(any(build_mesh(clean, 16, 16)[2]))

    def test_new_style_controls_reject_invalid_values(self):
        for field, values in (('defect_style', ('DIMPLE', '', None)),
                              ('defect_rotation', (-76, 76, float('nan'), float('inf'))),
                              ('secondary_strength', (-0.01, 1.01, float('nan'), float('inf')))):
            for value in values:
                with self.assertRaises(ValueError):
                    replace(PipeSpec(), **{field: value}).validate()

    def test_adaptive_is_optional_and_clean_grids_remain_identical(self):
        s = PipeSpec(defect_style='OBLIQUE')
        self.assertEqual(build_mesh(s, 24, 32), build_mesh(s, 24, 32, adaptive=False))
        for clean in (replace(s, defect='NONE'), replace(s, depth=0)):
            self.assertEqual(build_mesh(clean, 24, 32), build_mesh(clean, 24, 32, adaptive=True))

    def test_adaptive_rotated_fold_resolves_narrow_lip(self):
        # Actual specimen that showed zipper-like mesh aliasing in V3 review.
        s = PipeSpec(length=8, radius=.9, position=.818324, width=.025855,
                     arc=23.624327, irregularity=.168182, defect_rotation=38.099556,
                     depth=.117155, defect='FOLD', defect_style='OBLIQUE')
        ts, angles = sampling_grid(s, 144, 128, adaptive=True)
        self.assertLessEqual(2*len(ts)*len(angles), 200000)
        self.assertTrue(set(i/144 for i in range(145)).issubset(ts))
        self.assertTrue(set(math.tau*j/128 for j in range(128)).issubset(angles))
        r, theta = radius_at(s.position, s), math.radians(s.angle)
        dt = max(b-a for a,b in zip(ts, ts[1:]) if abs((a+b)/2-s.position)<.02)*s.length
        da = max(b-a for a,b in zip(angles, angles[1:]) if abs((a+b)/2-theta)<.12)*r
        turn = math.radians(s.defect_rotation+28)
        # Worst grid-cell diagonal projected onto the crease's narrow normal.
        projected_gap = abs(math.cos(turn))*dt + abs(math.sin(turn))*da
        lip_sigma = s.width*s.length*.70*.15
        samples_across_fwhm = 2.355*lip_sigma/projected_gap
        self.assertGreaterEqual(samples_across_fwhm, 6)

    def test_adaptive_grid_has_no_seam_duplicates_and_is_bounded_at_limits(self):
        for style in DEFECT_STYLES:
            s = PipeSpec(defect='FOLD', defect_style=style, defect_rotation=75,
                         angle=359, position=.97, width=.01, arc=65,
                         radius=.3, end_ratio=.35, depth=.25, irregularity=.65)
            ts, angles = sampling_grid(s, 144, 128, adaptive=True)
            self.assertLessEqual(2*len(ts)*len(angles), 200000)
            self.assertEqual((ts[0], ts[-1]), (0, 1))
            self.assertEqual(angles[0], 0)
            self.assertLess(angles[-1], math.tau)
            self.assertTrue(all(b-a>1e-10 for a,b in zip(ts, ts[1:])))
            self.assertTrue(all(b-a>1e-10 for a,b in zip(angles, angles[1:])))
            self.assertGreater(math.tau-angles[-1], 1e-10)

    def test_adaptive_wall_is_closed_nested_and_exactly_follows_displacement(self):
        s = PipeSpec(defect='FOLD', defect_style='OBLIQUE', defect_rotation=40,
                     angle=359, position=.94, width=.05, arc=12,
                     radius=.3, end_ratio=.35, wall_ratio=.22, depth=.25)
        ts, angles = sampling_grid(s, 24, 32, adaptive=True)
        vertices, faces, masks, regions = build_mesh(s, 24, 32, adaptive=True)
        half = len(vertices)//2
        self.assertEqual(half, len(ts)*len(angles))
        self.assertEqual(regions.count('rim'), 2*len(angles))
        edges = Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f, f[1:]+f[:1]))
        self.assertTrue(all(n==2 for n in edges.values()))
        self.assertFalse(any(masks[half:]))
        for i,t in enumerate(ts):
            for j,theta in enumerate(angles):
                index = i*len(angles)+j
                outer, inner = vertices[index], vertices[half+index]
                ro = outer[1]*math.cos(theta)+outer[2]*math.sin(theta)
                ri = inner[1]*math.cos(theta)+inner[2]*math.sin(theta)
                self.assertGreater(ri, .005)
                self.assertAlmostEqual(ro-ri, s.radius*s.wall_ratio, places=12)
                delta, mask = displacement(t, theta, s)
                self.assertAlmostEqual(ro, radius_at(t, s)+delta, places=12)
                self.assertEqual(masks[index], mask)

    def test_extreme_supported_shape_does_not_cross_axis(self):
        for kind in ('DENT','FOLD'):
            s=PipeSpec(radius=0.3,end_ratio=0.35,wall_ratio=0.22,depth=0.25,
                       defect=kind,position=0.92,irregularity=0.65,body_taper=0.12)
            for roundness in (0, 0.5, 1):
                vertices=build_mesh(replace(s, shoulder_roundness=roundness), 24, 32)[0]
                self.assertGreater(min(math.hypot(v[1],v[2]) for v in vertices), 0.005)
                # Signed projection catches a negative radius flipped across the axis.
                for index,v in enumerate(vertices):
                    theta=2*math.pi*(index%32)/32
                    self.assertGreater(v[1]*math.cos(theta)+v[2]*math.sin(theta),0.005)
                half=len(vertices)//2
                for outer,inner in zip(vertices[:half],vertices[half:]):
                    self.assertAlmostEqual(math.hypot(outer[1],outer[2])-math.hypot(inner[1],inner[2]),
                                           s.radius*s.wall_ratio,places=12)

    def test_default_profile_is_unchanged(self):
        s=PipeSpec()
        for i in range(1001):
            t=i/1000
            u=max(0.0,min(1.0,(t-s.taper_start)/(s.taper_end-s.taper_start)))
            original=s.radius*(1-(1-s.end_ratio)*u*u*(3-2*u))
            self.assertAlmostEqual(radius_at(t,s),original,places=15)

    def test_profile_endpoints_and_absolute_body_reduction(self):
        for amount in (0,0.04,0.12):
            for roundness in (0,0.5,1):
                s=PipeSpec(body_taper=amount,shoulder_roundness=roundness)
                self.assertEqual(radius_at(0,s),s.radius)
                self.assertEqual(radius_at(s.taper_start,s),s.radius*(1-amount))
                self.assertAlmostEqual(radius_at(s.taper_end,s),s.radius*s.end_ratio,places=15)
                self.assertAlmostEqual(radius_at(1,s),s.radius*s.end_ratio,places=15)
                # The straight portion loses radius at a constant rate.
                sample=[radius_at(t*s.taper_start,s) for t in (0.1,0.3,0.5,0.7)]
                self.assertAlmostEqual(sample[0]-sample[1],sample[2]-sample[3],places=15)

    def test_taper_stays_monotonic_and_has_no_diameter_steps(self):
        for amount in (0,0.12):
            for roundness in (0,0.5,1):
                s=PipeSpec(taper_start=0.80,taper_end=0.88,body_taper=amount,
                           shoulder_roundness=roundness,end_ratio=0.68)
                values=[radius_at(i/2000,s) for i in range(2001)]
                self.assertTrue(all(a>=b for a,b in zip(values,values[1:])))
                for join in (s.taper_start,s.taper_end):
                    self.assertLess(abs(radius_at(join-1e-8,s)-radius_at(join+1e-8,s)),1e-7)

    def test_first_derivatives_join_continuously(self):
        h=1e-7
        for roundness in (0,0.5,1):
            s=PipeSpec(body_taper=0.12,shoulder_roundness=roundness,
                       taper_start=0.8,taper_end=0.88)
            span=s.taper_end-s.taper_start
            joins=(0.9*s.taper_start,s.taper_start,s.taper_start+0.1*span,
                   s.taper_start+0.9*span,s.taper_end)
            for join in joins:
                left=(radius_at(join,s)-radius_at(join-h,s))/h
                right=(radius_at(join+h,s)-radius_at(join,s))/h
                self.assertAlmostEqual(left,right,delta=1e-4)

    def test_profile_controls_reject_nonfinite_and_out_of_range(self):
        for name,values in (('body_taper',(-0.01,0.121,float('nan'),float('inf'))),
                            ('shoulder_roundness',(-0.01,1.01,float('nan'),float('inf')))):
            for value in values:
                with self.assertRaises(ValueError):
                    replace(PipeSpec(),**{name:value}).validate()

    def test_zero_length_body_segment_remains_supported(self):
        s=PipeSpec(taper_start=0,body_taper=0.12,shoulder_roundness=0)
        self.assertEqual(radius_at(0,s),s.radius*(1-s.body_taper))
        self.assertGreater(min(math.hypot(v[1],v[2]) for v in build_mesh(s,16,16)[0]),0)

    def test_randomization_is_repeatable_and_local(self):
        a=random_spec(PipeSpec(), 100, 150)
        self.assertEqual(a,random_spec(PipeSpec(),100,150))
        self.assertNotEqual(a,random_spec(PipeSpec(),101,150))
        self.assertTrue(115 <= a.angle <= 185)

    def test_randomization_preserves_legacy_seed_mapping(self):
        s = random_spec(PipeSpec(), 100, 150)
        # Frozen original-generator output; new style draws must follow these.
        self.assertEqual(s.defect, 'DENT')
        self.assertEqual(s.position, 0.47409842231238836)
        self.assertEqual(s.depth, 0.2025162439381442)
        self.assertEqual(s.width, 0.04723232514698748)
        self.assertEqual(s.arc, 25.611908590517135)
        self.assertEqual(s.angle, 139.48158055801696)
        self.assertEqual(s.irregularity, 0.3027460092306747)

    def test_randomization_covers_styles_and_observed_orientation_families(self):
        specimens = [random_spec(PipeSpec(), seed, 150) for seed in range(256)]
        self.assertEqual(specimens, [random_spec(PipeSpec(), seed, 150) for seed in range(256)])
        self.assertEqual({s.defect_style for s in specimens}, set(DEFECT_STYLES))
        self.assertTrue(all(-75 <= s.defect_rotation <= 75 for s in specimens))
        self.assertTrue(all(0.25 <= s.secondary_strength <= 1 for s in specimens))
        for kind in ('DENT', 'FOLD'):
            self.assertEqual({s.defect_style for s in specimens if s.defect == kind}, set(DEFECT_STYLES))
        folds = [s for s in specimens if s.defect == 'FOLD']
        axial = [s for s in folds
                 if 45 <= s.defect_rotation + (28 if s.defect_style == 'OBLIQUE' else 0) <= 75]
        self.assertGreater(len(axial)/len(folds), 0.60)
        dents = [s for s in specimens if s.defect == 'DENT']
        self.assertTrue(any(s.defect_rotation == 0 for s in dents))
        self.assertTrue(any(s.defect_rotation < -40 for s in dents))
        self.assertTrue(any(s.defect_rotation > 40 for s in dents))

    def test_bbox_flips_bottom_origin_and_handles_empty(self):
        p=[0.0]*4*4*3
        p[(0*4+1)*4]=1
        p[(1*4+2)*4]=1
        box=mask_bbox(p,4,3)
        self.assertEqual(box,(1,1,2,2))
        self.assertEqual(yolo_box(box,4,3),(0.5,2/3,0.5,2/3))
        self.assertIsNone(mask_bbox([0.0]*48,4,3))

    def test_invalid_taper_rejected(self):
        with self.assertRaises(ValueError):
            build_mesh(PipeSpec(taper_start=0.9,taper_end=0.5))


if __name__ == '__main__':
    unittest.main()
