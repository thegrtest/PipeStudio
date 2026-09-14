"""Temporary material-only visual experiment; no core code or references edited.

blender -b --factory-startup --python verification/tune_finish_v3.py
.venv/Scripts/python.exe verification/tune_finish_v3.py --sheet
"""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'verification'/'finish-v3-tuning'
VARIANTS={
 'baseline':{},
 'drawn_medium':{'grain':(45,65,65),'lines':(.7,65,65),'drawing_bump_factor':3,
     'grain_roughness_factor':1.65,'patina_roughness_factor':1.3,
     'scratch_color_factor':1.35,'scuff_color_amount':.55,'smudge_color_amount':.36,
     'alloy_dark_factor':.92},
 'drawn_strong':{'grain':(32,48,48),'lines':(.7,45,45),'drawing_bump_factor':5,
     'grain_roughness_factor':2.1,'patina_roughness_factor':1.6,
     'scratch_color_factor':1.7,'scuff_color_amount':.68,'smudge_color_amount':.42,
     'alloy_dark_factor':.84},
}

def render():
    sys.path.insert(0,str(ROOT))
    import bpy
    import pipe_studio as studio
    source=ROOT/'verification'/'challenge-v3-initial'/'metadata'/'godslight_s000_reference.json'
    values=json.loads(source.read_text())['parameters']
    values.update(resolution=960,samples=48)
    studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
    original_update=studio.update_brass
    active={}
    def tuned(material,settings):
        original_update(material,settings)
        nodes=material.node_tree.nodes
        # These static finish-mix inputs are not reset by the base updater.
        nodes['Handling scuff color amount'].inputs[1].default_value=.40
        nodes['Handling smudge color amount'].inputs[1].default_value=.30
        if not active: return
        scale=settings.radius/.9
        nodes['Fine metal grainScale'].inputs[1].default_value=tuple(v/scale for v in active['grain'])
        nodes['Drawing linesScale'].inputs[1].default_value=tuple(v/scale for v in active['lines'])
        nodes['DrawingBump'].inputs['Distance'].default_value*=active['drawing_bump_factor']
        nodes['Grain roughness amplitude'].inputs[1].default_value*=active['grain_roughness_factor']
        nodes['Patina roughness amplitude'].inputs[1].default_value*=active['patina_roughness_factor']
        nodes['Scratch color amount'].inputs[1].default_value*=active['scratch_color_factor']
        nodes['Handling scuff color amount'].inputs[1].default_value=active['scuff_color_amount']
        nodes['Handling smudge color amount'].inputs[1].default_value=active['smudge_color_amount']
        low=nodes['AlloyColors'].color_ramp.elements[0]
        low.color=tuple(v*active['alloy_dark_factor'] for v in low.color[:3])+(1,)
    studio.update_brass=tuned
    results=[]
    for name,parameters in VARIANTS.items():
        active.clear();active.update(parameters)
        studio.apply_settings(scene,values)
        info=studio.export_frame(scene,OUT,name)
        info['test_overrides']=parameters
        results.append(info)
        print('TUNED_FINISH_RENDERED '+name,flush=True)
    studio.atomic_json(OUT/'experiment.json',{'source_parameters':values,'variants':results,
      'note':'Material-only monkeypatch experiment. Baseline illumination, camera and geometry unchanged.'})

def sheet():
    from PIL import Image,ImageDraw,ImageFont,ImageOps
    OUT.mkdir(parents=True,exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/consola.ttf',20)
    frames=[('Real reference',ROOT/'references'/'godslight-horizontal.jpg')]
    frames.extend((name,OUT/'images'/(name+'.png')) for name in VARIANTS)
    canvas=Image.new('RGB',(1920,1310),'#13202b');d=ImageDraw.Draw(canvas)
    for index,(label,path) in enumerate(frames):
        image=Image.open(path).convert('RGB');image=ImageOps.contain(image,(950,603))
        x=(index%2)*960;y=(index//2)*655
        d.text((x+12,y+8),label,fill='white',font=font)
        canvas.paste(image,(x,y+38))
    canvas.save(OUT/'comparison.jpg',quality=95)
    crops=Image.new('RGB',(1800,1000),'#13202b');d=ImageDraw.Draw(crops)
    for index,(label,path) in enumerate(frames):
        image=Image.open(path).convert('RGB')
        if index==0: box=(300,545,1260,790)
        else: box=(150,270,630,393)
        crop=image.crop(box);crop=ImageOps.contain(crop,(890,400))
        x=(index%2)*900;y=(index//2)*500
        d.text((x+12,y+8),label,fill='white',font=font);crops.paste(crop,(x,y+45))
    crops.save(OUT/'body-comparison.jpg',quality=95)

if __name__=='__main__':
    if '--sheet' in sys.argv: sheet()
    else: render()
