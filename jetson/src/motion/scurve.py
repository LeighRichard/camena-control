"""
S 曲线速度规划实现 - 与 STM32 端算法一致
"""

from dataclasses import dataclass
from typing import Tuple
import math


@dataclass
class MotionProfile:
    """运动配置"""
    max_velocity: float = 1000.0
    max_accel: float = 500.0
    jerk: float = 200.0


@dataclass
class SCurvePlanner:
    """S 曲线速度规划器"""
    profile: MotionProfile = None
    
    def __post_init__(self):
        if self.profile is None:
            self.profile = MotionProfile()
        self._position = 0.0
        self._velocity = 0.0
        self._acceleration = 0.0
        self._target = 0.0
        self._direction = 1.0
        self._phase = 0
        self._complete = True
    
    def plan(self, start: float, target: float):
        """
        规划从 start 到 target 的运动
        
        Args:
            start: 起始位置
            target: 目标位置
        """
        self._position = start
        self._velocity = 0.0
        self._acceleration = 0.0
        self._target = target
        self._direction = 1.0 if target >= start else -1.0
        self._phase = 0
        self._complete = abs(target - start) < 0.1
    
    def update(self, dt: float) -> Tuple[float, float, float]:
        """
        更新规划状态
        
        Args:
            dt: 时间间隔 (秒)
            
        Returns:
            (位置, 速度, 加速度)
        """
        if self._complete:
            return self._target, 0.0, 0.0
        
        distance = abs(self._target - self._position)
        max_vel = self.profile.max_velocity
        max_acc = self.profile.max_accel
        
        # 到达目标
        if distance <= 0.5:
            self._position = self._target
            self._velocity = 0.0
            self._acceleration = 0.0
            self._complete = True
            return self._position, 0.0, 0.0
        
        current_speed = abs(self._velocity)
        
        # 计算减速距离 (v^2 / 2a)
        decel_distance = (current_speed * current_speed) / (2.0 * max_acc) if max_acc > 0 else 0
        
        # 决定加速还是减速
        if distance > decel_distance * 1.5 and current_speed < max_vel:
            # 加速阶段
            self._acceleration = max_acc
        else:
            # 减速阶段
            self._acceleration = -max_acc
        
        # 更新速度
        new_speed = current_speed + self._acceleration * dt
        
        # 速度限幅
        new_speed = max(0.0, min(new_speed, max_vel))
        
        # 更新速度 (带方向)
        self._velocity = new_speed * self._direction
        
        # 更新位置
        self._position += self._velocity * dt
        
        # 检查是否到达目标
        if (self._direction > 0 and self._position >= self._target) or \
           (self._direction < 0 and self._position <= self._target):
            self._position = self._target
            self._velocity = 0.0
            self._complete = True
        
        return self._position, self._velocity, self._acceleration
    
    @property
    def is_complete(self) -> bool:
        """是否完成"""
        return self._complete
    
    @property
    def position(self) -> float:
        """当前位置"""
        return self._position
    
    @property
    def velocity(self) -> float:
        """当前速度"""
        return self._velocity
