"""
奥比中光相机控制器 - OpenNI2 后端
使用 OpenNI2 SDK 访问 Orbbec 深度相机
适用于 pyorbbecsdk 不可用或无法正常工作的情况
"""

from typing import Optional, Tuple, List
from enum import Enum
import numpy as np
import time
import logging

from .base_controller import BaseCameraController, ImagePair, CameraConfig
from .depth_processor import DepthProcessor

# 尝试导入 OpenNI2
try:
    import openni2
    OPENNI2_AVAILABLE = True
except ImportError:
    OPENNI2_AVAILABLE = False

logger = logging.getLogger(__name__)


class CameraStatus(Enum):
    """相机状态"""
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    READY = "ready"
    CAPTURING = "capturing"
    ERROR = "error"


class OrbbecControllerOpenNI2(BaseCameraController):
    """奥比中光相机控制器 - OpenNI2 实现"""
    
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
        self._device = None
        self._color_stream = None
        self._depth_stream = None
        self._status = CameraStatus.DISCONNECTED
        self._camera_config = CameraConfig(
            width=self.DEFAULT_COLOR_WIDTH,
            height=self.DEFAULT_COLOR_HEIGHT,
            fps=self.DEFAULT_FPS
        )
        self._last_error = ""
        self._device_info = {}
        
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
        return "orbbec-openni2"
    
    @property
    def camera_model(self) -> str:
        """获取相机型号"""
        if self._device_info:
            return self._device_info.get('name', 'Unknown Orbbec (OpenNI2)')
        return "Orbbec (OpenNI2)"
    
    def initialize(self) -> Tuple[bool, str]:
        """
        初始化奥比中光相机 (使用 OpenNI2)
        
        Returns:
            (成功标志, 错误信息)
        """
        if not OPENNI2_AVAILABLE:
            self._status = CameraStatus.ERROR
            return False, "openni2 未安装，请运行: pip install openni2"
        
        self._status = CameraStatus.INITIALIZING
        
        try:
            # 初始化 OpenNI2
            logger.info("初始化 OpenNI2...")
            openni2.initialize()
            
            # 打开设备
            logger.info("打开设备...")
            self._device = openni2.Device.open_any()
            
            if self._device is None:
                self._status = CameraStatus.ERROR
                return False, "未找到 OpenNI2 设备"
            
            # 获取设备信息
            try:
                self._device_info = {
                    'name': 'Orbbec Camera',
                    'vendor': self._device.get_info(openni2.Device.VENDOR),
                    'product': self._device.get_info(openni2.Device.PRODUCT),
                }
                logger.info(f"找到设备: {self._device_info}")
            except Exception as e:
                logger.warning(f"获取设备信息失败: {e}")
                self._device_info = {'name': 'Orbbec Camera'}
            
            # 创建彩色流
            logger.info("配置彩色流...")
            self._color_stream = self._device.create_color_stream()
            
            # 配置彩色流
            color_modes = self._color_stream.get_video_mode_choices()
            color_mode = None
            
            # 尝试找到 1920x1080 30fps
            for mode in color_modes:
                if (mode.fps == 30 and 
                    mode.resolutionX == 1920 and 
                    mode.resolutionY == 1080):
                    color_mode = mode
                    break
            
            # 如果找不到,使用第一个可用的
            if color_mode is None and color_modes:
                color_mode = color_modes[0]
                logger.warning(f"未找到 1920x1080@30fps, 使用 {color_mode.resolutionX}x{color_mode.resolutionY}@{color_mode.fps}fps")
            
            if color_mode:
                self._color_stream.set_video_mode(color_mode)
                self._color_stream.start()
                logger.info(f"彩色流启动: {color_mode.resolutionX}x{color_mode.resolutionY}@{color_mode.fps}fps")
            else:
                return False, "无法配置彩色流"
            
            # 创建深度流
            logger.info("配置深度流...")
            self._depth_stream = self._device.create_depth_stream()
            
            # 配置深度流
            depth_modes = self._depth_stream.get_video_mode_choices()
            depth_mode = None
            
            # 尝试找到 640x480 30fps
            for mode in depth_modes:
                if (mode.fps == 30 and 
                    mode.resolutionX == 640 and 
                    mode.resolutionY == 480):
                    depth_mode = mode
                    break
            
            # 如果找不到,使用第一个可用的
            if depth_mode is None and depth_modes:
                depth_mode = depth_modes[0]
                logger.warning(f"未找到 640x480@30fps, 使用 {depth_mode.resolutionX}x{depth_mode.resolutionY}@{depth_mode.fps}fps")
            
            if depth_mode:
                self._depth_stream.set_video_mode(depth_mode)
                self._depth_stream.start()
                logger.info(f"深度流启动: {depth_mode.resolutionX}x{depth_mode.resolutionY}@{depth_mode.fps}fps")
            else:
                return False, "无法配置深度流"
            
            # 等待几帧让相机稳定
            logger.info("等待相机稳定...")
            for _ in range(self.MIN_STABLE_FRAMES):
                try:
                    self._color_stream.read_frame()
                    self._depth_stream.read_frame()
                except Exception:
                    pass
            
            self._status = CameraStatus.READY
            logger.info(f"奥比中光相机初始化成功: {self.camera_model}")
            return True, ""
            
        except Exception as e:
            self._status = CameraStatus.ERROR
            self._last_error = str(e)
            logger.error(f"相机初始化失败: {e}")
            return False, str(e)
    
    def capture(
        self, 
        wait_frames: int = None, 
        position: Tuple[float, float, float] = None
    ) -> Tuple[Optional[ImagePair], str]:
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
        
        if wait_frames is None:
            wait_frames = self.DEFAULT_WAIT_FRAMES
        
        self._status = CameraStatus.CAPTURING
        
        try:
            # 丢弃前几帧，等待稳定
            for _ in range(wait_frames):
                try:
                    self._color_stream.read_frame()
                    self._depth_stream.read_frame()
                except Exception:
                    pass
            
            # 读取彩色帧
            color_frame = self._color_stream.read_frame()
            if color_frame is None:
                self._status = CameraStatus.READY
                return None, "获取彩色帧失败"
            
            # 读取深度帧
            depth_frame = self._depth_stream.read_frame()
            if depth_frame is None:
                self._status = CameraStatus.READY
                return None, "获取深度帧失败"
            
            # 转换为 numpy 数组
            # 彩色图像
            rgb = np.frombuffer(color_frame.get_buffer_as_uint8(), dtype=np.uint8)
            rgb = rgb.reshape((color_frame.height, color_frame.width, 3))
            
            # 深度图像
            depth = np.frombuffer(depth_frame.get_buffer_as_uint16(), dtype=np.uint16)
            depth = depth.reshape((depth_frame.height, depth_frame.width))
            
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
    
    def configure(self, config: CameraConfig) -> Tuple[bool, str]:
        """
        配置相机参数
        
        Args:
            config: 新的相机配置
            
        Returns:
            (成功标志, 错误信息)
        """
        # OpenNI2 的参数调整需要重新初始化流
        # 这里简化处理，仅记录配置
        logger.info(f"相机配置已更新: {config.to_dict()}")
        return True, ""
    
    def get_status(self) -> str:
        """获取相机状态"""
        return self._status.value
    
    def get_config(self) -> CameraConfig:
        """获取当前配置"""
        return self._camera_config
    
    def get_intrinsics(self) -> Optional[dict]:
        """
        获取相机内参
        
        Returns:
            内参字典，包含 fx, fy, cx, cy
        """
        if self._device is None:
            return None
        
        try:
            # 获取彩色流的内参
            if self._color_stream:
                mode = self._color_stream.get_video_mode()
                # OpenNI2 的内参获取方式可能因设备而异
                # 这里返回基本参数
                return {
                    'width': mode.resolutionX,
                    'height': mode.resolutionY,
                    'fx': mode.resolutionX / 2.0,  # 估算值
                    'fy': mode.resolutionY / 2.0,  # 估算值
                    'cx': mode.resolutionX / 2.0,
                    'cy': mode.resolutionY / 2.0,
                }
        except Exception as e:
            logger.error(f"获取内参失败: {e}")
            return None
    
    def get_depth_at_point(self, x: int, y: int, depth_image: np.ndarray) -> float:
        """
        获取指定点的深度值
        
        Args:
            x, y: 像素坐标（彩色图坐标系）
            depth_image: 深度图像
            
        Returns:
            深度值（米），无效返回 0
        """
        return self._depth_processor.get_depth_at_color_point(
            color_x=x,
            color_y=y,
            depth_image=depth_image,
            use_filter=True
        )
    
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
            x, y: 区域左上角坐标（彩色图坐标系）
            width, height: 区域尺寸
            depth_image: 深度图像
            method: 聚合方法 ('mean', 'median', 'min', 'max')
            
        Returns:
            深度值（米），无效返回 0
        """
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
        if self._color_stream is not None:
            try:
                self._color_stream.stop()
                self._color_stream.close()
                logger.info("彩色流已关闭")
            except Exception as e:
                logger.error(f"关闭彩色流时出错: {e}")
            finally:
                self._color_stream = None
        
        if self._depth_stream is not None:
            try:
                self._depth_stream.stop()
                self._depth_stream.close()
                logger.info("深度流已关闭")
            except Exception as e:
                logger.error(f"关闭深度流时出错: {e}")
            finally:
                self._depth_stream = None
        
        if self._device is not None:
            try:
                self._device.close()
                logger.info("设备已关闭")
            except Exception as e:
                logger.error(f"关闭设备时出错: {e}")
            finally:
                self._device = None
        
        try:
            openni2.unload()
            logger.info("OpenNI2 已卸载")
        except Exception as e:
            logger.error(f"卸载 OpenNI2 时出错: {e}")
        
        self._status = CameraStatus.DISCONNECTED
