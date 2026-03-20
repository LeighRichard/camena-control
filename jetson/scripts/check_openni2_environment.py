#!/usr/bin/env python3
"""
检查 OpenNI2 环境并提供建议
"""

import sys
import os
import subprocess

print("=" * 60)
print("OpenNI2 环境检查")
print("=" * 60)
print()

# 1. 检查 OpenNI2 库文件
print("[1] 检查 OpenNI2 库文件...")
try:
    result = subprocess.run(['find', '/usr', '-name', 'libOpenNI2*'], 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                          universal_newlines=True, timeout=5)
    if result.returncode == 0:
        libs = [line for line in result.stdout.split('\n') if line.strip()]
        if libs:
            print("    ✓ 找到 OpenNI2 库:")
            for lib in libs:
                print(f"      {lib}")
        else:
            print("    ✗ 未找到 OpenNI2 库")
except Exception as e:
    print(f"    ✗ 检查失败: {e}")
print()

# 2. 检查 ROS OpenNI2
print("[2] 检查 ROS OpenNI2...")
try:
    result = subprocess.run(['rospack', 'find', 'openni2_launch'], 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, timeout=5)
    if result.returncode == 0:
        print("    ✓ ROS OpenNI2 已安装")
        print(f"      路径: {result.stdout.strip()}")
    else:
        print("    ✗ ROS OpenNI2 未安装")
except Exception as e:
    print("    ✗ ROS 未安装或未配置")
print()

# 3. 检查 OpenNI2 Python 绑定
print("[3] 检查 OpenNI2 Python 绑定...")
try:
    import openni2
    print("    ✓ OpenNI2 Python 绑定已安装")
    print(f"      版本: {openni2.__version__ if hasattr(openni2, '__version__') else '未知'}")
except ImportError:
    print("    ✗ OpenNI2 Python 绑定未安装")
print()

# 4. 检查 pyorbbecsdk
print("[4] 检查 pyorbbecsdk...")
try:
    import pyorbbecsdk
    print("    ✓ pyorbbecsdk 已安装")
    print(f"      版本: {pyorbbecsdk.__version__ if hasattr(pyorbbecsdk, '__version__') else '未知'}")
except ImportError:
    print("    ✗ pyorbbecsdk 未安装")
print()

# 5. 总结和建议
print("=" * 60)
print("建议方案")
print("=" * 60)
print()

# 检查 ROS 是否可用
ros_available = False
try:
    subprocess.run(['rospack', 'find', 'openni2_launch'], 
                  capture_output=True, timeout=2)
    ros_available = True
except:
    pass

if ros_available:
    print("✅ 推荐方案 1: 使用 ROS OpenNI2")
    print("   您的系统已安装 ROS OpenNI2")
    print("   操作步骤:")
    print("   1. 设置 ROS 环境:")
    print("      source /opt/ros/<distro>/setup.bash")
    print("   2. 运行程序:")
    print("      python3 main.py")
    print()
else:
    print("⚠️  ROS OpenNI2 未安装")
    print("   安装命令:")
    print("   sudo apt-get install -y ros-melodic-openni2-launch")
    print("   或")
    print("   sudo apt-get install -y ros-noetic-openni2-launch")
    print()

print("✅ 推荐方案 2: 修复 pyorbbecsdk 权限问题")
print("   这是最简单的方法")
print("   操作步骤:")
print("   1. 设置 USB 权限:")
print("      sudo tee /etc/udev/rules.d/99-orbbec.rules > /dev/null <<EOF")
print('      SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"')
print("      EOF")
print("   2. 重新加载规则:")
print("      sudo udevadm control --reload-rules")
print("   3. 设置当前权限:")
print("      for dev in /dev/bus/usb/*/*; do sudo chmod 666 \"$dev\" 2>/dev/null; done")
print("   4. 重新插拔相机")
print("   5. 运行程序:")
print("      python3 main.py")
print()

print("📝 方案 3: 编译 OpenNI2 Python 绑定")
print("   参考: docs/OPENNI2_INSTALL_GUIDE.md")
print()

print("=" * 60)
print("快速修复命令 (方案 2)")
print("=" * 60)
print()
print("sudo tee /etc/udev/rules.d/99-orbbec.rules > /dev/null <<EOF")
print('SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"')
print("EOF")
print("sudo udevadm control --reload-rules")
print("sudo udevadm trigger")
print("for dev in /dev/bus/usb/*/*; do sudo chmod 666 \"$dev\" 2>/dev/null; done")
print("python3 main.py")
print()
