"""
视觉伺服控制模块

将视觉伺服功能拆分为多个子模块：
- controller: 主控制器
- tracker: 目标跟踪逻辑
- centering: 居中控制
- modes: 伺服模式和状态定义
"""

from .modes import ServoMode, TrackingState, TargetSwitchStrategy, ServoConfig, ServoStatus
from .controller import VisualServoController
from .tracker import TargetTrackingMixin
from .centering import CenteringMixin

__all__ = [
    'ServoMode',
    'TrackingState', 
    'TargetSwitchStrategy',
    'ServoConfig',
    'ServoStatus',
    'VisualServoController',
]
