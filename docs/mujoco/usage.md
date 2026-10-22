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

EOS can install the published `island/mujoco-sim` v0.1.0 release through its package client. Set `MUJOCO_ROOT` to a separate MuJoCo 3.16.0 installation, then run these commands from the Island-eos checkout:

```sh
./bin/island-pkg search mujoco
./bin/island-pkg doctor island/mujoco-sim
./bin/island-pkg install island/mujoco-sim
./bin/island-pkg activate island/mujoco-sim
```

`doctor` checks host requirements. `install` checks the archive size and SHA-256 against the published manifest. `activate` writes a separate EOS configuration bundle and prints the launch command; review that bundle and run the printed command with `--simulator`. See the [EOS package usage guide](https://github.com/Island-Team/Island-eos/blob/master/docs/eos/usage/ext/mujoco.md).

For a source checkout, EOS can still launch this package through its simulator wrapper. Copy `../Island-eos/etc/eos/eos.mujoco.toml` to the local EOS `etc/eos/eos.toml` after preserving your current configuration. In EOS `etc/eos/sim.toml`, select the MuJoCo backend and set paths for this checkout:

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
executable = "/absolute/path/to/Aether-EOS-mujoco-sim/build/eos-mujoco-sim"
scene = "/absolute/path/to/Aether-EOS-mujoco-sim/assets/scene.xml"
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
