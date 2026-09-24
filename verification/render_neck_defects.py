"""CPU-only development render, with the normal visibility and glare gates."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from neck_defect_plan import make_plan
from verification import render_visibility_robustness as runner
EDGE_ONLY=False

def preview_plan():
    plan=make_plan()
    if EDGE_ONLY:
        plan['samples']=[plan['samples'][3]]
        plan['expected_primary_counts']={'DENT':1};plan['expected_instance_counts']={'DENT':1}
        plan['expected_setup_counts']={'FOREGROUND':1}
        plan['samples'][0]['sample_id']+='_side';plan['samples'][0]['specimen_id']+='_side'
        plan['samples'][0]['review_scenario']='Crescent toward the neck silhouette'
    plan['preview']=True
    for row in plan['samples']:row['split']='test'
    return plan

runner.preview_plan=preview_plan
if __name__=='__main__':
    EDGE_ONLY='--edge-only' in sys.argv
    if EDGE_ONLY:sys.argv.remove('--edge-only')
    runner.main()
