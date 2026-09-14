from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as s
s.register(); scene=s.fresh_scene(); s.setup_scene(scene)
folder=ROOT/'verification'/'adaptive-v3'; folder.mkdir(exist_ok=True)
for stem in ('machine_s005_soft_box','machine_s005_left_rake','machine_s007_reference'):
    values=json.loads((ROOT/'verification'/'challenge-v3-initial'/'metadata'/(stem+'.json')).read_text())['parameters']
    s.apply_settings(scene,values)
    info=s.export_frame(scene,folder,stem)
    print('ADAPTIVE_RENDER',stem,info['mesh_vertices'],flush=True)
