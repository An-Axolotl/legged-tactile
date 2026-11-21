"""Turn results/metrics_*.json and media/videos/*.mp4 into the README's tables, statistics, charts and GIFs.

  results/summary.json     every (policy, condition, surface): means, and the difference to the no-tactile
                           baseline with a 95 % bootstrap CI over robots (2000 resamples)
  results/tables.md        the Markdown tables pasted into the README
  media/fig_*.png          charts
  media/gifs/*.gif         labelled side-by-side comparisons
"""
import glob
import json
import os

import imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SURF = ["extreme_ice", "ice", "wet", "regular", "sticky", "glue", "extra_sticky"]
MU = {"extreme_ice": 0.01, "ice": 0.05, "wet": 0.2, "regular": 0.8, "sticky": 2.0, "glue": 3.0, "extra_sticky": 5.0}
ORDER = ["baseline", "fsr", "resistance", "slip", "vibro", "all"]
LABEL = {"baseline": "proprioception only", "fsr": "+ FSR on/off", "resistance": "+ FSR resistance",
         "slip": "+ slip (shear N)", "vibro": "+ vibrotactile", "all": "+ all tactile"}
# validated categorical order (dataviz reference palette, light mode); baseline is neutral ink
COLOR = {"baseline": "#52514e", "fsr": "#2a78d6", "resistance": "#eb6834", "slip": "#1baf7a",
         "vibro": "#eda100", "all": "#e87ba4"}
CONDS = {"flat": "", "rough": "_rough", "dead": "_dead", "noisy": "_noisy",
         "mixed": "_mixed", "mixed_dead": "_mixed_dead", "mixed_noisy": "_mixed_noisy"}
FAULT_BASE = {"dead": "flat", "noisy": "flat", "mixed_dead": "mixed", "mixed_noisy": "mixed"}
METRICS = [("err", "velocity-tracking error [m/s]", False), ("fell", "fall rate", False),
           ("dist", "distance in 20 s [m]", True), ("slip", "foot slip while loaded [m/s]", False)]
rng = np.random.default_rng(0)
os.makedirs(os.path.join(ROOT, "media/gifs"), exist_ok=True)

# ------------------------------------------------------------------ load
R = {}
for v in ORDER:
    for c, suf in CONDS.items():
        f = os.path.join(ROOT, f"results/metrics_{v}{suf}.json")
        if os.path.exists(f):
            pe = json.load(open(f))["per_env"]
            sid = np.array(pe["surface"])
            R[v, c] = {s: {k: np.array(pe[k])[sid == i] for k in ("err", "fell", "dist", "slip")}
                       for i, s in enumerate(SURF)}
for c, base in FAULT_BASE.items():  # the baseline has no tactile sensors: faults do not change it
    if ("baseline", base) in R:
        R["baseline", c] = R["baseline", base]
print("loaded", sorted(R))


def boot_diff(a, b, n=2000):
    """mean(a) - mean(b) with a 95 % bootstrap CI (robots resampled independently)."""
    ia = rng.integers(0, len(a), (n, len(a)))
    ib = rng.integers(0, len(b), (n, len(b)))
    d = a[ia].mean(1) - b[ib].mean(1)
    return float(a.mean() - b.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def pooled(v, c, k):
    return np.concatenate([R[v, c][s][k] for s in SURF])


summary = {}
for (v, c), per in R.items():
    for s in SURF + ["mean"]:
        row = {}
        for k, _, higher in METRICS:
            a = pooled(v, c, k) if s == "mean" else per[s][k]
            row[k] = float(a.mean())
            if v != "baseline" and ("baseline", c) in R:
                b = pooled("baseline", c, k) if s == "mean" else R["baseline", c][s][k]
                d, lo, hi = boot_diff(a.astype(float), b.astype(float))
                better = (lo > 0) if higher else (hi < 0)
                worse = (hi < 0) if higher else (lo > 0)
                row[f"{k}_diff"] = [d, lo, hi, "tactile better" if better else "proprioception better" if worse else "no sig. difference"]
        summary[f"{v}|{c}|{s}"] = row
json.dump(summary, open(os.path.join(ROOT, "results/summary.json"), "w"), indent=1)

# ------------------------------------------------------------------ tables
T = []
for c in CONDS:
    vs = [v for v in ORDER if (v, c) in R]
    if not vs:
        continue
    T.append(f"\n<!-- condition: {c} -->\n")
    for k, name, higher in METRICS:
        T.append(f"\n**{name}** {'↑' if higher else '↓'} ({c})\n")
        T.append("| policy | " + " | ".join(f"{s.replace('_', ' ')} μ={MU[s]}" for s in SURF) + " | all surfaces |")
        T.append("|---|" + "---:|" * (len(SURF) + 1))
        for v in vs:
            cells = []
            for s in SURF + ["mean"]:
                row = summary[f"{v}|{c}|{s}"]
                val = f"{row[k]:.0%}" if k == "fell" else f"{row[k]:.2f}"
                if f"{k}_diff" in row:
                    tag = row[f"{k}_diff"][3]
                    val = f"**{val}**" if tag == "tactile better" else f"_{val}_ ▼" if tag == "proprioception better" else val
                cells.append(val)
            T.append(f"| {LABEL[v]} | " + " | ".join(cells) + " |")
T.append("\n**bold** = tactile policy significantly better than proprioception only (95 % bootstrap CI of the difference "
         "excludes 0); _italic_ ▼ = significantly worse; plain = no significant difference.\n")
open(os.path.join(ROOT, "results/tables.md"), "w").write("\n".join(T))

# where does proprioception win?
wins = [(key, k, row[f"{k}_diff"]) for key, row in summary.items() for k, _, _ in METRICS
        if f"{k}_diff" in row and row[f"{k}_diff"][3] == "proprioception better"]
with open(os.path.join(ROOT, "results/proprioception_wins.md"), "w") as f:
    for key, k, (d, lo, hi, _) in sorted(wins):
        f.write(f"- {key} {k}: diff {d:+.3f} [{lo:+.3f}, {hi:+.3f}]\n")
print(len(wins), "cells where proprioception wins")

# ------------------------------------------------------------------ charts
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#52514e",
                         "xtick.color": "#52514e", "ytick.color": "#52514e", "axes.spines.top": False,
                         "axes.spines.right": False, "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})

    # 1. velocity error vs friction, flat and rough (small multiples, one axis each)
    conds = [c for c in ("flat", "mixed") if ("baseline", c) in R]
    fig, axes = plt.subplots(1, len(conds), figsize=(5.2 * len(conds), 3.6), dpi=130, sharey=True, squeeze=False)
    for ax, c in zip(axes[0], conds):
        for v in ORDER:
            if (v, c) not in R:
                continue
            y = [summary[f"{v}|{c}|{s}"]["err"] for s in SURF]
            ax.plot(range(len(SURF)), y, color=COLOR[v], lw=2 if v in ("baseline", "all") else 1.4,
                    marker="o", ms=4, ls="--" if v == "baseline" else "-", label=LABEL[v])
        ax.set_xticks(range(len(SURF)), [f"{s.replace('_', chr(10))}\nμ={MU[s]}" for s in SURF], fontsize=7)
        ax.set_title({"flat": "flat ground", "mixed": "mixed terrain (stairs, rocky steps, rough, slopes, flat)"}[c], fontsize=10, color="#0b0b0b", loc="left")
        ax.grid(axis="y", color="#e6e5e0", lw=0.6)
    axes[0][0].set_ylabel("velocity-tracking error [m/s] (lower is better)")
    h, l = axes[0][0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=8, frameon=False, loc="lower center", ncol=6)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(os.path.join(ROOT, "media/fig_error_vs_friction.png"))
    plt.close(fig)

    # 2. difference to baseline, heat map with CI significance (flat)
    for c in [c for c in ("flat", "rough", "mixed") if ("all", c) in R]:
        vs = [v for v in ORDER[1:] if (v, c) in R]
        D = np.array([[summary[f"{v}|{c}|{s}"]["err_diff"][0] for s in SURF + ["mean"]] for v in vs])
        Sg = [[summary[f"{v}|{c}|{s}"]["err_diff"][3] for s in SURF + ["mean"]] for v in vs]
        from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
        cmap = LinearSegmentedColormap.from_list("div", ["#2a78d6", "#f0efec", "#eb6834"])
        lim = max(0.05, np.abs(D).max())
        fig, ax = plt.subplots(figsize=(8, 0.5 * len(vs) + 1.3), dpi=130)
        ax.imshow(D, cmap=cmap, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
        for i in range(len(vs)):
            for j in range(D.shape[1]):
                mark = "" if Sg[i][j] == "no sig. difference" else " *"
                ax.text(j, i, f"{D[i, j]:+.2f}{mark}", ha="center", va="center", fontsize=7.5, color="#0b0b0b")
        ax.set_xticks(range(D.shape[1]), [s.replace("_", "\n") for s in SURF] + ["all\nsurfaces"], fontsize=7)
        ax.set_yticks(range(len(vs)), [LABEL[v] for v in vs], fontsize=8)
        ax.set_title(f"velocity error minus proprioception-only [m/s], {c} ground\n"
                     f"blue = tactile helps, orange = tactile hurts, * = 95 % CI excludes 0", fontsize=8, loc="left",
                     color="#0b0b0b")
        ax.set_xticks(np.arange(-0.5, D.shape[1]), minor=True)
        ax.set_yticks(np.arange(-0.5, len(vs)), minor=True)
        ax.grid(which="minor", color="#fcfcfb", lw=2)
        ax.tick_params(which="minor", length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
        fig.tight_layout()
        fig.savefig(os.path.join(ROOT, f"media/fig_diff_{c}.png"))
        plt.close(fig)

    # 3. sensor faults: mean error over all surfaces, nominal vs noisy vs dead
    for fc in ("", "mixed"):
      pre = f"{fc}_" if fc else ""
      vs = [v for v in ORDER[1:] if (v, pre + "dead") in R]
      if vs:
          fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=130)
          w = 0.26
          styles = [(fc or "flat", "sensors OK", 1.0), (pre + "noisy", "noisy sensors", 0.6), (pre + "dead", "dead sensors", 0.3)]
          for k, (c, name, alpha) in enumerate(styles):
              ys = [summary[f"{v}|{c}|mean"]["err"] for v in vs]
              ax.bar(np.arange(len(vs)) + (k - 1) * w, ys, w - 0.03, color=[COLOR[v] for v in vs], alpha=alpha,
                     label=name, edgecolor="#fcfcfb", linewidth=1)
          b = summary[f"baseline|{fc or 'flat'}|mean"]["err"]
          ax.axhline(b, color=COLOR["baseline"], ls="--", lw=1.5)
          ax.text(len(vs) - 0.5, b, " proprioception only", va="bottom", ha="right", fontsize=7.5, color="#52514e")
          ax.set_xticks(range(len(vs)), [LABEL[v] for v in vs], fontsize=8)
          ax.set_ylabel("velocity error, all surfaces [m/s]")
          leg = ax.legend(fontsize=7, frameon=False, loc="upper left")
          for h in leg.legend_handles:
              h.set_color("#52514e")
          ax.grid(axis="y", color="#e6e5e0", lw=0.6)
          fig.tight_layout()
          fig.savefig(os.path.join(ROOT, f"media/fig_sensor_faults{'_' + fc if fc else ''}.png"))
          plt.close(fig)
except ImportError:
    print("matplotlib missing: no charts")

# ------------------------------------------------------------------ gifs
try:
    FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
except OSError:
    FONT = ImageFont.load_default()


def frames(name, label, size=(360, 225), every=3):
    p = os.path.join(ROOT, f"media/videos/{name}.mp4")
    if not os.path.exists(p):
        return None
    out = []
    for i, fr in enumerate(imageio.get_reader(p)):
        if i % every:
            continue
        im = Image.fromarray(fr).resize(size, Image.LANCZOS)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, size[0], 21], fill=(20, 20, 20))
        d.text((6, 3), label, fill=(255, 255, 255), font=FONT)
        out.append(np.asarray(im))
    return out


def save_row(path, clips):
    clips = [c for c in clips if c is not None]
    if len(clips) < 2:
        return
    n = min(len(c) for c in clips)
    sep = np.full((clips[0][0].shape[0], 4, 3), 255, np.uint8)
    gif = []
    for i in range(n):
        row = [clips[0][i]]
        for c in clips[1:]:
            row += [sep, c[i]]
        gif.append(np.concatenate(row, axis=1))
    tmp = path + ".full.gif"
    imageio.mimsave(tmp, gif, duration=1000 * 3 / 50, loop=0)
    # README-sized: 12 fps, 80 % scale, optimised 96-colour palette (~3-5 MB instead of 10-16 MB)
    os.system(f'ffmpeg -loglevel error -y -i "{tmp}" -vf "fps=12,scale=iw*0.8:-1:flags=lanczos,split[a][b];'
              f'[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:'
              f'diff_mode=rectangle" "{path}"')
    os.remove(tmp)
    print("gif", os.path.basename(path))


for s in SURF:
    save_row(os.path.join(ROOT, f"media/gifs/mixed_{s}.gif"),
             [frames(f"baseline_{s}_mixed_wide", f"proprioception only | {s.replace('_', ' ')} μ={MU[s]}", size=(480, 270)),
              frames(f"all_{s}_mixed_wide", f"+ all tactile | {s.replace('_', ' ')} μ={MU[s]}", size=(480, 270))])
for s in ("regular", "ice"):
    save_row(os.path.join(ROOT, f"media/gifs/mixed_dead_{s}.gif"),
             [frames(f"baseline_{s}_mixed_wide", f"proprioception only | {s}", size=(400, 225)),
              frames(f"all_{s}_mixed_wide", f"all tactile, sensors OK | {s}", size=(400, 225)),
              frames(f"all_{s}_mixed_wide_dead", f"all tactile, sensors DEAD | {s}", size=(400, 225))])
if os.environ.get("FLAT_GIFS"):
  for s in SURF:
    save_row(os.path.join(ROOT, f"media/gifs/compare_{s}.gif"),
             [frames(f"baseline_{s}", f"proprioception only | {s} μ={MU[s]}"),
              frames(f"all_{s}", f"+ all tactile | {s} μ={MU[s]}")])
  for s in ("ice", "glue"):
      save_row(os.path.join(ROOT, f"media/gifs/compare_{s}_rough.gif"),
               [frames(f"baseline_{s}_rough", f"proprioception only | rough {s}"),
                frames(f"all_{s}_rough", f"+ all tactile | rough {s}")])
  for s in ("extreme_ice", "ice", "glue"):
      save_row(os.path.join(ROOT, f"media/gifs/sensors_{s}.gif"),
               [frames(f"{v}_{s}", f"{LABEL[v]} | {s}", size=(270, 170)) for v in ("fsr", "resistance", "slip", "vibro")])
  for s in ("regular", "ice"):
      save_row(os.path.join(ROOT, f"media/gifs/dead_{s}.gif"),
               [frames(f"baseline_{s}", f"proprioception only | {s}"),
                frames(f"all_{s}", f"all tactile, sensors OK | {s}"),
                frames(f"all_{s}_dead", f"all tactile, sensors DEAD | {s}")])
