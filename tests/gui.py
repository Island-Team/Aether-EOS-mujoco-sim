#!/usr/bin/env python3
"""Manually verify that the X11 window shows the v2-controlled engine state."""

import argparse
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

from v2 import request


WINDOW = "IsOS MuJoCo — live simulation"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("scene", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        socket = root / "v2.sock"
        env = {**os.environ, "MUJOCO_GUI": "1"}
        process = subprocess.Popen(
            [str(args.binary.resolve()), "--socket", str(root / "legacy.sock"),
             "--benchmark-socket", str(root / "bench.sock"),
             "--v2-socket", str(socket), "--scene", str(args.scene.resolve())],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(100):
                info = subprocess.run(["xwininfo", "-name", WINDOW], capture_output=True, text=True)
                if socket.is_socket() and info.returncode == 0 and "Map State: IsViewable" in info.stdout:
                    break
                if process.poll() is not None:
                    raise RuntimeError(process.stdout.read().decode())
                time.sleep(0.1)
            else:
                raise RuntimeError("live simulator window was not visible")
            print(info.stdout, flush=True)

            def capture(label):
                path = args.output / f"{label}.xwd"
                subprocess.run(["xwd", "-name", WINDOW, "-out", str(path)], check=True)
                pixels = path.read_bytes()[-640 * 480 * 4:]
                digest = hashlib.sha256(pixels).hexdigest()
                print(label, "XWD pixel SHA-256", digest, flush=True)
                return digest

            before, _ = request(socket, "base_observe")
            print("base before", before["position_m"], flush=True)
            hash_before = capture("before")
            moved, _ = request(socket, "base_move", linear_x_m_s=0.4,
                               linear_y_m_s=0, angular_z_rad_s=0,
                               valid_for_ms=1000, command_id="gui-base-1")
            print("move", moved, flush=True)
            time.sleep(0.7)
            after, _ = request(socket, "base_observe")
            print("base after", after["position_m"], flush=True)
            hash_after = capture("after")
            assert after["position_m"][0] > before["position_m"][0] + 0.05
            assert hash_before != hash_after, "visible pixels did not change"
            stopped, _ = request(socket, "stop", command_id="gui-stop-1")
            print("stop", stopped, flush=True)
        finally:
            process.send_signal(signal.SIGINT)
            output, _ = process.communicate(timeout=10)
            print("exit", process.returncode, "socket removed", not socket.exists(), flush=True)
            print(output.decode(errors="replace"), flush=True)
            assert process.returncode == 0 and not socket.exists()


if __name__ == "__main__":
    main()
