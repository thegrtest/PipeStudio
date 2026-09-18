"""Review native camera patches against the rendered finish, outside training data."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from assembly_dent_page import ROOT, build

ROI = (940, 735, 1100, 815)
PART_ROI = (576, 700, 1170, 849)
SAMPLE = 'assembly_0000361000_f001'


def measurements(im):
    patch = np.asarray(im.crop(ROI).convert('RGB'), dtype=float)
    luminance = patch @ np.array([.2126, .7152, .0722])
    profile = luminance.mean(axis=1)
    peaks = []
    # Fixed windows correspond to the four bands in the reference. They are
    # appearance descriptors, not a claim of radiometric/material calibration.
    for a, b in ((9, 21), (22, 34), (35, 46), (47, 57)):
        y = a + int(profile[a:b].argmax())
        peaks.append(dict(row=y, luminance=round(float(profile[y]), 1)))
    return dict(band_peaks=peaks,
                quiet_median_rgb=np.median(patch[59:70], axis=(0, 1)).tolist(),
                row_luminance=profile.round(3).tolist())


def main(root):
    root = root.resolve()
    build(root)
    assets = root / 'review_assets'
    before = ROOT / 'verification/assembly_topdown_v4_matched/all/images' / (SAMPLE + '.png')
    after = root / 'all/images' / (SAMPLE + '.png')
    sources = [('real', 'Real camera', assets / 'real.jpg'),
               ('before', 'Previous v4 finish', before),
               ('after', 'Updated v5 finish', after)]
    metrics = dict(roi_xyxy=list(ROI), quiet_rows=[59, 70],
                   sample=SAMPLE, note='Local 8-bit display-pixel descriptors, not transfer accuracy.',
                   sources={})
    patches = []
    native = Image.new('RGB', (626, 3 * 191 + 16), (15, 27, 35))
    draw = ImageDraw.Draw(native)
    for i, (key, title, path) in enumerate(sources):
        with Image.open(path) as image:
            im = image.convert('RGB')
        assert im.size == (1920, 1200), (path, im.size)
        crop = im.crop(ROI)
        crop.save(assets / (key + '_patch.png'))
        im.crop((ROI[0], ROI[1] + 59, ROI[2], ROI[1] + 70)).save(assets / (key + '_quiet.png'))
        metrics['sources'][key] = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), **measurements(im))
        patches.append((title, crop))
        draw.text((16, 16 + i * 191), title + ' - native pixels', fill=(223, 235, 240))
        native.paste(im.crop(PART_ROI), (16, 40 + i * 191))
    native.save(assets / 'native_surface_comparison.png')
    contact = Image.new('RGB', (1008, 214), (15, 27, 35))
    draw = ImageDraw.Draw(contact)
    for i, (title, patch) in enumerate(patches):
        draw.text((12 + i * 336, 12), title, fill=(223, 235, 240))
        contact.paste(patch.resize((320, 160), Image.Resampling.NEAREST), (12 + i * 336, 38))
    contact.save(assets / 'patch_comparison.png')
    real = np.array(metrics['sources']['real']['quiet_median_rgb'])
    for key in ('before', 'after'):
        rgb = np.array(metrics['sources'][key]['quiet_median_rgb'])
        metrics['sources'][key]['quiet_median_mean_abs_rgb_difference'] = round(float(np.abs(rgb - real).mean()), 2)
    (root / 'surface_patch_metrics.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')

    cards = ''.join(f'<article><header><h2>{title}</h2><p>Identical 160 × 80 pixel body window</p></header>'
                    f'<img class="patch" src="review_assets/{key}_patch.png">'
                    f'<header><p>Quiet shaded strip, enlarged</p></header>'
                    f'<img class="patch quiet" src="review_assets/{key}_quiet.png"></article>'
                    for key, title, _ in sources)
    rows = ''
    for i in range(4):
        real_peak = metrics['sources']['real']['band_peaks'][i]
        new_peak = metrics['sources']['after']['band_peaks'][i]
        rows += f'<tr><td>Band {i+1}</td><td>{real_peak["row"]} / {new_peak["row"]}</td><td>{real_peak["luminance"]} / {new_peak["luminance"]}</td></tr>'
    rgb = ' · '.join(f'{title}: {metrics["sources"][key]["quiet_median_rgb"]}' for key, title, _ in sources)
    note = f'''<section class="note">
<h2>One small area, examined in layers</h2>
<p>Same native <b>160 × 80</b> body window at x=940–1099, y=735–814 from the supplied cam3936 image and each render. The full camera output remains <b>1920 × 1200</b>. The generated specimen keeps its geometry, defect, camera and seed for the before/after comparison.</p>
<ol><li><b>Reflection structure.</b> Isolating the emitters exposed a fifth broad glossy reflection from the fill light. Its glossy visibility is now disabled. The four inspection bars are repositioned and rebalanced: a stronger upper band and three quieter bands in the Balanced preset.</li>
<li><b>Shaded brass.</b> The blue shadow proxy was tinting the lower wall green. Excluding that proxy from glossy rays and adjusting the warm ambient/oxide contribution brings the quieter body areas closer to brown brass.</li>
<li><b>Fine grain.</b> New seeded, short-scale, directionally correlated finish variations replace the overly uniform stretched texture. Restrained larger roughness variations keep the bands from looking painted on. This is generated material detail; no real part pixels are used as a texture.</li>
<li><b>Contact.</b> The reflection bars illuminate the assemblies through light linking. Ambient light retains the contact shadow without the overly deep floor shadows caused by the reflection-calibration emitters.</li></ol>
</section>
<div class="patch-controls"><label><input id="smooth-patches" type="checkbox" onchange="document.body.classList.toggle('smooth-patches',this.checked)"> Smooth enlargement</label><span>Default: nearest-pixel enlargement so the native detail is visible.</span></div>
<div class="patch-grid">{cards}</div>
<details><summary>Local measurements and their limits</summary><p>The table uses mean display-pixel luminance across the fixed crop, with one peak window per reference band. Positions are rows within the crop; luminance is 0–255. This describes one appearance fit, not physical calibration or a model score. The previous image also has an extra band that a four-window metric cannot represent.</p>
<table><tr><th>Feature</th><th>Peak row: real / updated</th><th>Peak level: real / updated</th></tr>{rows}</table>
<p>Median RGB in the quiet strip (rows 59–69): {rgb}.</p>
<p><a href="surface_patch_metrics.json">Exact crops, source hashes and complete row profiles</a></p></details>
<article><header><h2>Full parts at native pixel scale</h2><p>The finish pass concentrates on the brass body. Copper and neck response still need a separate local comparison.</p></header><img src="review_assets/native_surface_comparison.png" style="width:auto;max-width:100%;margin:auto"></article>
<p class="note">These remain hybrid renders: two verified empty-track camera frames provide the background; every assembly and defect is rendered in Blender. Shared backgrounds can make whole-frame similarity misleading. The patch is closer, but residual differences remain and no indistinguishability or real-world detection claim is established. Twelve labeled examples below cover small/shallow/large dents, a fold, good parts, three roll positions and all three lighting presets. Geometric support labels do not guarantee that every shallow dent is easy to see.</p>'''
    page = (root / 'index.html').read_text(encoding='utf-8')
    page = page.replace('Small and shallow dents · Assembly Studio', 'Brass surface patch study · Assembly Studio')
    page = page.replace('Smaller dents, subtler reflections', 'Brass finish, one small area at a time')
    page = page.replace('New dent mix:', 'Unchanged dent mix:')
    page = page.replace('Previous refined environment', 'Updated finish — same camera station')
    page = page.replace('src="review_assets/previous.png"', f'src="all/images/{SAMPLE}.png"')
    start = page.index('<p class="note">')
    end = page.index('</p>', start) + 4
    page = page[:start] + note + page[end:]
    css = '''.patch-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:20px 0}.patch{image-rendering:pixelated}.smooth-patches .patch{image-rendering:auto}.quiet{margin-bottom:18px}.patch-controls{display:flex;gap:18px;padding:16px}li{margin:12px 0;line-height:1.6}details{padding:20px;margin:18px 0;background:#172630}table{border-collapse:collapse}td,th{padding:10px 18px;border-bottom:1px solid #3c5360;text-align:left}@media(max-width:900px){.patch-grid{grid-template-columns:1fr}}'''
    page = page.replace('</style>', css + '</style>')
    (root / 'index.html').write_text(page, encoding='utf-8')
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    main(parser.parse_args().root)
