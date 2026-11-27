"""Exact values of the cases (tests/truth/<name>.json, written by tests/truth_source/make_truth.py).

Every truth file is an object with exactly the keys `case_id` (the file stem) and `expected` (the exact report of
the case, in the form of SPEC.md section 3) and, optionally, `extra` (further exact values used by task_check.py).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRUTH = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in sorted((HERE / 'truth').glob('*.json'))}
