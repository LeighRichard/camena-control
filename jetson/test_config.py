#!/usr/bin/env python3
"""
测试配置解析
"""

import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.config import load_config, CameraConfig, OrbbecConfig, RealSenseConfig

def test_config_parsing():
    """测试配置解析"""
    print("=" * 60)
    print("测试配置解析")
    print("=" * 60)
    
    # 加载配置
    config_path = Path(__file__).parent / "config" / "system_config.yaml"
    config = load_config(config_path, validate=False)
    
    # 检查相机配置
    print("\n相机配置:")
    print(f"  类型: {config.camera.type}")
    print(f"  启用: {config.camera.enabled}")
    print(f"  必需: {config.camera.required}")
    
    # 检查 Orbbec 配置
    print("\nOrbbec 配置:")
    print(f"  彩色分辨率: {config.camera.orbbec.color.width}x{config.camera.orbbec.color.height}")
    print(f"  彩色帧率: {config.camera.orbbec.color.fps}")
    print(f"  深度分辨率: {config.camera.orbbec.depth.width}x{config.camera.orbbec.depth.height}")
    print(f"  深度帧率: {config.camera.orbbec.depth.fps}")
    print(f"  对齐模式: {config.camera.orbbec.align_mode}")
    print(f"  深度范围: {config.camera.orbbec.depth_range.min}-{config.camera.orbbec.depth_range.max}")
    
    # 检查 RealSense 配置
    print("\nRealSense 配置:")
    print(f"  分辨率: {config.camera.realsense.width}x{config.camera.realsense.height}")
    print(f"  帧率: {config.camera.realsense.fps}")
    print(f"  深度启用: {config.camera.realsense.enable_depth}")
    
    # 检查向后兼容属性
    print("\n向后兼容属性:")
    print(f"  通用宽度: {config.camera.width}")
    print(f"  通用高度: {config.camera.height}")
    print(f"  通用帧率: {config.camera.fps}")
    
    print("\n" + "=" * 60)
    print("配置解析测试通过")
    print("=" * 60)

if __name__ == "__main__":
    test_config_parsing()
