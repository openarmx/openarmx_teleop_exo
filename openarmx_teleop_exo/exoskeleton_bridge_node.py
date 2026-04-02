#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
#
# Copyright (c) 2026 Chengdu Changshu Robot Co., Ltd.
# https://www.openarmx.com
#
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike
# 4.0 International License (CC BY-NC-SA 4.0).
#
# To view a copy of this license, visit:
# http://creativecommons.org/licenses/by-nc-sa/4.0/
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.


"""
外骨骼-仿真桥接节点（带安全检查和插值）
接收 retargeting 后的关节数据 (/left_arm/joint_command, /right_arm/joint_command)
转换为控制器话题 (Float64MultiArray) 和 夹爪动作 (GripperCommand)

安全特性：
1. 启动时获取机器人当前位置
2. 检测外骨骼位置与机器人位置差异
3. 如果差异过大，报错并停止
4. 如果差异在安全范围内，使用插值平滑过渡
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
from control_msgs.action import GripperCommand
import numpy as np
import time

class ExoskeletonBridgeNode(Node):
    def __init__(self):
        super().__init__('exoskeleton_bridge_node')

        # ============ 安全参数 ============
        self.declare_parameter('max_joint_diff_rad', 0.873)  # 最大允许关节差异（弧度，约50度）
        self.declare_parameter('interpolation_duration', 3.0)  # 插值过渡时间（秒）
        self.declare_parameter('interpolation_rate_hz', 50.0)  # 插值频率（Hz）
        self.declare_parameter('enable_safety_check', True)  # 是否启用安全检查

        self.max_joint_diff = self.get_parameter('max_joint_diff_rad').value
        self.interpolation_duration = self.get_parameter('interpolation_duration').value
        self.interpolation_rate = self.get_parameter('interpolation_rate_hz').value
        self.enable_safety_check = self.get_parameter('enable_safety_check').value

        # ============ 其他参数 ============
        self.declare_parameter('gripper_threshold', 0.005)
        self.gripper_threshold = self.get_parameter('gripper_threshold').value

        self.declare_parameter('gripper_scaling_factor', 0.02)
        self.gripper_scale = self.get_parameter('gripper_scaling_factor').value

        # ============ 状态变量 ============
        # 机器人当前位置
        self.left_current_position = None
        self.right_current_position = None

        # 外骨骼目标位置
        self.left_target_position = None
        self.right_target_position = None

        # 插值状态
        self.left_interpolating = False
        self.right_interpolating = False
        self.left_interp_start_pos = None
        self.right_interp_start_pos = None
        self.left_interp_target_pos = None
        self.right_interp_target_pos = None
        self.left_interp_start_time = None
        self.right_interp_start_time = None

        # 安全检查状态
        self.left_safety_passed = False
        self.right_safety_passed = False
        self.left_first_command_received = False
        self.right_first_command_received = False

        # 夹爪状态
        self.last_left_gripper_pos = 0.0
        self.last_right_gripper_pos = 0.0
        self.left_gripper_goal_handle = None
        self.right_gripper_goal_handle = None

        # 日志计数器
        self.log_counter_left = 0
        self.log_counter_right = 0
        self.log_interval = 50
        self.gripper_log_counter_left = 0
        self.gripper_log_counter_right = 0
        self.gripper_log_interval = 100

        # ============ 订阅机器人当前状态 ============
        self.joint_states_sub = self.create_subscription(
            JointState,
            '/joint_states',
            self.joint_states_callback,
            10
        )

        # ============ 订阅外骨骼命令 ============
        self.left_arm_sub = self.create_subscription(
            JointState,
            '/left_arm/joint_command',
            self.left_arm_callback,
            10
        )

        self.right_arm_sub = self.create_subscription(
            JointState,
            '/right_arm/joint_command',
            self.right_arm_callback,
            10
        )

        # ============ 发布到控制器 ============
        self.left_arm_pub = self.create_publisher(
            Float64MultiArray,
            '/left_forward_position_controller/commands',
            10
        )

        self.right_arm_pub = self.create_publisher(
            Float64MultiArray,
            '/right_forward_position_controller/commands',
            10
        )

        # ============ 夹爪 Action Client ============
        self.left_gripper_client = ActionClient(self, GripperCommand, '/left_gripper_controller/gripper_cmd')
        self.right_gripper_client = ActionClient(self, GripperCommand, '/right_gripper_controller/gripper_cmd')

        # ============ 插值定时器 ============
        self.interpolation_timer = self.create_timer(
            1.0 / self.interpolation_rate,
            self.interpolation_callback
        )

        self.get_logger().info(
            f'\n'
            f'🛡️  外骨骼桥接节点已启动（带安全检查）\n'
            f'  安全检查: {"启用" if self.enable_safety_check else "禁用"}\n'
            f'  最大关节差异: {np.rad2deg(self.max_joint_diff):.1f}° ({self.max_joint_diff:.3f} rad)\n'
            f'  插值过渡时间: {self.interpolation_duration}秒\n'
            f'  插值频率: {self.interpolation_rate}Hz\n'
            f'  夹爪阈值: {self.gripper_threshold}m\n'
            f'  夹爪缩放因子: {self.gripper_scale}\n'
            f'📡 等待机器人 /joint_states 话题...'
        )

    def joint_states_callback(self, msg: JointState):
        """订阅机器人当前关节状态"""
        try:
            # 提取左臂关节（实际命名为 openarmx_left_joint1 到 openarmx_left_joint7）
            left_joints = []
            for i in range(1, 8):
                joint_name = f'openarmx_left_joint{i}'
                if joint_name in msg.name:
                    idx = msg.name.index(joint_name)
                    left_joints.append(msg.position[idx])

            if len(left_joints) == 7:
                self.left_current_position = np.array(left_joints)
                # 首次接收到位置时打印日志
                if not hasattr(self, '_left_position_received'):
                    self._left_position_received = True
                    self.get_logger().info(
                        f'✅ [LEFT] 已接收到机器人当前位置: {np.rad2deg(self.left_current_position).round(1)}'
                    )

            # 提取右臂关节（实际命名为 openarmx_right_joint1 到 openarmx_right_joint7）
            right_joints = []
            for i in range(1, 8):
                joint_name = f'openarmx_right_joint{i}'
                if joint_name in msg.name:
                    idx = msg.name.index(joint_name)
                    right_joints.append(msg.position[idx])

            if len(right_joints) == 7:
                self.right_current_position = np.array(right_joints)
                # 首次接收到位置时打印日志
                if not hasattr(self, '_right_position_received'):
                    self._right_position_received = True
                    self.get_logger().info(
                        f'✅ [RIGHT] 已接收到机器人当前位置: {np.rad2deg(self.right_current_position).round(1)}'
                    )

        except Exception as e:
            self.get_logger().error(f'解析 joint_states 失败: {e}')

    def left_arm_callback(self, msg: JointState):
        """处理左臂命令"""
        self._process_arm_command(msg, 'left')

    def right_arm_callback(self, msg: JointState):
        """处理右臂命令"""
        self._process_arm_command(msg, 'right')

    def _process_arm_command(self, msg: JointState, side: str):
        """处理手臂命令（带安全检查）"""
        try:
            if len(msg.position) < 7:
                return

            # 提取关节位置（前7个）
            target_joints = np.array(msg.position[:7])

            # 提取夹爪位置
            gripper_position = 0.0
            has_gripper_data = False
            if len(msg.position) >= 8:
                gripper_position = msg.position[7]
                has_gripper_data = True

            # 获取当前位置
            current_pos = self.left_current_position if side == 'left' else self.right_current_position

            if current_pos is None:
                if side == 'left':
                    if not hasattr(self, '_left_no_state_warned'):
                        self.get_logger().warn(
                            f'⚠️  [{side.upper()}] 尚未接收到机器人当前位置，等待 /joint_states 话题...'
                        )
                        self._left_no_state_warned = True
                else:
                    if not hasattr(self, '_right_no_state_warned'):
                        self.get_logger().warn(
                            f'⚠️  [{side.upper()}] 尚未接收到机器人当前位置，等待 /joint_states 话题...'
                        )
                        self._right_no_state_warned = True
                return

            # 检查是否是第一次收到命令
            first_command = (side == 'left' and not self.left_first_command_received) or \
                           (side == 'right' and not self.right_first_command_received)

            if first_command:
                if side == 'left':
                    self.left_first_command_received = True
                else:
                    self.right_first_command_received = True

                # 执行安全检查
                if self.enable_safety_check:
                    safety_passed = self._check_position_safety(current_pos, target_joints, side)

                    if not safety_passed:
                        # 安全检查失败，停止节点
                        self.get_logger().fatal(
                            f'\n'
                            f'🚨🚨🚨 安全检查失败！节点已停止！🚨🚨🚨\n'
                            f'[{side.upper()}] 外骨骼位置与机器人当前位置差异过大\n'
                            f'请将外骨骼移动到与机器人相近的位置后重新启动'
                        )
                        # 停止节点
                        raise SystemExit('安全检查失败')

                    # 安全检查通过，开始插值
                    if side == 'left':
                        self.left_safety_passed = True
                        self.left_interpolating = True
                        self.left_interp_start_pos = current_pos.copy()
                        self.left_interp_target_pos = target_joints.copy()
                        self.left_interp_start_time = time.time()
                        self.get_logger().info(
                            f'✅ [{side.upper()}] 安全检查通过，开始 {self.interpolation_duration}秒 插值过渡'
                        )
                    else:
                        self.right_safety_passed = True
                        self.right_interpolating = True
                        self.right_interp_start_pos = current_pos.copy()
                        self.right_interp_target_pos = target_joints.copy()
                        self.right_interp_start_time = time.time()
                        self.get_logger().info(
                            f'✅ [{side.upper()}] 安全检查通过，开始 {self.interpolation_duration}秒 插值过渡'
                        )
                else:
                    # 不启用安全检查，直接通过
                    if side == 'left':
                        self.left_safety_passed = True
                    else:
                        self.right_safety_passed = True
                    self.get_logger().info(f'⚠️  [{side.upper()}] 安全检查已禁用，直接转发命令')

            # 更新目标位置（用于插值）
            if side == 'left':
                self.left_target_position = target_joints
                # 如果正在插值，更新插值目标
                if self.left_interpolating:
                    self.left_interp_target_pos = target_joints.copy()
                # 如果不在插值且安全检查已通过，直接发布
                elif self.left_safety_passed:
                    self._publish_command(target_joints, gripper_position, side)
            else:
                self.right_target_position = target_joints
                if self.right_interpolating:
                    self.right_interp_target_pos = target_joints.copy()
                elif self.right_safety_passed:
                    self._publish_command(target_joints, gripper_position, side)

        except SystemExit:
            raise
        except Exception as e:
            self.get_logger().error(f'[{side.upper()}] 处理命令失败: {e}')

    def _check_position_safety(self, current_pos: np.ndarray, target_pos: np.ndarray, side: str) -> bool:
        """检查位置安全性"""
        joint_diffs = np.abs(target_pos - current_pos)
        max_diff = np.max(joint_diffs)
        max_diff_idx = np.argmax(joint_diffs)

        self.get_logger().info(
            f'\n'
            f'🔍 [{side.upper()}] 安全检查:\n'
            f'  当前位置: {np.rad2deg(current_pos).round(1)}\n'
            f'  目标位置: {np.rad2deg(target_pos).round(1)}\n'
            f'  最大差异: 关节{max_diff_idx+1} = {np.rad2deg(max_diff):.1f}° ({max_diff:.3f} rad)\n'
            f'  安全阈值: {np.rad2deg(self.max_joint_diff):.1f}° ({self.max_joint_diff:.3f} rad)'
        )

        if max_diff > self.max_joint_diff:
            self.get_logger().error(
                f'\n'
                f'❌ [{side.upper()}] 位置差异过大！\n'
                f'  关节{max_diff_idx+1} 差异: {np.rad2deg(max_diff):.1f}° > 阈值 {np.rad2deg(self.max_joint_diff):.1f}°\n'
                f'  当前值: {np.rad2deg(current_pos[max_diff_idx]):.1f}°\n'
                f'  目标值: {np.rad2deg(target_pos[max_diff_idx]):.1f}°'
            )
            return False

        return True

    def interpolation_callback(self):
        """插值定时器回调"""
        current_time = time.time()

        # 处理左臂插值
        if self.left_interpolating:
            elapsed = current_time - self.left_interp_start_time
            progress = min(elapsed / self.interpolation_duration, 1.0)

            # 线性插值
            interp_pos = self.left_interp_start_pos + \
                        (self.left_interp_target_pos - self.left_interp_start_pos) * progress

            # 发布插值位置
            self._publish_command(interp_pos, 0.0, 'left')

            # 检查是否完成插值
            if progress >= 1.0:
                self.left_interpolating = False
                self.get_logger().info(f'✅ [LEFT] 插值完成，切换到实时跟踪模式')

        # 处理右臂插值
        if self.right_interpolating:
            elapsed = current_time - self.right_interp_start_time
            progress = min(elapsed / self.interpolation_duration, 1.0)

            interp_pos = self.right_interp_start_pos + \
                        (self.right_interp_target_pos - self.right_interp_start_pos) * progress

            self._publish_command(interp_pos, 0.0, 'right')

            if progress >= 1.0:
                self.right_interpolating = False
                self.get_logger().info(f'✅ [RIGHT] 插值完成，切换到实时跟踪模式')

    def _publish_command(self, joint_positions, gripper_position, side: str):
        """发布命令到控制器"""
        try:
            # 构建命令（7个关节 + 1个夹爪）
            final_gripper_pos = gripper_position * self.gripper_scale
            arm_positions = list(joint_positions) + [final_gripper_pos]

            # 发布
            cmds = Float64MultiArray()
            cmds.data = arm_positions

            if side == 'left':
                self.left_arm_pub.publish(cmds)
                self.log_counter_left += 1
                if self.log_counter_left % self.log_interval == 0:
                    short_pos = [f"{np.rad2deg(x):.1f}" for x in joint_positions[:4]]
                    self.get_logger().info(
                        f'[LEFT] 发布: {short_pos}...° + 夹爪:{final_gripper_pos:.4f}m'
                    )
            else:
                self.right_arm_pub.publish(cmds)
                self.log_counter_right += 1
                if self.log_counter_right % self.log_interval == 0:
                    short_pos = [f"{np.rad2deg(x):.1f}" for x in joint_positions[:4]]
                    self.get_logger().info(
                        f'[RIGHT] 发布: {short_pos}...° + 夹爪:{final_gripper_pos:.4f}m'
                    )

        except Exception as e:
            self.get_logger().error(f'[{side.upper()}] 发布命令失败: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = ExoskeletonBridgeNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

