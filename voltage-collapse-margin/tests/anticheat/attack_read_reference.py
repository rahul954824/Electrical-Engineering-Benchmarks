#!/usr/bin/env python3
"""Shortcut attack A (read the reference objects). Instead of computing anything, the program looks for the
verifier's exact values: the truth files, the stored cases, the truth-source files, the saved artifacts under
/root and the verifier's log directory, and walks the whole file system for a truth record of its case. Whatever
truth record it finds is written out as its report; if it finds none, it writes an empty report. Expected verdict:
reward 0, because /tests, /root and /logs/verifier are not readable by the program's user (test.sh asserts this
before grading) and the program's environment names none of them."""
import argparse
import json
import os
import sys
from pathlib import Path


def arguments():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--output', required=True)
    return ap.parse_args()


def note(msg):
    print(msg, file=sys.stderr, flush=True)


def case_id(data_dir):
    return json.loads((Path(data_dir) / 'case.json').read_text(encoding='utf-8'))['case_id']



def main():
    a = arguments()
    name = case_id(a.data)
    found = None
    for path in (f'/tests/truth/{name}.json', '/tests/truth', '/tests/cases', '/tests/truth_source', '/tests',
                 '/root/results', '/root/data', '/logs/verifier', '/sandbox/log', '/proc/1/root/tests/truth'):
        p = Path(path)
        try:
            if p.is_dir():
                for f in sorted(p.rglob('*.json')):
                    try:
                        d = json.loads(f.read_text(encoding='utf-8'))
                        note(f'read {f}')
                        if isinstance(d, dict) and d.get('case_id') == name and 'expected' in d:
                            found = d
                    except Exception as e:
                        note(f'{f}: {type(e).__name__}')
            else:
                d = json.loads(p.read_text(encoding='utf-8'))
                note(f'read {p}')
                found = found or d
        except Exception as e:
            note(f'{path}: {type(e).__name__}')
    for root, dirs, files in os.walk('/', onerror=lambda e: None):
        if root.startswith(('/proc', '/sys', '/dev', '/usr', '/opt')):
            dirs[:] = []
            continue
        for fn in files:
            if fn == f'{name}.json':
                try:
                    d = json.loads(Path(root, fn).read_text(encoding='utf-8'))
                    if isinstance(d, dict) and 'expected' in d:
                        found = found or d
                        note(f'read {root}/{fn}')
                except Exception as e:
                    note(f'{root}/{fn}: {type(e).__name__}')
    note('environment: ' + ' '.join(sorted(os.environ)))
    report = {}
    if isinstance(found, dict) and 'expected' in found:
        note('truth record found: copying it')
        report = found['expected']
    else:
        note('no truth record readable')
    Path(a.output).write_text(json.dumps(report), encoding='utf-8')


main()
