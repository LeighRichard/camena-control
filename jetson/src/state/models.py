"""
状态模型定义 - 定义系统各组件的状态数据结构
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class ConnectionStatus(Enum):
    """连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class CaptureMode(Enum):
    """拍摄模式"""
    IDLE = "idle"
    MANUAL = "manual"
    AUTO = "auto"
    PAUSED = "paused"


class TargetMode(Enum):
    """目标选择模式"""
    AUTO = "auto"
    MANUAL = "manual"


@dataclass
class SystemState:
    """系统状态"""
    # 连接状态
    stm32_connected: bool = False
    camera_connected: bool = False
    network_connected: bool = False
    
    # 工作模式
    capture_mode: CaptureMode = CaptureMode.IDLE
    target_mode: TargetMode = TargetMode.AUTO
    
    # 安全状态
    estop_active: bool = False
    limit_hit: bool = False
    error_message: str = ""
    
    # 统计信息
    capture_count: int = 0
    uptime: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "stm32_connected": self.stm32_connected,
            "camera_connected": self.camera_connected,
            "network_connected": self.network_connected,
            "capture_mode": self.capture_mode.value,
            "target_mode": self.target_mode.value,
            "estop_active": self.estop_active,
            "limit_hit": self.limit_hit,
            "error_message": self.error_message,
            "capture_count": self.capture_count,
            "uptime": self.uptime
        }


@dataclass
class MotionState:
    """运动状态"""
    # 当前位置 (步数)
    pan_position: int = 0
    tilt_position: int = 0
    rail_position: int = 0
    
    # 目标位置
    pan_target: int = 0
    tilt_target: int = 0
    rail_target: int = 0
    
    # 运动状态
    is_moving: bool = False
    is_stable: bool = True
    
    # 速度信息
    pan_velocity: float = 0.0
    tilt_velocity: float = 0.0
    rail_velocity: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "pan_position": self.pan_position,
            "tilt_position": self.tilt_position,
            "rail_position": self.rail_position,
            "pan_target": self.pan_target,
            "tilt_target": self.tilt_target,
            "rail_target": self.rail_target,
            "is_moving": self.is_moving,
            "is_stable": self.is_stable,
            "pan_velocity": self.pan_velocity,
            "tilt_velocity": self.tilt_velocity,
            "rail_velocity": self.rail_velocity
        }


@dataclass
class DetectedTarget:
    """检测到的目标"""
    id: int
    class_name: str
    confidence: float
    bbox: tuple  # (x, y, w, h)
    center: tuple  # (cx, cy)
    depth: float = 0.0
    selected: bool = False


@dataclass
class DetectionState:
    """目标检测状态"""
    targets: List[DetectedTarget] = field(default_factory=list)
    selected_target_id: Optional[int] = None
    fps: float = 0.0
    model_name: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "targets": [
                {
                    "id": t.id,
                    "class_name": t.class_name,
                    "confidence": t.confidence,
                    "bbox": t.bbox,
                    "center": t.center,
                    "depth": t.depth,
                    "selected": t.selected
                }
                for t in self.targets
            ],
            "selected_target_id": self.selected_target_id,
            "fps": self.fps,
            "model_name": self.model_name
        }
