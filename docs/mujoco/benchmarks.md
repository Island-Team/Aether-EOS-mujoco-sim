# Robotic agent benchmarks

[Package overview](README.md) · [Usage](usage.md)

The catalog tests agents through the same EOS robot interface they would use outside this package. Each scene defines its own reset variation and success rule. Evaluators use the private benchmark service to establish the seed and read ground truth; an agent, including EGIA, sees only EOS discovery, observations, and primitives. The tasks are original package benchmarks inspired by academic robotics evaluation, including [LIBERO](https://arxiv.org/abs/2306.03310) and [ManiSkill3](https://arxiv.org/abs/2410.00425). They are not official ports of either benchmark, and their scores are not directly comparable to those suites.

## Scene catalog

| Scene | Task and variation | Success reported by `Score` |
| --- | --- | --- |
| [`assets/scene.xml`](../../assets/scene.xml) | Navigate the mobile manipulator to the table, lift the cube with sustained bilateral gripper contact, then release it in the marked tray. Reset varies cube and two obstacle positions from the seed. | `navigation`, `grasp`, and `placement` are separate Boolean goals. `collisions` records robot contact events with the table or obstacles; `elapsed_sim_s` is simulated time. |
| [`assets/scenes/navigation/scene.xml`](../../assets/scenes/navigation/scene.xml) | Drive the base through a cluttered scene to the `navigation_goal` at world XY `(0.45, -1.30)`. Reset varies the Y positions of two obstacles from the seed. | `navigation` is true while base XY is within 0.18 m of the goal and absolute yaw is below 0.15 rad. `grasp` and `placement` are inapplicable and remain false; evaluate collision count and simulated time separately. |

The pick-and-place oracle in `tests/engine.cpp` demonstrates one deterministic seed-42 completion using the same base, arm, and gripper commands exposed through EOS. It is a regression test for the engine and score, not a policy for other seeds or an agent benchmark result. The navigation engine test uses a two-leg route as a deterministic score check. Neither oracle should be presented to an evaluated agent as privileged task state.

## Episode method

Pin the package revision, scene path and asset hashes, EOS and agent revisions, task budget, seed list, and scoring rules before a run. Use the same seed list and duration for each compared agent. Start the scene and agent, then run `build/benchmark-eval --benchmark-socket /absolute/benchmark.sock --task navigation --seed 42 --duration-s 30` for one timed episode. The evaluator resets, resumes real-time simulation, waits the requested wall-clock duration, pauses, reads `Score`, and emits a JSON object. The agent acts independently through EOS. For deterministic command replay, keep the engine paused and use `Step(steps)` at explicit points through the private RPC instead of the timed evaluator.

Report each scene and seed separately, then aggregate success rate across the fixed list. `benchmark-eval` sets `success` to the conjunction of navigation, grasp, and placement for pick and place, or to navigation alone for the navigation task. Also report collisions and elapsed simulated time as separate measures; a successful goal may still have collision events. Report failed resets, unavailable EOS devices, agent timeouts, and incomplete episodes rather than silently dropping them. Do not use private state or scores in the agent's prompts, tools, or observations.

EGIA may be evaluated as an EOS client without changing its southbound protocol. Configure its connection profile to the running EOS gateway, check that expected device capabilities are discovered and healthy, and use its normal mission and primitive path. The evaluator's episode log should retain the EGIA/EOS versions, robot alias and runtime identity, seed, scene revision, and final score so a result can be reproduced. EOS discovery does not currently supply station or reachability bindings; task instructions must not assume those are discoverable.

## Adding a scene

Keep each new MJCF scene and its local assets together under `assets/scenes/<short-name>/`; retain the existing `assets/scene.xml` path for the first profile. Add a focused scene page or catalog entry with the research citation, source revision, license, imported-model provenance, robot capabilities, seed distribution, task instruction, private success rule, and known score limitations. Keep source asset licenses beside the assets and update [model provenance](../../assets/MODELS.md) when importing models.

Implement explicit engine admission for the scene's required names and geometry, deterministic reset, ground-truth state, and score. Avoid interpreting arbitrary loadable XML as a supported benchmark. Select the scene with `--scene` for direct runs or in the applied IsOS/EOS v2 graph for managed runs. Add a model-loading check, seeded replay check, positive and negative success checks, and a service smoke check before listing the scene here.

Version a scene by its package revision plus its XML and asset contents. If reset bounds, geometry, success thresholds, or scoring logic change, treat resulting scores as a new benchmark version and do not merge them into an earlier aggregate without identifying the change. Keep the exact seeds and evaluation budgets with published results.

**Related:** [Design](design.md) · [Benchmark interface](interfaces/benchmark.md) · [Usage](usage.md)
