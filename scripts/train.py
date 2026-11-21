"""Train a tactile A1 policy with robot_lab's RSL-RL training script.
    python scripts/train.py --task Tactile-A1-all-v0 --headless
(any robot_lab train.py argument works; ROBOT_LAB points at the robot_lab checkout, default ../robot_lab)."""
import os, runpy, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import tactile_loco  # noqa: F401  (registers the tasks)
RL = os.path.join(os.environ.get("ROBOT_LAB", os.path.join(os.path.dirname(os.path.dirname(HERE)), "robot_lab")),
                  "scripts/reinforcement_learning/rsl_rl")
sys.path.insert(0, RL)
sys.argv[0] = os.path.join(RL, "train.py")
runpy.run_path(sys.argv[0], run_name="__main__")
