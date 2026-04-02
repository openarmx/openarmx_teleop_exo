# openarmx_teleop_exo 使用说明

<h1>
  <span style="color:#0B6E4F;">openarmx_teleop_exo</span>
  <span style="font-size:18px;">外骨骼遥操作 ROS2 包说明</span>
</h1>

[English](README.md) | 简体中文

<p>
  <span style="font-size:16px;">
    本包用于将外骨骼设备数据通过 WebSocket 接入 ROS2，完成
    <b>数据解析</b> → <b>重定向映射</b> → <b>安全桥接</b> → <b>机器人控制</b>。
  </span>
</p>

> ✅ 适用目录：`src/openarmx_teleop_exo`
> 🌐 English version: `src/openarmx_teleop_exo/README_EN.md`

## 🔭 包内核心能力

1. `websocket_teleoperator`：接收 WebSocket 数据并发布 `/exo/*` 话题。
2. `exo_retargeting_node`：把外骨骼 16 维数据映射成机器人左右臂关节命令。
3. `exoskeleton_bridge_node`：做安全检查与插值过渡后转发到控制器命令话题。
4. `exoskeleton_display.launch.py`：可视化外骨骼模型（RViz）。

## 🧭 系统数据流

```text
外骨骼设备
  -> WebSocket
websocket_teleoperator
  -> /exo/joint_command
exo_retargeting_node
  -> /left_arm/joint_command + /right_arm/joint_command
exoskeleton_bridge_node
  -> /left_forward_position_controller/commands
  -> /right_forward_position_controller/commands
机器人控制器
```

## 📦 目录结构（重点）

```text
openarmx_teleop_exo/
├── launch/
│   ├── websocket_teleoperator.launch.py
│   ├── exo_retargeting.launch.py
│   ├── exoskeleton_bridge.launch.py
│   └── exoskeleton_display.launch.py
├── config/
│   ├── retargeting_OpenArm.yaml
│   ├── retargeting_OpenArmX.yaml
│   ├── qnbot_teleoperator_config.yaml
│   └── exoskeleton_display.rviz
├── openarmx_teleop_exo/
│   ├── websocket_teleoperator.py
│   ├── exo_retargeting_node.py
│   ├── exoskeleton_bridge_node.py
│   └── protocol/exo_protocol_parser.py
├── README.md
└── README_CN.md
```

## 🚀 快速启动

### 第 1 步：启动 WebSocket 遥操作服务（接收外骨骼数据）

```bash
cd openarmx_ws
source install/local_setup.bash
ros2 launch openarmx_teleop_exo websocket_teleoperator.launch.py
```

然后在上位机执行以下操作：

1. 打开上位机 `Qnbot HMI Control-1.2.2.AppImage`。
2. 点击左侧“外骨骼设备”。
3. 点击“添加外骨骼设备”，创建连接。
4. 在设备管理中点击小齿轮，将 `ws://localhost:19091` 添加到转发目标。
5. 再次将 `ws://localhost:19091` 粘贴到输入框中，点击“应用配置”。

<p>
  <span style="color:#B00020; font-size:18px;"><b>⚠️ 关键检查：</b></span>
  <span style="color:#B00020;"><b>如果没看到外骨骼数据转发，请优先检查上位机里的 WebSocket 目标地址是否正确。</b></span>
  <span style="color:#B00020;"><b>注意：两个手柄上的开关必须全部推上去才能进行通信！单人操作时可通过开关控制何时开始操作！</b></span>
</p>

### 第 2 步：启动外骨骼重定向节点（映射到 OpenArmX）

```bash
ros2 launch openarmx_teleop_exo exo_retargeting.launch.py robot_type:=OpenArmX
```

### 第 3 步：启动 OpenArmX（仿真或真机）

仿真模式：

```bash
ros2 launch openarmx_bringup openarmx.bimanual.launch.py \
  robot_controller:=forward_position_controller \
  use_fake_hardware:=true
```

真机模式（基础）：

```bash
ros2 launch openarmx_bringup openarmx.bimanual.launch.py \
  robot_controller:=forward_position_controller \
  use_fake_hardware:=false
```

真机模式（带 CAN 接口与控制模式）：

```bash
ros2 launch openarmx_bringup openarmx.bimanual.launch.py \
  right_can_interface:=can2 \
  left_can_interface:=can3 \
  control_mode:=mit \
  robot_controller:=forward_position_controller
```

### 第 4 步：启动 ROS2 桥接控制

```bash
ros2 launch openarmx_teleop_exo exoskeleton_bridge.launch.py \
  gripper_scaling_factor:=0.05
```

<p>
  <span style="color:#B00020; font-size:18px;"><b>⚠️ 必做：</b></span>
  <span style="color:#B00020;"><b>在第 4 步前，请先让外骨骼姿态接近机器人当前姿态</b>（每关节建议差值小于 50°），避免触发安全拒动或大幅跳变。</span>
</p>

## 🧠 节点说明

### 1. `websocket_teleoperator`

- 功能：监听 WebSocket（默认 `0.0.0.0:19091`），解析外骨骼数据并发布：
- `/exo/joint_command`（`sensor_msgs/JointState`，16 维：左7 + 右7 + 左扳机 + 右扳机）
- `/exo/gamepad_keys`（`sensor_msgs/Joy`，摇杆轴与按钮状态）
- 安全门控：
- 只有左右手柄 `Switch` 都为 `0` （推上去）才会转发控制数据。
- 频率限制：内部限制约 `100Hz`，超频消息会丢弃。
- 回零：目前代码中回零流程处于禁用状态（TODO）。

### 2. `exo_retargeting_node`

- 功能：订阅 `/exo/joint_command`，按 YAML 配置映射到目标机器人话题。
- 支持 `robot_type` 自动加载配置：
- `OpenArm` -> `config/retargeting_OpenArm.yaml`
- `OpenArmX` -> `config/retargeting_OpenArmX.yaml`
- 映射内容：
- 外骨骼索引映射（左/右臂 + trigger）
- 缩放系数 `scaling_factors`
- 偏置角 `offset_angles`
- 左右臂独立关节限位 `joint_limits`
- 输出：
- `/left_arm/joint_command`
- `/right_arm/joint_command`

### 3. `exoskeleton_bridge_node`

- 功能：对 retargeting 输出做最终安全处理后发给控制器。
- 关键安全机制：
- 启动后等待 `/joint_states`，获得机器人当前位置。
- 首次命令到来时做关节差值检查（默认阈值 `0.873 rad` ≈ `50°`）。
- 若超阈值则直接报错并停止；若通过则执行插值过渡（默认 3s, 50Hz）。
- 插值完成后进入实时跟踪转发模式。

<p>
  <span style="color:#0A58CA; font-size:17px;"><b>🛡️ 推荐配置：</b></span>
  <span style="color:#0A58CA;"><b>enable_safety_check:=true</b>，并适当增大 <b>interpolation_duration</b>（例如 5.0）。</span>
</p>

## 📡 主要话题接口

| 方向 | 话题 | 类型 | 说明 |
|---|---|---|---|
| 发布 | `/exo/joint_command` | `sensor_msgs/JointState` | 外骨骼融合关节命令（16维） |
| 发布 | `/exo/gamepad_keys` | `sensor_msgs/Joy` | 摇杆与按钮状态 |
| 订阅 | `/exo/joint_command` | `sensor_msgs/JointState` | retargeting 输入 |
| 发布 | `/left_arm/joint_command` | `sensor_msgs/JointState` | 左臂映射命令（含 gripper） |
| 发布 | `/right_arm/joint_command` | `sensor_msgs/JointState` | 右臂映射命令（含 gripper） |
| 订阅 | `/joint_states` | `sensor_msgs/JointState` | 机器人当前关节状态（桥接安全检查） |
| 发布 | `/left_forward_position_controller/commands` | `std_msgs/Float64MultiArray` | 左臂控制器命令（7+夹爪） |
| 发布 | `/right_forward_position_controller/commands` | `std_msgs/Float64MultiArray` | 右臂控制器命令（7+夹爪） |

## ⚙️ 常用参数

### `websocket_teleoperator.launch.py`

| 参数 | 默认值 | 说明 |
|---|---|---|
| `enable_left_arm` | `true` | 是否接收左臂数据 |
| `enable_right_arm` | `true` | 是否接收右臂数据 |
| `enable_left_joystick` | `true` | 是否接收左手柄数据 |
| `enable_right_joystick` | `true` | 是否接收右手柄数据 |
| `enable_vehicle_control` | `true` | 是否启用小车/滑台控制 |
| `websocket_host` | `0.0.0.0` | WebSocket 监听地址 |
| `websocket_port` | `19091` | WebSocket 端口 |

### `exo_retargeting.launch.py`

| 参数 | 默认值 | 说明 |
|---|---|---|
| `robot_type` | `OpenArm` | 机器人类型，决定加载哪个 retargeting 配置 |
| `enable_left_arm_retargeting` | `true` | 启用左臂映射 |
| `enable_right_arm_retargeting` | `true` | 启用右臂映射 |

### `exoskeleton_bridge.launch.py`

| 参数 | 默认值 | 说明 |
|---|---|---|
| `max_joint_diff_rad` | `0.873` | 首次接入最大允许关节差（rad） |
| `interpolation_duration` | `3.0` | 插值时长（秒） |
| `interpolation_rate_hz` | `50.0` | 插值频率（Hz） |
| `enable_safety_check` | `true` | 是否启用安全检查 |
| `gripper_scaling_factor` | `0.02` | 夹爪缩放系数 |
| `gripper_threshold` | `0.005` | 夹爪变化阈值 |

## 🔍 可视化与联调

### 外骨骼可视化

```bash
ros2 launch openarmx_teleop_exo exoskeleton_display.launch.py source:=exo_command
```

### 常用排查命令

```bash
ros2 topic list
ros2 topic hz /exo/joint_command
ros2 topic echo /exo/gamepad_keys
ros2 topic echo /joint_states
```

## ❗ 重要注意事项

1. `<span style="color:#B00020;"><b>硬件联调时务必先启用安全检查，再做桥接。</b></span>`
2. `<span style="color:#B00020;"><b>若出现“位置差异过大”，先调姿态，不建议直接放宽阈值。</b></span>`
3. `websocket_teleoperator` 当前为“收到即转发”模式，限位与动力学安全主要依赖下游节点和控制器。
4. `publish_rate_hz`、`timeout_ms` 在 launch 中有传参，但当前主节点内部未实际使用对应逻辑（保留参数）。
5. `setup.py` 中 `exo_protocol_parser` 入口路径与当前文件组织存在不一致，若单独运行该入口建议先核对。

## 🛠️ 编译

```bash
cd /home/openarmx/openarmx_ws
colcon build --packages-select openarmx_teleop_exo
source install/setup.bash
```

---
