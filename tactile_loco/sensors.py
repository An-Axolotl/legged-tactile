"""Simulated foot tactile sensors for a quadruped (Isaac Lab observation terms) and the per-environment
surface (friction) randomization used to train / evaluate on ice, glue and similar surfaces.

All sensors are computed from quantities a real foot sensor could measure, taken from the simulator:
  * normal foot load      F_n  = | net normal contact force on the foot |     (ContactSensor.net_forces_w)
  * shear / friction load F_t  = | friction force between foot and ground |   (ContactSensor.friction_forces_w)
  * foot velocity / acceleration of the foot body                             (Articulation data)

Sensors (each returns one value or a small vector per foot, feet ordered FL, FR, RL, RR):

  fsr_binary       FSR used as an on/off switch: 1 if F_n > threshold (default 3 N), else 0.
                   Each reading flips with probability `flip_prob` (sensor/ADC noise).
  fsr_resistance   The raw resistance of a force-sensing resistor (Interlink FSR-402-like model):
                       R(F) = 1 MΩ (open)                      for F < 0.2 N
                       R(F) = 150 kΩ · F^-0.85, clipped to [0.5 kΩ, 1 MΩ]   otherwise
                   reported in MΩ (so 0.0005 … 1.0, decreasing with load), ±5 % multiplicative noise.
  slip             "Slide N" sensor: the sliding (shear / friction) force F_t in newtons on the foot, and the
                   foot's tangential slip speed while in contact. Two values per foot; F_t is reported in N
                   multiplied by `force_scale` (default 0.02, i.e. units of 50 N) to keep inputs O(1).
  vibrotactile     Proposed extra sensor: a MEMS accelerometer in the foot tip, reporting vibration energy
                   log(1 + |a_foot| / g). Stick-slip on ice and sudden release from glue show up as high-frequency
                   foot accelerations that neither the FSR nor joint encoders see directly.
"""
from __future__ import annotations

import torch

from isaaclab.assets import Articulation
from isaaclab.managers import ManagerTermBase, SceneEntityCfg

G = 9.81

# Evaluation-only sensor faults (training always uses mode "none"):
#   "dead"  : every tactile sensor reads "no contact" (FSR 0, resistance open 1 MΩ, shear/slip 0, vibration 0)
#   "noisy" : 5x the nominal noise and 10 % of readings replaced by a random reading from the same foot vector
FAULT = {"mode": "none"}


def _fault(x: torch.Tensor, dead_value: float, noise: float) -> torch.Tensor:
    mode = FAULT["mode"]
    if mode == "dead":
        return torch.full_like(x, dead_value)
    if mode == "noisy":
        x = x + 5.0 * noise * torch.randn_like(x) * (x.abs().mean() + 1e-3)
        swap = torch.rand_like(x) < 0.10
        perm = x[:, torch.randperm(x.shape[1], device=x.device)]
        return torch.where(swap, perm, x)
    return x


def _normal_load(env, sensor_cfg: SceneEntityCfg) -> torch.Tensor:
    s = env.scene.sensors[sensor_cfg.name]
    return torch.linalg.norm(s.data.net_forces_w[:, sensor_cfg.body_ids], dim=-1)  # (N, 4)


def fsr_binary(env, sensor_cfg: SceneEntityCfg, threshold: float = 3.0, flip_prob: float = 0.02) -> torch.Tensor:
    on = (_normal_load(env, sensor_cfg) > threshold).float()
    if flip_prob > 0:
        flip = torch.rand_like(on) < flip_prob
        on = torch.where(flip, 1.0 - on, on)
    if FAULT["mode"] == "noisy":
        on = torch.where(torch.rand_like(on) < 0.10, 1.0 - on, on)
        return on
    return _fault(on, 0.0, 0.0)


def fsr_resistance(env, sensor_cfg: SceneEntityCfg, noise: float = 0.05) -> torch.Tensor:
    F = _normal_load(env, sensor_cfg)
    r_kohm = torch.clamp(150.0 * torch.clamp(F, min=1e-3) ** -0.85, 0.5, 1000.0)
    r_kohm = torch.where(F < 0.2, torch.full_like(r_kohm, 1000.0), r_kohm)
    if noise > 0:
        r_kohm = r_kohm * (1.0 + noise * torch.randn_like(r_kohm))
    return _fault(torch.clamp(r_kohm, 0.5, 1000.0) / 1000.0, 1.0, noise)  # MΩ


def slip(env, sensor_cfg: SceneEntityCfg, asset_cfg: SceneEntityCfg, contact_threshold: float = 3.0,
         force_scale: float = 0.02) -> torch.Tensor:
    s = env.scene.sensors[sensor_cfg.name]
    if s.data.friction_forces_w is not None:
        f_fric = s.data.friction_forces_w[:, sensor_cfg.body_ids].sum(dim=2)  # sum over filtered ground prims
        shear = torch.linalg.norm(f_fric, dim=-1)
    else:  # sensor not configured for friction: no shear information
        shear = torch.zeros_like(_normal_load(env, sensor_cfg))
    asset: Articulation = env.scene[asset_cfg.name]
    v = asset.data.body_lin_vel_w[:, asset_cfg.body_ids, :2]
    in_contact = _normal_load(env, sensor_cfg) > contact_threshold
    slip_speed = torch.linalg.norm(v, dim=-1) * in_contact
    return _fault(torch.cat([shear * force_scale, slip_speed], dim=-1), 0.0, 0.05)  # (N, 8): [F_t x4, v_slip x4]


def vibrotactile(env, asset_cfg: SceneEntityCfg, noise: float = 0.02) -> torch.Tensor:
    asset: Articulation = env.scene[asset_cfg.name]
    a = torch.linalg.norm(asset.data.body_lin_acc_w[:, asset_cfg.body_ids], dim=-1)
    out = torch.log1p(a / G)
    if noise > 0:
        out = out + noise * torch.randn_like(out)
    return _fault(out, 0.0, noise)


# ------------------------------------------------------------------------------------------- surfaces
# (static, dynamic) friction of the *foot* material; the terrain material is set to friction 1.0 with
# combine mode "multiply" (which wins over the robot's default "average"), so the foot-ground friction
# coefficient equals these values.
SURFACES = {
    "extreme_ice": (0.01, 0.005),   # the original project's ice setting
    "ice": (0.05, 0.03),
    "wet": (0.2, 0.15),
    "regular": (0.8, 0.6),
    "sticky": (2.0, 1.8),
    "glue": (3.0, 2.5),             # the original project's glue setting
    "extra_sticky": (5.0, 4.0),     # the original project's extra-sticky setting
}


class randomize_foot_surface(ManagerTermBase):
    """Event term: give every environment one surface (foot-ground friction) drawn from `surfaces`.

    Used at startup for training (each of the 4096 robots walks on one surface type) and for evaluation with a
    single surface.  Writes the friction of the foot collision shapes only.
    """

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        self.asset_cfg: SceneEntityCfg = cfg.params["asset_cfg"]
        self.asset: Articulation = env.scene[self.asset_cfg.name]
        self.shape_ids = []
        start = 0
        for i, link_path in enumerate(self.asset.root_physx_view.link_paths[0]):
            n = self.asset._physics_sim_view.create_rigid_body_view(link_path).max_shapes
            if i in self.asset_cfg.body_ids:
                self.shape_ids += list(range(start, start + n))
            start += n
        names = cfg.params["surfaces"]
        self.table = torch.tensor([SURFACES[n] for n in names], dtype=torch.float32)
        self.names = names

    def __call__(self, env, env_ids, asset_cfg, surfaces, cyclic: bool = False):
        if env_ids is None:
            env_ids = torch.arange(env.scene.num_envs, device="cpu")
        env_ids = env_ids.cpu()
        mats = self.asset.root_physx_view.get_material_properties()
        if cyclic:  # evaluation: env i walks on surface i % len(surfaces)
            idx = env_ids % len(self.names)
        else:
            idx = torch.randint(0, len(self.names), (len(env_ids),))
        if not hasattr(env, "surface_id"):
            env.surface_id = torch.zeros(env.scene.num_envs, dtype=torch.long)
        env.surface_id[env_ids] = idx
        for s in self.shape_ids:
            mats[env_ids, s, 0] = self.table[idx, 0]
            mats[env_ids, s, 1] = self.table[idx, 1]
            mats[env_ids, s, 2] = 0.0
        self.asset.root_physx_view.set_material_properties(mats, env_ids)
