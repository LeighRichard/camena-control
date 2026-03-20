"""
视觉模块属性测试

Property 12: 目标位置计算一致性
- 像素偏移应正确转换为角度调整
- 目标选择策略应一致
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings, assume
import math

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vision.detector import (
    ObjectDetector,
    DetectionConfig,
    DetectionResult,
    TargetInfo,
    SelectionStrategy
)
from vision.processor import (
    ImageProcessor,
    PositionAdjustment,
    QualityMetrics,
    CameraIntrinsics
)


# ============================================================================
# 策略定义
# ============================================================================

@st.composite
def valid_target_info(draw, image_width=1280, image_height=720):
    """生成有效的目标信息"""
    # 边界框
    box_w = draw(st.integers(20, min(300, image_width // 2)))
    box_h = draw(st.integers(20, min(300, image_height // 2)))
    x = draw(st.integers(0, image_width - box_w))
    y = draw(st.integers(0, image_height - box_h))
    
    center_x = x + box_w / 2
    center_y = y + box_h / 2
    
    return TargetInfo(
        id=draw(st.integers(1, 1000)),
        center_x=center_x,
        center_y=center_y,
        distance=draw(st.floats(100, 5000)),
        bounding_box=(x, y, box_w, box_h),
        confidence=draw(st.floats(0.5, 1.0)),
        class_name=draw(st.sampled_from(['apple', 'orange', 'tomato', 'pepper'])),
        class_id=draw(st.integers(0, 79))
    )


@st.composite
def pixel_position(draw, width=1280, height=720):
    """生成像素位置"""
    return (
        draw(st.floats(0, width)),
        draw(st.floats(0, height))
    )


# ============================================================================
# Property 12: 目标位置计算一致性
# ============================================================================

class TestPositionCalculationProperties:
    """位置计算属性测试"""
    
    @given(
        target_x=st.floats(0, 1280),
        target_y=st.floats(0, 720)
    )
    @settings(max_examples=100)
    def test_center_target_no_adjustment(self, target_x, target_y):
        """
        Property 12.1: 中心目标无需调整
        
        当目标在图像中心容差范围内时，不应产生调整
        """
        processor = ImageProcessor(1280, 720)
        tolerance = 50
        
        # 如果目标在中心容差范围内
        center_x, center_y = 640, 360
        if abs(target_x - center_x) < tolerance and abs(target_y - center_y) < tolerance:
            adjustment = processor.calculate_position_adjustment(
                target_x, target_y, tolerance_pixels=tolerance
            )
            assert adjustment.target_in_center
            assert adjustment.pan_delta == 0.0
            assert adjustment.tilt_delta == 0.0
    
    @given(
        offset_x=st.floats(-500, 500),
        offset_y=st.floats(-300, 300)
    )
    @settings(max_examples=100)
    def test_adjustment_direction_consistency(self, offset_x, offset_y):
        """
        Property 12.2: 调整方向一致性
        
        - 目标在右侧 -> pan_delta > 0
        - 目标在左侧 -> pan_delta < 0
        - 目标在上方 -> tilt_delta > 0
        - 目标在下方 -> tilt_delta < 0
        """
        processor = ImageProcessor(1280, 720)
        
        center_x, center_y = 640, 360
        target_x = center_x + offset_x
        target_y = center_y + offset_y
        
        # 确保不在中心容差范围内
        assume(abs(offset_x) >= 50 or abs(offset_y) >= 50)
        
        adjustment = processor.calculate_position_adjustment(
            target_x, target_y, tolerance_pixels=50
        )
        
        if abs(offset_x) >= 50:
            if offset_x > 0:
                assert adjustment.pan_delta > 0, "目标在右侧，pan_delta 应为正"
            else:
                assert adjustment.pan_delta < 0, "目标在左侧，pan_delta 应为负"
        
        if abs(offset_y) >= 50:
            if offset_y > 0:
                assert adjustment.tilt_delta < 0, "目标在下方，tilt_delta 应为负"
            else:
                assert adjustment.tilt_delta > 0, "目标在上方，tilt_delta 应为正"
    
    @given(
        offset=st.floats(100, 500)
    )
    @settings(max_examples=50)
    def test_adjustment_magnitude_proportional(self, offset):
        """
        Property 12.3: 调整量与偏移成正比
        
        更大的像素偏移应产生更大的角度调整
        """
        processor = ImageProcessor(1280, 720)
        
        center_x, center_y = 640, 360
        
        # 小偏移
        adj_small = processor.calculate_position_adjustment(
            center_x + offset / 2, center_y, tolerance_pixels=10
        )
        
        # 大偏移
        adj_large = processor.calculate_position_adjustment(
            center_x + offset, center_y, tolerance_pixels=10
        )
        
        assert abs(adj_large.pan_delta) > abs(adj_small.pan_delta)
    
    @given(
        target_x=st.floats(100, 1180),
        target_y=st.floats(100, 620)
    )
    @settings(max_examples=100)
    def test_adjustment_within_fov(self, target_x, target_y):
        """
        Property 12.4: 调整量在视场角范围内
        
        计算的角度调整不应超过相机视场角
        """
        processor = ImageProcessor(1280, 720)
        
        adjustment = processor.calculate_position_adjustment(
            target_x, target_y, tolerance_pixels=10
        )
        
        # D415 视场角
        fov_h, fov_v = 69.4, 42.5
        
        assert abs(adjustment.pan_delta) <= fov_h / 2 + 1  # 允许小误差
        assert abs(adjustment.tilt_delta) <= fov_v / 2 + 1


# ============================================================================
# 目标选择策略属性测试
# ============================================================================

class TestTargetSelectionProperties:
    """目标选择策略属性测试"""
    
    def test_nearest_selects_closest(self):
        """最近优先策略应选择距离最近的目标"""
        targets = [
            TargetInfo(1, 100, 100, 2000, (50, 50, 100, 100), 0.9, 'apple', 0),
            TargetInfo(2, 200, 200, 1000, (150, 150, 100, 100), 0.8, 'orange', 1),
            TargetInfo(3, 300, 300, 3000, (250, 250, 100, 100), 0.95, 'tomato', 2),
        ]
        
        detector = ObjectDetector()
        selected = detector.select_target(targets, SelectionStrategy.NEAREST)
        
        assert selected is not None
        assert selected.id == 2  # 距离 1000，最近
    
    def test_largest_selects_biggest(self):
        """最大优先策略应选择面积最大的目标"""
        targets = [
            TargetInfo(1, 100, 100, 2000, (50, 50, 100, 100), 0.9, 'apple', 0),  # 10000
            TargetInfo(2, 200, 200, 1000, (150, 150, 150, 150), 0.8, 'orange', 1),  # 22500
            TargetInfo(3, 300, 300, 3000, (250, 250, 80, 80), 0.95, 'tomato', 2),  # 6400
        ]
        
        detector = ObjectDetector()
        selected = detector.select_target(targets, SelectionStrategy.LARGEST)
        
        assert selected is not None
        assert selected.id == 2  # 面积 22500，最大
    
    def test_center_selects_closest_to_center(self):
        """中心优先策略应选择最接近图像中心的目标"""
        # 图像中心 (640, 360)
        targets = [
            TargetInfo(1, 100, 100, 2000, (50, 50, 100, 100), 0.9, 'apple', 0),
            TargetInfo(2, 650, 370, 1000, (600, 320, 100, 100), 0.8, 'orange', 1),  # 最接近中心
            TargetInfo(3, 1000, 500, 3000, (950, 450, 100, 100), 0.95, 'tomato', 2),
        ]
        
        detector = ObjectDetector()
        selected = detector.select_target(targets, SelectionStrategy.CENTER, (640, 360))
        
        assert selected is not None
        assert selected.id == 2  # 最接近中心
    
    def test_confidence_selects_highest(self):
        """置信度优先策略应选择置信度最高的目标"""
        targets = [
            TargetInfo(1, 100, 100, 2000, (50, 50, 100, 100), 0.7, 'apple', 0),
            TargetInfo(2, 200, 200, 1000, (150, 150, 100, 100), 0.8, 'orange', 1),
            TargetInfo(3, 300, 300, 3000, (250, 250, 100, 100), 0.95, 'tomato', 2),
        ]
        
        detector = ObjectDetector()
        selected = detector.select_target(targets, SelectionStrategy.CONFIDENCE)
        
        assert selected is not None
        assert selected.id == 3  # 置信度 0.95，最高
    
    def test_empty_targets_returns_none(self):
        """空目标列表应返回 None"""
        detector = ObjectDetector()
        
        for strategy in SelectionStrategy:
            selected = detector.select_target([], strategy)
            assert selected is None
    
    @given(targets=st.lists(valid_target_info(), min_size=1, max_size=10))
    @settings(max_examples=50)
    def test_selection_always_returns_from_list(self, targets):
        """
        Property: 选择结果总是来自输入列表
        """
        detector = ObjectDetector()
        
        for strategy in SelectionStrategy:
            selected = detector.select_target(targets, strategy)
            assert selected is None or selected in targets


# ============================================================================
# 检测配置属性测试
# ============================================================================

class TestDetectionConfigProperties:
    """检测配置属性测试"""
    
    @given(
        threshold=st.floats(0.1, 0.9),
        nms_threshold=st.floats(0.1, 0.9)
    )
    @settings(max_examples=50)
    def test_config_serialization_roundtrip(self, threshold, nms_threshold):
        """配置序列化往返一致性"""
        config = DetectionConfig(
            model_path="/path/to/model.engine",
            threshold=threshold,
            nms_threshold=nms_threshold,
            target_classes=['apple', 'orange'],
            selection_strategy=SelectionStrategy.NEAREST
        )
        
        config_dict = config.to_dict()
        restored = DetectionConfig.from_dict(config_dict)
        
        assert restored.threshold == config.threshold
        assert restored.nms_threshold == config.nms_threshold
        assert restored.target_classes == config.target_classes
        assert restored.selection_strategy == config.selection_strategy


# ============================================================================
# TargetInfo 属性测试
# ============================================================================

class TestTargetInfoProperties:
    """目标信息属性测试"""
    
    @given(target=valid_target_info())
    @settings(max_examples=50)
    def test_area_calculation(self, target):
        """面积计算应正确"""
        x, y, w, h = target.bounding_box
        assert target.area == w * h
    
    @given(target=valid_target_info())
    @settings(max_examples=50)
    def test_x1y1x2y2_conversion(self, target):
        """坐标格式转换应正确"""
        x, y, w, h = target.bounding_box
        x1, y1, x2, y2 = target.x1y1x2y2
        
        assert x1 == x
        assert y1 == y
        assert x2 == x + w
        assert y2 == y + h
    
    @given(target=valid_target_info())
    @settings(max_examples=50)
    def test_to_dict_contains_all_fields(self, target):
        """to_dict 应包含所有字段"""
        d = target.to_dict()
        
        assert 'id' in d
        assert 'center_x' in d
        assert 'center_y' in d
        assert 'distance' in d
        assert 'bounding_box' in d
        assert 'confidence' in d
        assert 'class_name' in d
        assert 'class_id' in d


# ============================================================================
# 图像质量评估属性测试
# ============================================================================

class TestImageQualityProperties:
    """图像质量评估属性测试"""
    
    def test_dark_image_low_brightness(self):
        """暗图像应有低亮度评分"""
        processor = ImageProcessor()
        dark_image = np.full((480, 640, 3), 20, dtype=np.uint8)
        
        quality = processor.evaluate_quality(dark_image)
        
        assert quality.brightness_score < 0.5
    
    def test_bright_image_low_brightness(self):
        """过亮图像应有低亮度评分"""
        processor = ImageProcessor()
        bright_image = np.full((480, 640, 3), 240, dtype=np.uint8)
        
        quality = processor.evaluate_quality(bright_image)
        
        assert quality.brightness_score < 0.5
    
    def test_uniform_image_low_contrast(self):
        """均匀图像应有低对比度评分"""
        processor = ImageProcessor()
        uniform_image = np.full((480, 640, 3), 128, dtype=np.uint8)
        
        quality = processor.evaluate_quality(uniform_image)
        
        assert quality.contrast_score < 0.1
    
    @given(brightness=st.integers(100, 160))
    @settings(max_examples=30)
    def test_mid_brightness_high_score(self, brightness):
        """中等亮度应有较高亮度评分"""
        processor = ImageProcessor()
        image = np.full((480, 640, 3), brightness, dtype=np.uint8)
        
        quality = processor.evaluate_quality(image)
        
        # 接近 128 的亮度应有较高评分
        assert quality.brightness_score > 0.5


# ============================================================================
# 3D 坐标转换属性测试
# ============================================================================

class TestCoordinateConversionProperties:
    """坐标转换属性测试"""
    
    def test_center_pixel_zero_xy(self):
        """图像中心像素应对应 X=0, Y=0"""
        processor = ImageProcessor(1280, 720)
        
        x, y, z = processor.pixel_to_3d(640, 360, 1000)
        
        assert abs(x) < 1  # 允许小误差
        assert abs(y) < 1
        assert z == 1000
    
    @given(
        depth=st.floats(100, 5000)
    )
    @settings(max_examples=50)
    def test_depth_preserved(self, depth):
        """深度值应保持不变"""
        processor = ImageProcessor(1280, 720)
        
        x, y, z = processor.pixel_to_3d(640, 360, depth)
        
        assert z == depth
    
    @given(
        pixel_x=st.floats(0, 1280),
        pixel_y=st.floats(0, 720)
    )
    @settings(max_examples=50)
    def test_angle_within_fov(self, pixel_x, pixel_y):
        """角度应在视场角范围内"""
        processor = ImageProcessor(1280, 720)
        
        angle_h, angle_v = processor.pixel_to_angle(pixel_x, pixel_y)
        
        # D415 视场角
        assert abs(angle_h) <= 35  # 约 FOV/2
        assert abs(angle_v) <= 22


# ============================================================================
# ObjectDetector 状态属性测试
# ============================================================================

class TestObjectDetectorStateProperties:
    """目标检测器状态属性测试"""
    
    def test_initial_state_not_loaded(self):
        """初始状态应为未加载"""
        detector = ObjectDetector()
        assert not detector.is_loaded()
    
    def test_simulation_mode_after_load_without_model(self):
        """无模型加载后应进入模拟模式"""
        detector = ObjectDetector()
        success, error = detector.load_model()
        
        assert success
        assert detector.is_loaded()
        assert detector.is_simulation_mode()
    
    def test_detect_returns_result_in_simulation(self):
        """模拟模式下检测应返回结果"""
        detector = ObjectDetector()
        detector.load_model()
        
        image = np.random.randint(0, 256, (720, 1280, 3), dtype=np.uint8)
        result = detector.detect(image)
        
        assert isinstance(result, DetectionResult)
        assert result.inference_time >= 0
    
    def test_unload_resets_state(self):
        """卸载应重置状态"""
        detector = ObjectDetector()
        detector.load_model()
        assert detector.is_loaded()
        
        detector.unload()
        assert not detector.is_loaded()
        assert not detector.is_simulation_mode()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
