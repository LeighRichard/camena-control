"""
控制模块

提供视觉伺服所需的控制算法：
- PID 控制器：精确的位置/速度控制
- 卡尔曼滤波器：目标位置预测和平滑
- 目标跟踪器：多目标跟踪和关联
"""

from .pid import PIDController, PIDConfig, DualAxisPID
from .kalman import KalmanFilter, KalmanConfig, TargetTracker

__all__ = [
    'PIDController',
    'PIDConfig', 
    'DualAxisPID',
    'KalmanFilter',
    'KalmanConfig',
    'TargetTracker'
]
