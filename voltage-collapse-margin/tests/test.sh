#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
# Fail-safe: a reward of 0 exists before any grading step; finalize_reward.py overwrites it with 1 on success.
echo 0 > /logs/verifier/reward.txt
# The program runs as uid 10001. Host bind mounts may otherwise expose a writable
# reward directory, letting a detached child rename and replace the final reward.
chmod 700 /logs/verifier
# The program may write only its fresh per-call working directory. Shared temporary/home locations must not
# carry state between invocations, and /root (the artifacts) and /tests (truth and cases) stay private.
chown root:root /home/runner /sandbox
for d in /tmp /var/tmp /home/runner /dev/shm /dev/mqueue /run/lock /tests /root; do
    if [ -e "$d" ]; then chmod 700 "$d"; fi
done
chmod 755 /sandbox
rm -f /logs/verifier/ctrf.json
python -c 'import os; os.setgroups([]); os.setgid(10001); os.setuid(10001); assert all(not os.access(p, os.W_OK) for p in ["/logs/verifier", "/tmp", "/var/tmp", "/home/runner", "/dev/shm", "/dev/mqueue", "/run/lock", "/sandbox", "/tests"]), "program could write persistent verifier state"; assert all(not os.access(p, os.R_OK) for p in ["/tests", "/root"]), "program could read the verifier or the artifacts"'
# Deterministic verifier process: fixed hash seed, single-threaded numerical libraries.
export PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
pytest_status=0
pytest -rA --tb=short -p no:cacheprovider --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py || pytest_status=$?
# Interrupted collection, internal errors, usage errors and empty collections
# are infrastructure failures. Preserve diagnostics without issuing a score.
if (( pytest_status > 1 )); then
    exit "$pytest_status"
fi
python /tests/finalize_reward.py "$pytest_status"
