"""Evaluate trained policies on each surface and optionally record a video per surface.

    python scripts/evaluate.py --variant all --headless                         # metrics -> results/metrics_<variant>.json
    python scripts/evaluate.py --variant all --headless --video --enable_cameras  # media/videos/<variant>_<surface>.mp4

Evaluation protocol (same for every variant, fixed seed):
  * flat ground, so that surface friction is the only thing that changes; every env gets surface i % 7
  * forward command 0.8 m/s for 20 s, plus a 0.5 rad/s turning command for the second half of the
    rollout (turning on ice is where most falls happen), no random pushes
  * a fall = base tilted > 60 deg or base below 0.15 m at any time (the robot may recover, still counted)
"""
import argparse
import json
import os
import sys

from isaaclab.app import AppLauncher

ap = argparse.ArgumentParser()
ap.add_argument("--variant", required=True)
ap.add_argument("--envs_per_surface", type=int, default=128)
ap.add_argument("--seconds", type=float, default=19.9)
ap.add_argument("--video", action="store_true")
ap.add_argument("--video_seconds", type=float, default=8.0)
ap.add_argument("--surfaces", default="")
ap.add_argument("--checkpoint", default="")
ap.add_argument("--terrain", choices=["flat", "rough"], default="flat")
ap.add_argument("--fault", choices=["none", "dead", "noisy"], default="none")
AppLauncher.add_app_launcher_args(ap)
args = ap.parse_args()
app = AppLauncher(args).app

import functools  # noqa: E402
print = functools.partial(print, flush=True)  # noqa: A001  (Isaac Sim exits before stdout is flushed)

import gymnasium as gym  # noqa: E402
import imageio  # noqa: E402
import torch  # noqa: E402
from isaaclab.terrains import MeshPlaneTerrainCfg  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402
from isaaclab_tasks.utils import get_checkpoint_path, load_cfg_from_registry  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import tactile_loco  # noqa: E402,F401
from tactile_loco import env_cfg as E  # noqa: E402
from tactile_loco import sensors as S_mod  # noqa: E402
from tactile_loco.sensors import SURFACES  # noqa: E402

task = f"Tactile-A1-{args.variant}-v0"
surfaces = tuple(args.surfaces.split(",")) if args.surfaces else tuple(SURFACES)
cfg = E.make(E.VARIANTS[args.variant], surfaces)()
n_per = 1 if args.video else args.envs_per_surface
cfg.scene.num_envs = n_per * len(surfaces)
cfg.seed = 0
if args.terrain == "flat":
    # flat tiles from the same terrain generator as training (same collider prim the friction sensor filters on)
    gen = cfg.scene.terrain.terrain_generator.replace(
        sub_terrains={"flat": MeshPlaneTerrainCfg(proportion=1.0)}, curriculum=False, num_rows=4, num_cols=4)
else:
    # the training terrain mix (slopes, stairs, boxes, noise) at uniformly random difficulty
    gen = cfg.scene.terrain.terrain_generator.replace(curriculum=False)
cfg.scene.terrain.terrain_generator = gen
cfg.scene.terrain.max_init_terrain_level = None
S_mod.FAULT["mode"] = args.fault
cfg.curriculum.terrain_levels = None
cfg.events.foot_surface.params["cyclic"] = True
cfg.events.randomize_push_robot = None
cfg.terminations.terrain_out_of_bounds = None  # the 20 s walk may leave its tile; no mid-rollout resets
cfg.events.randomize_apply_external_force_torque = None
cfg.events.randomize_reset_base.params["pose_range"] = {"x": (0, 0), "y": (0, 0), "yaw": (0, 0)}
if args.terrain == "rough":
    cfg.events.randomize_reset_base.params["pose_range"] = {"x": (-0.5, 0.5), "y": (-0.5, 0.5), "yaw": (-3.14, 3.14)}
cfg.events.randomize_reset_base.params["velocity_range"] = {}
cmd = cfg.commands.base_velocity
cmd.heading_command = False
cmd.rel_standing_envs = 0.0
cmd.resampling_time_range = (1e6, 1e6)
cmd.ranges.lin_vel_x = (0.8, 0.8)
cmd.ranges.lin_vel_y = (0.0, 0.0)
cmd.ranges.ang_vel_z = (0.0, 0.0)
if args.video:
    cfg.scene.env_spacing = 4.0
    cfg.viewer.origin_type = "asset_root"
    cfg.viewer.asset_name = "robot"
    cfg.viewer.eye = (1.6, -1.6, 0.8)
    cfg.viewer.lookat = (0.0, 0.0, 0.0)
    cfg.viewer.resolution = (640, 400)

agent = load_cfg_from_registry(task, "rsl_rl_cfg_entry_point")
log_root = os.path.join(ROOT, "logs/rsl_rl", agent.experiment_name)
if args.checkpoint:
    ckpt = args.checkpoint
elif os.path.isdir(log_root):
    ckpt = get_checkpoint_path(log_root, ".*", "model_.*.pt")
else:  # no local training run: use the released policy
    ckpt = os.path.join(ROOT, "checkpoints", f"{args.variant}.pt")
print("[eval] checkpoint", ckpt)
env = gym.make(task, cfg=cfg, render_mode="rgb_array" if args.video else None)
uw = env.unwrapped
venv = RslRlVecEnvWrapper(env, clip_actions=agent.clip_actions)
runner = OnPolicyRunner(venv, agent.to_dict(), log_dir=None, device=agent.device)
runner.load(ckpt)
policy = runner.get_inference_policy(device=uw.device)
robot = uw.scene["robot"]
feet = robot.find_bodies(".*_foot")[0]
dt = uw.step_dt
sid = uw.surface_id.to(uw.device)


def set_cmd(wz):
    term = uw.command_manager.get_term("base_velocity")
    term.vel_command_b[:, 0] = 0.8
    term.vel_command_b[:, 1] = 0.0
    term.vel_command_b[:, 2] = wz


def rollout(steps, frames_env=None):
    obs = venv.get_observations()
    obs = obs[0] if isinstance(obs, tuple) else obs
    N = uw.num_envs
    fell = torch.zeros(N, dtype=torch.bool, device=uw.device)
    err = torch.zeros(N, device=uw.device)
    slip = torch.zeros(N, device=uw.device)
    dist = torch.zeros(N, device=uw.device)
    steps_on = torch.zeros(N, device=uw.device)
    active = torch.ones(N, dtype=torch.bool, device=uw.device)  # stats freeze if an env is ever reset
    frames = []
    turn_at = steps * dt / 2  # straight for the first half, then turn
    for t in range(steps):
        set_cmd(0.0 if t * dt < turn_at else 0.5)
        obs, _, dones, _ = venv.step(policy(obs))
        set_cmd(0.0 if (t + 1) * dt < turn_at else 0.5)
        d = robot.data
        active &= ~dones.bool()
        a = active.float()
        z_ground = uw.scene.terrain.env_origins[:, 2] if args.terrain == "flat" else d.root_pos_w[:, 2] * 0 - 1e3
        fell |= active & ((d.projected_gravity_b[:, 2] > -0.5) | (d.root_pos_w[:, 2] - z_ground < 0.15))
        c = uw.command_manager.get_command("base_velocity")
        err += torch.linalg.norm(d.root_lin_vel_b[:, :2] - c[:, :2], dim=-1) * dt * a
        dist += d.root_lin_vel_b[:, 0] * dt * a
        fc = uw.scene["foot_contact"].data.net_forces_w.norm(dim=-1) > 3.0
        slip += (d.body_lin_vel_w[:, feet, :2].norm(dim=-1) * fc).sum(-1) * dt * a
        steps_on += a
        if t == steps - 1:
            ff = uw.scene["foot_contact"].data.friction_forces_w
            print(f"[eval] friction filter={uw.scene['foot_contact'].contact_physx_view.filter_count} "
                  f"mean shear={ff.norm(dim=-1).sum(-1).mean().item():.2f} N")
        if frames_env is not None:
            frames.append(env.render())
    T = steps_on.clamp(min=1) * dt
    print(f"[eval] envs reset mid-rollout: {int((~active).sum())}/{N}")
    return dict(fell=fell, err=err / T, slip=slip / T, dist=dist), frames


out = {}
torch.inference_mode().__enter__()  # whole evaluation (incl. resets) in inference mode
if not args.video:
    r, _ = rollout(int(args.seconds / dt))
    per_env = {"surface": sid.tolist(), **{k: v.float().tolist() for k, v in r.items()}}
    for i, s in enumerate(surfaces):
        m = sid == i
        out[s] = {"n": int(m.sum()), "fall_rate": r["fell"][m].float().mean().item(),
                  "vel_err": r["err"][m].mean().item(), "foot_slip_m_per_s": r["slip"][m].mean().item(),
                  "distance_m": r["dist"][m].mean().item()}
        print(f"[eval] {args.variant:10s} {s:13s} fall={out[s]['fall_rate']:.3f} vel_err={out[s]['vel_err']:.3f} "
              f"slip={out[s]['foot_slip_m_per_s']:.3f} dist={out[s]['distance_m']:.2f}")
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    suffix = ("" if args.terrain == "flat" else "_rough") + ("" if args.fault == "none" else f"_{args.fault}")
    with open(os.path.join(ROOT, f"results/metrics_{args.variant}{suffix}.json"), "w") as f:
        json.dump({"checkpoint": os.path.relpath(ckpt, ROOT), "terrain": args.terrain, "fault": args.fault,
                   "per_env": per_env, "surfaces": out}, f, indent=1)
else:
    os.makedirs(os.path.join(ROOT, "media/videos"), exist_ok=True)
    for i, s in enumerate(surfaces):
        venv.reset()
        uw.viewport_camera_controller.set_view_env_index(i)
        _, fr = rollout(int(args.video_seconds / dt), frames_env=i)
        path = os.path.join(ROOT, f"media/videos/{args.variant}_{s}{'' if args.terrain == 'flat' else '_rough'}{'' if args.fault == 'none' else '_' + args.fault}.mp4")
        imageio.mimsave(path, fr, fps=int(round(1 / dt)))
        print("[eval] wrote", path)
env.close()
app.close()
