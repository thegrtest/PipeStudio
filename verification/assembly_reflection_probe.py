"""One diagnostic render isolating reflection energy from ambient fill."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from assembly_plan import make_specimen,capture_pose
from assembly_scene import build_scene,pose_scene
from assembly_realism import configure_lights
r=make_specimen(361000,'dent',allowed_defects=('dent',))
scene,rig,body=build_scene(r,48)
pose_scene(scene,rig,body,r,capture_pose(r,1))
configure_lights(scene,r,.28)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.55
out=ROOT/'verification/assembly_reflection_probe';out.mkdir(exist_ok=True)
scene.render.filepath=str(out/'probe.png');bpy.ops.render.render(write_still=True)
