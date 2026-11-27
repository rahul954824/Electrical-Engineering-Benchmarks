"""Primitives shared by test_outputs.py and task_check.py (final harness code; nothing task-specific).

Every failure is an explicit AssertionError raised by require(): pytest then prints the message only, never
introspected operands, so a message can quote reported values, values derived from the submission and limits, and
never an exact value of tests/truth/.
"""
from __future__ import annotations

import math

# SPEC.md section 3: a reported value at most ROUND_OFF outside a stated bound or ordering stands for the bound
# (it is replaced by the bound before any other rule applies); a value further outside violates the bound.
ROUND_OFF = 1e-9


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def number(value, where):
    """A finite JSON number; booleans and nulls are not numbers (an integer too large for a float is not finite)."""
    require(type(value) in (int, float), f'{where}: must be a finite JSON number')
    try:
        out = float(value)
    except OverflowError:
        raise AssertionError(f'{where}: must be a finite JSON number') from None
    require(math.isfinite(out), f'{where}: must be a finite JSON number')
    return out


def integer(value, where):
    """A JSON integer (not a boolean, not a float such as 2.0)."""
    require(type(value) is int, f'{where}: must be a JSON integer')
    return value


def boolean(value, where):
    require(type(value) is bool, f'{where}: must be JSON true or false')
    return value


def keys_exactly(obj, keys, where):
    require(isinstance(obj, dict), f'{where}: must be a JSON object')
    require(set(obj) == set(keys), f'{where}: keys must be exactly {sorted(keys)}; found {sorted(obj)}')


def number_list(value, where, length=None):
    require(isinstance(value, list), f'{where}: must be a JSON list')
    if length is not None:
        require(len(value) == length, f'{where}: must have {length} entries; found {len(value)}')
    return [number(v, f'{where}[{i}]') for i, v in enumerate(value)]


def at_least(value, bound, where):
    """value >= bound; round-off down to bound - ROUND_OFF stands for the bound."""
    require(value >= bound - ROUND_OFF, f'{where}: reported {value!r} is below the bound {bound!r}')
    return max(value, bound)


def at_most(value, bound, where):
    """value <= bound; round-off up to bound + ROUND_OFF stands for the bound."""
    require(value <= bound + ROUND_OFF, f'{where}: reported {value!r} is above the bound {bound!r}')
    return min(value, bound)


def nonnegative(value, where):
    return at_least(value, 0.0, where)


def increasing(values, where):
    """A list in non-decreasing order; an inversion of at most ROUND_OFF stands for equality."""
    out = list(values)
    for i in range(1, len(out)):
        require(out[i] >= out[i - 1] - ROUND_OFF, f'{where}: entries must be in increasing order')
        out[i] = max(out[i], out[i - 1])
    return out


def within(value, exact, rel, ab, where, stated):
    """|value - exact| <= max(rel |exact|, ab). The message names the tolerance, never the exact value."""
    require(abs(value - float(exact)) <= max(rel * abs(float(exact)), ab),
            f'{where}: reported {value!r} is not within {stated} of the exact value')


def consistent(value, own, rel, ab, where, stated, of_what):
    """|value - own| <= max(rel |own|, ab), where `own` was recomputed by the verifier from other REPORTED values
    (so quoting it reveals nothing about the exact values)."""
    require(abs(value - float(own)) <= max(rel * abs(float(own)), ab),
            f'{where}: reported {value!r} is not within {stated} of {of_what} ({own!r})')
