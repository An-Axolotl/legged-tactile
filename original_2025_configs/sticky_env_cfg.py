# Copyright (c) 2024-2025 Ziqi Fan
# SPDX-License-Identifier: Apache-2.0

from isaaclab.utils import configclass
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.sim.spawners.materials import RigidBodyMaterialCfg

from .rough_cfg import UnitreeA1RoughEnvCfg

##
# Pre-defined configs
##
from robot_lab.assets.unitree import UNITREE_A1_CFG  # isort: skip


@configclass
class UnitreeA1StickyEnvCfg(UnitreeA1RoughEnvCfg):
    """Configuration for Unitree A1 locomotion on sticky/glue-like terrain."""

    def __post_init__(self):
        # Call parent post_init first
        super().__post_init__()
        
        # ------------------------------Terrain (Sticky Surface)------------------------------
        # Modify terrain physics material for sticky/glue-like properties
        # Very high friction = sticky surface
        self.scene.terrain.physics_material = RigidBodyMaterialCfg(
            static_friction=3.0,      # Very high static friction (glue-like)
            dynamic_friction=2.5,     # High dynamic friction
            restitution=0.0,          # No bounce
            friction_combine_mode="max",      # Use maximum friction in contacts
            restitution_combine_mode="min",   # Use minimum restitution
        )
        
        # Optional: Keep terrain flat for consistent sticky behavior
        # Comment this out if you want to keep rough terrain with sticky surface
        # self.scene.terrain.terrain_type = "plane"
        
        # ------------------------------Robot Foot Friction------------------------------
        # Ensure robot feet also have high friction to interact with sticky ground
        # This modifies the robot's foot material properties
        if hasattr(self.scene.robot.spawn, 'rigid_props'):
            # Increase contact parameters for better sticky contact detection
            self.scene.robot.spawn.rigid_props.contact_offset = 0.02
            self.scene.robot.spawn.rigid_props.rest_offset = 0.0
            self.scene.robot.spawn.rigid_props.max_depenetration_velocity = 1.0
        
        # ------------------------------Rewards Adjustment------------------------------
        # Sticky terrain changes locomotion dynamics, so adjust rewards accordingly
        
        # Feet slide penalty should be reduced/removed - sticky surface prevents sliding
        self.rewards.feet_slide.weight = 0.0
        
        # Increase penalty for high contact forces since sticky surface creates resistance
        self.rewards.contact_forces.weight = -2e-4  # More penalty for high forces
        
        # May need more torque/power to overcome sticky friction
        self.rewards.joint_torques_l2.weight = -1e-5  # Reduce penalty (was -2.5e-5)
        self.rewards.joint_power.weight = -1e-5       # Reduce penalty (was -2e-5)
        
        # Action rate penalty adjustment - may need more aggressive actions
        self.rewards.action_rate_l2.weight = -0.005   # Reduce penalty (was -0.01)
        
        # Feet air time becomes more important with sticky surface
        # Robot needs to work harder to lift feet
        self.rewards.feet_air_time.weight = 0.5
        self.rewards.feet_air_time.params["threshold"] = 0.3  # Lower threshold
        
        # Optional: Add penalty for feet getting stuck
        # self.rewards.feet_contact.weight = -0.1  # Penalize prolonged contact
        
        # ------------------------------Simulation Physics------------------------------
        # Optional: Adjust solver parameters for better sticky contact resolution
        if hasattr(self, 'sim') and hasattr(self.sim, 'physx'):
            self.sim.physx.bounce_threshold_velocity = 0.2
            self.sim.physx.friction_offset_threshold = 0.01
            self.sim.physx.friction_correlation_distance = 0.00625


@configclass
class UnitreeA1ExtraStickyEnvCfg(UnitreeA1RoughEnvCfg):
    """Configuration for extremely sticky terrain (even more glue-like)."""

    def __post_init__(self):
        super().__post_init__()
        
        # ------------------------------Extreme Sticky Terrain------------------------------
        self.scene.terrain.physics_material = RigidBodyMaterialCfg(
            static_friction=5.0,      # Extremely high static friction
            dynamic_friction=4.0,     # Extremely high dynamic friction
            restitution=0.0,
            friction_combine_mode="max",
            restitution_combine_mode="min",
        )
        
        # Use flat terrain for extreme sticky case
        self.scene.terrain.terrain_type = "plane"
        
        if hasattr(self.scene.robot.spawn, 'rigid_props'):
            self.scene.robot.spawn.rigid_props.contact_offset = 0.02
            self.scene.robot.spawn.rigid_props.rest_offset = 0.0
        
        # ------------------------------Aggressive Reward Adjustments------------------------------
        # Remove/reduce penalties that conflict with sticky terrain dynamics
        self.rewards.feet_slide.weight = 0.0
        self.rewards.contact_forces.weight = -3e-4
        
        # Significantly reduce energy penalties
        self.rewards.joint_torques_l2.weight = -5e-6
        self.rewards.joint_power.weight = -5e-6
        self.rewards.action_rate_l2.weight = -0.002
        
        # Strongly reward getting feet off ground
        self.rewards.feet_air_time.weight = 1.0
        self.rewards.feet_air_time.params["threshold"] = 0.25
        
        # Adjust velocity tracking - harder to achieve on sticky surface
        self.rewards.track_lin_vel_xy_exp.weight = 2.0  # Reduce from 3.0
        self.rewards.track_ang_vel_z_exp.weight = 1.0   # Reduce from 1.5