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
    self.assertEqual(refs, {"simulator", "front", "drive", "arm", "base-velocity",
                            "arm-movej", "camera-gate", "vision"})
    contributed_types = {node_type["id"] for node_type in contract["node_types"]}
    self.assertEqual(contributed_types, {"eos.process.mujoco@v1.0"})
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
    gate = nodes["camera-gate"]
    vision = nodes["vision"]
    self.assertEqual(gate["profile"]["inputs"]["frame"],
                     {"node": "@front", "output": "frame"})
    self.assertEqual(vision["profile"]["inputs"]["preview"],
                     {"node": "@camera-gate", "output": "preview"})
    self.assertEqual((gate["core"], gate["layer"], gate["group"]),
                     ("eos", "interface", "gate"))
    self.assertEqual((vision["core"], vision["layer"], vision["group"]),
                     ("isos", "ui", "panel"))
    self.assertEqual(vision["profile"]["node_type"], "isos.ui.vision@v1.0")

  def test_each_device_uses_one_package_pinned_adapter_and_typed_binding(self) -> None:
    contract = contributions()
    nodes = {node["ref"]: node for node in contract["node_sets"][0]["nodes"]}
    family = contract["adapter_families"][0]
    self.assertEqual(set(family["device_kinds"]), {"camera", "base", "manipulator"})
    self.assertEqual(set(family["supported_primitives"]),
                     {"base.velocity@1.0.0", "arm.movej@1.0.0"})
    for ref, kind in (("front", "camera"), ("drive", "base"), ("arm", "manipulator")):
      node = nodes[ref]
      self.assertEqual((node["core"], node["layer"], node["group"]),
                       ("eos", "hardware", kind))
      profile = node["profile"]
      self.assertEqual(profile["node_type"], f"eos.hardware.{kind}@v1.0")
      self.assertNotIn("package", profile)
      self.assertEqual(profile["adapter"]["type"], family["id"])
      self.assertEqual(profile["adapter"]["package"],
                       {"id": "island/mujoco-sim", "version": "2.0.0"})
    for device, binding, primitive in (("drive", "base-velocity", "base.velocity"),
                                       ("arm", "arm-movej", "arm.movej")):
      self.assertEqual(nodes[device]["profile"]["inputs"]["command"],
                       [{"node": f"@{binding}", "output": "command"}])
      self.assertEqual(nodes[binding]["profile"]["settings"]["primitive_name"], primitive)
      self.assertEqual(nodes[binding]["profile"]["settings"]["primitive_version"], "1.0.0")

  def test_ports_describe_frequency_transport_and_data_class(self) -> None:
    contract = contributions()
    for node_type in contract["node_types"]:
      for port in node_type["inputs"] + node_type["outputs"]:
        self.assertTrue(port["description"])
        self.assertIn(port["data_class"],
                      {"image", "observation", "command", "event", "state", "opaque"})


if __name__ == "__main__":
  unittest.main()
