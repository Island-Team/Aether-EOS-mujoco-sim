# IsOS managed MuJoCo v2 backend

[中文](../../docs_cn/mujoco/backend-v2_cn.md)

Build the simulator and stage a local `island/mujoco-sim@2.0.0` bundle:

```sh
export MUJOCO_ROOT=/absolute/path/to/mujoco-3.16.0
cmake -S . -B build -DMUJOCO_ROOT="$MUJOCO_ROOT"
cmake --build build -j
ctest --test-dir build --output-on-failure
python3 tests/node_contributions.py
python3 tools/build-backend-bundle.py --output /absolute/path/to/mujoco-v2-bundle
isos pkg link island/mujoco-sim 2.0.0 /absolute/path/to/mujoco-v2-bundle --manifest /absolute/path/to/mujoco-v2-bundle/release.json
```

The bundle contains an actual executable at `bin/eos-mujoco-sim`, the two
supported scenes and their model assets, `backend-v2.json`, and a local schema v4 `release.json`. The builder writes a checksummed release archive beside the bundle. The descriptor
declares the `mujoco-v2` protocol, `cam-0`, `base-0`, and `arm-0` device IDs,
and the external MuJoCo 3.16.0 library requirement. IsOS verifies the scene,
assets, executable, and library before run and supplies the library directory
to the child process. Package installation alone does not activate a graph.

The release's `node_contributions` declares a `sim-hardware` node set. It adds the EOS-owned simulator process under `process/mujoco` and camera, base, and manipulator nodes under `hardware/mujoco`. These types explicitly require the `mujoco` group; the generic omitted-group default for this package would be `mujoco-sim`. Their port declarations provide expected sample frequency, transport, and data class for the graph editor. The set also links the camera to a built-in EOS camera gate under `interface/gate` and makes that gate the default source of a built-in IsosUI Vision node under `system/ui`. IsOS catalogs the set after install or link; preview binds the scene and owner-only socket, resolves its symbolic node references, and validates the resulting shared graph. Only the four package-contributed MuJoCo nodes carry the `island/mujoco-sim@2.0.0` package pin; the gate and Vision nodes use their own built-in contracts. The release declaration is a reusable source for drafting nodes, not a second live graph. Vision can select another active compatible gate at runtime without changing this default edge.

The backend node's `settings.env` can contain `MUJOCO_GUI=1` or
`MUJOCO_GUI=true`. This opens an X11 window titled `IsOS MuJoCo — live
simulation` while EOS owns the simulator child. It renders camera frames from the
same `SimEngine` instance controlled by the v2 socket and benchmark socket.
The default is headless. A desktop with an accessible `DISPLAY` is required;
an unavailable display makes the simulator fail at startup. The independent
`tools/scene-view.sh` viewer remains a static scene preview.

The v2 socket uses an eight-byte little-endian frame header followed by JSON
metadata and an optional JPEG payload. Metadata is capped at 64 KiB; payload
is capped at 8 MiB. The request must include `version: "2.0.0"`, a string
`id`, `node`, and `op`. The response echoes ID and version and supplies `ok`
or `error.message`. Operations refer to the live state:

| Operation | Request fields | Response fields |
| --- | --- | --- |
| `health` | none | `accepted: bool` |
| `camera_capture` | none | `format: "jpeg"`, `rgb_length: u64` bytes, `depth_available: false`, `width_px: u32`, `height_px: u32`, JPEG payload |
| `base_observe` | none | `position_m: [f64; 2]`, `linear_velocity_m_s: [f64; 2]`, `yaw_rad: f64`, `angular_velocity_rad_s: f64` |
| `base_move` | `linear_x_m_s: f64`, `linear_y_m_s: f64`, `angular_z_rad_s: f64`, `valid_for_ms: f64` in `(0, 5000]`, `command_id: string` | `accepted: bool`; drive expires after `valid_for_ms` simulated time |
| `manipulator_observe` | none | `joint_positions_rad: [f64; 6]`, `joint_velocities_rad_s: [f64; 6]`, `end_position_m: [f64; 3]`, `end_orientation_xyzw: [f64; 4]` |
| `manipulator_move` | `joint_positions_rad: [f64; 6]`, `command_id: string` | `accepted: bool` |
| `stop` | `command_id: string` | `accepted: bool`; holds base and arm |

`timestamp_ns` is simulated time in nanoseconds and `sequence` is the engine
step count. Values are finite and movement bounds are enforced by the engine.
The v2 socket is owner-only (`0600`) and removed on normal shutdown. IsOS verifies the package and passes the executable and scene to EOS. EOS starts the simulator as its direct child, connects its hardware adapters as socket clients, and stops admitted actuators before terminating the simulator.

## Verification

On 2026-10-30, `cmake --build build -j4` and all ten CTest cases passed on
Ubuntu with MuJoCo 3.16.0. `tests/v2.py` exercised real JPEG capture, base
motion, six-joint command, safe stop, and socket cleanup. With
`MUJOCO_GUI=1` and `DISPLAY=:0`, `xwininfo` reported a visible 640×480
window. A v2 base command moved observed base x from -1.20 m to -0.951 m;
XWD captures of that window had different pixel hashes. The unavailable GUI
test confirmed startup failure removes every socket. The commands and full
output are in `logs/test/2026-10-30-v2-live/{build,ctest,bundle,gui}.log`;
XWD captures are in that same directory. Reproduce the visual check with
`python3 tests/gui.py build/eos-mujoco-sim assets/scene.xml
logs/test/2026-10-30-v2-live` on a desktop with X11 access.

The six-node preset and port metadata passed `python3 tests/node_contributions.py` (four tests) on 2026-10-30. `python3 tools/build-backend-bundle.py --build-dir build --output logs/test/20261030-general-interfaces/bundle-r3` staged a release candidate, and `ctest --test-dir build --output-on-failure` passed all ten simulator tests. Complete local output is in `logs/test/20261030-general-interfaces/`.

An isolated IsOS home then linked the corrected `bundle-r3`, previewed `sim-hardware` with a scene and socket, and validated the resulting graph through EOS `aether-profile`. The preview added six nodes, kept package pins only on the four MuJoCo types, and reported three IsOS-owned processes. Reproduction details are in `logs/test/20261030-general-interfaces/graph-preview.log`.
