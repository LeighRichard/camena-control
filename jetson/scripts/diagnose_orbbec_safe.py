#!/usr/bin/env python3
"""
Orbbec 相机诊断脚本 (改进版)
用于排查相机初始化问题,添加超时保护
"""

import sys
import os
import subprocess
import signal
import time

print("=" * 60)
print("Orbbec 相机诊断工具 (改进版)")
print("=" * 60)
print()

# 1. 检查 Python 版本
print("[1] Python 环境检查")
print(f"    Python 版本: {sys.version}")
print(f"    Python 路径: {sys.executable}")
print()

# 2. 检查系统依赖
print("[2] 系统依赖检查")
try:
    import ctypes
    libusb = ctypes.CDLL('libusb-1.0.so.0')
    print("    ✓ libusb-1.0 已安装")
except:
    print("    ✗ libusb-1.0 未找到")
    print("    安装命令: sudo apt-get install libusb-1.0-0-dev")
print()

# 3. 检查 USB 设备
print("[3] USB 设备检查")
try:
    # Python 3.6 兼容写法
    result = subprocess.run(
        ['lsusb'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=5
    )
    if result.returncode == 0:
        lines = result.stdout.split('\n')
        orbbec_devices = [line for line in lines if '2bc5' in line.lower() or 'orbbec' in line.lower()]
        
        if orbbec_devices:
            print("    ✓ 找到 Orbbec 设备:")
            for device in orbbec_devices:
                print(f"      {device}")
        else:
            print("    ✗ 未找到 Orbbec 设备 (Vendor ID: 2bc5)")
            print("    所有 USB 设备:")
            for line in lines[:10]:  # 只显示前10个
                if line.strip():
                    print(f"      {line}")
    else:
        print(f"    ✗ lsusb 执行失败: {result.stderr}")
except Exception as e:
    print(f"    ✗ 无法执行 lsusb: {e}")
print()

# 4. 检查 USB 权限
print("[4] USB 权限检查")
udev_rules_file = "/etc/udev/rules.d/99-orbbec.rules"
if os.path.exists(udev_rules_file):
    print(f"    ✓ udev 规则文件存在: {udev_rules_file}")
    try:
        with open(udev_rules_file, 'r') as f:
            content = f.read()
            print(f"    内容: {content.strip()}")
    except:
        print("    ✗ 无法读取文件 (需要 sudo 权限)")
else:
    print(f"    ✗ udev 规则文件不存在: {udev_rules_file}")
    print("    创建命令:")
    print("      sudo tee /etc/udev/rules.d/99-orbbec.rules > /dev/null <<EOF")
    print('      SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"')
    print("      EOF")
    print("      sudo udevadm control --reload-rules")
    print("      sudo udevadm trigger")
print()

# 5. 检查 USB 设备权限
print("[5] USB 设备权限检查")
try:
    # 查找 Orbbec 设备
    result = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        for line in result.stdout.split('\n'):
            if '2bc5' in line.lower():
                # 提取 Bus 和 Device 号
                parts = line.split()
                if len(parts) >= 4:
                    bus = parts[1]
                    device_num = parts[3].rstrip(':')
                    device_path = f"/dev/bus/usb/{bus}/{device_num}"
                    
                    if os.path.exists(device_path):
                        stat_info = os.stat(device_path)
                        mode = oct(stat_info.st_mode)[-3:]
                        print(f"    设备: {device_path}")
                        print(f"    权限: {mode} (需要 666)")
                        if mode == '666':
                            print("    ✓ 权限正确")
                        else:
                            print("    ✗ 权限不足")
                            print(f"    修复命令: sudo chmod 666 {device_path}")
                    else:
                        print(f"    ✗ 设备路径不存在: {device_path}")
except Exception as e:
    print(f"    ✗ 检查失败: {e}")
print()

# 6. 检查 pyorbbecsdk 安装 (使用超时)
print("[6] pyorbbecsdk 安装检查")

def check_pyorbbecsdk():
    """检查 pyorbbecsdk 安装,带超时保护"""
    try:
        # 使用子进程检查,避免卡住
        result = subprocess.run(
            [sys.executable, '-c', 'import pyorbbecsdk; print("OK")'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10
        )
        
        if result.returncode == 0 and 'OK' in result.stdout:
            print("    ✓ pyorbbecsdk 已安装")
            
            # 获取版本
            version_result = subprocess.run(
                [sys.executable, '-c', 
                 'import pyorbbecsdk; print(pyorbbecsdk.__version__ if hasattr(pyorbbecsdk, "__version__") else "未知")'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=5
            )
            if version_result.returncode == 0:
                print(f"    版本: {version_result.stdout.strip()}")
            
            # 获取路径
            path_result = subprocess.run(
                [sys.executable, '-c', 'import pyorbbecsdk; print(pyorbbecsdk.__file__)'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=5
            )
            if path_result.returncode == 0:
                print(f"    路径: {path_result.stdout.strip()}")
            
            return True
        else:
            print(f"    ✗ pyorbbecsdk 导入失败")
            if result.stderr:
                print(f"    错误: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print("    ✗ pyorbbecsdk 导入超时 (10秒)")
        print("    这通常表示 USB 设备访问权限问题")
        return False
    except Exception as e:
        print(f"    ✗ 检查失败: {e}")
        return False

check_pyorbbecsdk()
print()

# 7. 简单的相机测试 (可选)
print("[7] 相机初始化测试 (可选)")
print("    由于导入 pyorbbecsdk 可能会卡住,跳过自动测试")
print("    请手动运行以下命令测试:")
print("      python3 -c 'from pyorbbecsdk import Pipeline; p = Pipeline(); print(p.get_device_list().get_count())'")
print()

# 8. 总结和建议
print("=" * 60)
print("诊断总结")
print("=" * 60)
print()

# 检查关键问题
issues = []

# 检查 USB 设备
result = subprocess.run(
    ['lsusb'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    universal_newlines=True,
    timeout=5
)
if '2bc5' not in result.stdout.lower():
    issues.append("未找到 Orbbec USB 设备")

# 检查 udev 规则
if not os.path.exists("/etc/udev/rules.d/99-orbbec.rules"):
    issues.append("udev 规则未配置")

# 检查 libusb
try:
    ctypes.CDLL('libusb-1.0.so.0')
except:
    issues.append("libusb 未安装")

if issues:
    print("发现以下问题:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    print()
    print("建议执行以下修复步骤:")
    print()
    print("1. 运行自动修复脚本:")
    print("     chmod +x scripts/fix_orbbec_jetson.sh")
    print("     ./scripts/fix_orbbec_jetson.sh")
    print()
    print("2. 或手动执行:")
    print("     sudo apt-get install -y libusb-1.0-0-dev libudev-dev")
    print("     sudo tee /etc/udev/rules.d/99-orbbec.rules > /dev/null <<EOF")
    print('     SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"')
    print("     EOF")
    print("     sudo udevadm control --reload-rules")
    print("     sudo udevadm trigger")
    print("     sudo reboot")
else:
    print("✓ 未发现明显问题")
    print()
    print("如果相机仍然无法初始化,请:")
    print("  1. 重新插拔相机")
    print("  2. 尝试不同的 USB 端口 (推荐 USB 3.0)")
    print("  3. 使用 sudo 运行程序 (临时方案)")
    print("  4. 查看系统日志: dmesg | tail -50")

print()
