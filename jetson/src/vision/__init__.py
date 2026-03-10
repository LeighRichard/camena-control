"""
视觉处理模块

提供图像处理、目标检测、人脸识别和视觉伺服功能：
- 目标检测器：基于 YOLO/TensorRT 的目标检测
- 人脸识别器：人脸检测与识别（带记忆功能）
- 图像处理器：图像质量评估和位置计算
- 视觉伺服控制器：相机图像辅助电机控制
"""

# 基础模块（无循环依赖）
from .detector import (
    ObjectDetector,
    DetectionConfig,
    DetectionResult,
    TargetInfo,
    SelectionStrategy,
    TENSORRT_AVAILABLE
)

from .processor import (
    ImageProcessor,
    QualityMetrics,
    PositionAdjustment,
    CameraIntrinsics
)

from .face_recognition import (
    FaceRecognizer,
    FaceRecognitionConfig,
    FaceDetectionResult,
    FaceInfo,
    FaceDatabase,
    FACE_RECOGNITION_AVAILABLE,
    INSIGHTFACE_AVAILABLE
)

# 延迟导入视觉伺服模块（避免循环导入）
def _get_visual_servo():
    """延迟导入视觉伺服模块"""
    from .visual_servo import (
        VisualServoController,
        ServoConfig,
        ServoStatus,
        ServoMode,
        TrackingState,
        TargetSwitchStrategy
    )
    return {
        'VisualServoController': VisualServoController,
        'ServoConfig': ServoConfig,
        'ServoStatus': ServoStatus,
        'ServoMode': ServoMode,
        'TrackingState': TrackingState,
        'TargetSwitchStrategy': TargetSwitchStrategy
    }


def __getattr__(name):
    """延迟加载视觉伺服相关类"""
    visual_servo_names = [
        'VisualServoController', 'ServoConfig', 'ServoStatus',
        'ServoMode', 'TrackingState', 'TargetSwitchStrategy'
    ]
    if name in visual_servo_names:
        return _get_visual_servo()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # 检测器
    "ObjectDetector",
    "DetectionConfig",
    "DetectionResult",
    "TargetInfo",
    "SelectionStrategy",
    "TENSORRT_AVAILABLE",
    # 人脸识别
    "FaceRecognizer",
    "FaceRecognitionConfig",
    "FaceDetectionResult",
    "FaceInfo",
    "FaceDatabase",
    "FACE_RECOGNITION_AVAILABLE",
    "INSIGHTFACE_AVAILABLE",
    # 处理器
    "ImageProcessor",
    "QualityMetrics",
    "PositionAdjustment",
    "CameraIntrinsics",
    # 视觉伺服（延迟加载）
    "VisualServoController",
    "ServoConfig",
    "ServoStatus",
    "ServoMode",
    "TrackingState",
    "TargetSwitchStrategy"
]
