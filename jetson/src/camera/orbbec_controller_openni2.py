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
import threading

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


# 尝试导入 openni2
try:
    import openni2
    from openni2 import openni2_c_wrapper as oni
    OPENNI2_AVAILABLE = True
except ImportError:
    OPENNI2_AVAILABLE = False
    openni2 = None
    logger.warning("openni2 模块未安装，请执行: pip install openni2")


class OrbbecControllerOpenNI2(BaseCameraController):
    """
    奥比中光相机控制器 - OpenNI2 Python
    
    使用 openni2 Python 包访问相机
    """
    
    # 相机特性常量
    MIN_STABLE_FRAMES = 3
    DEFAULT_WAIT_FRAMES = 5
    MAX_FRAME_RETRY = 3
    FRAME_TIMEOUT_MS = 1000
    
    # 默认分辨率配置
    DEFAULT_COLOR_WIDTH = 640
    DEFAULT_COLOR_HEIGHT = 480
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
        self._device = None
        self._depth_stream = None
        self._color_stream = None
        
        # 图像缓冲
        self._latest_color_image = None
        self._latest_depth_image = None
        self._lock = threading.Lock()
        
        # 采集线程
        self._capture_thread = None
        self._capturing = False
        
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
        return "orbbec-openni2"
    
    @property
    def camera_model(self) -> str:
        if self._device_info:
            return self._device_info.get('name', 'Unknown Orbbec')
        return "Orbbec Camera (OpenNI2)"
    
    def _find_openni2_path(self) -> Optional[str]:
        """查找 OpenNI2 安装路径"""
        possible_paths = [
            os.path.expanduser("~/projects/camena-control/Arm64-Release/Arm64-Release"),
            os.path.expanduser("~/OpenNI-Linux-Arm64-2.3/Redist"),
            "/usr/local/lib",
            "/usr/lib",
        ]
        
        for path in possible_paths:
            lib_path = os.path.join(path, "libOpenNI2.so")
            if os.path.exists(lib_path):
                logger.info(f"找到 OpenNI2: {path}")
                return path
        
        return None
    
    def initialize(self) -> Tuple[bool, str]:
        """初始化相机"""
        if not OPENNI2_AVAILABLE:
            return False, "openni2 模块未安装，请执行: pip install openni2"
        
        self._status = CameraStatus.INITIALIZING
        
        try:
            # 查找并初始化 OpenNI2
            openni2_path = self._find_openni2_path()
            if openni2_path:
                openni2.initialize(openni2_path)
            else:
                openni2.initialize()
            
            logger.info("✓ OpenNI2 初始化成功")
            
            # 打开设备
            self._device = openni2.Device.open_any()
            if self._device is None:
                self._status = CameraStatus.ERROR
                return False, "无法打开设备"
            
            logger.info("✓ 设备打开成功")
            
            # 获取设备信息
            try:
                device_info = self._device.get_device_info()
                self._device_info = {
                    'name': device_info.name.decode() if isinstance(device_info.name, bytes) else device_info.name,
                    'vendor': device_info.vendor.decode() if isinstance(device_info.vendor, bytes) else device_info.vendor,
                }
                logger.info(f"设备信息: {self._device_info}")
            except Exception as e:
                logger.warning(f"获取设备信息失败: {e}")
                self._device_info = {'name': 'Orbbec Camera'}
            
            # 创建深度流
            try:
                self._depth_stream = self._device.create_depth_stream()
                self._depth_stream.start()
                logger.info("✓ 深度流启动成功")
            except Exception as e:
                logger.warning(f"创建深度流失败: {e}")
                self._depth_stream = None
            
            # 创建彩色流
            try:
                self._color_stream = self._device.create_color_stream()
                self._color_stream.start()
                logger.info("✓ 彩色流启动成功")
            except Exception as e:
                logger.warning(f"创建彩色流失败: {e}")
                self._color_stream = None
            
            # 检查是否有有效流
            if self._depth_stream is None and self._color_stream is None:
                self._status = CameraStatus.ERROR
                return False, "没有可用的视频流"
            
            # 启动采集线程
            self._capturing = True
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()
            
            self._status = CameraStatus.READY
            logger.info("✓ 相机初始化成功")
            return True, ""
            
        except Exception as e:
            self._status = CameraStatus.ERROR
            self._last_error = str(e)
            logger.error(f"相机初始化失败: {e}")
            return False, str(e)
    
    def _capture_loop(self):
        """后台采集循环"""
        while self._capturing:
            try:
                # 读取深度帧
                if self._depth_stream is not None:
                    try:
                        depth_frame = self._depth_stream.read_frame()
                        if depth_frame is not None:
                            depth_data = depth_frame.get_buffer_as_uint16()
                            width = depth_frame.width
                            height = depth_frame.height
                            
                            depth_image = np.frombuffer(depth_data, dtype=np.uint16)
                            depth_image = depth_image.reshape((height, width))
                            
                            with self._lock:
                                self._latest_depth_image = depth_image.copy()
                    except Exception as e:
                        logger.debug(f"读取深度帧失败: {e}")
                
                # 读取彩色帧
                if self._color_stream is not None:
                    try:
                        color_frame = self._color_stream.read_frame()
                        if color_frame is not None:
                            color_data = color_frame.get_buffer_as_uint8()
                            width = color_frame.width
                            height = color_frame.height
                            
                            color_image = np.frombuffer(color_data, dtype=np.uint8)
                            color_image = color_image.reshape((height, width, 3))
                            
                            with self._lock:
                                self._latest_color_image = color_image.copy()
                    except Exception as e:
                        logger.debug(f"读取彩色帧失败: {e}")
                
                time.sleep(0.001)
                
            except Exception as e:
                if self._capturing:
                    logger.debug(f"采集错误: {e}")
                time.sleep(0.1)
    
    def capture(self, wait_frames: int = None, position: Tuple[float, float, float] = None) -> Tuple[Optional[ImagePair], str]:
        """采集图像"""
        if self._status != CameraStatus.READY:
            return None, f"相机未就绪，当前状态: {self._status.value}"
        
        if wait_frames is None:
            wait_frames = self.DEFAULT_WAIT_FRAMES
        
        self._status = CameraStatus.CAPTURING
        
        try:
            # 等待帧
            wait_time = wait_frames * 0.033
            time.sleep(wait_time)
            
            # 获取最新图像
            with self._lock:
                color_image = self._latest_color_image.copy() if self._latest_color_image is not None else None
                depth_image = self._latest_depth_image.copy() if self._latest_depth_image is not None else None
            
            if color_image is None and depth_image is None:
                self._status = CameraStatus.READY
                return None, "未收到图像数据"
            
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
            logger.error(f"采集图像失败: {e}")
            return None, str(e)
    
    def get_depth_at_position(self, x: int, y: int, depth_image: np.ndarray = None) -> float:
        """获取指定位置的深度值"""
        if depth_image is None:
            with self._lock:
                if self._latest_depth_image is None:
                    return 0.0
                depth_image = self._latest_depth_image
        
        if 0 <= y < depth_image.shape[0] and 0 <= x < depth_image.shape[1]:
            return float(depth_image[y, x]) / 1000.0  # mm -> m
        
        return 0.0
    
    def close(self):
        """关闭相机"""
        # 停止采集线程
        self._capturing = False
        if self._capture_thread is not None:
            try:
                self._capture_thread.join(timeout=2.0)
            except:
                pass
            self._capture_thread = None
        
        # 停止流
        if self._depth_stream is not None:
            try:
                self._depth_stream.stop()
                self._depth_stream.close()
                logger.info("深度流已关闭")
            except:
                pass
            self._depth_stream = None
        
        if self._color_stream is not None:
            try:
                self._color_stream.stop()
                self._color_stream.close()
                logger.info("彩色流已关闭")
            except:
                pass
            self._color_stream = None
        
        # 关闭设备
        if self._device is not None:
            try:
                self._device.close()
                logger.info("设备已关闭")
            except:
                pass
            self._device = None
        
        # 关闭 OpenNI2
        try:
            openni2.unload()
            logger.info("OpenNI2 已关闭")
        except:
            pass
        
        self._status = CameraStatus.DISCONNECTED
        logger.info("相机已关闭")
    
    def get_intrinsic_matrix(self) -> np.ndarray:
        """获取相机内参矩阵"""
        fx = 525.0
        fy = 525.0
        cx = self.DEFAULT_DEPTH_WIDTH / 2
        cy = self.DEFAULT_DEPTH_HEIGHT / 2
        
        return np.array([
            [fx, 0, cx],
            [0, fy, cy],
            [0, 0, 1]
        ])
    
    def get_distortion_coeffs(self) -> np.ndarray:
        """获取畸变系数"""
        return np.array([0, 0, 0, 0, 0])
    
    def configure(self, config: CameraConfig) -> Tuple[bool, str]:
        """配置相机参数"""
        self._camera_config = config
        return True, ""
    
    def get_config(self) -> CameraConfig:
        """获取当前配置"""
        return self._camera_config
    
    def get_status(self) -> str:
        """获取相机状态"""
        return self._status.value
    
    def get_intrinsics(self) -> Optional[dict]:
        """获取相机内参"""
        matrix = self.get_intrinsic_matrix()
        return {
            'fx': matrix[0, 0],
            'fy': matrix[1, 1],
            'cx': matrix[0, 2],
            'cy': matrix[1, 2],
            'coeffs': self.get_distortion_coeffs().tolist()
        }
    
    def get_depth_at_point(self, x: int, y: int, depth_image: np.ndarray = None) -> float:
        """获取指定点的深度值"""
        return self.get_depth_at_position(x, y, depth_image)
    
    def get_depth_in_region(
        self, 
        x: int, y: int, 
        width: int, height: int, 
        depth_image: np.ndarray = None,
        method: str = 'median'
    ) -> float:
        """获取区域内的深度值"""
        if depth_image is None:
            with self._lock:
                if self._latest_depth_image is None:
                    return 0.0
                depth_image = self._latest_depth_image
        
        return self._depth_processor.get_depth_in_region(
            center_x=x + width // 2,
            center_y=y + height // 2,
            width=width,
            height=height,
            depth_image=depth_image,
            method=method
        )
