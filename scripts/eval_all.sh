#!/usr/bin/env bash
# All evaluation runs behind the README (≈ 1.5 h on one RTX 4090).
#   metrics: 6 policies x {flat, rough, flat + dead sensors, flat + noisy sensors}, 128 robots per surface
#   videos : baseline vs all-sensors on every surface (flat), on ice/glue (rough), and all-sensors with dead sensors
set -u
cd "$(dirname "$0")/.."
PY=${PY:-python}
EV="$PY scripts/evaluate.py --headless"
mkdir -p logs
for v in baseline fsr resistance slip vibro all; do
  $EV --variant $v                > logs/eval_$v.log 2>&1;           echo "flat  $v $?"
  $EV --variant $v --terrain rough > logs/eval_${v}_rough.log 2>&1;  echo "rough $v $?"
  if [ $v != baseline ]; then
    $EV --variant $v --fault dead  > logs/eval_${v}_dead.log 2>&1;   echo "dead  $v $?"
    $EV --variant $v --fault noisy > logs/eval_${v}_noisy.log 2>&1;  echo "noisy $v $?"
  fi
done
V="$EV --enable_cameras --video"
for v in baseline all; do
  $V --variant $v > logs/video_$v.log 2>&1; echo "video $v $?"
  $V --variant $v --terrain rough --surfaces ice,glue > logs/video_${v}_rough.log 2>&1; echo "video rough $v $?"
done
for v in fsr resistance slip vibro; do
  $V --variant $v --surfaces extreme_ice,ice,glue > logs/video_$v.log 2>&1; echo "video $v $?"
done
$V --variant all --fault dead --surfaces regular,ice > logs/video_all_dead.log 2>&1; echo "video dead $?"
$PY scripts/make_media.py > logs/make_media.log 2>&1; echo "media $?"
$PY scripts/write_readme.py; echo "readme $?"
echo EVAL DONE
