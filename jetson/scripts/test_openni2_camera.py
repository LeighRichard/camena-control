#!/usr/bin/env python3
"""
测试 OpenNI2 相机控制器
验证 OpenNI2 后端是否正常工作
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

print("=" * 60)
print("OpenNI2 相机控制器测试")
print("=" * 60)
print()

# 1. 检查 OpenNI2 安装
print("[1] 检查 OpenNI2 安装...")
try:
    import openni2
    print(f"    ✓ OpenNI2 已安装")
    print(f"    版本: {openni2.__version__ if hasattr(openni2, '__version__') else '未知'}")
except ImportError:
    print("    ✗ OpenNI2 未安装")
    print("    安装命令: pip install openni2")
    sys.exit(1)
print()

# 2. 初始化 OpenNI2
print("[2] 初始化 OpenNI2...")
try:
    openni2.initialize()
    print("    ✓ OpenNI2 初始化成功")
except Exception as e:
    print(f"    ✗ OpenNI2 初始化失败: {e}")
    sys.exit(1)
print()

# 3. 检查设备
print("[3] 检查设备...")
try:
    device = openni2.Device.open_any()
    if device:
        print("    ✓ 找到设备")
        print(f"      供应商: {device.get_info(openni2.Device.VENDOR)}")
        print(f"      产品: {device.get_info(openni2.Device.PRODUCT)}")
    else:
        print("    ✗ 未找到设备")
except Exception as e:
    print(f"    ✗ 检查设备失败: {e}")
print()

# 4. 测试相机控制器
print("[4] 测试相机控制器...")
try:
    from camera.factory import CameraFactory

    # 创建相机
    print("    创建相机...")
    camera = CameraFactory.create_camera("orbbec")

    if camera is None:
        print("    ✗ 相机创建失败")
    else:
        print(f"    ✓ 相机创建成功: {camera.camera_model}")
        print(f"      类型: {camera.camera_type}")

        # 测试采集图像
        print("    测试采集图像...")
        image_pair, error = camera.capture(wait_frames=3)

        if image_pair is None:
            print(f"    ✗ 采集图像失败: {error}")
        else:
            print(f"    ✓ 采集图像成功")
            print(f"      彩色图尺寸: {image_pair.rgb.shape}")
            print(f"      深度图尺寸: {image_pair.depth.shape}")

            # 测试深度查询
            print("    测试深度查询...")
            depth = camera.get_depth_at_point(
                image_pair.rgb.shape[1] // 2,
                image_pair.rgb.shape[0] // 2,
                image_pair.depth
            )
            print(f"      中心点深度: {depth:.2f}m")

        # 关闭相机
        camera.close()
        print("    ✓ 相机已关闭")

except Exception as e:
    print(f"    ✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
print()

# 5. 清理
print("[5] 清理...")
try:
    openni2.unload()
    print("    ✓ OpenNI2 已卸载")
except Exception as e:
    print(f"    ✗ 清理失败: {e}")
print()

# 6. 总结
print("=" * 60)
print("测试完成")
print("=" * 60)
print()
print("如果所有测试通过,OpenNI2 后端可以正常使用。")
print("您可以直接运行主程序:")
print("  python3 main.py")
print()
