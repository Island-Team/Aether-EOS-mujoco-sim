# IsOS 管理的 MuJoCo v2 后端

[English](../../docs/mujoco/backend-v2.md)

先构建模拟器，再生成本地 `island/mujoco-sim@2.0.0` 包：

```sh
. ./.env
cmake -S . -B build -DMUJOCO_ROOT="$MUJOCO_ROOT"
cmake --build build -j
ctest --test-dir build --output-on-failure
python3 tests/node_contributions.py
python3 tools/build-backend-bundle.py --output /absolute/path/to/mujoco-v2-bundle
isos pkg link island/mujoco-sim 2.0.0 /absolute/path/to/mujoco-v2-bundle --manifest /absolute/path/to/mujoco-v2-bundle/release.json
```

包中包含 `bin/eos-mujoco-sim`、两个场景及其资源、`backend-v2.json` 和本地 schema v4 `release.json`。构建工具还会在包目录旁生成带 SHA-256 校验值的发布归档。后端描述文件声明 `mujoco-v2` 协议、`cam-0`、`base-0`、`arm-0` 设备 ID，以及外部 MuJoCo 3.16.0 库依赖。IsOS 在运行前验证可执行文件、场景、资源和库；安装包本身不会启用部署图。

发布清单中的 `node_contributions` 声明 `sim-hardware` 节点集：`process/mujoco` 下的 EOS 模拟器进程，以及 `hardware/mujoco` 下的相机、底盘和机械臂节点。安装或链接后，IsOS 将节点集加入目录；预览时绑定场景与仅所有者可访问的套接字、解析符号节点引用，并验证生成的共享图。已应用的图固定使用 `island/mujoco-sim@2.0.0`。发布声明只用于生成节点草稿，不是第二份运行图。

后端节点的 `settings.env` 可设置 `MUJOCO_GUI=1` 或 `MUJOCO_GUI=true`，在支持 X11 的主机上打开 `IsOS MuJoCo — live simulation` 窗口。窗口渲染来自同一个 `SimEngine` 的相机画面；默认不显示 GUI。若请求 GUI 但显示服务不可用，模拟器启动失败。`tools/scene-view.sh` 仍用于独立的静态场景预览。

v2 Unix 套接字帧以八字节小端长度头开头，后接 JSON 元数据和可选 JPEG 负载。元数据上限为 64 KiB，负载上限为 8 MiB。请求包含 `version: "2.0.0"`、字符串 `id`、`node` 和 `op`；响应回显 ID 与版本，并返回 `ok` 或 `error.message`。

| 操作 | 请求字段 | 响应字段 |
| --- | --- | --- |
| `health` | 通用字段 | `accepted: bool` |
| `camera_capture` | 通用字段 | `format: "jpeg"`、`rgb_length: u64` 字节、`depth_available: false`、`width_px: u32`、`height_px: u32` 和 JPEG 负载 |
| `base_observe` | 通用字段 | `position_m: [f64; 2]`、`linear_velocity_m_s: [f64; 2]`、`yaw_rad: f64`、`angular_velocity_rad_s: f64` |
| `base_move` | `linear_x_m_s`、`linear_y_m_s`、`angular_z_rad_s: f64`，`valid_for_ms`，`command_id: string` | `accepted: bool`；租期结束后底盘停止 |
| `manipulator_observe` | 通用字段 | 六个关节位置、速度，以及末端位置和四元数 |
| `manipulator_move` | 六个关节目标和 `command_id: string` | `accepted: bool` |
| `stop` | `command_id: string` | `accepted: bool`；停止底盘和机械臂 |

`timestamp_ns` 是以纳秒为单位的模拟时间，`sequence` 是引擎步数。浮点数必须有限，运动边界由引擎强制执行。套接字权限为 `0600`，正常停止时会被移除。IsOS 验证包并把可执行文件及场景传给 EOS；EOS 将模拟器作为直接子进程启动，使用硬件适配器连接套接字，并在终止模拟器前停止已准入的执行器。

## 验证

2026-10-30 的现有基线在 Ubuntu 和 MuJoCo 3.16.0 上通过了十个 CTest 用例。`tests/v2.py` 覆盖 JPEG 捕获、底盘运动、六关节命令、安全停止和套接字清理。GUI 检查还验证了可见窗口、运动后像素变化，以及显示服务不可用时的启动失败。完整日志保存在本地 `logs/test/2026-10-30-v2-live/`。新增节点声明可用 `python3 tests/node_contributions.py` 检查，并需通过 IsOS 与 EOS 的完整图准入及运行集成测试。
