# Scene runtime and integration

[Package overview](README.md) · [Benchmark tasks](benchmarks.md)

One simulator process loads one scene profile at startup. Its engine owns MuJoCo model and data, deterministic seeded reset, fixed-step physics, robot command targets, telemetry, camera rendering, and scene-specific scores. The EOS-facing service and the benchmark service share that engine, but publish different information. The simulator socket returns device health, command outcomes, telemetry, and camera JPEGs. The benchmark socket lets a trusted evaluator reset or step the world and inspect ground truth and scores.

The existing path selector is the interface: direct launch uses `--scene`, and EOS uses `[simulator.mujoco].scene`. The selected MJCF declares exactly one supported custom numeric marker, `eos_benchmark_pick_place_v1` or `eos_benchmark_navigation_v1`; an unknown or multiple benchmark markers are rejected. The engine then checks required named elements, including `navigation_goal` for the navigation profile. A different XML file is not automatically an admitted benchmark; each profile needs explicit reset and scoring logic, documented capabilities, and tests. Changing a scene requires a process restart.

EOS owns `eos.simulator.v1.SimulatorService` and its HAL descriptor. This repository pins a copy of the EOS protobuf; EOS's `mujoco` hardware profile advertises a holonomic base, UR5e arm, Robotiq gripper, and camera. EOS maps normal gateway discovery, resources, and primitives onto the private simulator socket. `ExecuteResponse.accepted` indicates physical completion for motion, while stop and halt interrupt active motion. This package does not link into EOS core.

EGIA attaches to an already-running EOS gateway, discovers its healthy devices and versioned primitives, and executes through EOS. It does not receive benchmark seed, goal truth, privileged state, or score. EGIA fleet aliases identify EOS endpoints; the simulation scene remains EOS's configuration choice. Agent evaluation compares an EGIA or other agent's EOS-visible behavior with a separate evaluator's private result.

The Island package client installs the published simulator archive after checking its size, digest, and host requirements. Activation generates an isolated EOS profile with absolute executable and scene paths. This keeps the existing scene path selector, simulator RPC, EGIA southbound contract, and private benchmark boundary intact. A source build may still use absolute paths in the operator's own EOS profile.

## Timing and failures

MuJoCo advances in fixed 2 ms physics steps. A reset sets a deterministic seeded initial state and pauses real-time stepping. The evaluator can advance a bounded number of steps, inspect state, score, and resume live stepping. Repeatability requires the same scene version, seed, command sequence, and stepping schedule; asynchronous real-time observation is not a deterministic replay contract.

Startup fails for a missing or invalid scene, missing required scene elements, or an unusable socket. Unavailable or unsupported devices and commands fail through the EOS-facing service. The benchmark service reports reset or step errors in `StateResponse.ok` and `error`. Ground-truth fields that are irrelevant to a scene should not be used as an agent input or inferred as a goal.

**Related:** [Usage](usage.md) · [Simulator RPC](interfaces/simulator.md) · [Benchmark RPC](interfaces/benchmark.md)
