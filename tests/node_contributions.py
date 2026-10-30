#!/usr/bin/env python3
"""Check the packaged node set before IsOS performs full graph admission."""

from pathlib import Path
import re
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from node_contributions import contributions  # noqa: E402


def strings(value: object) -> list[str]:
  if isinstance(value, str):
    return [value]
  if isinstance(value, dict):
    return [item for child in value.values() for item in strings(child)]
  if isinstance(value, list):
    return [item for child in value for item in strings(child)]
  return []


class NodeContributionTests(unittest.TestCase):
  def test_node_set_has_resolvable_symbols_and_parameters(self) -> None:
    contract = contributions()
    node_set = contract["node_sets"][0]
    refs = {node["ref"] for node in node_set["nodes"]}
    self.assertEqual(refs, {"simulator", "front", "drive", "arm", "camera_gate", "vision"})
    contributed_types = {node_type["id"] for node_type in contract["node_types"]}
    self.assertEqual(len(contributed_types), 4)
    declared = set(node_set["parameters"])
    for node in node_set["nodes"]:
      if node["profile"]["node_type"] in contributed_types:
        self.assertEqual(node["core"], "eos")
        self.assertEqual(node["group"], "mujoco")
      for value in strings(node["profile"]):
        if value.startswith("@"):
          self.assertIn(value[1:], refs)
        for parameter in re.findall(r"\$\{([^}]+)\}", value):
          self.assertIn(parameter, declared)

  def test_vision_uses_a_typed_gate_with_an_editable_default_source(self) -> None:
    nodes = {node["ref"]: node for node in contributions()["node_sets"][0]["nodes"]}
    gate = nodes["camera_gate"]
    vision = nodes["vision"]
    self.assertEqual(gate["profile"]["inputs"]["frame"],
                     {"node": "@front", "output": "frame"})
    self.assertEqual(vision["profile"]["inputs"]["preview"],
                     {"node": "@camera_gate", "output": "preview"})
    self.assertEqual((gate["core"], gate["layer"], gate["group"]),
                     ("eos", "interface", "gate"))
    self.assertEqual((vision["core"], vision["layer"], vision["group"]),
                     ("isosui", "system", "ui"))

  def test_every_actuator_type_has_a_matching_stop_contract(self) -> None:
    contract = contributions()
    adapters = {item["id"]: item for item in contract["safety_adapters"]}
    for node_type in contract["node_types"]:
      if node_type["kind"] not in {"base", "manipulator"}:
        continue
      safety = adapters[node_type["safety_adapter_type"]]
      self.assertEqual(safety["kind"], node_type["kind"])
      self.assertTrue(safety["supports_stop"])
      self.assertGreaterEqual(
        set(safety["movement_modes"]), set(node_type["capabilities"]),
      )


if __name__ == "__main__":
  unittest.main()
