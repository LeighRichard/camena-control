"""
奥比中光相机控制器 - OpenNI2 Python 绑定
使用 Arm64-Release 中已验证的 OpenNI2 库

参考 SimpleViewer 示例实现
"""

from typing import Optional, Tuple
from enum import Enum
import numpy as np
import time
import logging
import os
import ctypes
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


class OrbbecControllerOpenNI2(BaseCameraController):
    """
    奥比中光相机控制器 - OpenNI2
    
    使用 ctypes 直接调用 OpenNI2 C API
    参考 Arm64-Release/SimpleViewer 示例
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
        
        # OpenNI2 句柄
        self._lib = None
        self._device_handle = None
        self._color_stream = None
        self._depth_stream = None
        self._color_frame = None
        self._depth_frame = None
        
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
    
    def _find_openni2_library(self) -> Optional[str]:
        """查找 OpenNI2 库路径"""
        # 优先使用 Arm64-Release 中的库
        possible_paths = [
            # 项目中的 Arm64-Release
            os.path.expanduser("~/projects/camena-control/Arm64-Release/Arm64-Release/libOpenNI2.so"),
            # 标准安装路径
            os.path.expanduser("~/OpenNI-Linux-Arm64-2.3/Redist/libOpenNI2.so"),
            "/usr/local/lib/libOpenNI2.so",
            "/usr/lib/libOpenNI2.so",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"找到 OpenNI2 库: {path}")
                return path
        
        return None
    
    def _find_drivers_path(self) -> Optional[str]:
        """查找 OpenNI2 驱动路径"""
        possible_paths = [
            os.path.expanduser("~/projects/camena-control/Arm64-Release/Arm64-Release/OpenNI2/Drivers"),
            os.path.expanduser("~/OpenNI-Linux-Arm64-2.3/Redist/OpenNI2/Drivers"),
            "/usr/local/lib/OpenNI2/Drivers",
            "/usr/lib/OpenNI2/Drivers",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"找到 OpenNI2 驱动: {path}")
                return path
        
        return None
    
    def _setup_environment(self) -> Tuple[bool, str]:
        """设置 OpenNI2 环境变量"""
        lib_path = self._find_openni2_library()
        if not lib_path:
            return False, "未找到 OpenNI2 库"
        
        drivers_path = self._find_drivers_path()
        if not drivers_path:
            return False, "未找到 OpenNI2 驱动"
        
        # 设置 OPENNI2_REDIST 环境变量
        redist_path = os.path.dirname(lib_path)
        os.environ['OPENNI2_REDIST'] = redist_path
        
        # 更新 LD_LIBRARY_PATH
        lib_dir = os.path.dirname(lib_path)
        current_ld = os.environ.get('LD_LIBRARY_PATH', '')
        if lib_dir not in current_ld:
            os.environ['LD_LIBRARY_PATH'] = f"{lib_dir}:{current_ld}"
        
        logger.info(f"OPENNI2_REDIST: {redist_path}")
        logger.info(f"Drivers: {drivers_path}")
        
        return True, ""
    
    def initialize(self) -> Tuple[bool, str]:
        """初始化相机"""
        self._status = CameraStatus.INITIALIZING
        
        try:
            # 设置环境
            logger.info("设置 OpenNI2 环境...")
            success, error = self._setup_environment()
            if not success:
                self._status = CameraStatus.ERROR
                return False, error
            
            # 加载 OpenNI2 库
            lib_path = self._find_openni2_library()
            logger.info(f"加载 OpenNI2 库: {lib_path}")
            
            try:
                self._lib = ctypes.CDLL(lib_path)
                logger.info("✓ OpenNI2 库加载成功")
            except OSError as e:
                self._status = CameraStatus.ERROR
                return False, f"加载 OpenNI2 库失败: {e}"
            
            # 初始化 OpenNI2
            logger.info("初始化 OpenNI2...")
            rc = self._lib.oniInitialize()
            if rc != 0:
                error_msg = self._get_extended_error()
                self._status = CameraStatus.ERROR
                return False, f"OpenNI2 初始化失败: {error_msg}"
            
            logger.info("✓ OpenNI2 初始化成功")
            
            # 打开设备
            logger.info("打开设备...")
            self._device_handle = ctypes.c_void_p()
            rc = self._lib.oniDeviceOpen(ctypes.c_char_p(None), ctypes.byref(self._device_handle))
            if rc != 0:
                error_msg = self._get_extended_error()
                self._lib.oniShutdown()
                self._status = CameraStatus.ERROR
                return False, f"打开设备失败: {error_msg}"
            
            logger.info("✓ 设备打开成功")
            
            # 创建深度流
            logger.info("创建深度流...")
            self._depth_stream = ctypes.c_void_p()
            rc = self._lib.oniStreamCreate(self._device_handle, 2, ctypes.byref(self._depth_stream))  # 2 = ONI_SENSOR_DEPTH
            if rc == 0:
                rc = self._lib.oniStreamStart(self._depth_stream)
                if rc != 0:
                    logger.warning(f"启动深度流失败: {self._get_extended_error()}")
                    self._lib.oniStreamDestroy(self._depth_stream)
                    self._depth_stream = None
                else:
                    logger.info("✓ 深度流启动成功")
            else:
                logger.warning(f"创建深度流失败: {self._get_extended_error()}")
                self._depth_stream = None
            
            # 创建彩色流
            logger.info("创建彩色流...")
            self._color_stream = ctypes.c_void_p()
            rc = self._lib.oniStreamCreate(self._device_handle, 1, ctypes.byref(self._color_stream))  # 1 = ONI_SENSOR_COLOR
            if rc == 0:
                rc = self._lib.oniStreamStart(self._color_stream)
                if rc != 0:
                    logger.warning(f"启动彩色流失败: {self._get_extended_error()}")
                    self._lib.oniStreamDestroy(self._color_stream)
                    self._color_stream = None
                else:
                    logger.info("✓ 彩色流启动成功")
            else:
                logger.warning(f"创建彩色流失败: {self._get_extended_error()}")
                self._color_stream = None
            
            # 检查是否有有效流
            if self._depth_stream is None and self._color_stream is None:
                self._lib.oniDeviceClose(self._device_handle)
                self._lib.oniShutdown()
                self._status = CameraStatus.ERROR
                return False, "没有可用的视频流"
            
            # 启动采集线程
            self._capturing = True
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()
            
            self._status = CameraStatus.READY
            self._device_info = {'name': 'Orbbec Camera (OpenNI2)'}
            logger.info("✓ 相机初始化成功")
            return True, ""
            
        except Exception as e:
            self._status = CameraStatus.ERROR
            self._last_error = str(e)
            logger.error(f"相机初始化失败: {e}")
            return False, str(e)
    
    def _get_extended_error(self) -> str:
        """获取 OpenNI2 扩展错误信息"""
        try:
            error_func = self._lib.oniGetExtendedError
            error_func.restype = ctypes.c_char_p
            return error_func().decode('utf-8')
        except:
            return ""
    
    def _capture_loop(self):
        """后台采集循环"""
        while self._capturing:
            try:
                # 读取深度帧
                if self._depth_stream is not None:
                    depth_frame = ctypes.c_void_p()
                    rc = self._lib.oniStreamReadFrame(self._depth_stream, ctypes.byref(depth_frame), 100)
                    if rc == 0:
                        # 获取帧数据
                        data = self._lib.oniFrameGetData(depth_frame)
                        width = self._lib.oniFrameGetWidth(depth_frame)
                        height = self._lib.oniFrameGetHeight(depth_frame)
                        
                        if data and width > 0 and height > 0:
                            # 转换为 numpy 数组
                            depth_array = ctypes.cast(data, ctypes.POINTER(ctypes.c_uint16))
                            depth_image = np.ctypeslib.as_array(depth_array, shape=(height, width))
                            
                            with self._lock:
                                self._latest_depth_image = depth_image.copy()
                        
                        self._lib.oniFrameRelease(depth_frame)
                
                # 读取彩色帧
                if self._color_stream is not None:
                    color_frame = ctypes.c_void_p()
                    rc = self._lib.oniStreamReadFrame(self._color_stream, ctypes.byref(color_frame), 100)
                    if rc == 0:
                        data = self._lib.oniFrameGetData(color_frame)
                        width = self._lib.oniFrameGetWidth(color_frame)
                        height = self._lib.oniFrameGetHeight(color_frame)
                        
                        if data and width > 0 and height > 0:
                            # 转换为 numpy 数组 (RGB888)
                            color_array = ctypes.cast(data, ctypes.POINTER(ctypes.c_uint8))
                            color_image = np.ctypeslib.as_array(color_array, shape=(height, width, 3))
                            
                            with self._lock:
                                self._latest_color_image = color_image.copy()
                        
                        self._lib.oniFrameRelease(color_frame)
                
                time.sleep(0.001)  # 1ms
                
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
        
        # 停止并销毁流
        if self._depth_stream is not None:
            try:
                self._lib.oniStreamStop(self._depth_stream)
                self._lib.oniStreamDestroy(self._depth_stream)
                logger.info("深度流已关闭")
            except:
                pass
            self._depth_stream = None
        
        if self._color_stream is not None:
            try:
                self._lib.oniStreamStop(self._color_stream)
                self._lib.oniStreamDestroy(self._color_stream)
                logger.info("彩色流已关闭")
            except:
                pass
            self._color_stream = None
        
        # 关闭设备
        if self._device_handle is not None:
            try:
                self._lib.oniDeviceClose(self._device_handle)
                logger.info("设备已关闭")
            except:
                pass
            self._device_handle = None
        
        # 关闭 OpenNI2
        if self._lib is not None:
            try:
                self._lib.oniShutdown()
                logger.info("OpenNI2 已关闭")
            except:
                pass
            self._lib = None
        
        self._status = CameraStatus.DISCONNECTED
        logger.info("相机已关闭")
    
    def get_intrinsic_matrix(self) -> np.ndarray:
        """获取相机内参矩阵"""
        # Orbbec 默认参数 (需要根据实际相机校准)
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
