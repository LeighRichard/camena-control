"""状态管理模块 - 负责系统状态管理、变化通知和日志记录"""

from .manager import StateManager, StateChangeEvent
from .models import (
    SystemState,
    MotionState,
    DetectionState,
    DetectedTarget,
    ConnectionStatus,
    CaptureMode,
    TargetMode
)

__all__ = [
    "StateManager",
    "StateChangeEvent",
    "SystemState",
    "MotionState",
    "DetectionState",
    "DetectedTarget",
    "ConnectionStatus",
    "CaptureMode",
    "TargetMode"
]
