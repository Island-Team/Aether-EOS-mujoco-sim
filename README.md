# EOS MuJoCo benchmark simulator

[GitHub repository](https://github.com/Island-Team/Aether-EOS-mujoco-sim)

This is an independent MuJoCo process for EOS simulator benchmarking. It implements the EOS `SimulatorService` contract on one local Unix socket and exposes a separate benchmark-only `BenchmarkService` on another. EOS does not link MuJoCo. The benchmark socket must be kept private to the benchmark harness; agents receive only EOS device discovery, observations, and primitive calls.

The EOS checkout documents package usage, development, design, and the simulator interface under `docs/eos/`. This README contains the standalone build and connection steps.

## Build

Requires C++20, CMake 3.22+, MuJoCo 3.16.0, protobuf, gRPC, and libjpeg. `MUJOCO_ROOT` is the directory containing `include/mujoco/mujoco.h` and `lib/libmujoco.so`.

```sh
cmake -S . -B build -DMUJOCO_ROOT="$HOME/mujoco-3.16.0-linux-x86_64/mujoco-3.16.0"
cmake --build build -j
```

## Connect to EOS

This package lives beside the `Island-eos` repository, at `../Aether-EOS-mujoco-sim`; it is built and versioned separately from EOS. From the `Island-eos` checkout, copy the benchmark EOS configuration to the ignored local configuration (save any existing `etc/eos/eos.toml` first):

```sh
cp etc/eos/eos.mujoco.toml etc/eos/eos.toml
```

In `etc/eos/sim.toml`, set these values, using absolute paths that match your checkout:

```toml
[simulator]
backend = "mujoco"
camera_source = "scene"
map_id = ""

[simulator.camera]
width_px = 640
height_px = 480
fps = 30

[simulator.mujoco]
executable = "/absolute/path/to/Aether-EOS-mujoco-sim/build/eos-mujoco-sim"
scene = "/absolute/path/to/Aether-EOS-mujoco-sim/assets/scene.xml"
```

Keep the other existing `[simulator]` values, including `host` and `port`. Then launch EOS with `./eos-launch.sh --simulator`; the wrapper starts this executable with the simulator and benchmark Unix sockets in `ISLAND_RUN`. Direct EOS discovery and `base.navigate` through `GatewayService` have been validated with this profile.

For standalone testing without EOS:

```sh
build/eos-mujoco-sim \
  --socket /tmp/eos-simulator.sock \
  --benchmark-socket /tmp/eos-benchmark.sock \
  --scene "$PWD/assets/scene.xml"
```

Sockets are mode `0600`. The benchmark API is defined in `proto/benchmark.proto`: `Reset(seed)`, `Step(steps)`, `SetPaused(paused)`, `State()`, and `Score()`. State includes ground-truth base, arm, object, obstacle, and gripper-pinch positions; it is private to the benchmark harness. `Step` advances fixed physics steps and is bounded to 100,000 per call. A reset seeds the scene variations and pauses real-time stepping for deterministic manual control. `SetPaused(false)` resumes the 2 ms physics clock; `--manual-step` starts the process paused. Scoring reports navigation, grasp, placement, collision count, and elapsed simulated time.

The EOS protocol is a pinned copy of `Island-eos/share/contracts/eos/external/simulator/simulator.proto`; update it only with a matching EOS contract change. For motion commands, `ExecuteResponse.accepted` means motion completed physically, not merely queued. Stop and halt commands interrupt active motion. Unsupported devices and commands are not advertised in the MuJoCo HAL profile.

`tests/engine.cpp` contains a deterministic seed-42 pickup-and-placement oracle. It uses the same base, arm, and gripper commands exposed through EOS, but is a regression test rather than an agent. Grasp scores only after sustained bilateral pad contact while the cube is lifted above the table; placement scores after release inside the marked tray. Collision scoring counts robot contact with the table or obstacles, including incidental arm/table contact during a successful pickup. The oracle currently completes all three task goals and records 11 collision events, so task completion and collision performance remain separate benchmark results. An end-to-end run through EOS `GatewayService` primitive calls and the private benchmark client scored navigation, grasp, and placement true on this scene.

The example scene and model attribution are documented under `assets/`.

## License

The package's original code and documentation are licensed under [Apache-2.0](LICENSE). Imported Menagerie model files retain their own licenses: [UR5e](assets/menagerie/universal_robots_ur5e/LICENSE) is BSD-3-Clause and [Robotiq 2F-85](assets/menagerie/robotiq_2f85/LICENSE) is BSD-2-Clause. Keep those license files and the [model provenance](assets/MODELS.md) when redistributing the scene or meshes. MuJoCo itself is installed separately through `MUJOCO_ROOT`.

On this headless EGL host, MuJoCo reports one OpenGL `0x502` warning when the
render context is first created. Camera frames still render as valid JPEGs;
the context is reused for later frames without repeating the warning.
