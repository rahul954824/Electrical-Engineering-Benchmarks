#!/usr/bin/env python3
"""Generate the example case and the further cases (SPEC.md section 5).

    python tests/truth_source/generate_cases.py            write environment/data/example/ and tests/cases/
    python tests/truth_source/generate_cases.py --check    regenerate and compare byte for byte (exit 1 on a
                                                           difference)

One random stream with the fixed seed SEED produces draws of the family one after another. A draw is kept only if
it meets the three rules of SPEC.md section 5 (accept()). The first kept draw that collapses at a smooth maximum
is the example case. Of the kept draws after it, the first three that collapse at a smooth maximum and the first
three that collapse at a mode change are the six further cases, numbered in the order in which they were drawn.
The seed was fixed before any case was solved and is never changed.
"""
import json
import math
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
TASK = TESTS.parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(HERE))
from task_check import CASE_COUNT, CASE_FILES  # noqa: E402
import independent_program as ind  # noqa: E402

SEED = 20261125
PER_KIND = 3               # further cases of each kind of collapse
V_BASE = (0.94, 1.08)      # rule (a): magnitudes of the base state, p.u.
LOADING_MIN = 0.2          # rule (b): smallest collapse loading
CLEARANCE = 0.01           # rule (c): a mode change that is not the collapse state lies this far below it


def r4(x):
    return round(float(x), 4)


def draw_case(rng):
    """One draw of the family of SPEC.md section 5 (without the base state)."""
    n = int(rng.integers(6, 10))
    units = int(rng.integers(2, 4))
    unit_buses = sorted(int(b) for b in rng.choice(np.arange(1, n), size=units, replace=False))
    pairs = set()
    for i in range(1, n):
        pairs.add((int(rng.integers(0, i)), i))
    extra = int(rng.integers(1, 4))
    while len(pairs) < n - 1 + extra:
        a, b = sorted(int(v) for v in rng.choice(n, size=2, replace=False))
        pairs.add((a, b))
    pairs = sorted(pairs)
    transformers = set(int(k) for k in rng.choice(len(pairs), size=2, replace=False))
    branches = []
    for k, (a, b) in enumerate(pairs):
        if k in transformers:
            branches.append({'from': a, 'to': b, 'r': 0.0, 'x': r4(rng.uniform(0.04, 0.12)), 'b': 0.0,
                             'tap': round(float(rng.uniform(0.94, 1.06)), 3)})
        else:
            x = rng.uniform(0.06, 0.24)
            branches.append({'from': a, 'to': b, 'r': r4(x * rng.uniform(0.08, 0.30)), 'x': r4(x),
                             'b': r4(rng.uniform(0.01, 0.08)), 'tap': 1.0})
    buses = []
    for i in range(n):
        if i != 0 and (i not in unit_buses or rng.random() < 0.5):
            pd = rng.uniform(0.25, 0.90)
            qd = pd * math.tan(math.acos(rng.uniform(0.85, 0.98)))
            dpd = pd * rng.uniform(0.5, 1.5)
            dqd = dpd * math.tan(math.acos(rng.uniform(0.85, 0.98)))
        else:
            pd = qd = dpd = dqd = 0.0
        buses.append({'pd': r4(pd), 'qd': r4(qd), 'dpd': r4(dpd), 'dqd': r4(dqd), 'gs': 0.0, 'bs': 0.0})
    load_buses = [i for i in range(n) if buses[i]['pd'] > 0 and i not in unit_buses]
    for i in rng.choice(load_buses, size=min(len(load_buses), int(rng.integers(1, 3))), replace=False):
        buses[int(i)]['bs'] = r4(rng.uniform(0.05, 0.25))
    total = sum(b['pd'] for b in buses)
    increase = sum(b['dpd'] for b in buses)
    w = rng.uniform(0.5, 1.5, size=units)
    w /= w.sum()
    share, dshare = rng.uniform(0.5, 0.8), rng.uniform(0.4, 0.8)
    generators = [{'bus': 0, 'slack': True, 'vset': r4(rng.uniform(1.02, 1.05))}]
    for k, b in enumerate(unit_buses):
        pg = share * total * w[k]
        qmax = pg * rng.uniform(0.6, 1.6)
        generators.append({'bus': b, 'slack': False, 'pg': r4(pg), 'dpg': r4(dshare * increase * w[k]),
                           'vset': r4(rng.uniform(1.00, 1.05)), 'qmin': r4(-qmax * rng.uniform(0.2, 0.5)),
                           'qmax': r4(qmax), 'mode_base': 'regulating'})
    return {'buses': buses, 'branches': branches, 'generators': generators}


def base_state(case):
    """Modes and state at zero loading: start with every generator regulating, solve, move every generator whose
    condition is violated to the mode of the violated condition, and repeat until none is. Writes `mode_base`,
    `voltage_base_pu` and `angle_base_deg` (rounded) into the case; False if the iteration finds no base state."""
    n = len(case['buses'])
    for bus in case['buses']:
        bus['voltage_base_pu'] = 1.0
        bus['angle_base_deg'] = 0.0
    for g in case['generators']:
        case['buses'][g['bus']]['voltage_base_pu'] = g['vset']
    for _ in range(12):
        model = ind.Model(case)
        th = np.radians([bus['angle_base_deg'] for bus in case['buses']])
        v = np.array([bus['voltage_base_pu'] for bus in case['buses']], dtype=float)
        solved = model.solve(th, v, 0.0, iterations=60)
        if solved is None or min(solved[1]) < 0.5:
            return False
        th, v = solved
        changes = model.violations(th, v, 0.0, slack=1e-9)
        for i, bus in enumerate(case['buses']):
            bus['voltage_base_pu'] = r4(v[i])
            bus['angle_base_deg'] = r4(math.degrees(th[i]))
        if not changes:
            return True
        units = [g for g in case['generators'] if not g['slack']]
        for k, target in changes:
            units[k]['mode_base'] = target
    return False


def accept(case):
    """Rules (a) to (c) of SPEC.md section 5; returns the kind of collapse of a kept draw, None otherwise."""
    if not base_state(case):
        return None
    magnitudes = [bus['voltage_base_pu'] for bus in case['buses']]
    if min(magnitudes) < V_BASE[0] or max(magnitudes) > V_BASE[1]:
        return None
    trace = []
    report = ind.collapse(json.loads(json.dumps(case)), trace)
    loading = report['collapse_loading']
    if loading < LOADING_MIN:
        return None
    changes = [lam for _, _, lam in trace]
    if report['collapse_kind'] == 'limit':
        changes = changes[:-1]
    if any(lam > loading - CLEARANCE for lam in changes):
        return None
    return report['collapse_kind']


def cases():
    rng = np.random.default_rng(SEED)
    out = {}
    count = {'fold': 0, 'limit': 0}
    while len(out) < CASE_COUNT:
        case = draw_case(rng)
        kind = accept(case)
        if kind is None:
            continue
        if 'example' not in out:
            if kind == 'fold':
                out['example'] = case
            continue
        if count[kind] < PER_KIND:
            count[kind] += 1
            out[f'further_{len(out)}'] = case
    return out


def text_of(name, case):
    doc = {'case_id': name, 'units': 'per unit on 100 MVA; angles in degrees'}
    doc.update(case)
    return json.dumps(doc, indent=1) + '\n'


def main():
    check = '--check' in sys.argv[1:]
    bad = 0
    assert CASE_FILES == ('case.json',)
    for name, case in cases().items():
        text = text_of(name, case)
        targets = [TESTS / 'cases' / f'{name}.case.json']
        if name == 'example':
            targets.append(TASK / 'environment' / 'data' / 'example' / 'case.json')
        for path in targets:
            if check:
                same = path.is_file() and path.read_text(encoding='utf-8') == text
                bad += not same
                print(f'{path.relative_to(TASK)}: {"identical" if same else "DIFFERENT"}')
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
                print(f'{path.relative_to(TASK)}: written')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
