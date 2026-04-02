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
from glob import glob
from setuptools import find_packages, setup

package_name = 'openarmx_teleop_exo'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    package_data={
        'openarmx_teleop_exo.openarm.src': ['*.so'],
        'openarmx_teleop_exo.openarm.mode': ['*.urdf', '*.xml', '*.stl', '*.dae', '*.STL', '*.TXT'],
        'openarmx_teleop_exo.openarm.mode.meshes': ['**/*.stl', '**/*.dae'],
    },
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Launch files
        ('share/' + package_name + '/launch', [
            'launch/websocket_teleoperator.launch.py',
            'launch/exoskeleton_display.launch.py',
            'launch/exo_retargeting.launch.py',
            'launch/exoskeleton_bridge.launch.py'
        ]),
        # Configuration files
        ('share/' + package_name + '/config', [
            'config/qnbot_teleoperator_config.yaml',
            'config/exoskeleton_display.rviz',
            'config/retargeting_OpenArm.yaml',
            'config/retargeting_OpenArmX.yaml'
        ]),
        # Kinematics chain files
        ('share/' + package_name + '/config/target', glob('config/target/*.yaml')),
        # URDF/xacro files
        ('share/' + package_name + '/resource/urdf', [
            'resource/urdf/qnbot_exoskeleton.xacro',
            'resource/urdf/qnbot_exoskeleton_right.xacro',
            'resource/urdf/qnbot_exoskeleton_left.xacro'
        ]),
        # Mesh files
        ('share/' + package_name + '/resource/meshs', glob('resource/meshs/*.STL')),
    ],
    install_requires=[
        'setuptools', 
        'websockets', 
        'asyncio',
        'numpy',
        'pin'  # Pinocchio for gravity compensation
    ],
    zip_safe=True,
    maintainer='user',
    maintainer_email='user@todo.todo',
    description='WebSocket远程控制器，接收外骨骼数据并转换为机器人关节命令',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'websocket_teleoperator = openarmx_teleop_exo.websocket_teleoperator:main',
            'exo_protocol_parser = openarmx_teleop_exo.exo_protocol_parser:main',
            'exo_retargeting_node = openarmx_teleop_exo.exo_retargeting_node:main',
            'exoskeleton_bridge_node = openarmx_teleop_exo.exoskeleton_bridge_node:main',
        ],
    },
)
