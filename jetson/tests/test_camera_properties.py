"""
相机模块属性测试

Property 8: 相机配置持久化一致性
- 配置参数设置后应能正确读取
- 配置序列化和反序列化应保持一致
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings, assume

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from camera.controller import (
    CameraConfig, 
    CameraStatus, 
    ImagePair, 
    ImageQuality,
    CameraController
)


# ============================================================================
# 策略定义
# ============================================================================

# 有效的分辨率组合
VALID_RESOLUTIONS = [
    (640, 360), (640, 480),
    (848, 480),
    (1280, 720),
    (1920, 1080)
]

# 有效的帧率
VALID_FPS = [6, 15, 30, 60]


@st.composite
def valid_camera_config(draw):
    """生成有效的相机配置"""
    width, height = draw(st.sampled_from(VALID_RESOLUTIONS))
    fps = draw(st.sampled_from(VALID_FPS))
    
    return CameraConfig(
        width=width,
        height=height,
        fps=fps,
        exposure=draw(st.integers(-1, 10000)),
        brightness=draw(st.integers(-64, 64)),
        contrast=draw(st.integers(0, 100)),
        gain=draw(st.integers(0, 128)),
        white_balance=draw(st.integers(-1, 6500)),
        auto_exposure=draw(st.booleans())
    )


@st.composite
def invalid_camera_config(draw):
    """生成无效的相机配置"""
    # 随机选择一个无效参数
    invalid_type = draw(st.sampled_from(['width', 'height', 'fps', 'brightness', 'contrast', 'gain']))
    
    config = CameraConfig()
    
    if invalid_type == 'width':
        config.width = draw(st.integers(100, 500))  # 无效宽度
    elif invalid_type == 'height':
        config.height = draw(st.integers(100, 300))  # 无效高度
    elif invalid_type == 'fps':
        config.fps = draw(st.sampled_from([1, 5, 10, 45, 90]))  # 无效帧率
    elif invalid_type == 'brightness':
        config.brightness = draw(st.one_of(
            st.integers(-200, -65),
            st.integers(65, 200)
        ))
    elif invalid_type == 'contrast':
        config.contrast = draw(st.one_of(
            st.integers(-100, -1),
            st.integers(101, 200)
        ))
    elif invalid_type == 'gain':
        config.gain = draw(st.one_of(
            st.integers(-100, -1),
            st.integers(129, 300)
        ))
    
    return config


@st.composite
def rgb_image(draw, width=640, height=480):
    """生成 RGB 图像"""
    return draw(st.from_type(np.ndarray).filter(lambda x: False)) or \
           np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)


# ============================================================================
# Property 8: 相机配置持久化一致性
# ============================================================================

class TestCameraConfigProperties:
    """相机配置属性测试"""
    
    @given(config=valid_camera_config())
    @settings(max_examples=100)
    def test_config_serialization_roundtrip(self, config: CameraConfig):
        """
        Property 8.1: 配置序列化往返一致性
        
        配置转换为字典再转回应该保持一致
        """
        # 序列化
        config_dict = config.to_dict()
        
        # 反序列化
        restored = CameraConfig.from_dict(config_dict)
        
        # 验证所有字段一致
        assert restored.width == config.width
        assert restored.height == config.height
        assert restored.fps == config.fps
        assert restored.exposure == config.exposure
        assert restored.brightness == config.brightness
        assert restored.contrast == config.contrast
        assert restored.gain == config.gain
        assert restored.white_balance == config.white_balance
        assert restored.auto_exposure == config.auto_exposure
    
    @given(config=valid_camera_config())
    @settings(max_examples=100)
    def test_valid_config_validation_passes(self, config: CameraConfig):
        """
        Property 8.2: 有效配置验证通过
        
        所有有效配置应该通过验证
        """
        valid, error = config.validate()
        assert valid, f"有效配置验证失败: {error}"
        assert error == ""
    
    @given(config=invalid_camera_config())
    @settings(max_examples=50)
    def test_invalid_config_validation_fails(self, config: CameraConfig):
        """
        Property 8.3: 无效配置验证失败
        
        无效配置应该被拒绝
        """
        valid, error = config.validate()
        assert not valid, "无效配置应该验证失败"
        assert error != "", "应该返回错误信息"
    
    @given(
        width=st.sampled_from([640, 848, 1280, 1920]),
        height=st.sampled_from([360, 480, 720, 1080]),
        fps=st.sampled_from([6, 15, 30, 60])
    )
    @settings(max_examples=50)
    def test_config_dict_contains_all_fields(self, width, height, fps):
        """
        Property 8.4: 配置字典包含所有字段
        
        to_dict() 应该包含所有配置字段
        """
        config = CameraConfig(width=width, height=height, fps=fps)
        config_dict = config.to_dict()
        
        required_fields = [
            'width', 'height', 'fps', 'exposure', 
            'brightness', 'contrast', 'gain', 
            'white_balance', 'auto_exposure'
        ]
        
        for field in required_fields:
            assert field in config_dict, f"缺少字段: {field}"


# ============================================================================
# 图像质量评估属性测试
# ============================================================================

class TestImageQualityProperties:
    """图像质量评估属性测试"""
    
    def test_dark_image_detected(self):
        """暗图像应该被检测到"""
        # 创建暗图像
        dark_image = np.full((480, 640, 3), 20, dtype=np.uint8)
        
        controller = CameraController()
        quality = controller.evaluate_image_quality(dark_image)
        
        assert quality.brightness < CameraController.MIN_BRIGHTNESS
        assert not quality.is_acceptable
        assert any("过暗" in s for s in quality.suggestions)
    
    def test_bright_image_detected(self):
        """过亮图像应该被检测到"""
        # 创建过亮图像
        bright_image = np.full((480, 640, 3), 240, dtype=np.uint8)
        
        controller = CameraController()
        quality = controller.evaluate_image_quality(bright_image)
        
        assert quality.brightness > CameraController.MAX_BRIGHTNESS
        assert not quality.is_acceptable
        assert any("过亮" in s for s in quality.suggestions)
    
    def test_normal_image_acceptable(self):
        """正常图像应该被接受"""
        # 创建有适当亮度和对比度的图像
        np.random.seed(42)
        normal_image = np.random.randint(60, 200, (480, 640, 3), dtype=np.uint8)
        
        # 添加一些边缘以提高清晰度
        normal_image[100:110, :, :] = 255
        normal_image[200:210, :, :] = 0
        normal_image[:, 100:110, :] = 255
        normal_image[:, 200:210, :] = 0
        
        controller = CameraController()
        quality = controller.evaluate_image_quality(normal_image)
        
        assert CameraController.MIN_BRIGHTNESS <= quality.brightness <= CameraController.MAX_BRIGHTNESS
        assert quality.contrast > 0
        assert quality.sharpness > 0
    
    @given(brightness_value=st.integers(0, 255))
    @settings(max_examples=50)
    def test_brightness_calculation_accuracy(self, brightness_value):
        """亮度计算应该准确"""
        # 创建均匀亮度图像
        uniform_image = np.full((100, 100, 3), brightness_value, dtype=np.uint8)
        
        controller = CameraController()
        quality = controller.evaluate_image_quality(uniform_image)
        
        # 亮度应该接近设定值
        assert abs(quality.brightness - brightness_value) < 1.0


# ============================================================================
# ImagePair 属性测试
# ============================================================================

class TestImagePairProperties:
    """图像对属性测试"""
    
    @given(
        depth_mm=st.integers(100, 10000)
    )
    @settings(max_examples=50)
    def test_depth_meters_conversion(self, depth_mm):
        """深度单位转换应该正确"""
        # 创建深度图
        depth = np.full((480, 640), depth_mm, dtype=np.uint16)
        rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        
        image_pair = ImagePair(
            rgb=rgb,
            depth=depth,
            timestamp=0.0
        )
        
        depth_m = image_pair.depth_meters
        expected_m = depth_mm / 1000.0
        
        assert np.allclose(depth_m, expected_m)
    
    def test_image_pair_with_position(self):
        """图像对应该正确存储位置信息"""
        rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        depth = np.zeros((480, 640), dtype=np.uint16)
        position = (45.0, 30.0, 100.0)
        
        image_pair = ImagePair(
            rgb=rgb,
            depth=depth,
            timestamp=1234567890.0,
            position=position
        )
        
        assert image_pair.position == position
        assert image_pair.timestamp == 1234567890.0


# ============================================================================
# CameraController 状态属性测试
# ============================================================================

class TestCameraControllerStateProperties:
    """相机控制器状态属性测试"""
    
    def test_initial_state_is_disconnected(self):
        """初始状态应该是断开连接"""
        controller = CameraController()
        assert controller.get_status() == CameraStatus.DISCONNECTED
    
    def test_default_config_is_valid(self):
        """默认配置应该有效"""
        controller = CameraController()
        config = controller.get_config()
        
        valid, error = config.validate()
        assert valid, f"默认配置无效: {error}"
    
    def test_capture_fails_when_not_ready(self):
        """未就绪时采集应该失败"""
        controller = CameraController()
        
        image_pair, error = controller.capture()
        
        assert image_pair is None
        assert "未就绪" in error
    
    def test_auto_exposure_fails_when_not_ready(self):
        """未就绪时自动曝光应该失败"""
        controller = CameraController()
        
        config, error = controller.auto_exposure_adjust()
        
        assert config is None
        assert "未就绪" in error


# ============================================================================
# 深度点查询属性测试
# ============================================================================

class TestDepthQueryProperties:
    """深度查询属性测试"""
    
    @given(
        x=st.integers(0, 639),
        y=st.integers(0, 479),
        depth_mm=st.integers(100, 10000)
    )
    @settings(max_examples=100)
    def test_depth_at_valid_point(self, x, y, depth_mm):
        """有效点的深度查询应该返回正确值"""
        depth_image = np.full((480, 640), depth_mm, dtype=np.uint16)
        
        controller = CameraController()
        depth_m = controller.get_depth_at_point(x, y, depth_image)
        
        expected_m = depth_mm / 1000.0
        assert abs(depth_m - expected_m) < 0.001
    
    @given(
        x=st.one_of(st.integers(-100, -1), st.integers(640, 1000)),
        y=st.integers(0, 479)
    )
    @settings(max_examples=50)
    def test_depth_at_invalid_x(self, x, y):
        """无效 x 坐标应该返回 0"""
        depth_image = np.full((480, 640), 1000, dtype=np.uint16)
        
        controller = CameraController()
        depth_m = controller.get_depth_at_point(x, y, depth_image)
        
        assert depth_m == 0.0
    
    @given(
        x=st.integers(0, 639),
        y=st.one_of(st.integers(-100, -1), st.integers(480, 1000))
    )
    @settings(max_examples=50)
    def test_depth_at_invalid_y(self, x, y):
        """无效 y 坐标应该返回 0"""
        depth_image = np.full((480, 640), 1000, dtype=np.uint16)
        
        controller = CameraController()
        depth_m = controller.get_depth_at_point(x, y, depth_image)
        
        assert depth_m == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
