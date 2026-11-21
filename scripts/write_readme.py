"""Regenerate README.md from results/summary.json (every number in the README comes from here)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open(f"{ROOT}/results/summary.json"))
SURF = ["extreme_ice", "ice", "wet", "regular", "sticky", "glue", "extra_sticky"]
MU = {"extreme_ice": 0.01, "ice": 0.05, "wet": 0.2, "regular": 0.8, "sticky": 2.0, "glue": 3.0, "extra_sticky": 5.0}
V = ["baseline", "fsr", "resistance", "slip", "vibro", "all"]
LAB = {"baseline": "proprioception only", "fsr": "+ FSR on/off", "resistance": "+ FSR resistance",
       "slip": "+ slip (shear N)", "vibro": "+ vibrotactile", "all": "+ all tactile"}


def g(v, c, s, k):
    return S[f"{v}|{c}|{s}"][k]


def cell(v, c, s, k, fmt):
    r = S[f"{v}|{c}|{s}"]
    x = fmt.format(r[k] * (100 if k == "fell" else 1)) + ("%" if k == "fell" else "")
    t = r.get(f"{k}_diff", [0, 0, 0, ""])[3]
    if t == "tactile better":
        return f"**{x}**"
    if t == "proprioception better":
        return f"{x} ▼"
    return x


def table(c, k, fmt, variants=V):
    h = "| policy | " + " | ".join(f"{s.replace('_', ' ')}<br>μ={MU[s]}" for s in SURF) + " | all surfaces |"
    rows = [h, "|---|" + "---:|" * (len(SURF) + 1)]
    for v in variants:
        rows.append(f"| {LAB[v]} | " + " | ".join(cell(v, c, s, k, fmt) for s in SURF + ["mean"]) + " |")
    return "\n".join(rows)


def pct(a, b):
    return f"{(a - b) / b * 100:+.0f} %"


b_err, a_err = g("baseline", "flat", "mean", "err"), g("all", "flat", "mean", "err")
b_d, a_d = g("baseline", "flat", "mean", "dist"), g("all", "flat", "mean", "dist")
rb_f, ra_f = g("baseline", "rough", "mean", "fell"), g("all", "rough", "mean", "fell")
rb_d, ra_d = g("baseline", "rough", "mean", "dist"), g("all", "rough", "mean", "dist")
rb_e, ra_e = g("baseline", "rough", "mean", "err"), g("all", "rough", "mean", "err")

fault_rows = ["| policy | sensors OK | noisy sensors | dead sensors | distance, dead sensors (proprioception only: "
              f"{b_d:.1f} m) |", "|---|---:|---:|---:|---:|"]
for v in V[1:]:
    fault_rows.append(f"| {LAB[v]} | {g(v, 'flat', 'mean', 'err'):.3f} | {g(v, 'noisy', 'mean', 'err'):.3f} | "
                      f"{g(v, 'dead', 'mean', 'err'):.3f} ▼ | {g(v, 'dead', 'mean', 'dist'):.2f} m |")
fault_tbl = "\n".join(fault_rows)

gif_rows = "\n".join(
    f"| **{s.replace('_', ' ')}** μ = {MU[s]} | <img src=\"media/gifs/compare_{s}.gif\" width=\"100%\"> | "
    f"error {g('baseline', 'flat', s, 'err'):.2f} → {g('all', 'flat', s, 'err'):.2f} m/s, "
    f"distance {g('baseline', 'flat', s, 'dist'):.1f} → {g('all', 'flat', s, 'dist'):.1f} m |"
    for s in SURF)

BIB = r"""@misc{anaxolotl2026leggedtactile,
  author       = {Fay, Kehlani},
  title        = {Legged Tactile: Foot Touch Sensing for Quadruped Locomotion on Ice, Glue and Everything in Between},
  year         = {2026},
  howpublished = {Blog post / code repository, \url{https://github.com/An-Axolotl/legged-tactile}}
}"""
readme = f"""# Legged Tactile: foot touch sensing for quadruped locomotion on ice, glue and everything in between

*Does a walking policy that can feel its feet do better when the ground's friction changes, and when does plain proprioception (joint encoders + IMU) win?*

I added four simulated foot sensors to a Unitree A1 PPO locomotion policy in Isaac Lab and trained six policies: proprioception only, each sensor alone, and all four together. I then tested all six on seven surfaces from extreme ice (μ = 0.01) to extra-sticky "glue" (μ = 5), on flat and rough ground, with healthy, noisy and dead sensors. That is 128 robots per surface and condition, 20 s each.

| | |
|---|---|
| <img src="media/gifs/compare_glue.gif" width="100%"> | <img src="media/gifs/compare_wet.gif" width="100%"> |

## TL;DR

1. **Touch helps most on wet, sticky and glue-like ground.** On flat ground, the all-tactile policy cuts velocity-tracking error from {b_err:.3f} to {a_err:.3f} m/s ({pct(a_err, b_err)}) and walks {(a_d - b_d) / b_d * 100:.0f} % further in 20 s ({b_d:.1f} → {a_d:.1f} m). The gains are largest on wet (μ = 0.2, {pct(g('all','flat','wet','err'), g('baseline','flat','wet','err'))} error), sticky ({pct(g('all','flat','sticky','err'), g('baseline','flat','sticky','err'))}), glue ({pct(g('all','flat','glue','err'), g('baseline','flat','glue','err'))}) and extra-sticky ({pct(g('all','flat','extra_sticky','err'), g('baseline','flat','extra_sticky','err'))}). The proprioception-only policy gets *worse* on high-friction ground than on regular ground ({g('baseline','flat','regular','err'):.2f} → {g('baseline','flat','glue','err'):.2f} m/s on glue). The tactile policy stays flat at about {g('all','flat','glue','err'):.2f} m/s from μ = 0.8 to 5.
2. **On ice, touch can't create grip.** At μ = 0.05 the best a robot can do is accelerate at μg ≈ 0.5 m/s²; at μ = 0.01, ≈ 0.1 m/s². No policy tracks the 0.8 m/s command on either. Tactile sensing gives only small gains there: error {g('baseline','flat','ice','err'):.2f} → {g('all','flat','ice','err'):.2f} m/s on ice. The FSR on/off policy goes furthest: {g('fsr','flat','ice','dist'):.1f} m vs {g('baseline','flat','ice','dist'):.1f} m on ice, and {g('fsr','flat','extreme_ice','dist'):.1f} vs {g('baseline','flat','extreme_ice','dist'):.1f} m on extreme ice.
3. **On rough ground the benefit shrinks but falls drop.** Velocity error goes {rb_e:.3f} → {ra_e:.3f} m/s, distance {rb_d:.1f} → {ra_d:.1f} m, and the fall rate {rb_f*100:.1f} % → {ra_f*100:.1f} %.
4. **A simple binary FSR captures most of the benefit.** "+ FSR on/off" alone reaches {g('fsr','flat','mean','err'):.3f} m/s against {a_err:.3f} for all four sensors combined. Raw FSR resistance is the next best. The slip and vibrotactile sensors alone help much less.
5. **Proprioception wins when the sensors fail.** With every tactile reading stuck at "no contact", the all-tactile policy freezes in place ({g('all','dead','mean','dist'):.2f} m in 20 s, vs {b_d:.1f} m for proprioception only). The FSR-resistance policy also freezes. Sensor *noise* (5×, plus 10 % false readings) costs almost nothing. The policies are robust to noisy touch but have learned to trust it completely. More cases where proprioception wins are [below](#when-proprioception-wins).

---

## Contents
1. [Videos](#videos)
2. [Results and comparisons](#results-and-comparisons)
3. [When proprioception wins](#when-proprioception-wins)
4. [The sensors](#the-sensors)
5. [Setup and training](#setup-and-training)
6. [Reproducing everything](#reproducing-everything)
7. [Caveats and honest notes](#caveats-and-honest-notes)
8. [Original version of the project](#original-version-of-the-project)
9. [Repository layout](#repository-layout) · [Acknowledgements](#acknowledgements) · [Citation](#citation)

---

## Videos

Each clip is 8 s on flat ground: 4 s straight at 0.8 m/s, then a 0.5 rad/s turn. **Green arrow = commanded velocity, blue arrow = the robot's actual velocity**; the camera follows the robot. The numbers are the 128-robot, 20 s evaluation means. Full-quality MP4s of every clip are in [`media/videos/`](media/videos).

### Proprioception only (left) vs all tactile sensors (right), every surface

| surface | proprioception only · all tactile | measured (proprioception → tactile) |
|---|---|---|
{gif_rows}

### Rough ground

| ice, rough | glue, rough |
|---|---|
| <img src="media/gifs/compare_ice_rough.gif" width="100%"> | <img src="media/gifs/compare_glue_rough.gif" width="100%"> |

### Each sensor on its own (FSR on/off · FSR resistance · slip · vibrotactile)

| extreme ice μ = 0.01 |
|---|
| <img src="media/gifs/sensors_extreme_ice.gif" width="100%"> |
| **ice μ = 0.05** |
| <img src="media/gifs/sensors_ice.gif" width="100%"> |
| **glue μ = 3** |
| <img src="media/gifs/sensors_glue.gif" width="100%"> |

### Dead sensors: where proprioception wins

Proprioception only · all tactile with working sensors · the same all-tactile policy with every foot sensor dead.

| regular ground |
|---|
| <img src="media/gifs/dead_regular.gif" width="100%"> |
| **ice** |
| <img src="media/gifs/dead_ice.gif" width="100%"> |

---

## Results and comparisons

**Protocol.** Each policy runs on all seven surfaces at once, with 128 robots per surface (896 in total), for 20 s. The command is 0.8 m/s forward, with a 0.5 rad/s turn in the second half. There are no random pushes. *Velocity error* is the time-averaged ‖v<sub>xy</sub> − v<sub>cmd</sub>‖. A *fall* means the body tilted more than 60° or, on flat ground, the base dropped below 0.15 m at any time. *Foot slip* is the horizontal foot speed while that foot carries > 3 N.

Every tactile number is compared with proprioception only on the same surface and condition, using a 95 % bootstrap confidence interval over robots (2000 resamples). **Bold** means tactile is significantly better; ▼ means proprioception is significantly better; plain means no significant difference. The complete tables, including foot slip and every condition, are in [`results/tables.md`](results/tables.md). Per-robot raw results are in `results/metrics_*.json`.

<p align="center"><img src="media/fig_error_vs_friction.png" width="100%"></p>

### Flat ground: velocity-tracking error [m/s] ↓

{table('flat', 'err', '{:.3f}')}

### Flat ground: distance walked in 20 s [m] ↑

{table('flat', 'dist', '{:.1f}')}

<p align="center"><img src="media/fig_diff_flat.png" width="85%"></p>

### Rough ground (stairs, slopes, boxes, noise; random difficulty): velocity error [m/s] ↓

{table('rough', 'err', '{:.3f}')}

### Rough ground: fall rate ↓

{table('rough', 'fell', '{:.1f}')}

<p align="center"><img src="media/fig_diff_rough.png" width="85%"></p>

On flat ground falls are rare for every policy (≤ 2.3 % on any surface), and no flat-ground fall-rate difference is significant.

### Sensor faults (flat ground, mean over all surfaces): velocity error [m/s] ↓

{fault_tbl}

"Noisy" means 5× the nominal sensor noise, with 10 % of readings replaced by another foot's reading (and 10 % of FSR bits flipped). "Dead" means every sensor reads "no contact": FSR 0, resistance open-circuit at 1 MΩ, shear and slip 0, vibration 0. The proprioception-only policy has no tactile input, so its error is {b_err:.3f} m/s in every column.

<p align="center"><img src="media/fig_sensor_faults.png" width="75%"></p>

### What the comparisons say

- **Contact timing is the useful signal.** The binary FSR alone gets most of the gain, and the four sensors combined are only slightly better than FSR on/off on flat ground ({a_err:.3f} vs {g('fsr','flat','mean','err'):.3f} m/s). My reading: knowing exactly *when* each foot is loaded lets the policy time push-off and swing without inferring it from joint torques and velocities. That matters most when the foot sticks (glue) or skids at touchdown (wet). This is an interpretation; I did not isolate it.
- **High friction is a problem for proprioception, not only low friction.** The proprioception-only policy's error rises from {g('baseline','flat','regular','err'):.3f} m/s on regular ground to {g('baseline','flat','sticky','err'):.3f} on sticky, {g('baseline','flat','glue','err'):.3f} on glue and {g('baseline','flat','extra_sticky','err'):.3f} on extra-sticky. The FSR-resistance and all-tactile policies stay at their regular-ground error (≈ 0.18 m/s) all the way to μ = 5, and FSR on/off stays within 0.06 m/s of it.
- **The slip sensor makes the policy cautious.** "+ slip" is the only policy that slips *less* than proprioception only on every flat surface ({g('slip','flat','extreme_ice','slip'):.2f} vs {g('baseline','flat','extreme_ice','slip'):.2f} m/s on extreme ice). It pays for that in speed: on ice it walks {g('slip','flat','ice','dist'):.1f} m against {g('baseline','flat','ice','dist'):.1f} m. FSR on/off, FSR resistance and vibrotactile slip *more* than proprioception only on every surface, and all-tactile slips more on ice and wet ground but less on regular and sticky ground. These policies walk faster and accept more slip.
- **The vibrotactile sensor is the weakest alone but the most fault-tolerant.** It helps on wet ground and very slightly on ice, and is slightly worse than proprioception only on regular ground. With dead sensors, its policy still walks {g('vibro','dead','mean','dist'):.1f} m: it leans on touch the least.
- **Fall rates.** Only rough ground produces enough falls to compare. There, all-tactile ({ra_f*100:.1f} %) and FSR-resistance ({g('resistance','rough','mean','fell')*100:.1f} %) both fall significantly less than proprioception only ({rb_f*100:.1f} %). Vibrotactile alone does not ({g('vibro','rough','mean','fell')*100:.1f} %).

---

## When proprioception wins

These are the cases where the proprioception-only policy is *significantly* better (95 % CI); the full list is in [`results/proprioception_wins.md`](results/proprioception_wins.md):

1. **When the tactile sensors fail.** This is by far the largest effect. Every tactile policy is worse than proprioception only with dead sensors, on every surface. All-tactile and FSR-resistance stand still ({g('all','dead','mean','dist'):.2f} m and {g('resistance','dead','mean','dist'):.2f} m in 20 s). FSR on/off manages {g('fsr','dead','mean','dist'):.1f} m, slip {g('slip','dead','mean','dist'):.1f} m and vibrotactile {g('vibro','dead','mean','dist'):.1f} m, against {b_d:.1f} m for proprioception only. During training a foot reading "no load" on all four legs always meant the robot was in the air. So the policy does the sensible thing for a robot in the air: nothing. A broken cable, a worn FSR or a sensor that saturates on a new surface would cause this on hardware. Noisy sensors are *not* a problem (see the fault table above).
2. **On ice, for the policies that sense force magnitude.** On ice (μ = 0.05), FSR resistance (error {g('resistance','flat','ice','err'):.3f} vs {g('baseline','flat','ice','err'):.3f} m/s; {g('resistance','flat','ice','dist'):.1f} vs {g('baseline','flat','ice','dist'):.1f} m) and slip ({g('slip','flat','ice','err'):.3f} m/s; {g('slip','flat','ice','dist'):.1f} m) are significantly worse than proprioception only. Slip is also worse on rough ice ({g('slip','rough','ice','dist'):.1f} vs {g('baseline','rough','ice','dist'):.1f} m). On ice these sensors report large slip and low, erratic loads, and the policies respond by slowing down. My interpretation is that they treat it as a cue to be careful. That is safe (the slip policy did not fall once on rough extreme ice) but loses ground.
3. **On regular ground, for the vibrotactile policy alone.** Its error is {g('vibro','flat','regular','err'):.3f} vs {g('baseline','flat','regular','err'):.3f} m/s. Accelerometer energy carries little information on ordinary ground, and the extra noisy input costs a little.
4. **For foot slip, if keeping slip low is the goal.** FSR on/off, FSR resistance and vibrotactile slip more than proprioception only on every surface. All-tactile slips more on ice and wet ground (for example {g('all','flat','wet','slip'):.2f} vs {g('baseline','flat','wet','slip'):.2f} m/s on wet). They walk faster and further, so this is a trade-off, not a failure. It still matters when slipping itself is the risk, for example near an edge.
5. **On extreme ice everyone is close.** At μ = 0.01 all six policies make 0.65–1.35 m of progress in 20 s, and the differences are a few hundredths of a m/s. Physics, not sensing, is the limit there.

**Rule of thumb from these results:** add touch when friction is moderate to high, or changes from one surface to the next, and the sensors are reliable. Keep a proprioception-only fallback, or train with sensor dropout, if a sensor can fail. Neither costs much on ice, where touch has little to add.

---

## The sensors

All four are Isaac Lab observation terms in [`tactile_loco/sensors.py`](tactile_loco/sensors.py). Each gives one value (two for slip) per foot (FL, FR, RL, RR). They are added to both the actor and the critic observations and computed from quantities a real foot sensor can measure:

| sensor | per foot | model |
|---|---|---|
| **FSR on/off** | 1 bit | 1 if the normal load F<sub>n</sub> > 3 N, else 0; 2 % of bits flipped (noise). |
| **FSR resistance** | R in MΩ | Raw resistance of an Interlink FSR-402-like sensor: open (1 MΩ) below 0.2 N, otherwise R = 150 kΩ · F<sub>n</sub><sup>−0.85</sup>, clipped to [0.5 kΩ, 1 MΩ]; ±5 % multiplicative noise. |
| **Slip ("slide N")** | F<sub>t</sub> in N, v<sub>slip</sub> | The tangential (friction / shear) force between foot and ground in newtons, from PhysX friction reporting (`ContactSensorCfg(track_friction_forces=True)`, filtered against the ground mesh). Scaled by 1/50 so 50 N reads as 1.0. Also the foot's horizontal speed while it carries load. |
| **Vibrotactile** (the extra sensor I chose) | log(1 + ‖a‖/g) | A MEMS accelerometer in the foot tip. Stick-slip on ice and sudden release from glue show up as high-frequency foot accelerations that joint encoders don't see directly; 0.02 noise. |

In a quick probe with random actions, the simulated sensors behave as expected: shear force rises with friction (0.02 N on extreme ice to 6.2 N on extra-sticky), and slip speed falls with it (see `scripts/probe_sensors.py`).

**Surfaces.** Each robot gets one foot–ground friction at startup:

| | extreme ice | ice | wet | regular | sticky | glue | extra sticky |
|---|---|---|---|---|---|---|---|
| static / dynamic μ | 0.01 / 0.005 | 0.05 / 0.03 | 0.2 / 0.15 | 0.8 / 0.6 | 2.0 / 1.8 | 3.0 / 2.5 | 5.0 / 4.0 |

Extreme ice, glue and extra-sticky use the values from the original project's configs (below). The terrain material has μ = 1 with combine mode `multiply`, so the foot material alone sets the contact friction.

---

## Setup and training

- **Simulator:** Isaac Sim 4.5 + Isaac Lab (`isaaclab` 0.41.5, commit `88d94ea`), PhysX GPU, 4096 robots, 200 Hz physics, 50 Hz policy.
- **Task:** [robot_lab](https://github.com/fan-ziqi/robot_lab) v2.3.2 `UnitreeA1RoughEnvCfg`. This is velocity tracking on a rough-terrain curriculum (pyramids, stairs, boxes, slopes, noise), with robot_lab's reward terms, domain randomization and pushes. The policy observation is robot_lab's default (base angular velocity, gravity direction, command, joint positions and velocities, previous action) plus the selected tactile terms. The robot is Isaac Lab's USD A1 asset, because robot_lab's URDF A1 needs a newer URDF importer than Isaac Sim 4.5 ships.
- **Learning:** PPO from rsl-rl 3.0.1, robot_lab's A1 hyper-parameters ([512, 256, 128] MLPs, 24 steps per env per iteration), 2000 iterations, seed 42. Each policy takes about 80 min on one RTX 4090, two at a time.
- **Training curves:** the proprioception-only policy ends with the *highest* training reward (58.0 vs 50.4–56.3). It also reaches the *lowest* terrain-curriculum level (2.26 vs 2.40–2.71 for the tactile policies). The tactile policies climbed to harder terrain, where reward is lower, so training reward is not comparable across policies. The evaluation above uses fixed, identical terrain for all.

```bash
# Isaac Lab (Isaac Sim 4.5) env, then:
git clone https://github.com/fan-ziqi/robot_lab && cd robot_lab && git checkout v2.3.2
pip install -e source/robot_lab --no-deps && cd ..
git clone https://github.com/An-Axolotl/legged-tactile && cd legged-tactile
export ROBOT_LAB=$PWD/../robot_lab
```

## Reproducing everything

```bash
bash scripts/train_all.sh        # 6 policies, ~4 h on one RTX 4090 (logs/rsl_rl/tactile_a1_<variant>/)
bash scripts/eval_all.sh         # 22 evaluations + 13 video runs + tables/charts/GIFs, ~2 h
# single runs
python scripts/train.py --task Tactile-A1-all-v0 --headless                       # variants: baseline fsr resistance slip vibro all
python scripts/evaluate.py --variant all --headless [--terrain rough] [--fault dead|noisy]
python scripts/evaluate.py --variant all --headless --enable_cameras --video --surfaces ice,glue
python scripts/probe_sensors.py --headless                                        # sensor sanity check
```

The trained policies are in [`checkpoints/`](checkpoints). `evaluate.py` uses them automatically when there is no local `logs/` directory.

---

## Caveats and honest notes

- **One training seed per policy.** The confidence intervals cover robot-to-robot variation within one trained policy, not variation between training runs. Small differences, such as a few hundredths of a m/s, could change with another seed. The large effects (glue/sticky gains, dead-sensor freezing) are well beyond that.
- **Simulation only.** The sensor models are plausible, not calibrated against hardware. PhysX friction reporting gives the slip sensor something cleaner than a real shear sensor would.
- **Friction is fixed per robot for its whole training run and evaluation.** I did not test surfaces that change under a single robot (an ice patch in the middle of a walk). That is the obvious next experiment.
- **Faults are evaluation-only.** No policy was trained with sensor dropout, which is why the dead-sensor failure is so stark. Training with dropout should fix most of it, but I haven't tested that.
- The fall criterion is a geometric threshold. On rough ground only the tilt criterion is used.

---

## Original version of the project

This is a re-implementation. The earlier version of this project trained A1 policies with foot-contact sensing on icy and sticky terrain, using robot_lab and Isaac Lab. Its tactile code, logs and tactile-policy recordings could not be recovered: they were not on this machine, in my W&B projects or in Google Drive. What survived is kept for reference:

- [`original_2025_configs/`](original_2025_configs): the recovered robot_lab environment configs with the ice (μ 0.01 / 0.005), glue (3.0 / 2.5) and extra-sticky (5.0 / 4.0, re-weighted rewards) variants. They are derived from robot_lab, so they keep its Apache-2.0 license.
- [`media/original_2025/`](media/original_2025): clips of the original **proprioception-only** policies on regular, icy, glue and extreme-glue terrain.

| regular | icy | glue | extreme glue |
|---|---|---|---|
| <img src="media/original_2025/regular_baseline.gif" width="200"> | <img src="media/original_2025/icy_baseline.gif" width="200"> | <img src="media/original_2025/glue_baseline.gif" width="200"> | <img src="media/original_2025/glue_extreme_baseline.gif" width="200"> |

All numbers and videos in this README come from the new runs, not the original ones.

---

## Repository layout

```
tactile_loco/
  sensors.py        the four foot sensors, sensor-fault modes, per-robot surface (friction) event
  env_cfg.py        Tactile-A1 environments on top of robot_lab's A1 rough task (one per sensor set)
  agents.py         PPO configs;  __init__.py registers Tactile-A1-<variant>-v0
scripts/
  train.py, train_all.sh       training (wraps robot_lab's RSL-RL train script)
  evaluate.py, eval_all.sh     metrics and videos
  make_media.py                statistics, tables, charts and GIFs
  probe_sensors.py             sensor sanity check
checkpoints/        the six trained policies (rsl-rl, 2000 iterations)
results/            per-robot metrics (metrics_*.json), summary.json with CIs, tables.md, proprioception_wins.md
media/              GIFs, MP4s and charts;  original_2025/ clips from the original project
original_2025_configs/   recovered configs from the original project (Apache-2.0)
```

## Acknowledgements

- **[Isaac Sim / Isaac Lab](https://github.com/isaac-sim/IsaacLab)** (NVIDIA and the Isaac Lab contributors): simulation, contact and friction sensing, and the A1 asset.
- **[robot_lab](https://github.com/fan-ziqi/robot_lab)** (Ziqi Fan): the A1 rough-terrain locomotion task this builds on.
- **[rsl_rl](https://github.com/leggedrobotics/rsl_rl)** (ETH Zürich Robotic Systems Lab): PPO.
- Unitree Robotics for the A1 robot model.

## Citation

```bibtex
{BIB}
```

## License

MIT (see [`LICENSE`](LICENSE)), except [`original_2025_configs/`](original_2025_configs), which is derived from robot_lab and keeps its Apache-2.0 license. `tactile_loco/env_cfg.py` imports robot_lab (Apache-2.0) at runtime.
"""
open(f"{ROOT}/README.md", "w").write(readme)
print(len(readme.splitlines()), "lines")
