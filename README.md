# EOS MuJoCo benchmark simulator

[GitHub repository](https://github.com/Island-Team/isos-mujoco-sim)

This independent C++ package runs robotic benchmark scenes in MuJoCo. EOS connects to its simulator socket and exposes normal robot discovery, observations, and primitives to agents such as EGIA. A trusted evaluator alone connects to the separate benchmark socket for seeded resets, manual stepping, ground truth, and scores.

The catalog starts with [pick and place](assets/scene.xml) and [navigation](assets/scenes/navigation/scene.xml). Select one scene at process startup with `--scene` or EOS `[simulator.mujoco].scene`. Read the [documentation map](docs/mujoco/doc_index.md) for setup, benchmark methods, interfaces, model provenance, and the path for adding a scene.

For the IsOS/EOS 2.0.0 graph and framed socket path, use the
[v2 backend guide](docs/mujoco/backend-v2.md). It stages a local backend
bundle with `tools/build-backend-bundle.py`. Set `MUJOCO_GUI=1` in the IsOS
backend node environment to view the running simulator's live state.

## Quick start

For an IsOS deployment, install the approved `island/mujoco-sim` backend package
with `isos backends install`, then select its exact version in the deployment
graph and run `isos config apply`. GitHub Release v1.0.1 is available; its package
catalog entry is published. See [package usage](docs/mujoco/usage.md)
for the local candidate install and graph setup. MuJoCo 3.16.0 remains an
operator-provided dependency. Set `MUJOCO_ROOT` in the IsOS-managed EOS node's
`launch.env` so EOS can pass it to the simulator process.

The following source build is useful for development and direct runs.

Requires C++20, CMake 3.22+, MuJoCo 3.16.0, protobuf, gRPC, and libjpeg. Copy [.env.example](.env.example) to the ignored `.env`, set `MUJOCO_ROOT` to your actual MuJoCo installation directory, then source it before building. The directory must contain `include/mujoco/mujoco.h`, `lib/libmujoco.so`, `bin/compile`, and `bin/simulate`.

```sh
. ./.env
: "${MUJOCO_ROOT:?Set MUJOCO_ROOT to your installed MuJoCo 3.16.0 directory}"
cmake -S . -B build -DMUJOCO_ROOT="$MUJOCO_ROOT"
cmake --build build -j
ctest --test-dir build --output-on-failure
```

For a standalone background run, `launch.sh` uses the configured scene and creates owner-only sockets under `.run/mujoco/`. It loads the local `.env` automatically; `kill.sh` stops only processes started by this launcher. Copy [launch.conf.example](launch.conf.example) to the ignored `launch.conf` to change defaults.

```sh
./launch.sh --scene pick-place --no-gui
./kill.sh
```

Use `--scene navigation` for the navigation task or `--gui` to open a separate MuJoCo viewer of the selected XML. The viewer does not display the running simulator's live state. For a direct run, pass absolute paths; the second socket is private to the evaluator.

```sh
build/eos-mujoco-sim \
  --socket /tmp/eos-simulator.sock \
  --benchmark-socket /tmp/eos-benchmark.sock \
  --scene "$PWD/assets/scene.xml"
```

Use `tools/scene-view.sh --scene "$PWD/assets/scene.xml"` for an interactive MuJoCo preview, or add `--check` for a headless model-loading check. `build/benchmark-eval` runs a timed private episode while the agent acts through EOS. See [usage](docs/mujoco/usage.md) for EOS launch, the navigation scene, and evaluator flags.

## License

Original package code and documentation are [Apache-2.0](LICENSE). Imported Menagerie models retain their [UR5e](assets/menagerie/universal_robots_ur5e/LICENSE) and [Robotiq 2F-85](assets/menagerie/robotiq_2f85/LICENSE) licenses. Keep the [model provenance](assets/MODELS.md) and source licenses with redistributed assets. MuJoCo is installed separately.
