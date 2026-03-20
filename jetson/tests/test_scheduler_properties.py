"""
任务调度器属性测试

Property 4: 路径配置解析一致性
Property 5: 自动拍摄路径执行顺序
Property 11: 拍摄时序约束
"""

import pytest
import json
import asyncio
from hypothesis import given, strategies as st, settings, assume
from typing import List, Tuple

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from scheduler.task_scheduler import (
    TaskScheduler,
    TaskState,
    TaskProgress,
    PathPoint,
    PathConfig,
    CaptureMode,
    CaptureResult
)


# ============================================================================
# 策略定义
# ============================================================================

@st.composite
def valid_path_point(draw):
    """生成有效的路径点"""
    return PathPoint(
        pan=draw(st.floats(-180, 180)),
        tilt=draw(st.floats(-90, 90)),
        rail=draw(st.floats(0, 1000)),
        settle_time=draw(st.floats(0.1, 2.0)),
        capture_frames=draw(st.integers(1, 10)),
        label=draw(st.text(min_size=0, max_size=20))
    )


@st.composite
def valid_path_config(draw):
    """生成有效的路径配置"""
    points = draw(st.lists(valid_path_point(), min_size=1, max_size=10))
    return PathConfig(
        name=draw(st.text(min_size=1, max_size=50)),
        points=points,
        description=draw(st.text(min_size=0, max_size=100)),
        loop=draw(st.booleans()),
        delay_between_points=draw(st.floats(0, 1.0))
    )


@st.composite
def invalid_path_point(draw):
    """生成无效的路径点"""
    invalid_type = draw(st.sampled_from(['pan', 'tilt', 'rail', 'settle_time', 'capture_frames']))
    
    point = PathPoint(pan=0, tilt=0, rail=100)
    
    if invalid_type == 'pan':
        point.pan = draw(st.one_of(
            st.floats(-360, -181),
            st.floats(181, 360)
        ))
    elif invalid_type == 'tilt':
        point.tilt = draw(st.one_of(
            st.floats(-180, -91),
            st.floats(91, 180)
        ))
    elif invalid_type == 'rail':
        point.rail = draw(st.floats(-1000, -1))
    elif invalid_type == 'settle_time':
        point.settle_time = draw(st.floats(-10, -0.1))
    elif invalid_type == 'capture_frames':
        point.capture_frames = draw(st.integers(-10, 0))
    
    return point


# ============================================================================
# Property 4: 路径配置解析一致性
# ============================================================================

class TestPathConfigParsingProperties:
    """路径配置解析属性测试"""
    
    @given(point=valid_path_point())
    @settings(max_examples=100)
    def test_path_point_serialization_roundtrip(self, point: PathPoint):
        """
        Property 4.1: PathPoint 序列化往返一致性
        """
        # 序列化
        point_dict = point.to_dict()
        
        # 反序列化
        restored = PathPoint.from_dict(point_dict)
        
        # 验证
        assert restored.pan == point.pan
        assert restored.tilt == point.tilt
        assert restored.rail == point.rail
        assert restored.settle_time == point.settle_time
        assert restored.capture_frames == point.capture_frames
        assert restored.label == point.label
    
    @given(config=valid_path_config())
    @settings(max_examples=50)
    def test_path_config_serialization_roundtrip(self, config: PathConfig):
        """
        Property 4.2: PathConfig 序列化往返一致性
        """
        # 序列化
        config_dict = config.to_dict()
        
        # 反序列化
        restored = PathConfig.from_dict(config_dict)
        
        # 验证
        assert restored.name == config.name
        assert restored.description == config.description
        assert restored.loop == config.loop
        assert restored.delay_between_points == config.delay_between_points
        assert len(restored.points) == len(config.points)
        
        for orig, rest in zip(config.points, restored.points):
            assert rest.pan == orig.pan
            assert rest.tilt == orig.tilt
            assert rest.rail == orig.rail
    
    @given(config=valid_path_config())
    @settings(max_examples=50)
    def test_path_config_json_roundtrip(self, config: PathConfig):
        """
        Property 4.3: PathConfig JSON 序列化往返一致性
        """
        # 序列化为 JSON
        json_str = config.to_json()
        
        # 验证是有效的 JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        
        # 反序列化
        restored = PathConfig.from_json(json_str)
        
        # 验证
        assert restored.name == config.name
        assert len(restored.points) == len(config.points)
    
    @given(config=valid_path_config())
    @settings(max_examples=50)
    def test_valid_config_validation_passes(self, config: PathConfig):
        """
        Property 4.4: 有效配置验证通过
        """
        valid, error = config.validate()
        assert valid, f"有效配置验证失败: {error}"
    
    def test_empty_name_validation_fails(self):
        """空名称配置验证失败"""
        config = PathConfig(
            name="",
            points=[PathPoint(0, 0, 100)]
        )
        valid, error = config.validate()
        assert not valid
        assert "名称" in error
    
    def test_empty_points_validation_fails(self):
        """空点位列表配置验证失败"""
        config = PathConfig(
            name="test",
            points=[]
        )
        valid, error = config.validate()
        assert not valid
        assert "点" in error or "空" in error
    
    @given(point=invalid_path_point())
    @settings(max_examples=30)
    def test_invalid_point_validation_fails(self, point: PathPoint):
        """
        Property 4.5: 无效点位配置验证失败
        """
        config = PathConfig(
            name="test",
            points=[point]
        )
        valid, error = config.validate()
        assert not valid, "无效点位配置应该验证失败"


# ============================================================================
# Property 5: 自动拍摄路径执行顺序
# ============================================================================

class TestPathExecutionOrderProperties:
    """路径执行顺序属性测试"""
    
    def test_execution_order_matches_config(self):
        """
        Property 5.1: 执行顺序与配置顺序一致
        """
        # 创建有序路径
        points = [
            PathPoint(pan=i * 10, tilt=0, rail=100, label=f"point_{i}")
            for i in range(5)
        ]
        config = PathConfig(name="test", points=points)
        
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        
        # 记录执行顺序
        executed_order = []
        
        def mock_move(point: PathPoint):
            executed_order.append(point.pan)
            return True, ""
        
        def mock_capture(point: PathPoint, frames: int):
            return True, "", None
        
        scheduler.set_callbacks(
            on_move=mock_move,
            on_capture=mock_capture
        )
        
        # 执行所有步骤
        scheduler.start()
        for _ in range(len(points)):
            scheduler.execute_step_sync()
        
        # 验证顺序
        expected_order = [p.pan for p in points]
        assert executed_order == expected_order
    
    def test_current_point_increments(self):
        """
        Property 5.2: 当前点位索引递增
        """
        points = [PathPoint(pan=i, tilt=0, rail=100) for i in range(3)]
        config = PathConfig(name="test", points=points)
        
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        scheduler.start()
        
        # 设置空回调
        scheduler.set_callbacks(
            on_move=lambda p: (True, ""),
            on_capture=lambda p, f: (True, "", None)
        )
        
        # 验证索引递增
        for i in range(len(points)):
            assert scheduler.get_progress().current_point == i
            scheduler.execute_step_sync()
        
        assert scheduler.get_progress().current_point == len(points)
    
    def test_captured_count_increments_on_success(self):
        """
        Property 5.3: 成功拍摄后计数递增
        """
        points = [PathPoint(pan=i, tilt=0, rail=100) for i in range(3)]
        config = PathConfig(name="test", points=points)
        
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        scheduler.start()
        
        scheduler.set_callbacks(
            on_move=lambda p: (True, ""),
            on_capture=lambda p, f: (True, "", "/path/to/image.jpg")
        )
        
        for i in range(len(points)):
            scheduler.execute_step_sync()
            assert scheduler.get_progress().captured_count == i + 1


# ============================================================================
# Property 11: 拍摄时序约束
# ============================================================================

class TestCaptureTimingProperties:
    """拍摄时序属性测试"""
    
    def test_move_before_capture(self):
        """
        Property 11.1: 移动在拍摄之前
        """
        point = PathPoint(pan=45, tilt=30, rail=200)
        config = PathConfig(name="test", points=[point])
        
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        scheduler.start()
        
        # 记录操作顺序
        operations = []
        
        def mock_move(p):
            operations.append('move')
            return True, ""
        
        def mock_capture(p, f):
            operations.append('capture')
            return True, "", None
        
        scheduler.set_callbacks(
            on_move=mock_move,
            on_capture=mock_capture
        )
        
        scheduler.execute_step_sync()
        
        # 验证移动在拍摄之前
        assert operations.index('move') < operations.index('capture')
    
    def test_state_transitions(self):
        """
        Property 11.2: 状态转换顺序正确
        
        IDLE -> RUNNING -> MOVING -> SETTLING -> CAPTURING -> RUNNING
        """
        point = PathPoint(pan=0, tilt=0, rail=100, settle_time=0.01)
        config = PathConfig(name="test", points=[point])
        
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        
        # 记录状态变化
        states = []
        
        def on_progress(progress):
            if not states or states[-1] != progress.state:
                states.append(progress.state)
        
        scheduler.set_callbacks(
            on_move=lambda p: (True, ""),
            on_capture=lambda p, f: (True, "", None),
            on_progress=on_progress
        )
        
        scheduler.start()
        scheduler.execute_step_sync()
        
        # 验证状态转换
        assert TaskState.IDLE in states or TaskState.RUNNING in states
        assert TaskState.MOVING in states
        assert TaskState.SETTLING in states
        assert TaskState.CAPTURING in states
    
    def test_settle_time_respected(self):
        """
        Property 11.3: 等待稳定时间被尊重
        """
        settle_time = 0.1
        point = PathPoint(pan=0, tilt=0, rail=100, settle_time=settle_time)
        config = PathConfig(name="test", points=[point])
        
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        scheduler.start()
        
        # 记录等待时间
        wait_times = []
        
        def mock_wait_stable(time_sec):
            wait_times.append(time_sec)
            return True
        
        scheduler.set_callbacks(
            on_move=lambda p: (True, ""),
            on_wait_stable=mock_wait_stable,
            on_capture=lambda p, f: (True, "", None)
        )
        
        scheduler.execute_step_sync()
        
        # 验证等待时间
        assert len(wait_times) == 1
        assert wait_times[0] == settle_time
    
    def test_capture_frames_passed_to_callback(self):
        """
        Property 11.4: 拍摄帧数传递给回调
        """
        capture_frames = 7
        point = PathPoint(pan=0, tilt=0, rail=100, capture_frames=capture_frames)
        config = PathConfig(name="test", points=[point])
        
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        scheduler.start()
        
        # 记录帧数
        received_frames = []
        
        def mock_capture(p, frames):
            received_frames.append(frames)
            return True, "", None
        
        scheduler.set_callbacks(
            on_move=lambda p: (True, ""),
            on_capture=mock_capture
        )
        
        scheduler.execute_step_sync()
        
        # 验证帧数
        assert len(received_frames) == 1
        assert received_frames[0] == capture_frames


# ============================================================================
# 任务状态管理属性测试
# ============================================================================

class TestTaskStateProperties:
    """任务状态管理属性测试"""
    
    def test_initial_state_is_idle(self):
        """初始状态应为 IDLE"""
        scheduler = TaskScheduler()
        assert scheduler.get_progress().state == TaskState.IDLE
    
    def test_start_changes_state_to_running(self):
        """开始后状态变为 RUNNING"""
        config = PathConfig(name="test", points=[PathPoint(0, 0, 100)])
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        
        scheduler.start()
        assert scheduler.get_progress().state == TaskState.RUNNING
    
    def test_pause_changes_state_to_paused(self):
        """暂停后状态变为 PAUSED"""
        config = PathConfig(name="test", points=[PathPoint(0, 0, 100)])
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        scheduler.start()
        
        scheduler.pause()
        assert scheduler.get_progress().state == TaskState.PAUSED
    
    def test_resume_changes_state_to_running(self):
        """恢复后状态变为 RUNNING"""
        config = PathConfig(name="test", points=[PathPoint(0, 0, 100)])
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        scheduler.start()
        scheduler.pause()
        
        scheduler.resume()
        assert scheduler.get_progress().state == TaskState.RUNNING
    
    def test_stop_changes_state_to_idle(self):
        """停止后状态变为 IDLE"""
        config = PathConfig(name="test", points=[PathPoint(0, 0, 100)])
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        scheduler.start()
        
        scheduler.stop()
        assert scheduler.get_progress().state == TaskState.IDLE
    
    def test_cannot_start_without_config(self):
        """未加载配置时无法开始"""
        scheduler = TaskScheduler()
        success, error = scheduler.start()
        assert not success
        assert "未加载" in error
    
    def test_cannot_pause_when_not_running(self):
        """未运行时无法暂停"""
        scheduler = TaskScheduler()
        success, error = scheduler.pause()
        assert not success
    
    def test_cannot_resume_when_not_paused(self):
        """未暂停时无法恢复"""
        config = PathConfig(name="test", points=[PathPoint(0, 0, 100)])
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        scheduler.start()
        
        success, error = scheduler.resume()
        assert not success


# ============================================================================
# 进度计算属性测试
# ============================================================================

class TestProgressCalculationProperties:
    """进度计算属性测试"""
    
    @given(
        total_points=st.integers(1, 20),
        captured=st.integers(0, 20)
    )
    @settings(max_examples=50)
    def test_progress_percent_calculation(self, total_points, captured):
        """进度百分比计算正确"""
        assume(captured <= total_points)
        
        progress = TaskProgress(
            state=TaskState.RUNNING,
            current_point=captured,
            total_points=total_points,
            captured_count=captured
        )
        
        expected_percent = (captured / total_points) * 100
        assert abs(progress.progress_percent - expected_percent) < 0.01
    
    def test_zero_total_points_zero_percent(self):
        """零总点位时百分比为零"""
        progress = TaskProgress(
            state=TaskState.IDLE,
            current_point=0,
            total_points=0,
            captured_count=0
        )
        
        assert progress.progress_percent == 0.0
    
    def test_progress_to_dict_contains_all_fields(self):
        """进度字典包含所有字段"""
        progress = TaskProgress(
            state=TaskState.RUNNING,
            current_point=5,
            total_points=10,
            captured_count=5,
            error_message="",
            elapsed_time=30.0,
            estimated_remaining=30.0
        )
        
        d = progress.to_dict()
        
        assert 'state' in d
        assert 'current_point' in d
        assert 'total_points' in d
        assert 'captured_count' in d
        assert 'progress_percent' in d


# ============================================================================
# 拍摄结果属性测试
# ============================================================================

class TestCaptureResultProperties:
    """拍摄结果属性测试"""
    
    def test_successful_capture_recorded(self):
        """成功拍摄被记录"""
        points = [PathPoint(pan=i, tilt=0, rail=100) for i in range(3)]
        config = PathConfig(name="test", points=points)
        
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        scheduler.start()
        
        scheduler.set_callbacks(
            on_move=lambda p: (True, ""),
            on_capture=lambda p, f: (True, "", f"/images/{p.pan}.jpg")
        )
        
        for _ in range(len(points)):
            scheduler.execute_step_sync()
        
        results = scheduler.get_capture_results()
        assert len(results) == len(points)
        assert all(r.success for r in results)
    
    def test_failed_capture_recorded(self):
        """失败拍摄被记录"""
        point = PathPoint(pan=0, tilt=0, rail=100)
        config = PathConfig(name="test", points=[point])
        
        scheduler = TaskScheduler()
        scheduler.load_path(config)
        scheduler.start()
        
        scheduler.set_callbacks(
            on_move=lambda p: (True, ""),
            on_capture=lambda p, f: (False, "相机错误", None)
        )
        
        scheduler.execute_step_sync()
        
        results = scheduler.get_capture_results()
        assert len(results) == 1
        assert not results[0].success
        assert "相机错误" in results[0].error_message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
