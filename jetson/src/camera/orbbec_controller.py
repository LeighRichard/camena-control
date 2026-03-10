"""
奥比中光相机控制器 - 支持咪咕款等 Orbbec 系列深度相机
"""

from typing import Optional, Tuple, List
from enum import Enum
import numpy as np
import time
import logging

from .base_controller import BaseCameraController, ImagePair, CameraConfig
from .depth_processor import DepthProcessor

# 尝试导入 pyorbbecsdk
try:
    from pyorbbecsdk import (
        Pipeline, Config, 
        OBSensorType, OBFormat, OBAlignMode,
        OBException
    )
    ORBBEC_AVAILABLE = True
except ImportError:
    ORBBEC_AVAILABLE = False

logger = logging.getLogger(__name__)


class CameraStatus(Enum):
    """相机状态"""
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    READY = "ready"
    CAPTURING = "capturing"
    ERROR = "error"


class OrbbecController(BaseCameraController):
    """奥比中光相机控制器"""
    
    # 相机特性常量
    MIN_STABLE_FRAMES = 3          # 最小稳定帧数
    DEFAULT_WAIT_FRAMES = 5        # 默认等待帧数
    
    # 默认分辨率配置
    DEFAULT_COLOR_WIDTH = 1920
    DEFAULT_COLOR_HEIGHT = 1080
    DEFAULT_DEPTH_WIDTH = 640
    DEFAULT_DEPTH_HEIGHT = 480
    DEFAULT_FPS = 30
    
    def __init__(self):
        self._pipeline = None
        self._config = None
        self._device = None
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
            min_depth=0.6,  # Orbbec 最小工作距离
            max_depth=8.0   # Orbbec 最大工作距离（保守值）
        )
        logger.info(f"深度处理器已初始化: {self._depth_processor}")
    
    @property
    def camera_type(self) -> str:
        """获取相机类型"""
        return "orbbec"
    
    @property
    def camera_model(self) -> str:
        """获取相机型号"""
        if self._device_info:
            return self._device_info.get('name', 'Unknown Orbbec')
        return "Orbbec"
    
    def initialize(self) -> Tuple[bool, str]:
        """
        初始化奥比中光相机
        
        Returns:
            (成功标志, 错误信息)
        """
        if not ORBBEC_AVAILABLE:
            self._status = CameraStatus.ERROR
            return False, "pyorbbecsdk 未安装，请运行: pip install pyorbbecsdk"
        
        self._status = CameraStatus.INITIALIZING
        
        try:
            # 创建 Pipeline
            self._pipeline = Pipeline()
            
            # 获取设备列表
            device_list = self._pipeline.get_device_list()
            device_count = device_list.get_count()
            
            if device_count == 0:
                self._status = CameraStatus.ERROR
                return False, "未找到奥比中光设备"
            
            # 获取第一个设备
            self._device = device_list.get_device(0)
            
            # 获取设备信息
            try:
                self._device_info = {
                    'name': self._device.get_device_info().get_name(),
                    'serial': self._device.get_device_info().get_serial_number(),
                    'firmware': self._device.get_device_info().get_firmware_version(),
                }
                logger.info(f"找到奥比中光设备: {self._device_info['name']}")
            except Exception:
                # 获取设备信息失败，使用默认值
                self._device_info = {'name': 'Orbbec Camera'}
            
            # 创建配置
            self._config = Config()
            
            # 配置彩色流
            try:
                color_profiles = self._pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
                color_profile = color_profiles.get_video_stream_profile(
                    self.DEFAULT_COLOR_WIDTH,
                    self.DEFAULT_COLOR_HEIGHT,
                    OBFormat.RGB,
                    self.DEFAULT_FPS
                )
                self._config.enable_stream(color_profile)
                logger.info(f"彩色流配置: {self.DEFAULT_COLOR_WIDTH}x{self.DEFAULT_COLOR_HEIGHT}@{self.DEFAULT_FPS}fps")
            except Exception as e:
                logger.warning(f"配置彩色流失败: {e}")
                return False, f"配置彩色流失败: {e}"
            
            # 配置深度流
            try:
                depth_profiles = self._pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
                depth_profile = depth_profiles.get_video_stream_profile(
                    self.DEFAULT_DEPTH_WIDTH,
                    self.DEFAULT_DEPTH_HEIGHT,
                    OBFormat.Y16,
                    self.DEFAULT_FPS
                )
                self._config.enable_stream(depth_profile)
                logger.info(f"深度流配置: {self.DEFAULT_DEPTH_WIDTH}x{self.DEFAULT_DEPTH_HEIGHT}@{self.DEFAULT_FPS}fps")
            except Exception as e:
                logger.warning(f"配置深度流失败: {e}")
                return False, f"配置深度流失败: {e}"
            
            # 启用对齐（深度对齐到彩色）
            try:
                self._config.set_align_mode(OBAlignMode.ALIGN_D2C_HW_MODE)
                logger.info("启用深度对齐到彩色（硬件模式）")
            except Exception as e:
                logger.warning(f"设置对齐模式失败: {e}")
            
            # 启动 Pipeline
            self._pipeline.start(self._config)
            
            # 等待几帧让相机稳定
            for _ in range(self.MIN_STABLE_FRAMES):
                try:
                    self._pipeline.wait_for_frames(timeout_ms=5000)
                except Exception:
                    # 等待帧超时，继续尝试
                    pass
            
            self._status = CameraStatus.READY
            logger.info(f"奥比中光相机初始化成功: {self.camera_model}")
            return True, ""
            
        except OBException as e:
            self._status = CameraStatus.ERROR
            self._last_error = str(e)
            logger.error(f"奥比中光相机初始化失败: {e}")
            return False, str(e)
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
            position: 当前相机位置 (pan, tilt, rail)
            
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
                    self._pipeline.wait_for_frames(timeout_ms=1000)
                except Exception:
                    # 等待帧超时，继续尝试
                    pass
            
            # 获取帧集
            frameset = self._pipeline.wait_for_frames(timeout_ms=1000)
            
            if frameset is None:
                self._status = CameraStatus.READY
                return None, "获取帧集失败"
            
            # 获取彩色帧
            color_frame = frameset.get_color_frame()
            if color_frame is None:
                self._status = CameraStatus.READY
                return None, "获取彩色帧失败"
            
            # 获取深度帧
            depth_frame = frameset.get_depth_frame()
            if depth_frame is None:
                self._status = CameraStatus.READY
                return None, "获取深度帧失败"
            
            # 转换为 numpy 数组
            # 彩色图像
            color_data = np.asanyarray(color_frame.get_data(), dtype=np.uint8)
            color_height = color_frame.get_height()
            color_width = color_frame.get_width()
            rgb = color_data.reshape((color_height, color_width, 3))
            
            # 深度图像
            depth_data = np.asanyarray(depth_frame.get_data(), dtype=np.uint16)
            depth_height = depth_frame.get_height()
            depth_width = depth_frame.get_width()
            depth = depth_data.reshape((depth_height, depth_width))
            
            # 创建图像对
            image_pair = ImagePair(
                rgb=rgb,
                depth=depth,
                timestamp=time.time(),
                position=position
            )
            
            self._status = CameraStatus.READY
            return image_pair, ""
            
        except OBException as e:
            self._status = CameraStatus.READY
            logger.error(f"采集图像失败: {e}")
            return None, str(e)
        except Exception as e:
            self._status = CameraStatus.READY
            logger.error(f"采集图像失败: {e}")
            return None, str(e)
    
    def configure(self, config: CameraConfig) -> Tuple[bool, str]:
        """
        配置相机参数
        
        注意: Orbbec 相机的分辨率配置需要重启 Pipeline
        
        Args:
            config: 新的相机配置
            
        Returns:
            (成功标志, 错误信息)
        """
        # 保存旧配置
        old_config = self._camera_config
        self._camera_config = config
        
        # Orbbec 相机的参数调整通常需要重启 Pipeline
        # 这里简化处理，仅记录配置
        logger.info(f"相机配置已更新: {config.to_dict()}")
        
        # 实现曝光、增益等参数的动态调整
        if self._pipeline is not None and self._device is not None:
            try:
                # 尝试导入属性ID
                try:
                    from pyorbbecsdk import OBPropID
                except ImportError:
                    OBPropID = None
                
                if OBPropID:
                    # 获取传感器
                    color_sensor = self._device.get_sensor(OBSensorType.COLOR_SENSOR)
                    depth_sensor = self._device.get_sensor(OBSensorType.DEPTH_SENSOR)
                    
                    # 设置曝光时间（如果配置中指定）
                    if hasattr(config, 'exposure_time') and config.exposure_time is not None:
                        if color_sensor:
                            color_sensor.set_property(
                                OBPropID.OB_PROP_COLOR_EXPOSURE_INT,
                                int(config.exposure_time)
                            )
                            logger.debug(f"彩色传感器曝光时间设置为: {config.exposure_time}")
                    
                    # 设置增益（如果配置中指定）
                    if hasattr(config, 'gain') and config.gain is not None:
                        if color_sensor:
                            color_sensor.set_property(
                                OBPropID.OB_PROP_COLOR_GAIN_INT,
                                int(config.gain)
                            )
                            logger.debug(f"彩色传感器增益设置为: {config.gain}")
                    
                    # 设置深度传感器曝光（如果配置中指定）
                    if hasattr(config, 'depth_exposure') and config.depth_exposure is not None:
                        if depth_sensor:
                            depth_sensor.set_property(
                                OBPropID.OB_PROP_DEPTH_EXPOSURE_INT,
                                int(config.depth_exposure)
                            )
                            logger.debug(f"深度传感器曝光时间设置为: {config.depth_exposure}")
                    
                    # 自动曝光模式切换
                    if hasattr(config, 'auto_exposure'):
                        auto_exposure = config.auto_exposure
                        if color_sensor:
                            color_sensor.set_property(
                                OBPropID.OB_PROP_COLOR_AUTO_EXPOSURE_BOOL,
                                auto_exposure
                            )
                            logger.debug(f"彩色传感器自动曝光: {'开启' if auto_exposure else '关闭'}")
                        if depth_sensor:
                            depth_sensor.set_property(
                                OBPropID.OB_PROP_DEPTH_AUTO_EXPOSURE_BOOL,
                                auto_exposure
                            )
                            logger.debug(f"深度传感器自动曝光: {'开启' if auto_exposure else '关闭'}")
                            
            except Exception as e:
                logger.warning(f"设置相机参数失败: {e}，部分参数可能不支持")
        
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
        if self._pipeline is None:
            return None
        
        try:
            # 获取彩色流的内参
            color_profiles = self._pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
            if color_profiles.get_count() > 0:
                profile = color_profiles.get_video_stream_profile(
                    self.DEFAULT_COLOR_WIDTH,
                    self.DEFAULT_COLOR_HEIGHT,
                    OBFormat.RGB,
                    self.DEFAULT_FPS
                )
                intrinsics = profile.get_intrinsics()
                
                return {
                    'width': intrinsics.width,
                    'height': intrinsics.height,
                    'fx': intrinsics.fx,
                    'fy': intrinsics.fy,
                    'cx': intrinsics.cx,
                    'cy': intrinsics.cy,
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
        # 使用深度处理器进行坐标转换和深度查询（带滤波）
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
        # 计算区域中心点（彩色图坐标）
        center_x = x + width // 2
        center_y = y + height // 2
        
        # 转换到深度图坐标
        depth_x, depth_y = self._depth_processor.color_to_depth_coords(center_x, center_y)
        
        # 计算深度图中的区域尺寸
        scale_x = self._depth_processor.scale_x
        scale_y = self._depth_processor.scale_y
        depth_width = int(width * scale_x)
        depth_height = int(height * scale_y)
        
        # 使用深度处理器查询区域深度
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
        if self._pipeline is not None:
            try:
                self._pipeline.stop()
                logger.info("奥比中光相机已关闭")
            except Exception as e:
                logger.error(f"关闭相机时出错: {e}")
            finally:
                self._pipeline = None
                self._config = None
                self._device = None
        
        self._status = CameraStatus.DISCONNECTED
