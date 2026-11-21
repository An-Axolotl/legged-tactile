#!/usr/bin/env bash
# Mixed-terrain evaluation (flat, stair pyramids, rocky steps, rough, slopes) + wide original-style videos.
set -u
cd "$(dirname "$0")/.."
PY=${PY:-python}
EV="$PY scripts/evaluate.py --headless --terrain mixed"
mkdir -p logs
for v in baseline fsr resistance slip vibro all; do
  $EV --variant $v > logs/eval_${v}_mixed.log 2>&1; echo "mixed $v $?"
  if [ $v != baseline ]; then
    $EV --variant $v --fault dead  > logs/eval_${v}_mixed_dead.log 2>&1;  echo "mixed dead $v $?"
    $EV --variant $v --fault noisy > logs/eval_${v}_mixed_noisy.log 2>&1; echo "mixed noisy $v $?"
  fi
done
V="$EV --enable_cameras --video --wide 32"
for s in extreme_ice ice wet regular sticky glue extra_sticky; do
  for v in baseline all; do
    $V --variant $v --surfaces $s > logs/video_${v}_${s}_mixed.log 2>&1; echo "video $v $s $?"
  done
done
for s in regular ice; do
  $V --variant all --fault dead --surfaces $s > logs/video_all_${s}_mixed_dead.log 2>&1; echo "video dead $s $?"
done
echo MIXED DONE
