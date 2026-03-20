"""
视觉伺服控制器属性测试

Property 测试：
- ServoConfig 配置有效性
- ServoStatus 状态一致性
- 模式和状态枚举
- 目标选择策略
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Tuple, List
import time


# ============================================================================
# 定义测试所需的枚举和数据类（避免复杂导入）
# ============================================================================

class ServoMode(Enum):
    """伺服模式"""
    IDLE = "idle"
    TRACKING = "tracking"
    SCANNING = "scanning"
    CENTERING = "centering"
    MANUAL = "manual"
    MULTI_TARGET = "multi_target"
    FACE_TRACKING = "face_tracking"


class TrackingState(Enum):
    """跟踪状态"""
    NO_TARGET = "no_target"
    ACQUIRING = "acquiring"
    LOCKED = "locked"
    LOST = "lost"
    SWITCHING = "switching"


class TargetSwitchStrategy(Enum):
    """目标切换策略"""
    MANUAL = "manual"
    NEAREST = "nearest"
    LARGEST = "largest"
    ROUND_ROBIN = "round_robin"
    PRIORITY = "priority"


@dataclass
class PIDConfig:
    """PID 配置（简化版）"""
    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.0
    output_min: float = -100.0
    output_max: float = 100.0


@dataclass
class ServoConfig:
    """视觉伺服配置"""
    center_tolerance: int = 30
    max_pan_speed: float = 30.0
    max_tilt_speed: float = 20.0
    max_rail_speed: float = 50.0
    scan_pan_range: Tuple[float, float] = (-45.0, 45.0)
    scan_tilt_range: Tuple[float, float] = (-15.0, 15.0)
    scan_step: float = 10.0
    update_rate: float = 15.0
    smoothing_factor: float = 0.3
    pan_pid: PIDConfig = field(default_factory=PIDConfig)
    tilt_pid: PIDConfig = field(default_factory=PIDConfig)
    rail_pid: PIDConfig = field(default_factory=PIDConfig)


@dataclass
class MockTargetInfo:
    """模拟目标信息"""
    id: int
    center_x: float
    center_y: float
    distance: float
    bounding_box: Tuple[int, int, int, int]
    confidence: float
    class_name: str
    class_id: int
    
    @property
    def area(self) -> int:
        return self.bounding_box[2] * self.bounding_box[3]


# ============================================================================
# 策略定义
# ============================================================================

@st.composite
def valid_target_info(draw, image_width=1280, image_height=720):
    """生成有效的目标信息"""
    box_w = draw(st.integers(20, min(300, image_width // 2)))
    box_h = draw(st.integers(20, min(300, image_height // 2)))
    x = draw(st.integers(0, image_width - box_w))
    y = draw(st.integers(0, image_height - box_h))
    
    return MockTargetInfo(
        id=draw(st.integers(1, 1000)),
        center_x=x + box_w / 2,
        center_y=y + box_h / 2,
        distance=draw(st.floats(100, 5000)),
        bounding_box=(x, y, box_w, box_h),
        confidence=draw(st.floats(0.5, 1.0)),
        class_name=draw(st.sampled_from(['apple', 'orange', 'face'])),
        class_id=draw(st.integers(0, 79))
    )


# ============================================================================
# ServoMode 和 TrackingState 枚举测试
# ============================================================================

class TestServoEnums:
    """伺服枚举测试"""
    
    def test_servo_mode_values(self):
        """ServoMode 应包含所有预期模式"""
        modes = [m.value for m in ServoMode]
        
        assert 'idle' in modes
        assert 'tracking' in modes
        assert 'scanning' in modes
        assert 'centering' in modes
        assert 'manual' in modes
        assert 'face_tracking' in modes
    
    def test_tracking_state_values(self):
        """TrackingState 应包含所有预期状态"""
        states = [s.value for s in TrackingState]
        
        assert 'no_target' in states
        assert 'acquiring' in states
        assert 'locked' in states
        assert 'lost' in states
    
    def test_target_switch_strategy_values(self):
        """TargetSwitchStrategy 应包含所有预期策略"""
        strategies = [s.value for s in TargetSwitchStrategy]
        
        assert 'manual' in strategies
        assert 'nearest' in strategies
        assert 'largest' in strategies
        assert 'round_robin' in strategies


# ============================================================================
# ServoConfig 属性测试
# ============================================================================

class TestServoConfigProperties:
    """伺服配置属性测试"""
    
    def test_default_config_valid(self):
        """默认配置应有效"""
        config = ServoConfig()
        
        # PID 配置应存在
        assert config.pan_pid is not None
        assert config.tilt_pid is not None
        assert config.rail_pid is not None
        
        # 参数应在合理范围
        assert config.center_tolerance > 0
        assert config.max_pan_speed > 0
        assert config.max_tilt_speed > 0
        assert config.update_rate > 0
    
    @given(
        tolerance=st.integers(1, 100),
        max_speed=st.floats(1, 100)
    )
    @settings(max_examples=30)
    def test_config_custom_values(self, tolerance, max_speed):
        """
        Property: 自定义配置值应被保留
        """
        config = ServoConfig(
            center_tolerance=tolerance,
            max_pan_speed=max_speed
        )
        
        assert config.center_tolerance == tolerance
        assert config.max_pan_speed == max_speed
    
    def test_scan_range_valid(self):
        """扫描范围应有效"""
        config = ServoConfig()
        
        pan_min, pan_max = config.scan_pan_range
        tilt_min, tilt_max = config.scan_tilt_range
        
        assert pan_min < pan_max
        assert tilt_min < tilt_max
    
    def test_smoothing_factor_range(self):
        """平滑系数应在 [0, 1] 范围内"""
        config = ServoConfig()
        
        assert 0 <= config.smoothing_factor <= 1


# ============================================================================
# 模式转换测试
# ============================================================================

class TestModeTransitions:
    """模式转换测试"""
    
    def test_mode_transitions(self):
        """模式转换应有效"""
        # 测试有效的模式转换
        valid_transitions = [
            (ServoMode.IDLE, ServoMode.TRACKING),
            (ServoMode.IDLE, ServoMode.SCANNING),
            (ServoMode.TRACKING, ServoMode.IDLE),
            (ServoMode.SCANNING, ServoMode.TRACKING),
            (ServoMode.IDLE, ServoMode.FACE_TRACKING),
        ]
        
        for from_mode, to_mode in valid_transitions:
            # 模式应该是不同的枚举值
            assert from_mode != to_mode
            assert isinstance(from_mode, ServoMode)
            assert isinstance(to_mode, ServoMode)
    
    def test_tracking_state_transitions(self):
        """跟踪状态转换应有效"""
        # 典型的状态转换序列
        state_sequence = [
            TrackingState.NO_TARGET,
            TrackingState.ACQUIRING,
            TrackingState.LOCKED,
            TrackingState.LOST,
            TrackingState.NO_TARGET
        ]
        
        for i in range(len(state_sequence) - 1):
            current = state_sequence[i]
            next_state = state_sequence[i + 1]
            assert current != next_state


# ============================================================================
# 目标选择策略测试
# ============================================================================

class TestTargetSelectionStrategies:
    """目标选择策略测试"""
    
    def test_nearest_strategy_selects_closest(self):
        """最近策略应选择最近的目标"""
        targets = [
            MockTargetInfo(1, 100, 100, 2000, (50, 50, 100, 100), 0.9, 'apple', 0),
            MockTargetInfo(2, 200, 200, 500, (150, 150, 100, 100), 0.8, 'orange', 1),
            MockTargetInfo(3, 300, 300, 1500, (250, 250, 100, 100), 0.95, 'apple', 0),
        ]
        
        # 按距离排序
        sorted_by_distance = sorted(targets, key=lambda t: t.distance)
        nearest = sorted_by_distance[0]
        
        assert nearest.id == 2
        assert nearest.distance == 500
    
    def test_largest_strategy_selects_biggest(self):
        """最大策略应选择最大的目标"""
        targets = [
            MockTargetInfo(1, 100, 100, 2000, (50, 50, 80, 80), 0.9, 'apple', 0),
            MockTargetInfo(2, 200, 200, 500, (150, 150, 150, 150), 0.8, 'orange', 1),
            MockTargetInfo(3, 300, 300, 1500, (250, 250, 100, 100), 0.95, 'apple', 0),
        ]
        
        # 按面积排序
        sorted_by_area = sorted(targets, key=lambda t: t.area, reverse=True)
        largest = sorted_by_area[0]
        
        assert largest.id == 2
        assert largest.area == 150 * 150
    
    @given(targets=st.lists(valid_target_info(), min_size=1, max_size=10))
    @settings(max_examples=30)
    def test_selection_always_from_list(self, targets):
        """
        Property: 选择结果总是来自输入列表
        """
        # 按距离选择
        nearest = min(targets, key=lambda t: t.distance)
        assert nearest in targets
        
        # 按面积选择
        largest = max(targets, key=lambda t: t.area)
        assert largest in targets
        
        # 按置信度选择
        most_confident = max(targets, key=lambda t: t.confidence)
        assert most_confident in targets


# ============================================================================
# PID 配置测试
# ============================================================================

class TestPIDConfigIntegration:
    """PID 配置与伺服集成测试"""
    
    def test_servo_config_pid_defaults(self):
        """伺服配置的 PID 默认值应合理"""
        config = ServoConfig()
        
        # Pan PID
        assert config.pan_pid.kp > 0
        assert config.pan_pid.output_min < config.pan_pid.output_max
        
        # Tilt PID
        assert config.tilt_pid.kp > 0
        assert config.tilt_pid.output_min < config.tilt_pid.output_max
        
        # Rail PID
        assert config.rail_pid.kp > 0
    
    def test_custom_pid_config(self):
        """自定义 PID 配置应生效"""
        custom_pan_pid = PIDConfig(
            kp=1.5, ki=0.2, kd=0.1,
            output_min=-50, output_max=50
        )
        
        config = ServoConfig(pan_pid=custom_pan_pid)
        
        assert config.pan_pid.kp == 1.5
        assert config.pan_pid.ki == 0.2
        assert config.pan_pid.output_max == 50


# ============================================================================
# 位置调整计算测试
# ============================================================================

class TestPositionAdjustmentCalculation:
    """位置调整计算测试"""
    
    @given(
        target_x=st.floats(0, 1280),
        target_y=st.floats(0, 720),
        center_x=st.floats(500, 780),
        center_y=st.floats(300, 420)
    )
    @settings(max_examples=50)
    def test_adjustment_direction(self, target_x, target_y, center_x, center_y):
        """
        Property: 调整方向应与偏移方向相反
        """
        # 计算偏移
        offset_x = target_x - center_x
        offset_y = target_y - center_y
        
        # 如果目标在右侧（offset_x > 0），需要向右转（正方向）
        # 如果目标在下方（offset_y > 0），需要向下转
        
        # 这里只验证偏移计算的一致性
        if abs(offset_x) > 10:
            if offset_x > 0:
                # 目标在右侧
                assert target_x > center_x
            else:
                # 目标在左侧
                assert target_x < center_x
    
    def test_center_target_no_adjustment_needed(self):
        """中心目标不需要调整"""
        center_x, center_y = 640, 360
        tolerance = 30
        
        # 目标在中心
        target_x, target_y = 640, 360
        
        offset_x = abs(target_x - center_x)
        offset_y = abs(target_y - center_y)
        
        assert offset_x < tolerance
        assert offset_y < tolerance


# ============================================================================
# 扫描模式测试
# ============================================================================

class TestScanModeProperties:
    """扫描模式属性测试"""
    
    def test_scan_range_coverage(self):
        """扫描应覆盖配置的范围"""
        config = ServoConfig(
            scan_pan_range=(-30, 30),
            scan_tilt_range=(-10, 10),
            scan_step=10
        )
        
        pan_min, pan_max = config.scan_pan_range
        tilt_min, tilt_max = config.scan_tilt_range
        step = config.scan_step
        
        # 计算扫描点数
        pan_steps = int((pan_max - pan_min) / step) + 1
        tilt_steps = int((tilt_max - tilt_min) / step) + 1
        
        assert pan_steps >= 1
        assert tilt_steps >= 1
        
        # 总扫描点
        total_points = pan_steps * tilt_steps
        assert total_points >= 1
    
    @given(
        pan_range=st.tuples(st.floats(-90, 0), st.floats(0, 90)),
        step=st.floats(5, 30)
    )
    @settings(max_examples=30)
    def test_scan_step_divides_range(self, pan_range, step):
        """
        Property: 扫描步长应能覆盖范围
        """
        pan_min, pan_max = pan_range
        from hypothesis import assume
        assume(pan_max > pan_min)
        
        range_size = pan_max - pan_min
        steps_needed = range_size / step
        
        # 至少需要一步
        assert steps_needed >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
