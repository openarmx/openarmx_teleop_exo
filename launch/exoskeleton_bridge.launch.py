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


import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # 声明启动参数
    gripper_threshold_arg = DeclareLaunchArgument(
        'gripper_threshold',
        default_value='0.005',
        description='夹爪位置变化的最小阈值 (m)，用于减少Action请求频率'
    )

    gripper_scaling_factor_arg = DeclareLaunchArgument(
        'gripper_scaling_factor',
        default_value='0.02',
        description='夹爪数值缩放因子：外骨骼归一化值(0-1) -> 机械臂物理值(米)。默认0.02表示外骨骼1.0对应机械臂2cm'
    )

    # 安全检查参数
    max_joint_diff_arg = DeclareLaunchArgument(
        'max_joint_diff_rad',
        default_value='0.873',
        description='最大允许关节差异（弧度），约50度。超过此值将拒绝启动'
    )

    interpolation_duration_arg = DeclareLaunchArgument(
        'interpolation_duration',
        default_value='3.0',
        description='插值过渡时间（秒），从当前位置平滑过渡到外骨骼位置'
    )

    interpolation_rate_arg = DeclareLaunchArgument(
        'interpolation_rate_hz',
        default_value='50.0',
        description='插值频率（Hz）'
    )

    enable_safety_check_arg = DeclareLaunchArgument(
        'enable_safety_check',
        default_value='true',
        description='是否启用安全检查。建议始终启用以防止电机过载'
    )

    # 桥接节点
    bridge_node = Node(
        package='openarmx_teleop_exo',
        executable='exoskeleton_bridge_node',
        name='exoskeleton_bridge_node',
        output='screen',
        parameters=[{
            'gripper_threshold': LaunchConfiguration('gripper_threshold'),
            'gripper_scaling_factor': LaunchConfiguration('gripper_scaling_factor'),
            'max_joint_diff_rad': LaunchConfiguration('max_joint_diff_rad'),
            'interpolation_duration': LaunchConfiguration('interpolation_duration'),
            'interpolation_rate_hz': LaunchConfiguration('interpolation_rate_hz'),
            'enable_safety_check': LaunchConfiguration('enable_safety_check'),
        }]
    )

    return LaunchDescription([
        gripper_threshold_arg,
        gripper_scaling_factor_arg,
        max_joint_diff_arg,
        interpolation_duration_arg,
        interpolation_rate_arg,
        enable_safety_check_arg,
        bridge_node
    ])


