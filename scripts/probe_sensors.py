"""Sanity check of the simulated foot sensors: one env per surface, random small actions, print per-surface
averages of every sensor and the foot friction actually written to PhysX.
    python scripts/probe_sensors.py --headless
"""
import argparse
import os
import sys

from isaaclab.app import AppLauncher

ap = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(ap)
args = ap.parse_args()
app = AppLauncher(args).app

import functools  # noqa: E402
import gymnasium as gym  # noqa: E402
print = functools.partial(print, flush=True)  # Isaac Sim exits before stdout is flushed
import torch  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tactile_loco  # noqa: E402,F401
from tactile_loco.env_cfg import A1Tactile_all_EnvCfg  # noqa: E402
from tactile_loco.sensors import SURFACES  # noqa: E402

cfg = A1Tactile_all_EnvCfg()
cfg.scene.num_envs = 64
cfg.scene.terrain.max_init_terrain_level = 0
env = gym.make("Tactile-A1-all-v0", cfg=cfg)
uw = env.unwrapped
obs, _ = env.reset()
names = list(SURFACES)
robot = uw.scene["robot"]
mats = robot.root_physx_view.get_material_properties()
foot_shapes = uw.event_manager._mode_term_cfgs["startup"][-1].func.shape_ids
print("foot shape ids", foot_shapes)
acc = {k: [] for k in ["fsr", "res", "shear", "slip", "vib", "Fn"]}
sensor = uw.scene["foot_contact"]
print("friction filter count:", sensor.contact_physx_view.filter_count)
for t in range(150):
    act = 0.3 * torch.randn(uw.num_envs, uw.action_manager.total_action_dim, device=uw.device)
    obs, *_ = env.step(act)
    if t > 50:
        from tactile_loco import sensors as S
        from isaaclab.managers import SceneEntityCfg
        sc = SceneEntityCfg("foot_contact", body_names=".*_foot"); sc.resolve(uw.scene)
        ac = SceneEntityCfg("robot", body_names=".*_foot"); ac.resolve(uw.scene)
        acc["Fn"].append(S._normal_load(uw, sc).cpu())
        acc["fsr"].append(S.fsr_binary(uw, sc).cpu())
        acc["res"].append(S.fsr_resistance(uw, sc).cpu())
        sl = S.slip(uw, sc, ac).cpu()
        acc["shear"].append(sl[:, :4] / 0.02); acc["slip"].append(sl[:, 4:])
        acc["vib"].append(S.vibrotactile(uw, ac).cpu())
A = {k: torch.stack(v).mean(0).mean(-1) for k, v in acc.items()}
sid = uw.surface_id
for i, n in enumerate(names):
    m = sid == i
    if m.any():
        mu = mats[m.nonzero()[0, 0], foot_shapes[0], :2].tolist()
        print(f"{n:13s} n={int(m.sum()):3d} mu(s,d)={mu[0]:.3f},{mu[1]:.3f}  Fn={A['Fn'][m].mean():6.1f} N  "
              f"FSR on={A['fsr'][m].mean():.2f}  R={A['res'][m].mean()*1000:7.1f} kΩ  shear={A['shear'][m].mean():6.2f} N  "
              f"slip={A['slip'][m].mean():.3f} m/s  vib={A['vib'][m].mean():.3f}")
env.close()
app.close()
