"""Issue a binary reward only for a complete, consistent grading report.

The expected node set is exact: test_artifacts and one test_case[<name>] per truth file, CASE_COUNT of them
(task_check.py; SPEC.md section 4 states the same number of runs). A missing, duplicated, skipped or unexpected
node, a setup or teardown error, or a summary that disagrees with the node outcomes leaves the fail-safe reward 0
of test.sh in place and raises.
"""
import json
from pathlib import Path
import sys

from task_check import CASE_COUNT
from truth import TRUTH


def expected_nodes():
    if len(TRUTH) != CASE_COUNT:
        raise ValueError(f'tests/truth lists {len(TRUTH)} cases, not {CASE_COUNT}')
    nodes = {'test_outputs.py::test_artifacts'}
    nodes |= {f'test_outputs.py::test_case[{name}]' for name in TRUTH}
    return nodes


def grade(report, pytest_status):
    if pytest_status not in (0, 1):
        raise ValueError('pytest did not complete grading')
    results = report['results']
    tests = results['tests']
    expected = expected_nodes()
    names = [item['name'] for item in tests]
    if len(names) != len(expected) or set(names) != expected:
        raise ValueError('missing, duplicated or unexpected grading nodes')
    statuses = [item['status'] for item in tests]
    if any(status not in ('passed', 'failed') for status in statuses):
        raise ValueError('grading was skipped or incomplete')
    for item in tests:
        phases = item.get('extra', {}).get('failure_phases', [])
        if item['status'] == 'failed' and (not phases or any(phase != 'call' for phase in phases)):
            raise ValueError('verifier setup/teardown error or missing failure evidence')
    summary = results['summary']
    counts = {status: statuses.count(status) for status in ('passed', 'failed', 'skipped', 'pending', 'other')}
    if summary['tests'] != len(expected) or any(summary.get(key, 0) != value for key, value in counts.items()):
        raise ValueError('inconsistent grading summary')
    failed = counts['failed'] > 0
    if pytest_status != int(failed):
        raise ValueError('pytest exit status disagrees with actual test outcomes')
    return int(not failed)


if __name__ == '__main__':
    logs = Path('/logs/verifier')
    score = grade(json.loads((logs / 'ctrf.json').read_text(encoding='utf-8')), int(sys.argv[1]))
    assert score in (0, 1)
    (logs / 'reward.txt').write_text('1\n' if score == 1 else '0\n', encoding='utf-8')
