#!/usr/bin/env python3
"""Write tests/truth/<name>.json for every case of tests/cases/ with the independent implementation.

    python tests/truth_source/make_truth.py            write the truth files
    python tests/truth_source/make_truth.py --check    recompute and compare with the stored files (exit 1 on a
                                                       difference)

Each case directory is rebuilt in a temporary directory from tests/cases/<name>.<file> and
tests/truth_source/independent_program.py is run on it exactly as a submission would be
(`--data <case_dir> --output <report.json>`); with the environment variable TRUTH_GRADE=1, which the independent
program may use to select tighter numerical settings than in its scored run. The truth file is
{"case_id": <name>, "expected": <its report>}. Final harness code: nothing here is task-specific.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
TESTS = HERE.parent
sys.path.insert(0, str(TESTS))
from task_check import CASE_COUNT, CASE_FILES  # noqa: E402


def case_names():
    first = CASE_FILES[0]
    return sorted(p.name[:-len(first) - 1] for p in (TESTS / 'cases').glob(f'*.{first}'))


def expected(name):
    with tempfile.TemporaryDirectory() as tmp:
        case_dir = Path(tmp) / 'case'
        case_dir.mkdir()
        for file_name in CASE_FILES:
            shutil.copyfile(TESTS / 'cases' / f'{name}.{file_name}', case_dir / file_name)
        out = Path(tmp) / 'report.json'
        env = dict(os.environ, TRUTH_GRADE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
        subprocess.run([sys.executable, str(HERE / 'independent_program.py'), '--data', str(case_dir),
                        '--output', str(out)], check=True, env=env, cwd=tmp)
        return json.loads(out.read_text(encoding='utf-8'))


def main():
    check = '--check' in sys.argv[1:]
    names = case_names()
    if len(names) != CASE_COUNT:
        sys.exit(f'tests/cases holds {len(names)} cases, task_check.CASE_COUNT is {CASE_COUNT}')
    (TESTS / 'truth').mkdir(exist_ok=True)
    bad = 0
    for name in names:
        text = json.dumps({'case_id': name, 'expected': expected(name)}, indent=1) + '\n'
        path = TESTS / 'truth' / f'{name}.json'
        if check:
            same = path.is_file() and path.read_text(encoding='utf-8') == text
            bad += not same
            print(f'{name}: {"identical" if same else "DIFFERENT"}')
        else:
            path.write_text(text, encoding='utf-8')
            print(f'{name}: written')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
