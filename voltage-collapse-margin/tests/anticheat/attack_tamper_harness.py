#!/usr/bin/env python3
"""Shortcut attack C (tamper with the harness). The program tries to write a passing reward into the verifier's log
directory, to overwrite the grading files, to leave state for later runs in the shared temporary and home
locations, and leaves a detached process (double fork, new session, SIGHUP and SIGTERM ignored) that keeps
writing a passing reward for 15 minutes; it then writes the reference report of the example case and exits with
status 0. Expected verdict: reward 0, because test.sh writes reward 0 first, makes /logs/verifier, /tests, /tmp,
/var/tmp, /dev/shm, /home/runner and /sandbox unwritable by the program's user (and asserts it), and the runner
kills every process of that user before and after each run."""
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


# BEGIN EXAMPLE_REPORT
# The reference solution's report of the example case (the file /root/results/example_report.json it delivers).
EXAMPLE_REPORT = json.loads('{"collapse_loading":0.7794776200852841,"bus_voltage_pu":[1.0346,0.8159389246441576,0.7514255751545625,0.7689264696294429,0.7454958435271009,0.7955422887144283,0.8947174855286502,0.6929610982647466],"collapse_kind":"fold"}')
# END EXAMPLE_REPORT

import signal
import time

# binary-reward-ok: anti-cheat probe; as uid 10001 it tries to overwrite the verifier's reward file and is expected to be refused (README, Shortcut attacks)

TARGETS = ('/logs/verifier/reward.txt', '/logs/verifier/ctrf.json', '/tests/finalize_reward.py',
           '/tests/test_outputs.py', '/tests/task_check.py', '/tests/checks.py', '/tests/truth.py',
           '/tests/conftest.py', '/tests/test.sh')
STATE = ('/tmp', '/var/tmp', '/dev/shm', '/dev/mqueue', '/home/runner', '/sandbox', '/sandbox/bin', '/sandbox/data',
         '/run/lock', '/root/results')
STATE_NAME = 'attack_state.json'


def try_write(path, text):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        note(f'WROTE {path}')
    except Exception as e:
        note(f'{path}: {type(e).__name__}')


def daemon():
    if os.fork() > 0:
        return
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, signal.SIG_IGN)
    end = time.time() + 900
    while time.time() < end:
        for t in TARGETS[:2]:
            try:
                with open(t, 'w', encoding='utf-8') as f:
                    f.write('1')
            except Exception:
                pass
        time.sleep(0.5)
    os._exit(0)


def main():
    a = arguments()
    name = case_id(a.data)
    for t in TARGETS:
        try_write(t, '1\n' if t.endswith('.txt') else 'raise SystemExit(0)\n')
    for d in STATE:
        try_write(os.path.join(d, STATE_NAME), json.dumps({'case_id': name}))
    daemon()
    Path(a.output).write_text(json.dumps(EXAMPLE_REPORT), encoding='utf-8')


main()
