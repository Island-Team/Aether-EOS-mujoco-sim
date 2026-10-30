"""Declarative EOS node types and graph set shipped with the MuJoCo package."""


BACKEND = "eos.process.mujoco@v1.0"
CAMERA = "eos.hardware.mujoco_camera@v1.0"
BASE = "eos.hardware.mujoco_base@v1.0"
MANIPULATOR = "eos.hardware.mujoco_manipulator@v1.0"
CAMERA_GATE = "eos.interface.camera_gate@v1.0"
VISION = "isosui.system.vision@v1.0"
DISPATCHER = "cores/eos/layers/dispatcher/groups/control/nodes/command"


def port(name: str, data_type: str, required: bool = False) -> dict:
  return {"name": name, "data_type": data_type, "required": required}


def node_type(id: str, layer: str, kind: str, lifecycle: str,
              capabilities: list[str], inputs: list[dict], outputs: list[dict],
              settings: list[dict] | None = None,
              safety_adapter_type: str | None = None) -> dict:
  return {
    "id": id,
    "core": "eos",
    "layer": layer,
    "group": "mujoco",
    "kind": kind,
    "lifecycle": lifecycle,
    "capabilities": capabilities,
    "settings": settings or [],
    "inputs": inputs,
    "outputs": outputs,
    "safety_adapter_type": safety_adapter_type,
  }


def setting(name: str, data_type: str, required: bool = False) -> dict:
  return {"name": name, "data_type": data_type, "required": required}


def hardware_profile(id: str, type_id: str, label: str, description: str,
                     frame_id: str, capabilities: list[str], device_id: str,
                     max_rate_hz: float, max_payload_bytes: int) -> dict:
  return {
    "id": id,
    "node_type": type_id,
    "label": label,
    "description": description,
    "frame_id": frame_id,
    "capabilities": capabilities,
    "references": ["@simulator"],
    "adapter": {
      "type": "mujoco-v2",
      "settings": {
        "backend": "@simulator",
        "socket_path": "${socket}",
        "simulator_node": device_id,
        "device_id": device_id,
      },
    },
    "health_timing": {"poll_interval_ms": 100, "stale_after_ms": 500},
    "observation": {"max_rate_hz": max_rate_hz, "max_payload_bytes": max_payload_bytes},
  }


def contributions() -> dict:
  camera = hardware_profile(
    "front", CAMERA, "Front RGB camera", "MuJoCo JPEG camera decoded to RGB8",
    "front_camera_optical", ["rgb8"], "cam-0", 30.0, 8388608,
  )
  base = hardware_profile(
    "drive", BASE, "Planar base", "MuJoCo base velocity controller",
    "base_link", ["body_velocity"], "base-0", 50.0, 4096,
  )
  base["movement"] = {
    "modes": ["body_velocity"],
    "limits": {"max_linear_m_s": 1.0, "max_angular_rad_s": 1.5,
               "max_velocity_lease_ms": 500},
  }
  base["inputs"] = {"command": {"node": "${dispatcher}", "output": "base_command"}}
  arm = hardware_profile(
    "arm", MANIPULATOR, "Six axis arm", "MuJoCo six-joint position controller",
    "arm_base", ["joint_positions"], "arm-0", 50.0, 4096,
  )
  arm["joint_names"] = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
  arm["movement"] = {
    "modes": ["joint_positions"],
    "limits": {"max_joint_position_rad": 3.14, "max_joint_speed_rad_s": 1.0},
  }
  arm["inputs"] = {
    "command": {"node": "${dispatcher}", "output": "manipulator_command"},
  }
  return {
    "node_types": [
      node_type(
        BACKEND, "process", "software", "process", ["process"], [],
        [port("status", "status"), port("health", "health")],
        [setting("scene", "string", True), setting("socket", "string", True),
         setting("env", "string_table"), setting("start_timeout_ms", "positive_integer")],
      ),
      node_type(
        CAMERA, "hardware", "camera", "adapter", ["rgb8", "aligned_depth_u16"], [],
        [port("frame", "camera_frame"), port("health", "health"),
         port("status", "status")],
      ),
      node_type(
        BASE, "hardware", "base", "adapter", ["body_velocity", "relative_pose"],
        [port("command", "base_movement", True)],
        [port("observation", "base_observation"), port("outcome", "command_outcome"),
         port("health", "health"), port("status", "status")],
        safety_adapter_type="mujoco-v2-base",
      ),
      node_type(
        MANIPULATOR, "hardware", "manipulator", "adapter",
        ["joint_positions", "end_effector_pose"],
        [port("command", "manipulator_movement", True)],
        [port("observation", "manipulator_observation"),
         port("outcome", "command_outcome"), port("health", "health"),
         port("status", "status")],
        safety_adapter_type="mujoco-v2-manipulator",
      ),
    ],
    "safety_adapters": [
      {"id": "mujoco-v2-base", "kind": "base",
       "movement_modes": ["body_velocity", "relative_pose"], "supports_stop": True},
      {"id": "mujoco-v2-manipulator", "kind": "manipulator",
       "movement_modes": ["joint_positions", "end_effector_pose"], "supports_stop": True},
    ],
    "node_sets": [{
      "id": "sim-hardware",
      "parameters": {
        "scene": {"type": "string", "default": "pick-place"},
        "socket": {"type": "string"},
        "dispatcher": {"type": "string", "default": DISPATCHER},
      },
      "nodes": [
        {"ref": "simulator", "core": "eos", "layer": "process", "group": "mujoco",
         "profile": {
           "id": "simulator", "node_type": BACKEND, "label": "MuJoCo simulator",
           "description": "EOS-owned simulator child from the verified package",
           "capabilities": ["process"],
           "settings": {"scene": "${scene}", "socket": "${socket}"},
         }},
        {"ref": "front", "core": "eos", "layer": "hardware", "group": "mujoco",
         "profile": camera},
        {"ref": "drive", "core": "eos", "layer": "hardware", "group": "mujoco",
         "profile": base},
        {"ref": "arm", "core": "eos", "layer": "hardware", "group": "mujoco",
         "profile": arm},
        {"ref": "camera_gate", "core": "eos", "layer": "interface", "group": "gate",
         "profile": {
           "id": "front-preview", "node_type": CAMERA_GATE,
           "label": "Front camera preview gate",
           "description": "Publishes a bounded preview of the MuJoCo front camera",
           "inputs": {"frame": {"node": "@front", "output": "frame"}},
         }},
        {"ref": "vision", "core": "isosui", "layer": "system", "group": "ui",
         "profile": {
           "id": "vision", "node_type": VISION,
           "label": "Vision monitor",
           "description": "Displays a selected active camera gate in IsosUI",
           "inputs": {"preview": {"node": "@camera_gate", "output": "preview"}},
         }},
      ],
    }],
  }
