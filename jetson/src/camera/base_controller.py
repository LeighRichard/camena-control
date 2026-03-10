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
