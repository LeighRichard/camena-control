"""
运动控制模块 - S 曲线速度规划

PID 控制器已移至 control 模块，请使用：
from control.pid import PIDController
"""

from .scurve import SCurvePlanner, MotionProfile

# 为了向后兼容，从 control 模块导入 PID
from ..control.pid import PIDController

__all__ = ["PIDController", "SCurvePlanner", "MotionProfile"]
