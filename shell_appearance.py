"""Exterior finish presets. No geometry, defect, camera-pose or lighting keys."""

POLYMER_DEFAULTS = dict(
    plastic_roughness=.24, plastic_specular=.45, plastic_coat=.055,
    plastic_finish_variation=.28, groove_polish=.72, groove_residue=.40,
    crimp_roughness=.185, plastic_ink_wear=.18,
    inspection_softness=.5, inspection_scatter=.065)

POLYMER_LIMITS = dict(
    plastic_roughness=(.12,.7), plastic_specular=(0,.6), plastic_coat=(0,.3),
    plastic_finish_variation=(0,1), groove_polish=(0,1), groove_residue=(0,1),
    crimp_roughness=(.12,.7), plastic_ink_wear=(0,1),
    inspection_softness=(0,1.5), inspection_scatter=(0,.2))

APPEARANCE_PRESETS = {
    'REFERENCE': dict(**POLYMER_DEFAULTS, dust_amount=.16, finish_marks=.48,
                      texture_strength=.56, wear=.42, roughness=.27,
                      oxide_amount=.48, polish_amount=.32, sensor_noise=.0075),
    'SATIN': dict(plastic_roughness=.31,plastic_specular=.30,plastic_coat=.01,
                  plastic_finish_variation=.60,groove_polish=.25,groove_residue=.55,
                  crimp_roughness=.23,plastic_ink_wear=.7,inspection_softness=.55,inspection_scatter=.065,
                  dust_amount=.18,finish_marks=.5,texture_strength=.56,wear=.42,roughness=.27,
                  oxide_amount=.48,polish_amount=.32,sensor_noise=.009),
    'CLEAN': dict(plastic_roughness=.30, plastic_specular=.43, plastic_coat=.045,
                  plastic_finish_variation=.10, groove_polish=.5, groove_residue=0.,
                  crimp_roughness=.26, plastic_ink_wear=.1,
                  inspection_softness=0., inspection_scatter=0., dust_amount=0.,
                  finish_marks=0., texture_strength=.35, wear=.08, roughness=.25,
                  oxide_amount=.15, polish_amount=.50, sensor_noise=0.),
}


def appearance_settings(profile):
    """Return a copy so callers can tweak a preset without modifying it globally."""
    return dict(APPEARANCE_PRESETS[profile])
