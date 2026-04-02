# openarmx_teleop_exo Guide

<h1>
  <span style="color:#0B6E4F;">openarmx_teleop_exo</span>
  <span style="font-size:18px;">Exoskeleton Teleoperation ROS2 Package</span>
</h1>

English | [简体中文](README_CN.md)

<p>
  <span style="font-size:16px;">
    This package connects exoskeleton device data to ROS2 via WebSocket and completes:
    <b>data parsing</b> → <b>retargeting</b> → <b>safety bridge</b> → <b>robot control</b>.
  </span>
</p>

> ✅ Directory: `src/openarmx_teleop_exo`

## 🔭 Core Capabilities

1. `websocket_teleoperator`: receives WebSocket data and publishes `/exo/*` topics.
2. `exo_retargeting_node`: maps 16D exoskeleton data to left/right robot joint commands.
3. `exoskeleton_bridge_node`: performs safety checks and interpolation, then forwards to controllers.
4. `exoskeleton_display.launch.py`: visualizes the exoskeleton model in RViz.

## 🧭 Data Flow

```text
Exoskeleton device
  -> WebSocket
websocket_teleoperator
  -> /exo/joint_command
exo_retargeting_node
  -> /left_arm/joint_command + /right_arm/joint_command
exoskeleton_bridge_node
  -> /left_forward_position_controller/commands
  -> /right_forward_position_controller/commands
Robot controller
```

## 📦 Key Directory Structure

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

## 🚀 Quick Start

### Step 1: Start WebSocket Teleoperation Service (receive exoskeleton data)

```bash
cd openarmx_ws
source install/local_setup.bash
ros2 launch openarmx_teleop_exo websocket_teleoperator.launch.py
```

Then configure the upper computer:

1. Open `Qnbot HMI Control-1.2.2.AppImage`.
2. Click **Exoskeleton Device** in the left panel.
3. Click **Add Exoskeleton Device** and create a connection.
4. In device management, click the gear icon and add `ws://localhost:19091` to forwarding targets.
5. Paste `ws://localhost:19091` again in the input box and click **Apply Configuration**.

<p>
  <span style="color:#B00020; font-size:18px;"><b>⚠️ Key Check:</b></span>
  <span style="color:#B00020;"><b>If no data is forwarded, check the WebSocket target in HMI first.</b></span>
  <span style="color:#B00020;"><b>Both controller switches must be pushed up (Switch=0) for communication.</b></span>
</p>

### Step 2: Start Exoskeleton Retargeting Node (map to OpenArmX)

```bash
ros2 launch openarmx_teleop_exo exo_retargeting.launch.py robot_type:=OpenArmX
```

### Step 3: Start OpenArmX (simulation or real hardware)

Simulation mode:

```bash
ros2 launch openarmx_bringup openarmx.bimanual.launch.py \
  robot_controller:=forward_position_controller \
  use_fake_hardware:=true
```

Real hardware mode (basic):

```bash
ros2 launch openarmx_bringup openarmx.bimanual.launch.py \
  robot_controller:=forward_position_controller \
  use_fake_hardware:=false
```

Real hardware mode (with CAN interfaces and control mode):

```bash
ros2 launch openarmx_bringup openarmx.bimanual.launch.py \
  right_can_interface:=can2 \
  left_can_interface:=can3 \
  control_mode:=mit \
  robot_controller:=forward_position_controller
```

### Step 4: Start ROS2 Bridge Control

```bash
ros2 launch openarmx_teleop_exo exoskeleton_bridge.launch.py \
  gripper_scaling_factor:=0.05
```

<p>
  <span style="color:#B00020; font-size:18px;"><b>⚠️ Required:</b></span>
  <span style="color:#B00020;"><b>Before Step 4, align exoskeleton posture close to robot posture</b> (recommended: each joint difference < 50°), to avoid safety rejection or large jumps.</span>
</p>

## 🧠 Node Details

### 1. `websocket_teleoperator`

- Listens on WebSocket (default `0.0.0.0:19091`), parses exoskeleton data, publishes:
- `/exo/joint_command` (`sensor_msgs/JointState`, 16D: left7 + right7 + left trigger + right trigger)
- `/exo/gamepad_keys` (`sensor_msgs/Joy`, joystick axes and buttons)
- Safety gate:
- Data is forwarded only when both left/right `Switch` are `0` (up position).
- Rate limit:
- Internal publish limit is about `100Hz`; over-rate messages are dropped.
- Homing:
- Currently disabled in code (TODO).

### 2. `exo_retargeting_node`

- Subscribes `/exo/joint_command`, maps by YAML config to robot command topics.
- Auto config selection by `robot_type`:
- `OpenArm` -> `config/retargeting_OpenArm.yaml`
- `OpenArmX` -> `config/retargeting_OpenArmX.yaml`
- Mapping includes:
- Exoskeleton index mapping (left/right arm + trigger)
- `scaling_factors`
- `offset_angles`
- Per-arm joint limits `joint_limits`
- Outputs:
- `/left_arm/joint_command`
- `/right_arm/joint_command`

### 3. `exoskeleton_bridge_node`

- Final safety processing before sending to controllers.
- Safety mechanism:
- Waits for `/joint_states` at startup to get robot current posture.
- On first command, checks joint differences (default threshold `0.873 rad` ≈ `50°`).
- If over threshold: stop with error.
- If within threshold: run interpolation transition (default 3s at 50Hz).
- After interpolation: switch to real-time tracking.

<p>
  <span style="color:#0A58CA; font-size:17px;"><b>🛡️ Recommended:</b></span>
  <span style="color:#0A58CA;"><b>enable_safety_check:=true</b>, and increase <b>interpolation_duration</b> when needed (e.g. `5.0`).</span>
</p>

## 📡 Main ROS Topics

| Direction | Topic | Type | Description |
|---|---|---|---|
| Publish | `/exo/joint_command` | `sensor_msgs/JointState` | Exoskeleton fused joint command (16D) |
| Publish | `/exo/gamepad_keys` | `sensor_msgs/Joy` | Joystick and button states |
| Subscribe | `/exo/joint_command` | `sensor_msgs/JointState` | Retargeting input |
| Publish | `/left_arm/joint_command` | `sensor_msgs/JointState` | Left arm mapped command (with gripper) |
| Publish | `/right_arm/joint_command` | `sensor_msgs/JointState` | Right arm mapped command (with gripper) |
| Subscribe | `/joint_states` | `sensor_msgs/JointState` | Robot current states for safety check |
| Publish | `/left_forward_position_controller/commands` | `std_msgs/Float64MultiArray` | Left controller command (7 + gripper) |
| Publish | `/right_forward_position_controller/commands` | `std_msgs/Float64MultiArray` | Right controller command (7 + gripper) |

## ⚙️ Common Parameters

### `websocket_teleoperator.launch.py`

| Parameter | Default | Description |
|---|---|---|
| `enable_left_arm` | `true` | Enable left arm data |
| `enable_right_arm` | `true` | Enable right arm data |
| `enable_left_joystick` | `true` | Enable left joystick data |
| `enable_right_joystick` | `true` | Enable right joystick data |
| `enable_vehicle_control` | `true` | Enable vehicle/elevator control |
| `websocket_host` | `0.0.0.0` | WebSocket host |
| `websocket_port` | `19091` | WebSocket port |

### `exo_retargeting.launch.py`

| Parameter | Default | Description |
|---|---|---|
| `robot_type` | `OpenArm` | Robot type to choose retargeting config |
| `enable_left_arm_retargeting` | `true` | Enable left arm retargeting |
| `enable_right_arm_retargeting` | `true` | Enable right arm retargeting |

### `exoskeleton_bridge.launch.py`

| Parameter | Default | Description |
|---|---|---|
| `max_joint_diff_rad` | `0.873` | Max allowed first-contact joint difference (rad) |
| `interpolation_duration` | `3.0` | Interpolation duration (s) |
| `interpolation_rate_hz` | `50.0` | Interpolation frequency (Hz) |
| `enable_safety_check` | `true` | Enable safety check |
| `gripper_scaling_factor` | `0.02` | Gripper scaling factor |
| `gripper_threshold` | `0.005` | Gripper change threshold |

## 🔍 Visualization and Debugging

### Exoskeleton visualization

```bash
ros2 launch openarmx_teleop_exo exoskeleton_display.launch.py source:=exo_command
```

### Useful debug commands

```bash
ros2 topic list
ros2 topic hz /exo/joint_command
ros2 topic echo /exo/gamepad_keys
ros2 topic echo /joint_states
```

## ❗ Important Notes

1. `<span style="color:#B00020;"><b>Always keep safety check enabled before bridge control on hardware.</b></span>`
2. `<span style="color:#B00020;"><b>If you see “joint difference too large”, align posture first. Do not just increase threshold.</b></span>`
3. `websocket_teleoperator` is currently a direct forwarding path; final safety still depends on downstream controllers and constraints.
4. `publish_rate_hz` and `timeout_ms` are passed from launch, but not actively used in current main node logic.
5. `setup.py` entry for `exo_protocol_parser` may not match current file layout; verify before standalone usage.

## 🛠️ Build

```bash
cd /home/openarmx/openarmx_ws
colcon build --packages-select openarmx_teleop_exo
source install/setup.bash
```

