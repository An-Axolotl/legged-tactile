"""Registers Tactile-A1-<variant>-v0 tasks (string entry points only: safe to import before Isaac Sim starts)."""
import gymnasium as gym

VARIANTS = ["baseline", "fsr", "resistance", "slip", "vibro", "all"]
for v in VARIANTS:
    gym.register(
        id=f"Tactile-A1-{v}-v0",
        entry_point="isaaclab.envs:ManagerBasedRLEnv",
        disable_env_checker=True,
        kwargs={"env_cfg_entry_point": f"tactile_loco.env_cfg:A1Tactile_{v}_EnvCfg",
                "rsl_rl_cfg_entry_point": f"tactile_loco.agents:A1Tactile_{v}_PPO"},
    )
