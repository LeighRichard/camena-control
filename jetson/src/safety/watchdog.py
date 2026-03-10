"""
通信看门狗实现 - 与 STM32 端逻辑一致
"""

import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class CommunicationWatchdog:
    """
    通信看门狗
    
    监控通信状态，超时后触发回调
    """
    timeout_ms: int = 1000  # 默认 1 秒超时
    enabled: bool = True
    
    def __post_init__(self):
        self._last_feed_time: float = time.time()
        self._timeout_callback: Optional[Callable[[], None]] = None
        self._is_timeout: bool = False
    
    def feed(self):
        """喂狗 - 收到有效通信时调用"""
        self._last_feed_time = time.time()
        self._is_timeout = False
    
    def check(self) -> bool:
        """
        检查是否超时
        
        Returns:
            True 如果超时
        """
        if not self.enabled:
            return False
        
        elapsed_ms = (time.time() - self._last_feed_time) * 1000
        
        if elapsed_ms > self.timeout_ms:
            if not self._is_timeout:
                self._is_timeout = True
                if self._timeout_callback:
                    self._timeout_callback()
            return True
        
        return False
    
    def set_timeout(self, timeout_ms: int):
        """设置超时时间"""
        self.timeout_ms = timeout_ms
    
    def set_callback(self, callback: Callable[[], None]):
        """设置超时回调"""
        self._timeout_callback = callback
    
    def enable(self, enabled: bool = True):
        """启用/禁用看门狗"""
        self.enabled = enabled
        if enabled:
            self._last_feed_time = time.time()
            self._is_timeout = False
    
    @property
    def is_timeout(self) -> bool:
        """是否已超时"""
        return self._is_timeout
    
    @property
    def elapsed_ms(self) -> float:
        """自上次喂狗以来的时间 (毫秒)"""
        return (time.time() - self._last_feed_time) * 1000


class WatchdogSimulator:
    """
    看门狗模拟器 - 用于属性测试
    
    使用模拟时间而非真实时间
    """
    
    def __init__(self, timeout_ms: int = 1000):
        self.timeout_ms = timeout_ms
        self.enabled = True
        self._current_time_ms: int = 0
        self._last_feed_time_ms: int = 0
        self._is_timeout: bool = False
        self._motion_stopped: bool = False
    
    def advance_time(self, delta_ms: int):
        """推进模拟时间"""
        self._current_time_ms += delta_ms
    
    def feed(self):
        """喂狗"""
        self._last_feed_time_ms = self._current_time_ms
        self._is_timeout = False
    
    def check(self) -> bool:
        """检查是否超时"""
        if not self.enabled:
            return False
        
        elapsed = self._current_time_ms - self._last_feed_time_ms
        
        if elapsed > self.timeout_ms:
            if not self._is_timeout:
                self._is_timeout = True
                self._motion_stopped = True  # 模拟停止运动
            return True
        
        return False
    
    @property
    def is_timeout(self) -> bool:
        return self._is_timeout
    
    @property
    def motion_stopped(self) -> bool:
        return self._motion_stopped
    
    def reset_motion(self):
        """重置运动状态"""
        self._motion_stopped = False
