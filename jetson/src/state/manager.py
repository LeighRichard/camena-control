"""
状态管理器模块 - 负责系统状态管理、变化通知和日志记录

实现：
- 系统状态集中管理
- 状态变化通知机制
- 状态历史记录
- 线程安全访问
"""

import threading
import time
import logging
import json
from typing import Optional, Callable, List, Dict, Any, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from queue import Queue
from datetime import datetime

from .models import SystemState, MotionState, DetectionState, DetectedTarget


class StateChangeEvent:
    """状态变化事件"""
    
    def __init__(self, path: str, old_value: Any, new_value: Any, timestamp: float = None):
        self.path = path
        self.old_value = old_value
        self.new_value = new_value
        self.timestamp = timestamp or time.time()
    
    def to_dict(self) -> dict:
        return {
            'path': self.path,
            'old_value': self._serialize(self.old_value),
            'new_value': self._serialize(self.new_value),
            'timestamp': self.timestamp
        }
    
    def _serialize(self, value: Any) -> Any:
        """序列化值"""
        if isinstance(value, Enum):
            return value.value
        return value


class StateManager:
    """
    系统状态管理器
    
    负责：
    - 维护系统各组件状态
    - 状态变化通知（支持同步和异步）
    - 日志记录
    - 状态快照和恢复
    """
    
    def __init__(self, max_history: int = 1000):
        """
        初始化状态管理器
        
        Args:
            max_history: 最大历史记录数
        """
        self._lock = threading.RLock()
        self._system_state = SystemState()
        self._motion_state = MotionState()
        self._detection_state = DetectionState()
        
        # 监听器
        self._listeners: List[Callable[[StateChangeEvent], None]] = []
        self._async_listeners: List[Callable[[StateChangeEvent], None]] = []
        
        # 事件队列（用于异步通知）
        self._event_queue: Queue = Queue()
        self._event_thread: Optional[threading.Thread] = None
        self._running = False
        
        # 日志
        self._logger = logging.getLogger("StateManager")
        
        # 历史记录
        self._state_history: List[StateChangeEvent] = []
        self._max_history = max_history
        
        # 启动时间
        self._start_time = time.time()
    
    def start(self):
        """启动异步事件处理"""
        if self._running:
            return
        
        self._running = True
        self._event_thread = threading.Thread(target=self._event_loop, daemon=True)
        self._event_thread.start()
        self._logger.info("状态管理器已启动")
    
    def stop(self):
        """停止异步事件处理"""
        self._running = False
        if self._event_thread:
            self._event_queue.put(None)  # 发送停止信号
            self._event_thread.join(timeout=1.0)
        self._logger.info("状态管理器已停止")
    
    def _event_loop(self):
        """异步事件处理循环"""
        while self._running:
            try:
                event = self._event_queue.get(timeout=0.1)
                if event is None:
                    break
                
                # 通知异步监听器
                for listener in self._async_listeners:
                    try:
                        listener(event)
                    except Exception as e:
                        self._logger.error(f"异步监听器错误: {e}")
                        
            except Exception:
                pass  # 超时，继续循环
    
    @property
    def system_state(self) -> SystemState:
        """获取系统状态"""
        with self._lock:
            return self._system_state
    
    @property
    def motion_state(self) -> MotionState:
        """获取运动状态"""
        with self._lock:
            return self._motion_state
    
    @property
    def detection_state(self) -> DetectionState:
        """获取检测状态"""
        with self._lock:
            return self._detection_state
    
    def update_system_state(self, **kwargs) -> List[StateChangeEvent]:
        """
        更新系统状态
        
        Args:
            **kwargs: 要更新的状态字段
            
        Returns:
            状态变化事件列表
        """
        events = []
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._system_state, key):
                    old_value = getattr(self._system_state, key)
                    if old_value != value:
                        setattr(self._system_state, key, value)
                        event = StateChangeEvent(f"system.{key}", old_value, value)
                        events.append(event)
                        self._process_event(event)
        return events
    
    def update_motion_state(self, **kwargs) -> List[StateChangeEvent]:
        """
        更新运动状态
        
        Args:
            **kwargs: 要更新的状态字段
            
        Returns:
            状态变化事件列表
        """
        events = []
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._motion_state, key):
                    old_value = getattr(self._motion_state, key)
                    if old_value != value:
                        setattr(self._motion_state, key, value)
                        event = StateChangeEvent(f"motion.{key}", old_value, value)
                        events.append(event)
                        self._process_event(event)
        return events
    
    def update_detection_state(self, **kwargs) -> List[StateChangeEvent]:
        """
        更新检测状态
        
        Args:
            **kwargs: 要更新的状态字段
            
        Returns:
            状态变化事件列表
        """
        events = []
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._detection_state, key):
                    old_value = getattr(self._detection_state, key)
                    if old_value != value:
                        setattr(self._detection_state, key, value)
                        event = StateChangeEvent(f"detection.{key}", old_value, value)
                        events.append(event)
                        self._process_event(event)
        return events
    
    def set_targets(self, targets: List[DetectedTarget]):
        """设置检测目标列表"""
        with self._lock:
            old_targets = self._detection_state.targets
            self._detection_state.targets = targets
            
            event = StateChangeEvent(
                "detection.targets",
                len(old_targets),
                len(targets)
            )
            self._process_event(event)
    
    def select_target(self, target_id: Optional[int]):
        """选择目标"""
        with self._lock:
            old_id = self._detection_state.selected_target_id
            self._detection_state.selected_target_id = target_id
            
            # 更新目标的 selected 标志
            for target in self._detection_state.targets:
                target.selected = (target.id == target_id)
            
            if old_id != target_id:
                event = StateChangeEvent("detection.selected_target_id", old_id, target_id)
                self._process_event(event)
    
    def _process_event(self, event: StateChangeEvent):
        """处理状态变化事件"""
        # 记录历史
        self._state_history.append(event)
        if len(self._state_history) > self._max_history:
            self._state_history = self._state_history[-self._max_history:]
        
        # 日志
        self._logger.debug(f"状态变化: {event.path} = {event.new_value}")
        
        # 同步通知
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                self._logger.error(f"监听器回调错误: {e}")
        
        # 异步通知
        if self._running:
            self._event_queue.put(event)
    
    def add_listener(self, callback: Callable[[StateChangeEvent], None], async_mode: bool = False):
        """
        添加状态变化监听器
        
        Args:
            callback: 回调函数
            async_mode: 是否异步模式
        """
        with self._lock:
            if async_mode:
                self._async_listeners.append(callback)
            else:
                self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[StateChangeEvent], None]):
        """移除状态变化监听器"""
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)
            if callback in self._async_listeners:
                self._async_listeners.remove(callback)
    
    def get_full_state(self) -> Dict[str, Any]:
        """获取完整状态快照"""
        with self._lock:
            # 更新运行时间
            self._system_state.uptime = time.time() - self._start_time
            
            return {
                "system": self._system_state.to_dict(),
                "motion": self._motion_state.to_dict(),
                "detection": self._detection_state.to_dict(),
                "timestamp": time.time(),
                "datetime": datetime.now().isoformat()
            }
    
    def get_history(self, limit: int = 100, path_filter: str = None) -> List[Dict[str, Any]]:
        """
        获取状态变化历史
        
        Args:
            limit: 返回记录数限制
            path_filter: 路径过滤（如 "motion." 只返回运动相关）
            
        Returns:
            历史记录列表
        """
        with self._lock:
            history = self._state_history[-limit:]
            
            if path_filter:
                history = [e for e in history if e.path.startswith(path_filter)]
            
            return [e.to_dict() for e in history]
    
    def get_state_json(self) -> str:
        """获取状态的 JSON 字符串"""
        return json.dumps(self.get_full_state(), ensure_ascii=False, indent=2)
    
    def reset(self):
        """重置所有状态"""
        with self._lock:
            self._system_state = SystemState()
            self._motion_state = MotionState()
            self._detection_state = DetectionState()
            self._state_history.clear()
            self._start_time = time.time()
            self._logger.info("状态已重置")
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.stop()
        return False
