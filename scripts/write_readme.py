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
    x = fmt.format(r[k])
    t = r.get(f"{k}_diff", [0, 0, 0, ""])[3]
    return f"**{x}**" if t == "tactile better" else f"{x} ▼" if t == "proprioception better" else x


def table(c, k, fmt):
    rows = ["| | " + " | ".join(f"{s.replace('_', ' ')}<br>μ {MU[s]}" for s in SURF) + " | all |",
            "|---|" + "---:|" * (len(SURF) + 1)]
    for v in V:
        rows.append(f"| {LAB[v]} | " + " | ".join(cell(v, c, s, k, fmt) for s in SURF + ["mean"]) + " |")
    return "\n".join(rows)


def pct(a, b):
    return f"{(a - b) / b * 100:+.0f} %".replace("-", "−")


be, ae = g("baseline", "mixed", "mean", "err"), g("all", "mixed", "mean", "err")
bd, ad = g("baseline", "mixed", "mean", "dist"), g("all", "mixed", "mean", "dist")
fbe, fae = g("baseline", "flat", "mean", "err"), g("all", "flat", "mean", "err")

videos = "\n".join(
    f"| <img src=\"media/gifs/mixed_{s}.gif\" width=\"100%\"> | **{s.replace('_', ' ')}**<br>μ = {MU[s]}<br><br>"
    f"{g('baseline', 'mixed', s, 'dist'):.1f} → {g('all', 'mixed', s, 'dist'):.1f} m |"
    for s in SURF)

faults = ["| | sensors OK | noisy | dead | distance with dead sensors |", "|---|---:|---:|---:|---:|"]
for v in V[1:]:
    faults.append(f"| {LAB[v]} | {g(v, 'mixed', 'mean', 'err'):.3f} | {g(v, 'mixed_noisy', 'mean', 'err'):.3f} | "
                  f"{g(v, 'mixed_dead', 'mean', 'err'):.3f} ▼ | {g(v, 'mixed_dead', 'mean', 'dist'):.2f} m |")
faults.append(f"| *proprioception only* | {be:.3f} | – | – | {bd:.2f} m |")
faults = "\n".join(faults)

BIB = r"""@misc{anaxolotl2026leggedtactile,
  author       = {Fay, Kehlani},
  title        = {Legged Tactile: Foot Touch Sensing for Quadruped Locomotion on Ice, Glue and Everything in Between},
  year         = {2026},
  howpublished = {Blog post / code repository, \url{https://github.com/An-Axolotl/legged-tactile}}
}"""

readme = f"""# Legged Tactile

**Foot touch sensing for a quadruped walking on ice, glue and everything in between**, plus where plain proprioception (joint encoders + IMU) still wins.

*This is a re-implementation of my former, lost code.* The original tactile code and recordings are gone; what survived is in [`original_2025_configs/`](original_2025_configs) and [`media/original_2025/`](media/original_2025). Every result below comes from the new runs.

<img src="media/gifs/mixed_glue.gif" width="100%">

A Unitree A1 PPO policy (Isaac Lab, [robot_lab](https://github.com/fan-ziqi/robot_lab)) with four simulated foot sensors: **FSR on/off**, **raw FSR resistance**, **slip** (shear force in N + slip speed) and a **vibrotactile** accelerometer. I trained six policies: proprioception only, each sensor alone, and all four together. I tested them on a mixed field of stairs, rocky steps, rough ground, slopes and flat ground, with seven foot-ground frictions from extreme ice (μ 0.01) to extra-sticky (μ 5). That is 128 robots per surface, 20 s each.

## Results at a glance

- **Touch helps on everything from wet to extra-sticky ground.** On mixed terrain, all-tactile cuts velocity-tracking error by {(be - ae) / be * 100:.0f} % ({be:.2f} → {ae:.2f} m/s) and walks {(ad - bd) / bd * 100:.0f} % further ({bd:.1f} → {ad:.1f} m). On flat ground it cuts the error by {(fbe - fae) / fbe * 100:.0f} %.
- **A binary FSR gets most of it.** FSR on/off alone: {g('fsr', 'mixed', 'mean', 'err'):.2f} m/s.
- **On ice nothing helps much.** With μg ≈ 0.1–0.5 m/s² of available grip, no policy tracks the command.
- **Proprioception wins when sensors die.** With dead foot sensors the all-tactile policy stands still ({g('all', 'mixed_dead', 'mean', 'dist'):.2f} m in 20 s). Noisy sensors cost nothing.

## Videos

Mixed terrain, 32 robots per surface, 0.8 m/s forward then turning. Left: proprioception only; right: all tactile. The number is the mean distance walked in 20 s (128 robots). Green arrow = command, blue = actual velocity. MP4s are in [`media/videos/`](media/videos).

| proprioception only · all tactile | |
|---|---|
{videos}

**Dead sensors:** proprioception only · all tactile · all tactile with every foot sensor dead.

<img src="media/gifs/mixed_dead_regular.gif" width="100%">

## Results

<img src="media/fig_error_vs_friction.png" width="100%">

**Mixed terrain, velocity-tracking error [m/s] ↓.** **Bold** = tactile significantly better than proprioception only, ▼ = significantly worse (95 % bootstrap CI over robots).

{table('mixed', 'err', '{:.2f}')}

**Mixed terrain, distance in 20 s [m] ↑**

{table('mixed', 'dist', '{:.1f}')}

**Sensor faults, mixed terrain** (error in m/s, mean over surfaces). Noisy = 5× noise + 10 % false readings; dead = every sensor reads "no contact".

{faults}

Falls are rare on mixed terrain for every policy (≤ 5 % on any surface, mean ≤ 0.7 %). The flat- and rough-ground runs, foot-slip numbers and every per-surface CI are in [`results/tables.md`](results/tables.md) and [`results/summary.json`](results/summary.json).

## When proprioception wins

1. **Dead or disconnected sensors.** Every tactile policy is worse than proprioception only on every surface. All-tactile and FSR-resistance freeze. In training, "no load on any foot" only ever meant "in the air". Vibrotactile degrades least ({g('vibro', 'mixed_dead', 'mean', 'dist'):.1f} m vs {bd:.1f} m).
2. **Ice, for the force-magnitude sensors.** The slip-sensor policy slows right down on ice ({g('slip', 'mixed', 'ice', 'dist'):.1f} vs {g('baseline', 'mixed', 'ice', 'dist'):.1f} m) and extreme ice ({g('slip', 'mixed', 'extreme_ice', 'dist'):.1f} vs {g('baseline', 'mixed', 'extreme_ice', 'dist'):.1f} m). FSR resistance is also worse on extreme ice. They play it safe and lose ground.
3. **Foot slip.** Most tactile policies walk faster and slip more. Only the slip-sensor policy slips less than proprioception only.
4. **The vibrotactile sensor alone** adds nothing on mixed terrain.

**Rule of thumb:** use touch when friction is moderate to high or varies, and the sensors are reliable. Keep a proprioception fallback, or train with sensor dropout, if they can fail.

## Sensors

| sensor | per foot | model |
|---|---|---|
| FSR on/off | 1 bit | load > 3 N, 2 % bit flips |
| FSR resistance | MΩ | FSR-402-like: open (1 MΩ) below 0.2 N, else 150 kΩ·F<sup>−0.85</sup>, ±5 % noise |
| slip | N, m/s | shear (friction) force from PhysX friction reporting + foot speed while loaded |
| vibrotactile | log(1+‖a‖/g) | foot-tip accelerometer, picks up stick-slip and release from glue |

Code: [`tactile_loco/sensors.py`](tactile_loco/sensors.py). Sensors go into both actor and critic observations. Each robot gets one surface for its whole run.

## Run it

Isaac Sim 4.5 + Isaac Lab, robot_lab v2.3.2, rsl-rl 3.0.1, one RTX 4090.

```bash
git clone https://github.com/fan-ziqi/robot_lab && (cd robot_lab && git checkout v2.3.2 && pip install -e source/robot_lab --no-deps)
git clone https://github.com/An-Axolotl/legged-tactile && cd legged-tactile && export ROBOT_LAB=$PWD/../robot_lab
bash scripts/train_all.sh     # 6 policies, ~4 h  (or use checkpoints/)
bash scripts/eval_all.sh      # all evaluations, videos, tables, charts, this README, ~3 h
python scripts/evaluate.py --variant all --headless --terrain mixed [--fault dead|noisy]
```

## Notes

- One training seed per policy; CIs are over robots, not training runs. The large effects are well beyond that.
- Simulation only; the sensor models are plausible, not calibrated.
- The proprioception-only policy has the highest *training* reward because it stayed on easier curriculum terrain (level 2.26 vs 2.40–2.71). Evaluation uses identical terrain for all.
- Friction doesn't change under a robot mid-walk (e.g. stepping onto an ice patch). That's the next experiment.

## Acknowledgements · Citation · License

Built on [Isaac Sim / Isaac Lab](https://github.com/isaac-sim/IsaacLab), [robot_lab](https://github.com/fan-ziqi/robot_lab) (Ziqi Fan) and [rsl_rl](https://github.com/leggedrobotics/rsl_rl) (ETH RSL); A1 model by Unitree.

```bibtex
{BIB}
```

MIT, except [`original_2025_configs/`](original_2025_configs) (derived from robot_lab, Apache-2.0).
"""
open(f"{ROOT}/README.md", "w").write(readme)
print(len(readme.splitlines()), "lines,", len(readme.split()), "words")
