"""
视觉伺服模式和状态定义

定义伺服模式、跟踪状态、配置和状态数据类
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List
from enum import Enum

from ...control.pid import PIDConfig
from ...control.kalman import KalmanConfig
from ..detector import TargetInfo
from ..processor import PositionAdjustment


class ServoMode(Enum):
    """伺服模式"""
    IDLE = "idle"                   # 空闲
    TRACKING = "tracking"           # 目标跟踪
    SCANNING = "scanning"           # 扫描寻找目标
    CENTERING = "centering"         # 居中调整
    MANUAL = "manual"               # 手动控制
    MULTI_TARGET = "multi_target"   # 多目标模式
    FACE_TRACKING = "face_tracking" # 人脸跟踪模式


class TrackingState(Enum):
    """跟踪状态"""
    NO_TARGET = "no_target"         # 无目标
    ACQUIRING = "acquiring"         # 正在捕获
    LOCKED = "locked"               # 已锁定
    LOST = "lost"                   # 目标丢失
    SWITCHING = "switching"         # 切换目标中


class TargetSwitchStrategy(Enum):
    """目标切换策略"""
    MANUAL = "manual"               # 手动切换
    NEAREST = "nearest"             # 最近优先
    LARGEST = "largest"             # 最大优先
    ROUND_ROBIN = "round_robin"     # 轮询
    PRIORITY = "priority"           # 优先级（基于类别）


@dataclass
class ServoConfig:
    """视觉伺服配置"""
    # PID 控制参数
    pan_pid: PIDConfig = field(default_factory=lambda: PIDConfig(
        kp=0.8, ki=0.1, kd=0.05,
        output_min=-30, output_max=30,
        deadband=5.0, derivative_filter=0.2
    ))
    tilt_pid: PIDConfig = field(default_factory=lambda: PIDConfig(
        kp=0.6, ki=0.08, kd=0.04,
        output_min=-20, output_max=20,
        deadband=5.0, derivative_filter=0.2
    ))
    rail_pid: PIDConfig = field(default_factory=lambda: PIDConfig(
        kp=0.3, ki=0.05, kd=0.02,
        output_min=-50, output_max=50,
        deadband=10.0
    ))
    
    # 卡尔曼滤波参数
    kalman: KalmanConfig = field(default_factory=lambda: KalmanConfig(
        process_noise_pos=1.0,
        process_noise_vel=10.0,
        measurement_noise=5.0
    ))
    
    # 死区设置（像素）
    center_tolerance: int = 30
    
    # 速度限制（度/秒 或 mm/秒）
    max_pan_speed: float = 30.0
    max_tilt_speed: float = 20.0
    max_rail_speed: float = 50.0
    
    # 跟踪参数
    lost_timeout: float = 2.0       # 目标丢失超时（秒）
    acquire_frames: int = 3         # 捕获确认帧数
    prediction_enabled: bool = True # 启用预测
    prediction_time: float = 0.1    # 预测时间（秒）
    
    # 扫描参数
    scan_pan_range: Tuple[float, float] = (-45.0, 45.0)
    scan_tilt_range: Tuple[float, float] = (-15.0, 15.0)
    scan_step: float = 10.0
    scan_dwell_time: float = 0.5
    
    # 目标距离
    target_distance: float = 500.0
    distance_tolerance: float = 50.0
    
    # 多目标参数
    switch_strategy: TargetSwitchStrategy = TargetSwitchStrategy.NEAREST
    switch_cooldown: float = 2.0    # 切换冷却时间
    priority_classes: List[str] = field(default_factory=list)
    
    # 更新频率
    update_rate: float = 15.0       # Hz
    
    # 平滑参数
    smoothing_factor: float = 0.3   # 输出平滑系数 (0-1)


@dataclass
class ServoStatus:
    """伺服状态"""
    mode: ServoMode
    tracking_state: TrackingState
    target: Optional[TargetInfo]
    adjustment: Optional[PositionAdjustment]
    fps: float
    last_update: float
    pid_error: Tuple[float, float] = (0.0, 0.0)
    predicted_position: Optional[Tuple[float, float]] = None
    tracked_targets: int = 0
