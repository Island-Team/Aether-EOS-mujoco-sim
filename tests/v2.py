#!/usr/bin/env python3
"""Exercise the real framed socket and the shared live simulator state."""

import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time


def request(path: Path, op: str, **fields):
    body = json.dumps({"version": "2.0.0", "id": op, "node": "test", "op": op, **fields}).encode()
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(5)
        connection.connect(str(path))
        connection.sendall(struct.pack("<II", len(body), 0) + body)
        header = connection.recv(8)
        if len(header) != 8:
            raise RuntimeError("short response header")
        metadata_size, payload_size = struct.unpack("<II", header)
        assert 0 < metadata_size <= 65536 and payload_size <= 8 * 1024 * 1024

        def read(size):
            data = bytearray()
            while len(data) < size:
                part = connection.recv(size - len(data))
                if not part:
                    raise RuntimeError("short response")
                data.extend(part)
            return bytes(data)

        metadata = json.loads(read(metadata_size))
        payload = read(payload_size)
        assert metadata["version"] == "2.0.0" and metadata["id"] == op, metadata
        assert metadata["ok"], metadata
        return metadata, payload


def main():
    binary, scene = sys.argv[1:3]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "v2.sock"
        process = subprocess.Popen(
            [binary, "--socket", str(root / "legacy.sock"),
             "--benchmark-socket", str(root / "benchmark.sock"),
             "--v2-socket", str(path), "--scene", scene],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(100):
                if path.is_socket():
                    break
                if process.poll() is not None:
                    raise RuntimeError(process.stdout.read().decode())
                time.sleep(0.05)
            assert path.is_socket(), "v2 socket was not created"
            assert path.stat().st_mode & 0o777 == 0o600
            request(path, "health")
            camera, jpeg = request(path, "camera_capture")
            assert camera["format"] == "jpeg" and camera["rgb_length"] == len(jpeg)
            assert camera["width_px"] == 640 and camera["height_px"] == 480
            assert jpeg[:2] == b"\xff\xd8" and len(jpeg) > 1000
            base, _ = request(path, "base_observe")
            assert len(base["position_m"]) == 2
            arm, _ = request(path, "manipulator_observe")
            assert len(arm["joint_positions_rad"]) == 6
            moved, _ = request(path, "base_move", linear_x_m_s=0.3,
                               linear_y_m_s=0, angular_z_rad_s=0,
                               valid_for_ms=500, command_id="base-1")
            assert moved["accepted"]
            time.sleep(0.35)
            after, _ = request(path, "base_observe")
            assert after["position_m"][0] > base["position_m"][0] + 0.01
            moved, _ = request(path, "manipulator_move",
                               joint_positions_rad=[0.1] * 6, command_id="arm-1")
            assert moved["accepted"]
            request(path, "stop", command_id="stop-1")
            print("v2 camera, base motion, arm command, safe stop passed")
        finally:
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=10)
            assert process.returncode == 0
            assert not path.exists(), "v2 socket remained after shutdown"


if __name__ == "__main__":
    main()
