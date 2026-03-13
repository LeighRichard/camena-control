"""
相机控制器抽象基类 - 定义统一的相机接口

支持多种深度相机：
- Intel RealSense 系列
- 奥比中光（Orbbec）系列
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
from dataclasses import dataclass
import numpy as np


@dataclass
class ImagePair:
    """图像对数据结构"""
    rgb: np.ndarray             # RGB 图像 (H, W, 3)
    depth: np.ndarray           # 深度图像 (H, W)，单位毫米
    timestamp: float            # 采集时间戳
    position: Optional[Tuple[float, float, float]] = None  # (pan, tilt, rail)
    
    @property
    def depth_meters(self) -> np.ndarray:
        """获取米为单位的深度图"""
        return self.depth.astype(np.float32) / 1000.0


@dataclass
class CameraConfig:
    """相机配置（通用）"""
    width: int = 1280
    height: int = 720
    fps: int = 30
    enable_depth: bool = False  # 是否启用深度流
    exposure: int = -1          # -1 表示自动曝光
    brightness: int = 0         # 亮度调节
    contrast: int = 50          # 对比度
    gain: int = 16              # 增益
    white_balance: int = -1     # -1 表示自动白平衡
    auto_exposure: bool = True
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'enable_depth': self.enable_depth,
            'exposure': self.exposure,
            'brightness': self.brightness,
            'contrast': self.contrast,
            'gain': self.gain,
            'white_balance': self.white_balance,
            'auto_exposure': self.auto_exposure
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CameraConfig':
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def validate(self) -> Tuple[bool, str]:
        """
        验证配置参数
        
        Returns:
            (是否有效, 错误信息)
        """
        errors = []
        
        # 验证分辨率
        if self.width < 320 or self.width > 4096:
            errors.append(f"宽度 {self.width} 超出有效范围 [320, 4096]")
        if self.height < 240 or self.height > 2160:
            errors.append(f"高度 {self.height} 超出有效范围 [240, 2160]")
        
        # 验证帧率
        if self.fps < 1 or self.fps > 120:
            errors.append(f"帧率 {self.fps} 超出有效范围 [1, 120]")
        
        # 验证亮度
        if self.brightness < -64 or self.brightness > 64:
            errors.append(f"亮度 {self.brightness} 超出有效范围 [-64, 64]")
        
        # 验证对比度
        if self.contrast < 0 or self.contrast > 100:
            errors.append(f"对比度 {self.contrast} 超出有效范围 [0, 100]")
        
        # 验证增益
        if self.gain < 0 or self.gain > 128:
            errors.append(f"增益 {self.gain} 超出有效范围 [0, 128]")
        
        # 验证白平衡（-1 表示自动，0 表示未设置，其他值应在有效范围内）
        # 允许 -1, 0 或 2500-6500 范围内的值
        if self.white_balance < -1 or self.white_balance > 6500:
            errors.append(f"白平衡 {self.white_balance} 超出有效范围 [-1, 6500]")
        elif self.white_balance not in [-1, 0] and self.white_balance < 2500:
            # 如果不是 -1 或 0，且小于 2500，给出警告但不报错
            pass  # 允许中间值
        
        if errors:
            return False, "; ".join(errors)
        return True, ""


class BaseCameraController(ABC):
    """
    相机控制器抽象基类
    
    定义所有深度相机必须实现的接口
    """
    
    @abstractmethod
    def initialize(self) -> Tuple[bool, str]:
        """
        初始化相机
        
        Returns:
            (成功标志, 错误信息)
        """
        pass
    
    @abstractmethod
    def capture(
        self, 
        wait_frames: int = None, 
        position: Tuple[float, float, float] = None
    ) -> Tuple[Optional[ImagePair], str]:
        """
        采集图像
        
        Args:
            wait_frames: 等待稳定的帧数
            position: 当前相机位置 (pan, tilt, rail)
            
        Returns:
            (图像对, 错误信息)
        """
        pass
    
    @abstractmethod
    def configure(self, config: CameraConfig) -> Tuple[bool, str]:
        """
        配置相机参数
        
        Args:
            config: 新的相机配置
            
        Returns:
            (成功标志, 错误信息)
        """
        pass
    
    @abstractmethod
    def get_status(self) -> str:
        """
        获取相机状态
        
        Returns:
            状态字符串
        """
        pass
    
    @abstractmethod
    def get_config(self) -> CameraConfig:
        """
        获取当前配置
        
        Returns:
            当前相机配置
        """
        pass
    
    @abstractmethod
    def get_intrinsics(self) -> Optional[dict]:
        """
        获取相机内参
        
        Returns:
            内参字典，包含 fx, fy, cx, cy, coeffs
        """
        pass
    
    @abstractmethod
    def get_depth_at_point(self, x: int, y: int, depth_image: np.ndarray) -> float:
        """
        获取指定点的深度值
        
        Args:
            x, y: 像素坐标
            depth_image: 深度图像
            
        Returns:
            深度值（米），无效返回 0
        """
        pass
    
    @abstractmethod
    def get_depth_in_region(
        self, 
        x: int, y: int, 
        width: int, height: int, 
        depth_image: np.ndarray,
        method: str = 'median'
    ) -> float:
        """
        获取区域内的深度值（带滤波）
        
        Args:
            x, y: 区域左上角坐标
            width, height: 区域尺寸
            depth_image: 深度图像
            method: 聚合方法 ('mean', 'median', 'min', 'max')
            
        Returns:
            深度值（米），无效返回 0
        """
        pass
    
    @abstractmethod
    def close(self):
        """关闭相机"""
        pass
    
    def __enter__(self):
        """上下文管理器入口"""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False
    
    @property
    @abstractmethod
    def camera_type(self) -> str:
        """
        获取相机类型
        
        Returns:
            相机类型字符串 ('realsense', 'orbbec', 等)
        """
        pass
    
    @property
    @abstractmethod
    def camera_model(self) -> str:
        """
        获取相机型号
        
        Returns:
            相机型号字符串 ('D415', 'Astra Mini', 等)
        """
        pass
