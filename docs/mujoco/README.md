# MuJoCo benchmark package

The simulator loads one scene at process startup, executes robot commands and renders observations for EOS, and reports evaluation truth through a separate private service. EOS remains independent of MuJoCo. EGIA and other agents interact through EOS discovery, resources, and primitives; the evaluator controls episodes and reads scores.

The current scene catalog contains a pick-and-place task and a navigation task. Both use the same robot-facing device interface; their resets and success rules belong to the selected scene profile. See the [documentation map](doc_index.md) for focused usage, design, benchmark, and interface pages.
