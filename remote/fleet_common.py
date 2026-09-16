"""Pure planning and file-integrity helpers shared by fleet controller and nodes."""
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import uuid


def digest_file(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): result.update(block)
    return result.hexdigest()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def read_json(path, default=None):
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError: return default


def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', value):
        raise ValueError('Unsafe job/node identifier')
    return value


def inside(root, relative):
    path = (Path(root)/relative).resolve()
    if not path.is_relative_to(Path(root).resolve()) or path == Path(root).resolve():
        raise ValueError('Path leaves its dataset directory')
    return path


def allocate(count, nodes):
    """Smooth weighted round robin: deterministic, complete, and no duplicate work."""
    names = list(nodes)
    if not names or count < len(names):
        raise ValueError('There must be at least one sample per selected node')
    weights = {name: int(nodes[name].get('weight', 1)) for name in names}
    if any(weight <= 0 for weight in weights.values()):
        raise ValueError('Node weights must be positive integers')
    assigned = {name: [] for name in names}
    score = dict.fromkeys(names, 0)
    for index in range(count):
        if index < len(names):
            selected = names[index]
        else:
            for name in names: score[name] += weights[name]
            selected = max(names, key=score.get)
            score[selected] -= sum(weights.values())
        assigned[selected].append(index)
    return assigned


def split_plan(plan, assignments):
    indices = [i for values in assignments.values() for i in values]
    if sorted(indices) != list(range(len(plan['samples']))):
        raise ValueError('Assignments must cover the plan exactly once')
    result = {}
    for name, values in assignments.items():
        shard = copy.deepcopy(plan)
        shard['samples'] = [copy.deepcopy(plan['samples'][i]) for i in values]
        shard['fleet_parent_sha256'] = digest_json(plan)
        shard['fleet_node'] = name
        rows = shard['samples']
        if 'generation_policy' in shard:
            ids={r['sample_id'] for r in rows}
            shard['generation_policy']['preserved_sample_ids']=[sid for sid in shard['generation_policy'].get('preserved_sample_ids',[]) if sid in ids]
        shard['expected_primary_counts'] = dict(Counter(r['primary_kind'] for r in rows))
        shard['expected_instance_counts'] = dict(Counter(a['kind'] for r in rows for a in r['instances']))
        shard['expected_setup_counts'] = dict(Counter(r['setup'] for r in rows))
        result[name] = shard
    return result
