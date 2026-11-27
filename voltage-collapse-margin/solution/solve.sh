#!/bin/bash
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd /root
mkdir -p /root/results
cp /solution/tool.py /root/results/tool.py
# the report of the example case, computed at run time by the delivered program
python3 /root/results/tool.py --data /root/data/example --output /root/results/example_report.json
