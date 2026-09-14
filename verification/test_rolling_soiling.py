from pathlib import Path
import copy
import json
import sys
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root))
from rolling_soiling import assign, material_parameters

original = [dict(index=i, defect=dict(kind='dent', depth=.02+i*.001) if i%3 else None) for i in range(31)]
options = dict(mix_soiling=True, dirty_fraction=.5, dirt_strength=1.)
first = copy.deepcopy(original); assign(first, options, 61000)
repeat = copy.deepcopy(original); assign(repeat, options, 61000)
other = copy.deepcopy(original); assign(other, options, 61001)
assert first == repeat and first != other
assert [i['defect'] for i in first] == [i['defect'] for i in original]
for offset in range(0, 30, 6):
    states = [i['normal_appearance']['category'] for i in first[offset:offset+6]]
    assert states.count('heavy') == 3 and states.count('clean') == 2 and states.count('light') == 1
assert len({i['normal_appearance']['seed'] for i in first}) == 31
disabled = copy.deepcopy(original); assign(disabled, {}, 61000)
assert disabled == original
assert material_parameters({'dust_amount': .22}, disabled[0]) == {'dust_amount': .22}
report = dict(passed=True, deterministic=True, independent_of_defects=True,
    normal_label_policy=True, per_six=dict(heavy=3, clean=2, light=1), unique_soiling_seeds=31)
(root/'verification/rolling-soiling-validation.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report))
