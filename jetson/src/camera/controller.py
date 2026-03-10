"""
相机控制器模块 - 向后兼容层

为了保持向后兼容，此模块导出 RealSenseController 作为 CameraController。
新代码应该使用 factory.py 创建相机实例。
"""

from .realsense_controller import (
    RealSenseController,
    CameraStatus,
    ImageQuality,
    REALSENSE_AVAILABLE
)
from .base_controller import ImagePair, CameraConfig

# 向后兼容：导出 RealSenseController 作为 CameraController
CameraController = RealSenseController

__all__ = [
    'CameraController',
    'RealSenseController',
    'CameraStatus',
    'ImagePair',
    'ImageQuality',
    'CameraConfig',
    'REALSENSE_AVAILABLE'
]
