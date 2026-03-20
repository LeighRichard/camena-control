"""
奥比中光相机控制器 - OpenNI2 Python 绑定
使用 openni2 Python 包访问相机

需要安装: pip install openni2
"""

from typing import Optional, Tuple
from enum import Enum
import numpy as np
import time
import logging
import os

from .base_controller import BaseCameraController, ImagePair, CameraConfig
from .depth_processor import DepthProcessor

logger = logging.getLogger(__name__)


class CameraStatus(Enum):
    """相机状态"""
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    READY = "ready"
    CAPTURING = "capturing"
    ERROR = "error"


class OrbbecControllerOpenNI2Python(BaseCameraController):
    """奥比中光相机控制器 - OpenNI2 Python 绑定"""
    
    # 相机特性常量
    MIN_STABLE_FRAMES = 3
    DEFAULT_WAIT_FRAMES = 5
    
    # 默认分辨率配置
    DEFAULT_COLOR_WIDTH = 1920
    DEFAULT_COLOR_HEIGHT = 1080
    DEFAULT_DEPTH_WIDTH = 640
    DEFAULT_DEPTH_HEIGHT = 480
    DEFAULT_FPS = 30
    
    def __init__(self):
        self._status = CameraStatus.DISCONNECTED
        self._camera_config = CameraConfig(
            width=self.DEFAULT_COLOR_WIDTH,
            height=self.DEFAULT_COLOR_HEIGHT,
            fps=self.DEFAULT_FPS
        )
        self._last_error = ""
        self._device_info = {}
        
        # OpenNI2 对象
        self._openni2 = None
        self._device = None
        self._color_stream = None
        self._depth_stream = None
        
        # 创建深度处理器
        self._depth_processor = DepthProcessor(
            color_size=(self.DEFAULT_COLOR_WIDTH, self.DEFAULT_COLOR_HEIGHT),
            depth_size=(self.DEFAULT_DEPTH_WIDTH, self.DEFAULT_DEPTH_HEIGHT),
            filter_size=5,
            min_depth=0.6,
            max_depth=8.0,
        )
        logger.info(f"深度处理器已初始化: {self._depth_processor}")
    
    @property
    def camera_type(self) -> str:
        """获取相机类型"""
        return "orbbec-openni2-python"
    
    @property
    def camera_model(self) -> str:
        """获取相机型号"""
        if self._device_info:
            return self._device_info.get('name', 'Unknown Orbbec')
        return "Orbbec Camera (OpenNI2 Python)"
    
    def _find_openni2_path(self) -> Optional[str]:
        """查找 OpenNI2 安装路径"""
        possible_paths = [
            os.path.expanduser("~/OpenNI-Linux-Arm64-2.3"),
            "/usr/local/lib/OpenNI2",
            "/usr/lib/OpenNI2",
            "/opt/OpenNI2",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"找到 OpenNI2: {path}")
                return path
        
        return None
    
    def _setup_openni2_env(self) -> Tuple[bool, str]:
        """设置 OpenNI2 环境变量"""
        openni2_path = self._find_openni2_path()
        
        if not openni2_path:
            return False, "未找到 OpenNI2 安装路径"
        
        # 设置环境变量
        redist_path = os.path.join(openni2_path, "Redist")
        lib_path = os.path.join(openni2_path, "lib")
        
        if not os.path.exists(redist_path):
            redist_path = os.path.join(openni2_path, "drivers")
        
        # 设置环境变量
        os.environ['OPENNI2_REDIST'] = redist_path
        
        # 更新 LD_LIBRARY_PATH
        current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
        if lib_path not in current_ld_path:
            os.environ['LD_LIBRARY_PATH'] = f"{lib_path}:{current_ld_path}"
        
        logger.info(f"OPENNI2_REDIST: {redist_path}")
        logger.info(f"LD_LIBRARY_PATH: {os.environ['LD_LIBRARY_PATH']}")
        
        return True, ""
    
    def initialize(self) -> Tuple[bool, str]:
        """
        初始化相机
        
        Returns:
            (成功标志, 错误信息)
        """
        self._status = CameraStatus.INITIALIZING
        
        try:
            # 设置 OpenNI2 环境
            logger.info("设置 OpenNI2 环境...")
            success, error = self._setup_openni2_env()
            if not success:
                self._status = CameraStatus.ERROR
                return False, error
            
            # 尝试导入 openni2
            logger.info("导入 openni2 模块...")
            try:
                import openni2
                from openni2 import Device, VideoMode, PixelFormat
                
                # 初始化 OpenNI2
                openni2.initialize()
                logger.info("✓ OpenNI2 已初始化")
                
                # 打开设备
                logger.info("打开相机设备...")
                self._device = Device.open_any()
                
                if not self._device:
                    self._status = CameraStatus.ERROR
                    return False, "无法打开相机设备"
                
                logger.info(f"✓ 设备已打开: {self._device.get_device_info()}")
                
                # 创建深度流
                logger.info("创建深度流...")
                self._depth_stream = self._device.create_depth_stream()
                self._depth_stream.start()
                logger.info("✓ 深度流已启动")
                
                # 创建彩色流
                logger.info("创建彩色流...")
                self._color_stream = self._device.create_color_stream()
                self._color_stream.start()
                logger.info("✓ 彩色流已启动")
                
                self._openni2 = openni2
                
            except ImportError as e:
                self._status = CameraStatus.ERROR
                return False, f"无法导入 openni2 模块: {e}\n请安装: pip install openni2"
            except Exception as e:
                self._status = CameraStatus.ERROR
                return False, f"OpenNI2 初始化失败: {e}"
            
            self._status = CameraStatus.READY
            self._device_info = {
                'name': 'Orbbec Camera (OpenNI2)',
                'vendor': 'Orbbec',
            }
            
            logger.info("✓ 相机初始化成功")
            return True, ""
            
        except Exception as e:
            self._status = CameraStatus.ERROR
            self._last_error = str(e)
            logger.error(f"相机初始化失败: {e}")
            return False, str(e)
    
    def capture(self, wait_frames: int = None, position: Tuple[float, float, float] = None) -> Tuple[Optional[ImagePair], str]:
        """
        采集图像
        
        Args:
            wait_frames: 等待稳定的帧数
            position: 当前相机位置
            
        Returns:
            (图像对, 错误信息)
        """
        if self._status != CameraStatus.READY:
            return None, f"相机未就绪，当前状态: {self._status.value}"
        
        if not self._openni2 or not self._device:
            return None, "OpenNI2 未初始化"
        
        if wait_frames is None:
            wait_frames = self.DEFAULT_WAIT_FRAMES
        
        if wait_frames < 0:
            return None, f"无效的 wait_frames 参数: {wait_frames}"
        
        self._status = CameraStatus.CAPTURING
        
        try:
            # 等待稳定帧
            for _ in range(wait_frames):
                if self._depth_stream:
                    self._depth_stream.read_frame()
                if self._color_stream:
                    self._color_stream.read_frame()
            
            # 读取深度帧
            depth_image = None
            if self._depth_stream:
                depth_frame = self._depth_stream.read_frame()
                depth_data = depth_frame.get_buffer_as_uint16()
                depth_image = np.frombuffer(depth_data, dtype=np.uint16)
                depth_image = depth_image.reshape((self.DEFAULT_DEPTH_HEIGHT, self.DEFAULT_DEPTH_WIDTH)).copy()
            
            # 读取彩色帧
            color_image = None
            if self._color_stream:
                color_frame = self._color_stream.read_frame()
                color_data = color_frame.get_buffer_as_uint8()
                color_image = np.frombuffer(color_data, dtype=np.uint8)
                color_image = color_image.reshape((self.DEFAULT_COLOR_HEIGHT, self.DEFAULT_COLOR_WIDTH, 3)).copy()
            
            # 检查是否成功获取数据
            if color_image is None and depth_image is None:
                self._status = CameraStatus.READY
                return None, "无法获取任何图像数据"
            
            # 如果只有深度图，创建空白 RGB
            if color_image is None:
                logger.warning("未获取到彩色图像，使用空白图像")
                color_image = np.zeros((self.DEFAULT_COLOR_HEIGHT, self.DEFAULT_COLOR_WIDTH, 3), dtype=np.uint8)
            
            # 如果只有彩色图，创建空白深度
            if depth_image is None:
                logger.warning("未获取到深度图像，使用空白图像")
                depth_image = np.zeros((self.DEFAULT_DEPTH_HEIGHT, self.DEFAULT_DEPTH_WIDTH), dtype=np.uint16)
            
            # 创建图像对
            image_pair = ImagePair(
                rgb=color_image,
                depth=depth_image,
                timestamp=time.time(),
                position=position
            )
            
            self._status = CameraStatus.READY
            return image_pair, ""
            
        except Exception as e:
            self._status = CameraStatus.READY
            logger.error(f"图像采集失败: {e}")
            return None, str(e)
    
    def configure(self, config: CameraConfig) -> Tuple[bool, str]:
        """配置相机参数"""
        logger.info(f"相机配置已更新: {config.to_dict()}")
        return True, ""
    
    def get_status(self) -> str:
        """获取相机状态"""
        return self._status.value
    
    def get_config(self) -> CameraConfig:
        """获取当前配置"""
        return self._camera_config
    
    def get_intrinsics(self) -> Optional[dict]:
        """获取相机内参"""
        return None
    
    def get_depth_at_point(self, x: int, y: int, depth_image: np.ndarray) -> float:
        """获取指定点的深度值"""
        if depth_image is None:
            return 0.0
        return self._depth_processor.get_depth_at_color_point(
            color_x=x,
            color_y=y,
            depth_image=depth_image,
            use_filter=True
        )
    
    def get_depth_in_region(self, x: int, y: int, width: int, height: int, depth_image: np.ndarray, method: str = 'median') -> float:
        """获取区域内的深度值"""
        if depth_image is None:
            return 0.0
        
        center_x = x + width // 2
        center_y = y + height // 2
        
        depth_x, depth_y = self._depth_processor.color_to_depth_coords(center_x, center_y)
        
        scale_x = self._depth_processor.scale_x
        scale_y = self._depth_processor.scale_y
        depth_width = int(width * scale_x)
        depth_height = int(height * scale_y)
        
        return self._depth_processor.get_depth_in_region(
            center_x=depth_x,
            center_y=depth_y,
            width=depth_width,
            height=depth_height,
            depth_image=depth_image,
            method=method
        )
    
    def close(self):
        """关闭相机"""
        try:
            if self._depth_stream:
                self._depth_stream.stop()
                self._depth_stream = None
            
            if self._color_stream:
                self._color_stream.stop()
                self._color_stream = None
            
            if self._device:
                self._device.close()
                self._device = None
            
            if self._openni2:
                self._openni2.unload()
                self._openni2 = None
            
            self._status = CameraStatus.DISCONNECTED
            logger.info("相机已关闭")
            
        except Exception as e:
            logger.error(f"关闭相机时出错: {e}")
