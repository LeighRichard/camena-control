#!/usr/bin/env python3
"""
Orbbec 相机诊断脚本
用于排查相机初始化问题
"""

import sys
import os

print("=" * 60)
print("Orbbec 相机诊断工具")
print("=" * 60)
print()

# 1. 检查 Python 版本
print("[1] Python 环境检查")
print(f"    Python 版本: {sys.version}")
print(f"    Python 路径: {sys.executable}")
print()

# 2. 检查 pyorbbecsdk 安装
print("[2] pyorbbecsdk 安装检查")
try:
    import pyorbbecsdk
    print(f"    ✓ pyorbbecsdk 已安装")
    print(f"    版本: {pyorbbecsdk.__version__ if hasattr(pyorbbecsdk, '__version__') else '未知'}")
    print(f"    路径: {pyorbbecsdk.__file__}")
    
    # 检查关键类
    print("    检查关键类:")
    classes = ['Pipeline', 'Config', 'OBSensorType', 'OBFormat', 'OBAlignMode']
    for cls_name in classes:
        if hasattr(pyorbbecsdk, cls_name):
            print(f"      ✓ {cls_name}")
        else:
            print(f"      ✗ {cls_name} 不存在")
    
    # 检查 OBException
    if hasattr(pyorbbecsdk, 'OBException'):
        print("      ✓ OBException 存在")
        OBException = pyorbbecsdk.OBException
        print(f"        类型: {type(OBException)}")
        print(f"        是异常类: {issubclass(OBException, BaseException) if isinstance(OBException, type) else '不是类'}")
    else:
        print("      ✗ OBException 不存在")
        
except ImportError as e:
    print(f"    ✗ pyorbbecsdk 未安装: {e}")
    print("    安装命令: pip install pyorbbecsdk")
print()

# 3. 检查系统依赖
print("[3] 系统依赖检查")
try:
    import ctypes
    libusb = ctypes.CDLL('libusb-1.0.so.0')
    print("    ✓ libusb-1.0 已安装")
except:
    print("    ✗ libusb-1.0 未找到")
    print("    安装命令: sudo apt-get install libusb-1.0-0-dev")
print()

# 4. 检查 USB 设备
print("[4] USB 设备检查")
import subprocess
try:
    result = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=5)
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

# 5. 检查 USB 权限
print("[5] USB 权限检查")
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

# 6. 尝试初始化相机
print("[6] 相机初始化测试")
try:
    from pyorbbecsdk import Pipeline, Config, OBSensorType, OBFormat, OBAlignMode
    
    print("    创建 Pipeline...")
    pipeline = Pipeline()
    
    print("    获取设备列表...")
    device_list = pipeline.get_device_list()
    device_count = device_list.get_count()
    
    print(f"    找到 {device_count} 个设备")
    
    if device_count > 0:
        device = device_list.get_device(0)
        print(f"    ✓ 设备 0: {device}")
        
        try:
            device_info = device.get_device_info()
            print(f"      名称: {device_info.get_name()}")
            print(f"      序列号: {device_info.get_serial_number()}")
            print(f"      固件版本: {device_info.get_firmware_version()}")
        except Exception as e:
            print(f"      获取设备信息失败: {e}")
        
        # 尝试配置流
        print("    配置流...")
        config = Config()
        
        try:
            # 彩色流
            color_profiles = pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
            color_profile = color_profiles.get_video_stream_profile(1920, 1080, OBFormat.RGB, 30)
            config.enable_stream(color_profile)
            print("      ✓ 彩色流配置成功")
        except Exception as e:
            print(f"      ✗ 彩色流配置失败: {e}")
        
        try:
            # 深度流
            depth_profiles = pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
            depth_profile = depth_profiles.get_video_stream_profile(640, 480, OBFormat.Y16, 30)
            config.enable_stream(depth_profile)
            print("      ✓ 深度流配置成功")
        except Exception as e:
            print(f"      ✗ 深度流配置失败: {e}")
        
        # 尝试启动
        print("    启动 Pipeline...")
        try:
            pipeline.start(config)
            print("    ✓ Pipeline 启动成功")
            
            # 尝试获取帧
            print("    尝试获取帧...")
            for i in range(3):
                try:
                    frameset = pipeline.wait_for_frames(timeout_ms=5000)
                    if frameset:
                        color_frame = frameset.get_color_frame()
                        depth_frame = frameset.get_depth_frame()
                        if color_frame and depth_frame:
                            print(f"      ✓ 帧 {i+1}: 彩色 {color_frame.get_width()}x{color_frame.get_height()}, "
                                  f"深度 {depth_frame.get_width()}x{depth_frame.get_height()}")
                        else:
                            print(f"      ✗ 帧 {i+1}: 帧数据不完整")
                except Exception as e:
                    print(f"      ✗ 帧 {i+1}: {e}")
            
            pipeline.stop()
            print("    ✓ Pipeline 已停止")
            
        except Exception as e:
            print(f"    ✗ Pipeline 启动失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("    ✗ 未找到设备")
        
except Exception as e:
    print(f"    ✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
print()

# 7. 总结和建议
print("=" * 60)
print("诊断总结")
print("=" * 60)
print()
print("如果遇到问题,请按以下步骤排查:")
print()
print("1. USB 权限问题:")
print("   - 创建 udev 规则 (见上方命令)")
print("   - 重新插拔相机")
print("   - 或使用 sudo 运行程序")
print()
print("2. 驱动问题:")
print("   - 检查 lsusb 是否能看到设备")
print("   - 检查 libusb 是否安装")
print()
print("3. SDK 问题:")
print("   - 重新安装: pip install --upgrade --force-reinstall pyorbbecsdk")
print("   - 检查 Python 版本兼容性")
print()
print("4. 硬件问题:")
print("   - 尝试不同的 USB 端口 (USB 3.0 推荐)")
print("   - 检查 USB 线缆")
print("   - 检查设备供电")
print()
