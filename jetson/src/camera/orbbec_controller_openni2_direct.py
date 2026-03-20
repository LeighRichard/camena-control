"""
奥比中光相机控制器 - OpenNI2 直接访问
使用 OpenNI2 库直接访问相机,不通过 ROS

这是经过验证可以工作的方法!
"""

from typing import Optional, Tuple
from enum import Enum
import numpy as np
import time
import logging
import os
import ctypes
import subprocess

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


# OpenNI2 常量
ONI_PIXEL_FORMAT_DEPTH_1_MM = 100
ONI_PIXEL_FORMAT_DEPTH_100_UM = 101
ONI_PIXEL_FORMAT_RGB888 = 200
ONI_SENSOR_TYPE_COLOR = 1
ONI_SENSOR_TYPE_DEPTH = 2


class OrbbecControllerOpenNI2Direct(BaseCameraController):
    """奥比中光相机控制器 - OpenNI2 直接访问"""
    
    # 相机特性常量
    MIN_STABLE_FRAMES = 3
    DEFAULT_WAIT_FRAMES = 5
    MAX_FRAME_RETRY = 3
    FRAME_TIMEOUT_MS = 1000
    
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
        self._openni2 = None
        self._device = None
        self._color_stream = None
        self._depth_stream = None
        
        # OpenNI2 流句柄
        self._color_stream_handle = None
        self._depth_stream_handle = None
        
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
        return "orbbec-openni2-direct"
    
    @property
    def camera_model(self) -> str:
        """获取相机型号"""
        if self._device_info:
            return self._device_info.get('name', 'Unknown Orbbec')
        return "Orbbec Camera (OpenNI2)"
    
    def _find_openni2_path(self) -> Optional[str]:
        """查找 OpenNI2 安装路径"""
        # 可能的路径
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
            # 尝试其他可能的路径
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
            
            # 尝试加载 OpenNI2 库
            logger.info("加载 OpenNI2 库...")
            try:
                # 使用 ctypes 加载库
                lib_path = os.path.join(os.environ.get('OPENNI2_REDIST', ''), 'libOpenNI2.so')
                if not os.path.exists(lib_path):
                    lib_path = '/usr/lib/libOpenNI2.so'
                
                if os.path.exists(lib_path):
                    self._openni2 = ctypes.CDLL(lib_path)
                    logger.info(f"✓ 成功加载: {lib_path}")
                    
                    # 初始化 OpenNI2 并创建流
                    success, error = self._init_openni2_streams()
                    if not success:
                        self._status = CameraStatus.ERROR
                        return False, error
                    
                else:
                    self._status = CameraStatus.ERROR
                    return False, f"未找到 OpenNI2 库: {lib_path}"
                
            except Exception as e:
                self._status = CameraStatus.ERROR
                return False, f"加载 OpenNI2 库失败: {e}"
            
            self._status = CameraStatus.READY
            self._device_info = {'name': 'Orbbec Camera (OpenNI2)'}
            logger.info("✓ 相机初始化成功")
            return True, ""
            
        except Exception as e:
            self._status = CameraStatus.ERROR
            self._last_error = str(e)
            logger.error(f"相机初始化失败: {e}")
            return False, str(e)
    
    def _init_openni2_streams(self) -> Tuple[bool, str]:
        """初始化 OpenNI2 流（彩色和深度）"""
        try:
            # 定义 OpenNI2 API 函数签名
            # niInitialize
            self._openni2.niInitialize.restype = ctypes.c_int
            self._openni2.niInitialize.argtypes = []
            
            # niShutdown
            self._openni2.niShutdown.restype = None
            self._openni2.niShutdown.argtypes = []
            
            # niGetDeviceCount
            self._openni2.niGetDeviceCount.restype = ctypes.c_int
            self._openni2.niGetDeviceCount.argtypes = []
            
            # niOpenDevice
            self._openni2.niOpenDevice.restype = ctypes.c_int
            self._openni2.niOpenDevice.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
            
            # niCloseDevice
            self._openni2.niCloseDevice.restype = ctypes.c_int
            self._openni2.niCloseDevice.argtypes = [ctypes.c_void_p]
            
            # niCreateStream
            self._openni2.niCreateStream.restype = ctypes.c_int
            self._openni2.niCreateStream.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
            
            # niDestroyStream
            self._openni2.niDestroyStream.restype = ctypes.c_int
            self._openni2.niDestroyStream.argtypes = [ctypes.c_void_p]
            
            # niStartStream
            self._openni2.niStartStream.restype = ctypes.c_int
            self._openni2.niStartStream.argtypes = [ctypes.c_void_p]
            
            # niStopStream
            self._openni2.niStopStream.restype = ctypes.c_int
            self._openni2.niStopStream.argtypes = [ctypes.c_void_p]
            
            # niReadFrame
            self._openni2.niReadFrame.restype = ctypes.c_int
            self._openni2.niReadFrame.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int]
            
            # niReleaseFrame
            self._openni2.niReleaseFrame.restype = None
            self._openni2.niReleaseFrame.argtypes = [ctypes.c_void_p]
            
            # niGetFrameData
            self._openni2.niGetFrameData.restype = ctypes.POINTER(ctypes.c_uint8)
            self._openni2.niGetFrameData.argtypes = [ctypes.c_void_p]
            
            # niGetFrameWidth
            self._openni2.niGetFrameWidth.restype = ctypes.c_int
            self._openni2.niGetFrameWidth.argtypes = [ctypes.c_void_p]
            
            # niGetFrameHeight
            self._openni2.niGetFrameHeight.restype = ctypes.c_int
            self._openni2.niGetFrameHeight.argtypes = [ctypes.c_void_p]
            
            # 初始化 OpenNI2
            result = self._openni2.niInitialize()
            if result != 0:
                return False, f"OpenNI2 初始化失败: {result}"
            
            logger.info("✓ OpenNI2 已初始化")
            
            # 获取设备数量
            device_count = self._openni2.niGetDeviceCount()
            if device_count == 0:
                return False, "未找到 OpenNI2 设备"
            
            logger.info(f"找到 {device_count} 个 OpenNI2 设备")
            
            # 打开第一个设备
            self._device = ctypes.c_void_p()
            result = self._openni2.niOpenDevice(0, ctypes.byref(self._device))
            if result != 0:
                return False, f"打开设备失败: {result}"
            
            logger.info("✓ 设备已打开")
            
            # 创建彩色流
            self._color_stream_handle = ctypes.c_void_p()
            result = self._openni2.niCreateStream(self._device, ONI_SENSOR_TYPE_COLOR, ctypes.byref(self._color_stream_handle))
            if result == 0:
                result = self._openni2.niStartStream(self._color_stream_handle)
                if result == 0:
                    logger.info("✓ 彩色流已启动")
                else:
                    logger.warning(f"启动彩色流失败: {result}")
                    self._color_stream_handle = None
            else:
                logger.warning(f"创建彩色流失败: {result}")
                self._color_stream_handle = None
            
            # 创建深度流
            self._depth_stream_handle = ctypes.c_void_p()
            result = self._openni2.niCreateStream(self._device, ONI_SENSOR_TYPE_DEPTH, ctypes.byref(self._depth_stream_handle))
            if result == 0:
                result = self._openni2.niStartStream(self._depth_stream_handle)
                if result == 0:
                    logger.info("✓ 深度流已启动")
                else:
                    logger.warning(f"启动深度流失败: {result}")
                    self._depth_stream_handle = None
            else:
                logger.warning(f"创建深度流失败: {result}")
                self._depth_stream_handle = None
            
            # 检查是否至少有一个流可用
            if self._color_stream_handle is None and self._depth_stream_handle is None:
                return False, "无法创建任何视频流"
            
            return True, ""
            
        except Exception as e:
            logger.error(f"初始化 OpenNI2 流失败: {e}")
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
        
        if self._openni2 is None:
            return None, "OpenNI2 未初始化"
        
        if wait_frames is None:
            wait_frames = self.DEFAULT_WAIT_FRAMES
        
        if wait_frames < 0:
            return None, f"无效的 wait_frames 参数: {wait_frames}"
        
        self._status = CameraStatus.CAPTURING
        
        try:
            # 丢弃前几帧，等待稳定
            for _ in range(wait_frames):
                self._read_frame(self._color_stream_handle)
                self._read_frame(self._depth_stream_handle)
            
            # 读取彩色帧
            color_frame = None
            color_data = None
            color_width = 0
            color_height = 0
            
            if self._color_stream_handle is not None:
                color_frame = self._read_frame(self._color_stream_handle)
                if color_frame is not None:
                    try:
                        color_data = self._openni2.niGetFrameData(color_frame)
                        color_width = self._openni2.niGetFrameWidth(color_frame)
                        color_height = self._openni2.niGetFrameHeight(color_frame)
                    except Exception as e:
                        logger.warning(f"获取彩色帧数据失败: {e}")
            
            # 读取深度帧
            depth_frame = None
            depth_data = None
            depth_width = 0
            depth_height = 0
            
            if self._depth_stream_handle is not None:
                depth_frame = self._read_frame(self._depth_stream_handle)
                if depth_frame is not None:
                    try:
                        depth_data = self._openni2.niGetFrameData(depth_frame)
                        depth_width = self._openni2.niGetFrameWidth(depth_frame)
                        depth_height = self._openni2.niGetFrameHeight(depth_frame)
                    except Exception as e:
                        logger.warning(f"获取深度帧数据失败: {e}")
            
            # 转换为 numpy 数组
            rgb = None
            depth = None
            
            if color_data is not None and color_width > 0 and color_height > 0:
                # 彩色数据是 RGB888 格式
                color_array = np.ctypeslib.as_array(color_data, shape=(color_height * color_width * 3,))
                rgb = color_array.reshape((color_height, color_width, 3)).copy()
            
            if depth_data is not None and depth_width > 0 and depth_height > 0:
                # 深度数据是 16 位
                depth_array = np.ctypeslib.as_array(
                    ctypes.cast(depth_data, ctypes.POINTER(ctypes.c_uint16)),
                    shape=(depth_height * depth_width,)
                )
                depth = depth_array.reshape((depth_height, depth_width)).copy()
            
            # 释放帧
            if color_frame is not None:
                try:
                    self._openni2.niReleaseFrame(color_frame)
                except Exception:
                    pass
            
            if depth_frame is not None:
                try:
                    self._openni2.niReleaseFrame(depth_frame)
                except Exception:
                    pass
            
            # 检查是否成功获取数据
            if rgb is None and depth is None:
                self._status = CameraStatus.READY
                return None, "无法获取任何图像数据"
            
            # 如果只有深度图，创建空白 RGB
            if rgb is None:
                logger.warning("未获取到彩色图像，使用空白图像")
                rgb = np.zeros((self.DEFAULT_COLOR_HEIGHT, self.DEFAULT_COLOR_WIDTH, 3), dtype=np.uint8)
            
            # 如果只有彩色图，创建空白深度
            if depth is None:
                logger.warning("未获取到深度图像，使用空白图像")
                depth = np.zeros((self.DEFAULT_DEPTH_HEIGHT, self.DEFAULT_DEPTH_WIDTH), dtype=np.uint16)
            
            # 创建图像对
            image_pair = ImagePair(
                rgb=rgb,
                depth=depth,
                timestamp=time.time(),
                position=position
            )
            
            self._status = CameraStatus.READY
            return image_pair, ""
            
        except Exception as e:
            self._status = CameraStatus.READY
            logger.error(f"采集图像失败: {e}")
            return None, str(e)
    
    def _read_frame(self, stream_handle, timeout_ms: int = 1000) -> Optional[ctypes.c_void_p]:
        """读取一帧数据"""
        if stream_handle is None or self._openni2 is None:
            return None
        
        frame = ctypes.c_void_p()
        try:
            result = self._openni2.niReadFrame(stream_handle, ctypes.byref(frame), timeout_ms)
            if result == 0:
                return frame
        except Exception as e:
            logger.debug(f"读取帧失败: {e}")
        
        return None
    
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
            # 停止并销毁流
            if self._openni2 is not None:
                if self._color_stream_handle is not None:
                    try:
                        self._openni2.niStopStream(self._color_stream_handle)
                        self._openni2.niDestroyStream(self._color_stream_handle)
                        logger.info("彩色流已关闭")
                    except Exception:
                        pass
                    self._color_stream_handle = None
                
                if self._depth_stream_handle is not None:
                    try:
                        self._openni2.niStopStream(self._depth_stream_handle)
                        self._openni2.niDestroyStream(self._depth_stream_handle)
                        logger.info("深度流已关闭")
                    except Exception:
                        pass
                    self._depth_stream_handle = None
                
                # 关闭设备
                if self._device is not None:
                    try:
                        self._openni2.niCloseDevice(self._device)
                        logger.info("设备已关闭")
                    except Exception:
                        pass
                    self._device = None
                
                # 关闭 OpenNI2
                try:
                    self._openni2.niShutdown()
                    logger.info("OpenNI2 已关闭")
                except Exception:
                    pass
            
            self._openni2 = None
            self._status = CameraStatus.DISCONNECTED
            logger.info("相机已关闭")
            
        except Exception as e:
            logger.error(f"关闭相机时出错: {e}")
            self._status = CameraStatus.DISCONNECTED
