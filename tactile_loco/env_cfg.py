"""Tactile A1 locomotion environments (robot_lab v2.3.2 A1 rough-terrain task + foot sensors + surfaces)."""
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import ContactSensorCfg
import isaaclab.sim as sim_utils
from isaaclab.utils import configclass
from isaaclab_assets.robots.unitree import UNITREE_A1_CFG as A1_USD

from robot_lab.tasks.manager_based.locomotion.velocity.config.quadruped.unitree_a1.rough_env_cfg import (
    UnitreeA1RoughEnvCfg,
)

from . import sensors as S

GROUND = "/World/ground/terrain/mesh"
FEET = ".*_foot"
SENSOR_TERMS = ("fsr", "resistance", "slip", "vibro")


@configclass
class TactileA1EnvCfg(UnitreeA1RoughEnvCfg):
    # Isaac Lab's USD A1 (robot_lab's URDF A1 needs a URDF importer newer than Isaac Sim 4.5 ships)
    base_link_name = "trunk"
    tactile: tuple = ()                       # subset of SENSOR_TERMS added to the policy (and critic) observation
    surfaces: tuple = tuple(S.SURFACES)       # each env gets one of these foot-ground frictions

    def __post_init__(self):
        super().__post_init__()
        # robot_lab only prunes zero-weight rewards for its own class name
        self.disable_zero_weight_rewards()
        self.scene.robot = A1_USD.replace(prim_path="{ENV_REGEX_NS}/Robot")
        # terrain friction 1.0, "multiply" -> foot-ground friction = the foot surface value
        self.scene.terrain.physics_material = sim_utils.RigidBodyMaterialCfg(
            static_friction=1.0, dynamic_friction=1.0, restitution=0.0,
            friction_combine_mode="multiply", restitution_combine_mode="multiply")
        self.sim.physics_material = self.scene.terrain.physics_material
        # foot sensor with friction (shear) force tracking against the ground
        self.scene.foot_contact = ContactSensorCfg(
            prim_path="{ENV_REGEX_NS}/Robot/" + FEET, history_length=3, track_air_time=False,
            track_friction_forces=True, filter_prim_paths_expr=[GROUND])
        # per-env surface, applied after robot_lab's whole-body material randomisation
        self.events.foot_surface = EventTerm(
            func=S.randomize_foot_surface, mode="startup",
            params={"asset_cfg": SceneEntityCfg("robot", body_names=FEET), "surfaces": tuple(self.surfaces)})
        def terms(): return dict(
            fsr=ObsTerm(func=S.fsr_binary, params={"sensor_cfg": SceneEntityCfg("foot_contact", body_names=FEET)}),
            resistance=ObsTerm(func=S.fsr_resistance, params={"sensor_cfg": SceneEntityCfg("foot_contact", body_names=FEET)}),
            slip=ObsTerm(func=S.slip, params={"sensor_cfg": SceneEntityCfg("foot_contact", body_names=FEET),
                                              "asset_cfg": SceneEntityCfg("robot", body_names=FEET)}),
            vibro=ObsTerm(func=S.vibrotactile, params={"asset_cfg": SceneEntityCfg("robot", body_names=FEET)}),
        )
        for name in self.tactile:  # separate term objects per group (body ids are resolved per term)
            setattr(self.observations.policy, f"tactile_{name}", terms()[name])
            setattr(self.observations.critic, f"tactile_{name}", terms()[name])


def make(tactile, surfaces=tuple(S.SURFACES)):
    @configclass
    class _Cfg(TactileA1EnvCfg):
        def __post_init__(self):
            self.tactile = tuple(tactile)
            self.surfaces = tuple(surfaces)
            super().__post_init__()
    return _Cfg


VARIANTS = {"baseline": (), "fsr": ("fsr",), "resistance": ("resistance",), "slip": ("slip",),
            "vibro": ("vibro",), "all": SENSOR_TERMS}
for _v, _t in VARIANTS.items():
    globals()[f"A1Tactile_{_v}_EnvCfg"] = make(_t)
