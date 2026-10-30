#!/usr/bin/env python3
"""Stage the local island/mujoco-sim@2.0.0 IsOS backend bundle."""

import argparse
import json
import os
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    binary = args.build_dir / "eos-mujoco-sim"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        parser.error(f"build the simulator first: {binary}")
    bundle = args.output.resolve()
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "bin").mkdir(exist_ok=True)
    shutil.copy2(binary, bundle / "bin/eos-mujoco-sim")
    shutil.copytree(ROOT / "assets", bundle / "assets", dirs_exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", bundle / "LICENSE")
    descriptor = {
        "schema_version": "2.0.0",
        "package": {"id": "island/mujoco-sim", "version": "2.0.0"},
        "entrypoint": "bin/eos-mujoco-sim",
        "protocol": "mujoco-v2",
        "scenes": [
            {"id": "pick-place", "path": "assets/scene.xml"},
            {"id": "navigation", "path": "assets/scenes/navigation/scene.xml"},
        ],
        "devices": {"camera": "cam-0", "base": "base-0", "manipulator": "arm-0"},
        "runtime": {
            "mujoco_version": "3.16.0",
            "environment_variable": "MUJOCO_ROOT",
            "library": "lib/libmujoco.so.3.16.0",
        },
    }
    (bundle / "backend-v2.json").write_text(json.dumps(descriptor, indent=2) + "\n")
    print(bundle)


if __name__ == "__main__":
    main()
