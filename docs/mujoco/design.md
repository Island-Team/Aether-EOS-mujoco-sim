# Scene runtime and integration

[中文](../../docs_cn/mujoco/design_cn.md)

[Package overview](README.md) · [Benchmark tasks](benchmarks.md)

One simulator process loads one scene profile at startup. Its engine owns MuJoCo model and data, deterministic seeded reset, fixed-step physics, robot command targets, telemetry, camera rendering, and scene-specific scores. The EOS-facing service and the benchmark service share that engine, but publish different information. The simulator socket returns device health, command outcomes, telemetry, and camera JPEGs. The benchmark socket lets a trusted evaluator reset or step the world and inspect ground truth and scores.

Direct launch uses `--scene`; an IsOS/EOS v2 deployment selects the scene in its applied shared graph and EOS passes that path to its simulator child. The selected MJCF declares exactly one supported custom numeric marker, `eos_benchmark_pick_place_v1` or `eos_benchmark_navigation_v1`; an unknown or multiple benchmark markers are rejected. The engine then checks required named elements, including `navigation_goal` for the navigation profile. A different XML file is not automatically an admitted benchmark; each profile needs explicit reset and scoring logic, documented capabilities, and tests. Changing a scene requires a process restart.

The simulator still exposes the legacy `eos.simulator.v1.SimulatorService` gRPC socket for older direct integrations. The current IsOS/EOS v2 runtime connects generic camera, base, and manipulator adapters to the separate owner-only framed socket selected by `--v2-socket`; its contract is in [backend-v2.md](backend-v2.md). EOS owns the simulator child and exposes graph-declared observation and primitive ports to agents. The benchmark socket remains separate from both robot-facing interfaces. This package does not link into EOS core.

EGIA attaches to an already-running EOS gateway, discovers its healthy devices and versioned primitives, and executes through EOS. It does not receive benchmark seed, goal truth, privileged state, or score. EGIA fleet aliases identify EOS endpoints; the simulation scene remains EOS's configuration choice. Agent evaluation compares an EGIA or other agent's EOS-visible behavior with a separate evaluator's private result.

The published v1.0.1 package and its generated EOS profile belong to the legacy route. For v2, IsOS links or installs an exact `island/mujoco-sim@0.1.1` bundle, verifies its executable, scene, assets, and external MuJoCo library, and applies a shared graph revision through the `sim-hardware` node set. EOS reads that graph and starts the verified simulator as its direct child. A source build may still run directly with absolute scene and socket paths.

## Timing and failures

MuJoCo advances in fixed 2 ms physics steps. A reset sets a deterministic seeded initial state and pauses real-time stepping. The evaluator can advance a bounded number of steps, inspect state, score, and resume live stepping. Repeatability requires the same scene version, seed, command sequence, and stepping schedule; asynchronous real-time observation is not a deterministic replay contract.

Startup fails for a missing or invalid scene, missing required scene elements, or an unusable socket. Unavailable or unsupported devices and commands fail through the EOS-facing service. The benchmark service reports reset or step errors in `StateResponse.ok` and `error`. Ground-truth fields that are irrelevant to a scene should not be used as an agent input or inferred as a goal.

**Related:** [Usage](usage.md) · [Simulator RPC](interfaces/simulator.md) · [Benchmark RPC](interfaces/benchmark.md)
