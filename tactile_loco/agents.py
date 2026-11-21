from isaaclab.utils import configclass
from robot_lab.tasks.manager_based.locomotion.velocity.config.quadruped.unitree_a1.agents.rsl_rl_ppo_cfg import (
    UnitreeA1RoughPPORunnerCfg,
)

from .env_cfg import VARIANTS


def make(v):
    @configclass
    class _Ppo(UnitreeA1RoughPPORunnerCfg):
        def __post_init__(self):
            super().__post_init__()
            self.max_iterations = 2000
            self.save_interval = 250
            self.experiment_name = f"tactile_a1_{v}"
    return _Ppo


for _v in VARIANTS:
    globals()[f"A1Tactile_{_v}_PPO"] = make(_v)
