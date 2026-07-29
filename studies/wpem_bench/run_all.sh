#!/bin/sh
# Run every benchmark case, one at a time.
#
# Serially on purpose: several of these hold the full Jacobian for a
# 6000-point multi-phase model, and four concurrently was enough to get one
# OOM-killed on a 26 GB machine.
set -u
cd "$(dirname "$0")" || exit 1
PY=../../.venv/bin/python
rm -f logs/seq.status
mkdir -p logs
for case in run_nacl_li2co3 run_mnru run_pbso4 run_tb2bacoo5 run_ti15nb run_egypt run_insitu; do
    printf '>>> %s\n' "$case"
    "$PY" -u "$case.py" > "logs/${case#run_}.log" 2>&1
    printf '%s=%s\n' "$case" "$?" >> logs/seq.status
done
printf 'ALLDONE\n' >> logs/seq.status
