# Build and run

[Package overview](README.md) · [Benchmark tasks](benchmarks.md)

Build the simulator separately from EOS. Install MuJoCo 3.16.0, copy [`.env.example`](../../.env.example) to the ignored `.env`, and set `MUJOCO_ROOT` there to its real installation directory. It must contain `include/mujoco/mujoco.h`, `lib/libmujoco.so`, `bin/compile`, and `bin/simulate`. CMake also needs C++20, protobuf, gRPC, and libjpeg.

```sh
. ./.env
: "${MUJOCO_ROOT:?Set MUJOCO_ROOT to your installed MuJoCo 3.16.0 directory}"
cmake -S . -B build -DMUJOCO_ROOT="$MUJOCO_ROOT"
cmake --build build -j
ctest --test-dir build --output-on-failure
```

## Standalone launcher

The root scripts manage a standalone simulator in the background. They load the local `.env` and optional ignored `launch.conf`; [launch.conf.example](../../launch.conf.example) shows the defaults. Relative scene, executable, and run-directory paths are resolved from the repository root. The default run directory is `.run/mujoco/`, with owner-only simulator and benchmark sockets, logs, and process records.

```sh
./launch.sh --scene pick-place --no-gui
./kill.sh
./launch.sh --scene navigation --gui
./kill.sh
```

`--gui` opens MuJoCo's independent `simulate` viewer for the same XML. It requires a desktop display and the `MUJOCO_ROOT` viewer tools; it does not show the live simulator state or seeded reset variation. `--no-gui` is the default. `--manual-step`, `--run-dir PATH`, and `--executable PATH` override launcher defaults. If you use a custom run directory, pass the same `--run-dir` to `kill.sh`. The stop script checks the recorded process identity and only stops processes started by `launch.sh`; it does not stop EOS-owned simulator processes. Inspect `.run/mujoco/simulator.log` or `viewer.log` if startup fails.

For direct execution without the process scripts, the executable requires three absolute paths. `--scene` chooses one supported profile when the process starts. `--manual-step` starts paused; otherwise the simulator advances at the 2 ms physics step in real time. A benchmark `Reset` also pauses it for deterministic stepping. Both socket paths must differ, and the scene must be a regular file.

```sh
build/eos-mujoco-sim \
  --socket /tmp/eos-simulator.sock \
  --benchmark-socket /tmp/eos-benchmark.sock \
  --scene "$PWD/assets/scenes/navigation/scene.xml" \
  --manual-step
```

The Unix sockets are owner-only (`0600`). Use a private runtime directory for evaluation and give the benchmark socket only to the evaluator. Stop the process with `SIGINT` or `SIGTERM`; it removes its sockets on normal shutdown. `--help` prints the available flags.

## EOS and EGIA

IsOS installs the `island/mujoco-sim` backend package and activates it through the deployment graph. The v1.0.1 GitHub Release is available; its package-center entry has not been published yet. After catalog publication, install the exact approved version with IsOS:

```sh
isos packages search mujoco
isos backends install island/mujoco-sim --version 1.0.1
```

`isos backends install` checks the platform, archive size, and SHA-256 against the approved manifest. Add a backend node with the exact package ID and version, `owned: false`, and an EOS-to-backend `backend_attachment` edge to the IsOS deployment graph. Do not set `settings.sidecar_of` on this backend. Add `MUJOCO_ROOT` to the EOS node's `launch.env`; IsOS passes that environment to EOS, which launches the packaged simulator from its generated module. Then run `isos config validate` and `isos config apply`, followed by an explicit EOS start or restart.

For a local release candidate before catalog publication, install the exact archive through IsOS's unapproved-manifest path:

```sh
isos packages install --manifest island-release.json --asset mujoco-sim-v1.0.1-linux-x86_64.tar.gz --allow-unapproved
```

Configure an IsOS graph like this, replacing the EOS executable, config, and MuJoCo root paths with the local installation paths:

```json
{
  "schema_version": 1,
  "name": "default",
  "nodes": [
    {
      "id": "eos",
      "kind": "component",
      "role": "eos",
      "enabled": true,
      "contract": "island.eos.v1",
      "launch": {
        "command": ["/path/to/Island-eos/bin/eosd", "--config", "/path/to/eos.toml"],
        "env": {"MUJOCO_ROOT": "/path/to/mujoco-3.16.0"}
      },
      "settings": {
        "eos_config": "/path/to/eos.toml",
        "north_http_url": "http://127.0.0.1:16005"
      }
    },
    {
      "id": "mujoco",
      "kind": "backend",
      "enabled": true,
      "owned": false,
      "package": {"id": "island/mujoco-sim", "version": "1.0.1"}
    }
  ],
  "edges": [{"from": "eos", "to": "mujoco", "kind": "backend_attachment"}]
}
```

For a source checkout, use the same package module with the local `MUJOCO_ROOT` in the IsOS EOS node's `launch.env`. See the [IsOS package guide](https://github.com/Island-Team/isos/blob/master/docs/isos/usage/packages.md) and [deployment graph contract](https://github.com/Island-Team/isos/blob/master/docs/isos/interfaces/deployment-graph.md).

```toml
[simulator]
backend = "mujoco"
map_id = ""
camera_source = "scene"

[simulator.camera]
width_px = 640
height_px = 480
fps = 30

[simulator.mujoco]
executable = "/absolute/path/to/isos-mujoco-sim/build/eos-mujoco-sim"
scene = "/absolute/path/to/isos-mujoco-sim/assets/scene.xml"
```

Keep EOS's existing loopback `host` and `port` settings in the same `[simulator]` table. Replace only the `scene` path with `assets/scenes/navigation/scene.xml` to select navigation. EOS rejects unknown keys and other camera settings for MuJoCo. Launch from the EOS checkout with `./eos-launch.sh --simulator`; its wrapper passes both socket paths and the selected scene to this executable. Restart the simulator to change scenes.

EGIA connects to the already-running EOS gateway through its normal connection profile. EGIA does not start this process or connect to the benchmark socket. EOS discovery and primitive calls are the agent's action and observation route.

## Timed agent episode

Start the simulator and EOS/EGIA agent first. The evaluator connects only to the private benchmark socket. This example resets seed 42, resumes real-time simulation for 30 wall-clock seconds while the separate agent acts, pauses, and prints one JSON score object:

```sh
build/benchmark-eval \
  --benchmark-socket /absolute/path/to/benchmark.sock \
  --task navigation \
  --seed 42 \
  --duration-s 30
```

Use `--task pick-place` with `assets/scene.xml`, or `--task navigation` with `assets/scenes/navigation/scene.xml`. The evaluator does not inspect the scene or run an agent policy, so the caller must match `--task` to the selected scene. It accepts a positive duration up to 3600 seconds. Its `success` is all three goals for pick and place or `navigation` alone for navigation; collision count and elapsed simulated time are reported separately. See [benchmark method](benchmarks.md) for multi-seed reporting.

## Scene inspection and verification

The standalone viewer compiles MJCF first. It shows the XML's initial layout; seeded variations happen only during `Reset` in the running simulator.

```sh
. ./.env
: "${MUJOCO_ROOT:?Set MUJOCO_ROOT to your installed MuJoCo 3.16.0 directory}"
tools/scene-view.sh --scene "$PWD/assets/scene.xml"
tools/scene-view.sh --check --scene "$PWD/assets/scenes/navigation/scene.xml"
tools/scene-view.sh --snapshot /tmp/navigation.png --scene "$PWD/assets/scenes/navigation/scene.xml"
```

The interactive viewer needs a desktop display. `--check` validates model loading headlessly; `--snapshot` needs MuJoCo's `bin/render`. Run `ctest --test-dir build --output-on-failure` for engine, socket, evaluator, and scene checks. A passing viewer check establishes XML loadability, while the engine and smoke checks exercise reset, commands, service behavior, and scoring.

**Related:** [Design](design.md) · [EOS simulator interface](interfaces/simulator.md) · [Benchmark interface](interfaces/benchmark.md)
