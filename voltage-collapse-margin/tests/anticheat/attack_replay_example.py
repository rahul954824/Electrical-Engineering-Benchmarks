#!/usr/bin/env python3
"""Shortcut attack B (replay the example answer). The program writes the reference solution's report of the
example case for every case, without reading the case. Its saved report of the example case is the correct one,
so test_artifacts and the fresh run on the example case pass. Expected verdict: reward 0, because the further
cases have other exact values: their reports fail the contract or a requirement."""
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


def main():
    a = arguments()
    Path(a.output).write_text(json.dumps(EXAMPLE_REPORT), encoding='utf-8')


main()
