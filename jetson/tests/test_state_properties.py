"""
状态管理模块属性测试

Property 6: 状态变化传播完整性
- 状态更新应触发监听器
- 状态历史应正确记录
"""

import pytest
import time
from hypothesis import given, strategies as st, settings
from typing import List

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from state.manager import StateManager, StateChangeEvent
from state.models import (
    SystemState, 
    MotionState, 
    DetectionState,
    DetectedTarget,
    CaptureMode,
    TargetMode
)


# ============================================================================
# Property 6: 状态变化传播完整性
# ============================================================================

class TestStateChangeNotificationProperties:
    """状态变化通知属性测试"""
    
    def test_listener_receives_all_changes(self):
        """
        Property 6.1: 监听器接收所有状态变化
        """
        manager = StateManager()
        received_events: List[StateChangeEvent] = []
        
        def listener(event: StateChangeEvent):
            received_events.append(event)
        
        manager.add_listener(listener)
        
        # 更新多个状态
        manager.update_system_state(stm32_connected=True)
        manager.update_system_state(camera_connected=True)
        manager.update_motion_state(pan_position=100)
        
        # 验证所有变化都被接收
        assert len(received_events) == 3
        assert received_events[0].path == "system.stm32_connected"
        assert received_events[1].path == "system.camera_connected"
        assert received_events[2].path == "motion.pan_position"
    
    def test_listener_receives_correct_values(self):
        """
        Property 6.2: 监听器接收正确的新旧值
        """
        manager = StateManager()
        received_events: List[StateChangeEvent] = []
        
        manager.add_listener(lambda e: received_events.append(e))
        
        # 初始值为 False，更新为 True
        manager.update_system_state(stm32_connected=True)
        
        assert len(received_events) == 1
        assert received_events[0].old_value == False
        assert received_events[0].new_value == True
    
    def test_no_notification_for_same_value(self):
        """
        Property 6.3: 相同值不触发通知
        """
        manager = StateManager()
        received_events: List[StateChangeEvent] = []
        
        manager.add_listener(lambda e: received_events.append(e))
        
        # 设置初始值
        manager.update_system_state(stm32_connected=True)
        assert len(received_events) == 1
        
        # 设置相同值
        manager.update_system_state(stm32_connected=True)
        assert len(received_events) == 1  # 不应增加
    
    def test_multiple_listeners_all_notified(self):
        """
        Property 6.4: 多个监听器都被通知
        """
        manager = StateManager()
        listener1_events = []
        listener2_events = []
        
        manager.add_listener(lambda e: listener1_events.append(e))
        manager.add_listener(lambda e: listener2_events.append(e))
        
        manager.update_system_state(stm32_connected=True)
        
        assert len(listener1_events) == 1
        assert len(listener2_events) == 1
    
    def test_removed_listener_not_notified(self):
        """
        Property 6.5: 移除的监听器不再接收通知
        """
        manager = StateManager()
        received_events = []
        
        def listener(e):
            received_events.append(e)
        
        manager.add_listener(listener)
        manager.update_system_state(stm32_connected=True)
        assert len(received_events) == 1
        
        manager.remove_listener(listener)
        manager.update_system_state(camera_connected=True)
        assert len(received_events) == 1  # 不应增加


# ============================================================================
# 状态历史记录属性测试
# ============================================================================

class TestStateHistoryProperties:
    """状态历史记录属性测试"""
    
    def test_history_records_all_changes(self):
        """历史记录所有变化"""
        manager = StateManager()
        
        manager.update_system_state(stm32_connected=True)
        manager.update_motion_state(pan_position=100)
        manager.update_motion_state(tilt_position=50)
        
        history = manager.get_history()
        assert len(history) == 3
    
    def test_history_order_is_chronological(self):
        """历史记录按时间顺序"""
        manager = StateManager()
        
        manager.update_system_state(stm32_connected=True)
        time.sleep(0.01)
        manager.update_motion_state(pan_position=100)
        
        history = manager.get_history()
        assert history[0]['timestamp'] <= history[1]['timestamp']
    
    def test_history_limit_respected(self):
        """历史记录数量限制"""
        manager = StateManager(max_history=5)
        
        # 生成超过限制的变化
        for i in range(10):
            manager.update_motion_state(pan_position=i)
        
        history = manager.get_history(limit=100)
        assert len(history) <= 5
    
    def test_history_filter_by_path(self):
        """历史记录路径过滤"""
        manager = StateManager()
        
        manager.update_system_state(stm32_connected=True)
        manager.update_motion_state(pan_position=100)
        manager.update_motion_state(tilt_position=50)
        
        motion_history = manager.get_history(path_filter="motion.")
        assert len(motion_history) == 2
        assert all(h['path'].startswith('motion.') for h in motion_history)


# ============================================================================
# 状态快照属性测试
# ============================================================================

class TestStateSnapshotProperties:
    """状态快照属性测试"""
    
    def test_full_state_contains_all_components(self):
        """完整状态包含所有组件"""
        manager = StateManager()
        state = manager.get_full_state()
        
        assert 'system' in state
        assert 'motion' in state
        assert 'detection' in state
        assert 'timestamp' in state
    
    def test_full_state_reflects_updates(self):
        """完整状态反映更新"""
        manager = StateManager()
        
        manager.update_system_state(stm32_connected=True)
        manager.update_motion_state(pan_position=100)
        
        state = manager.get_full_state()
        
        assert state['system']['stm32_connected'] == True
        assert state['motion']['pan_position'] == 100
    
    @given(
        pan=st.integers(-10000, 10000),
        tilt=st.integers(-10000, 10000),
        rail=st.integers(0, 10000)
    )
    @settings(max_examples=50)
    def test_motion_state_roundtrip(self, pan, tilt, rail):
        """运动状态往返一致性"""
        manager = StateManager()
        
        manager.update_motion_state(
            pan_position=pan,
            tilt_position=tilt,
            rail_position=rail
        )
        
        state = manager.get_full_state()
        
        assert state['motion']['pan_position'] == pan
        assert state['motion']['tilt_position'] == tilt
        assert state['motion']['rail_position'] == rail


# ============================================================================
# 目标检测状态属性测试
# ============================================================================

class TestDetectionStateProperties:
    """目标检测状态属性测试"""
    
    def test_set_targets_updates_state(self):
        """设置目标更新状态"""
        manager = StateManager()
        
        targets = [
            DetectedTarget(
                id=1, class_name='apple', confidence=0.9,
                bbox=(100, 100, 50, 50), center=(125, 125), depth=1000
            ),
            DetectedTarget(
                id=2, class_name='orange', confidence=0.8,
                bbox=(200, 200, 60, 60), center=(230, 230), depth=1500
            )
        ]
        
        manager.set_targets(targets)
        
        state = manager.get_full_state()
        assert len(state['detection']['targets']) == 2
    
    def test_select_target_updates_selected_flag(self):
        """选择目标更新选中标志"""
        manager = StateManager()
        
        targets = [
            DetectedTarget(id=1, class_name='apple', confidence=0.9,
                          bbox=(100, 100, 50, 50), center=(125, 125)),
            DetectedTarget(id=2, class_name='orange', confidence=0.8,
                          bbox=(200, 200, 60, 60), center=(230, 230))
        ]
        
        manager.set_targets(targets)
        manager.select_target(1)
        
        # 验证选中状态
        assert manager.detection_state.selected_target_id == 1
        assert manager.detection_state.targets[0].selected == True
        assert manager.detection_state.targets[1].selected == False
    
    def test_select_none_clears_selection(self):
        """选择 None 清除选中"""
        manager = StateManager()
        
        targets = [
            DetectedTarget(id=1, class_name='apple', confidence=0.9,
                          bbox=(100, 100, 50, 50), center=(125, 125))
        ]
        
        manager.set_targets(targets)
        manager.select_target(1)
        manager.select_target(None)
        
        assert manager.detection_state.selected_target_id is None
        assert manager.detection_state.targets[0].selected == False


# ============================================================================
# 线程安全属性测试
# ============================================================================

class TestThreadSafetyProperties:
    """线程安全属性测试"""
    
    def test_concurrent_updates_no_crash(self):
        """并发更新不崩溃"""
        import threading
        
        manager = StateManager()
        errors = []
        
        def update_system():
            try:
                for i in range(100):
                    manager.update_system_state(capture_count=i)
            except Exception as e:
                errors.append(e)
        
        def update_motion():
            try:
                for i in range(100):
                    manager.update_motion_state(pan_position=i)
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=update_system),
            threading.Thread(target=update_motion)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
    
    def test_concurrent_read_write_no_crash(self):
        """并发读写不崩溃"""
        import threading
        
        manager = StateManager()
        errors = []
        
        def writer():
            try:
                for i in range(100):
                    manager.update_motion_state(pan_position=i)
            except Exception as e:
                errors.append(e)
        
        def reader():
            try:
                for _ in range(100):
                    _ = manager.get_full_state()
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader)
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0


# ============================================================================
# 状态模型属性测试
# ============================================================================

class TestStateModelProperties:
    """状态模型属性测试"""
    
    def test_system_state_to_dict_complete(self):
        """SystemState.to_dict 包含所有字段"""
        state = SystemState()
        d = state.to_dict()
        
        expected_fields = [
            'stm32_connected', 'camera_connected', 'network_connected',
            'capture_mode', 'target_mode', 'estop_active', 'limit_hit',
            'error_message', 'capture_count', 'uptime'
        ]
        
        for field in expected_fields:
            assert field in d
    
    def test_motion_state_to_dict_complete(self):
        """MotionState.to_dict 包含所有字段"""
        state = MotionState()
        d = state.to_dict()
        
        expected_fields = [
            'pan_position', 'tilt_position', 'rail_position',
            'pan_target', 'tilt_target', 'rail_target',
            'is_moving', 'is_stable',
            'pan_velocity', 'tilt_velocity', 'rail_velocity'
        ]
        
        for field in expected_fields:
            assert field in d
    
    def test_detection_state_to_dict_complete(self):
        """DetectionState.to_dict 包含所有字段"""
        state = DetectionState()
        d = state.to_dict()
        
        expected_fields = ['targets', 'selected_target_id', 'fps', 'model_name']
        
        for field in expected_fields:
            assert field in d


# ============================================================================
# 状态管理器生命周期测试
# ============================================================================

class TestStateManagerLifecycleProperties:
    """状态管理器生命周期属性测试"""
    
    def test_reset_clears_all_state(self):
        """重置清除所有状态"""
        manager = StateManager()
        
        manager.update_system_state(stm32_connected=True, capture_count=10)
        manager.update_motion_state(pan_position=100)
        
        manager.reset()
        
        state = manager.get_full_state()
        assert state['system']['stm32_connected'] == False
        assert state['system']['capture_count'] == 0
        assert state['motion']['pan_position'] == 0
    
    def test_reset_clears_history(self):
        """重置清除历史"""
        manager = StateManager()
        
        manager.update_system_state(stm32_connected=True)
        assert len(manager.get_history()) > 0
        
        manager.reset()
        assert len(manager.get_history()) == 0
    
    def test_context_manager_start_stop(self):
        """上下文管理器启动和停止"""
        with StateManager() as manager:
            manager.update_system_state(stm32_connected=True)
            state = manager.get_full_state()
            assert state['system']['stm32_connected'] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
