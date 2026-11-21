#!/usr/bin/env bash
# Train every sensor variant (2 at a time on one 24 GB GPU). Logs: logs/rsl_rl/tactile_a1_<variant>/
set -u
cd "$(dirname "$0")/.."
PY=${PY:-python}
run() { $PY scripts/train.py --task Tactile-A1-$1-v0 --headless --seed 42 > logs/train_$1.log 2>&1; echo "$1 exit=$?"; }
mkdir -p logs
for pair in "baseline all" "fsr slip" "resistance vibro"; do
  set -- $pair; run $1 & run $2 & wait
done
echo TRAIN DONE
