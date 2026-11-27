"""A report holds the collapse loading of the network, the voltage magnitude of every bus in the state reached at
that loading, and the kind of collapse; all are compared with the exact values of the case in
tests/truth/<name>.json.

The only task-specific module of the verifier. test_outputs.py calls, in this order,

    case   = parse_case(texts)                  texts: {file name of CASE_FILES: text of the stored file}
    values = validate(report, case, where)      contract of SPEC.md section 3 (before any exact value is used)
    consistency(values, case, where)            every reported value defined through other reported values
    compare(values, truth, case, where)         against tests/truth/<name>.json (truth['expected'])

Rules for this file:
  * raise only through the primitives of checks.py: a message quotes reported values and limits, never an exact
    value, and no f-string in a message interpolates a name holding one;
  * validate() uses nothing of the truth; bounds go through at_least so that round-off of at most ROUND_OFF stands
    for the bound (SPEC.md section 3 states this as an output rule);
  * every tolerance below has a row in the README table "Tolerances and their rationale".
"""
from __future__ import annotations

import json

from checks import ROUND_OFF, at_least, keys_exactly, nonnegative, number, number_list, require, within  # noqa: F401

# --- task parameters (SPEC.md sections 4 and 5; README; task.toml [verifier].timeout_sec >= 1.5 x their product)
CASE_COUNT = 7             # the example case and six further cases
CALL_SECONDS = 120         # wall clock of one run of the program, from process start to exit
CASE_FILES = ('case.json',)   # the files of a case directory (SPEC.md section 2); case.json carries `case_id`

# --- tolerances (README, Tolerances and their rationale)
TOL_LOADING = (1e-4, 0.0)     # requirement 1: collapse_loading within 1e-4 relative
TOL_VOLTAGE = (0.0, 1e-3)     # requirement 2: every entry of bus_voltage_pu within 1e-3 p.u.
KINDS = ('fold', 'limit')     # requirement 3: collapse_kind equals the kind of the case
TOP_KEYS = ('collapse_loading', 'bus_voltage_pu', 'collapse_kind')


def parse_case(texts):
    """The parsed case.json: its case_id and its number of buses (the length of the reported list)."""
    case = json.loads(texts['case.json'])
    return {'case_id': case['case_id'], 'buses': len(case['buses'])}


def validate(report, case, where):
    """Contract of SPEC.md section 3: exact keys, a non-negative collapse loading (round-off of at most 1e-9 below
    zero stands for zero), one finite non-negative magnitude per bus, and one of the two kinds as a string."""
    keys_exactly(report, TOP_KEYS, where)
    loading = nonnegative(number(report['collapse_loading'], f'{where}.collapse_loading'), f'{where}.collapse_loading')
    volts = number_list(report['bus_voltage_pu'], f'{where}.bus_voltage_pu', length=case['buses'])
    volts = [nonnegative(v, f'{where}.bus_voltage_pu[{i}]') for i, v in enumerate(volts)]
    kind = report['collapse_kind']
    require(type(kind) is str and kind in KINDS, f'{where}.collapse_kind: must be one of the strings {list(KINDS)}')
    return {'collapse_loading': loading, 'bus_voltage_pu': volts, 'collapse_kind': kind}


def consistency(values, case, where):
    """SPEC.md section 3 defines no reported value through other reported values: nothing to recompute."""
    return None


def compare(values, truth, case, where):
    """Requirement 1: the collapse loading within 1e-4 relative. Requirement 2: every magnitude within 1e-3 p.u.
    Requirement 3: the kind of collapse."""
    exact = truth['expected']
    within(values['collapse_loading'], exact['collapse_loading'], *TOL_LOADING, f'{where}.collapse_loading',
           '1e-4 relative')
    for i, (value, ex) in enumerate(zip(values['bus_voltage_pu'], exact['bus_voltage_pu'])):
        within(value, ex, *TOL_VOLTAGE, f'{where}.bus_voltage_pu[{i}]', '1e-3 p.u.')
    require(values['collapse_kind'] == exact['collapse_kind'],
            f'{where}.collapse_kind: reported {values["collapse_kind"]!r} is not the kind of collapse of the case')
