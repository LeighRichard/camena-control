"""
RealSense 相机控制器 - 支持 Intel RealSense D415 等系列深度相机
"""

from typing import Optional, Tuple, List
from enum import Enum
import numpy as np
import time
import logging

from .base_controller import BaseCameraController, ImagePair, CameraConfig

# 尝试导入 pyrealsense2，如果不可用则使用模拟模式
try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError:
    REALSENSE_AVAILABLE = False

logger = logging.getLogger(__name__)


class CameraStatus(Enum):
    """相机状态"""
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    READY = "ready"
    CAPTURING = "capturing"
    ERROR = "error"


from dataclasses import dataclass, field
from typing import List


@dataclass
class ImageQuality:
    """图像质量评估结果"""
    brightness: float           # 平均亮度 (0-255)
    contrast: float             # 对比度 (标准差)
    sharpness: float            # 清晰度 (拉普拉斯方差)
    is_acceptable: bool         # 是否可接受
    suggestions: List[str] = field(default_factory=list)


class RealSenseController(BaseCameraController):
    """Intel RealSense D415 相机控制器"""
    
    @property
    def camera_type(self) -> str:
        """获取相机类型"""
        return "realsense"
    
    @property
    def camera_model(self) -> str:
        """获取相机型号"""
        if self._device:
            try:
                return self._device.get_info(rs.camera_info.name)
            except Exception:
                # 获取相机信息失败，返回默认值
                pass
        return "RealSense D415"
    
    # D415 相机特性常量
    ROLLING_SHUTTER_DELAY_MS = 33  # 滚动快门延迟
    MIN_STABLE_FRAMES = 3          # 最小稳定帧数
    DEFAULT_WAIT_FRAMES = 5        # 默认等待帧数
    
    # 图像质量阈值
    MIN_BRIGHTNESS = 40
    MAX_BRIGHTNESS = 220
    MIN_CONTRAST = 20
    MIN_SHARPNESS = 100
    
    def __init__(self):
        self._pipeline = None
        self._profile = None
        self._config = CameraConfig()
        self._status = CameraStatus.DISCONNECTED
        self._device = None
        self._depth_sensor = None
        self._color_sensor = None
        self._align = None
        self._last_error = ""
    
    def initialize(self) -> Tuple[bool, str]:
        """
        初始化相机
        
        Returns:
            (成功标志, 错误信息)
        """
        if not REALSENSE_AVAILABLE:
            self._status = CameraStatus.ERROR
            return False, "pyrealsense2 未安装"
        
        self._status = CameraStatus.INITIALIZING
        
        try:
            # 创建上下文并查找设备
            ctx = rs.context()
            devices = ctx.query_devices()
            
            if len(devices) == 0:
                self._status = CameraStatus.ERROR
                return False, "未找到 RealSense 设备"
            
            # 查找 D415
            self._device = None
            for dev in devices:
                if 'D415' in dev.get_info(rs.camera_info.name):
                    self._device = dev
                    break
            
            if self._device is None:
                # 使用第一个可用设备
                self._device = devices[0]
                logger.warning(f"未找到 D415，使用: {self._device.get_info(rs.camera_info.name)}")
            
            # 创建管道
            self._pipeline = rs.pipeline()
            config = rs.config()
            
            # 配置流
            config.enable_stream(
                rs.stream.color, 
                self._config.width, 
                self._config.height, 
                rs.format.rgb8, 
                self._config.fps
            )
            config.enable_stream(
                rs.stream.depth, 
                self._config.width, 
                self._config.height, 
                rs.format.z16, 
                self._config.fps
            )
            
            # 启动管道
            self._profile = self._pipeline.start(config)
            
            # 获取传感器引用
            self._depth_sensor = self._profile.get_device().first_depth_sensor()
            self._color_sensor = self._profile.get_device().first_color_sensor()
            
            # 创建对齐对象（将深度对齐到彩色）
            self._align = rs.align(rs.stream.color)
            
            # 应用初始配置
            self._apply_sensor_settings()
            
            # 等待几帧让相机稳定
            for _ in range(self.MIN_STABLE_FRAMES):
                self._pipeline.wait_for_frames(timeout_ms=5000)
            
            self._status = CameraStatus.READY
            logger.info(f"相机初始化成功: {self._device.get_info(rs.camera_info.name)}")
            return True, ""
            
        except Exception as e:
            self._status = CameraStatus.ERROR
            self._last_error = str(e)
            logger.error(f"相机初始化失败: {e}")
            return False, str(e)
    
    def _apply_sensor_settings(self):
        """应用传感器设置"""
        if self._color_sensor is None:
            return
        
        try:
            # 设置自动曝光
            if self._config.auto_exposure:
                self._color_sensor.set_option(rs.option.enable_auto_exposure, 1)
            else:
                self._color_sensor.set_option(rs.option.enable_auto_exposure, 0)
                if self._config.exposure > 0:
                    self._color_sensor.set_option(rs.option.exposure, self._config.exposure)
            
            # 设置亮度
            if rs.option.brightness in [opt.option for opt in self._color_sensor.get_supported_options()]:
                self._color_sensor.set_option(rs.option.brightness, self._config.brightness)
            
            # 设置对比度
            if rs.option.contrast in [opt.option for opt in self._color_sensor.get_supported_options()]:
                self._color_sensor.set_option(rs.option.contrast, self._config.contrast)
            
            # 设置增益
            if rs.option.gain in [opt.option for opt in self._color_sensor.get_supported_options()]:
                self._color_sensor.set_option(rs.option.gain, self._config.gain)
            
            # 设置白平衡
            if self._config.white_balance < 0:
                self._color_sensor.set_option(rs.option.enable_auto_white_balance, 1)
            else:
                self._color_sensor.set_option(rs.option.enable_auto_white_balance, 0)
                self._color_sensor.set_option(rs.option.white_balance, self._config.white_balance)
                
        except Exception as e:
            logger.warning(f"应用传感器设置时出错: {e}")
    
    def capture(self, wait_frames: int = None, position: Tuple[float, float, float] = None) -> Tuple[Optional[ImagePair], str]:
        """
        采集图像
        
        D415 使用滚动快门，需要等待多帧确保图像稳定。
        
        Args:
            wait_frames: 等待稳定的帧数，None 使用默认值
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
            # 丢弃前几帧，等待滚动快门稳定
            for _ in range(wait_frames):
                self._pipeline.wait_for_frames(timeout_ms=1000)
            
            # 获取帧
            frames = self._pipeline.wait_for_frames(timeout_ms=1000)
            
            # 对齐深度到彩色
            aligned_frames = self._align.process(frames)
            
            color_frame = aligned_frames.get_color_frame()
            depth_frame = aligned_frames.get_depth_frame()
            
            if not color_frame or not depth_frame:
                self._status = CameraStatus.READY
                return None, "获取帧失败"
            
            # 转换为 numpy 数组
            rgb = np.asanyarray(color_frame.get_data())
            depth = np.asanyarray(depth_frame.get_data())
            
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
        # 验证配置
        valid, error = config.validate()
        if not valid:
            return False, error
        
        # 检查是否需要重启管道（分辨率或帧率改变）
        need_restart = (
            config.width != self._config.width or
            config.height != self._config.height or
            config.fps != self._config.fps
        )
        
        old_config = self._config
        self._config = config
        
        if need_restart and self._pipeline is not None:
            # 需要重启管道
            try:
                self._pipeline.stop()
                
                rs_config = rs.config()
                rs_config.enable_stream(
                    rs.stream.color, 
                    config.width, 
                    config.height, 
                    rs.format.rgb8, 
                    config.fps
                )
                rs_config.enable_stream(
                    rs.stream.depth, 
                    config.width, 
                    config.height, 
                    rs.format.z16, 
                    config.fps
                )
                
                self._profile = self._pipeline.start(rs_config)
                self._depth_sensor = self._profile.get_device().first_depth_sensor()
                self._color_sensor = self._profile.get_device().first_color_sensor()
                
                # 等待稳定
                for _ in range(self.MIN_STABLE_FRAMES):
                    self._pipeline.wait_for_frames(timeout_ms=5000)
                    
            except Exception as e:
                self._config = old_config
                logger.error(f"重启管道失败: {e}")
                return False, str(e)
        
        # 应用传感器设置
        self._apply_sensor_settings()
        
        logger.info(f"相机配置已更新: {config.width}x{config.height}@{config.fps}fps")
        return True, ""
    
    def get_status(self) -> CameraStatus:
        """获取相机状态"""
        return self._status
    
    def get_config(self) -> CameraConfig:
        """获取当前配置"""
        return self._config
    
    def evaluate_image_quality(self, image: np.ndarray) -> ImageQuality:
        """
        评估图像质量
        
        Args:
            image: RGB 图像
            
        Returns:
            图像质量评估结果
        """
        # 转换为灰度图（使用标准 RGB 权重）
        if len(image.shape) == 3:
            gray = (0.299 * image[:, :, 0] + 
                    0.587 * image[:, :, 1] + 
                    0.114 * image[:, :, 2]).astype(np.float32)
        else:
            gray = image.astype(np.float32)
        
        # 计算亮度（平均值）
        brightness = float(np.mean(gray))
        
        # 计算对比度（标准差）
        contrast = float(np.std(gray))
        
        # 计算清晰度（拉普拉斯方差，使用卷积实现）
        # 拉普拉斯核: [[0, 1, 0], [1, -4, 1], [0, 1, 0]]
        laplacian = self._laplacian_variance(gray)
        sharpness = float(laplacian)
        
        # 生成建议
        suggestions = []
        is_acceptable = True
        
        if brightness < self.MIN_BRIGHTNESS:
            suggestions.append("图像过暗，建议增加曝光或增益")
            is_acceptable = False
        elif brightness > self.MAX_BRIGHTNESS:
            suggestions.append("图像过亮，建议减少曝光或增益")
            is_acceptable = False
        
        if contrast < self.MIN_CONTRAST:
            suggestions.append("对比度过低，建议调整对比度参数")
            is_acceptable = False
        
        if sharpness < self.MIN_SHARPNESS:
            suggestions.append("图像模糊，建议检查对焦或减少运动")
            is_acceptable = False
        
        return ImageQuality(
            brightness=brightness,
            contrast=contrast,
            sharpness=sharpness,
            is_acceptable=is_acceptable,
            suggestions=suggestions
        )
    
    def auto_exposure_adjust(self, target_brightness: float = 128.0) -> Tuple[Optional[CameraConfig], str]:
        """
        自动调整曝光参数
        
        基于当前图像亮度自动调整曝光和增益参数。
        
        Args:
            target_brightness: 目标亮度值 (0-255)
            
        Returns:
            (调整后的配置, 错误信息)
        """
        if self._status != CameraStatus.READY:
            return None, f"相机未就绪，当前状态: {self._status.value}"
        
        try:
            # 采集当前图像
            image_pair, error = self.capture(wait_frames=3)
            if image_pair is None:
                return None, error
            
            # 评估当前质量
            quality = self.evaluate_image_quality(image_pair.rgb)
            
            # 如果已经可接受，不需要调整
            if quality.is_acceptable:
                return self._config, ""
            
            # 计算亮度差异
            brightness_diff = target_brightness - quality.brightness
            
            # 创建新配置
            new_config = CameraConfig(
                width=self._config.width,
                height=self._config.height,
                fps=self._config.fps,
                exposure=self._config.exposure,
                brightness=self._config.brightness,
                contrast=self._config.contrast,
                gain=self._config.gain,
                white_balance=self._config.white_balance,
                auto_exposure=False  # 切换到手动模式
            )
            
            # 调整参数
            if abs(brightness_diff) > 30:
                # 大幅调整增益
                gain_adjust = int(brightness_diff / 4)
                new_config.gain = max(0, min(128, self._config.gain + gain_adjust))
            else:
                # 小幅调整亮度
                brightness_adjust = int(brightness_diff / 2)
                new_config.brightness = max(-64, min(64, self._config.brightness + brightness_adjust))
            
            # 应用新配置
            success, error = self.configure(new_config)
            if not success:
                return None, error
            
            logger.info(f"自动曝光调整完成: 亮度 {quality.brightness:.1f} -> 目标 {target_brightness:.1f}")
            return new_config, ""
            
        except Exception as e:
            logger.error(f"自动曝光调整失败: {e}")
            return None, str(e)
    
    def _laplacian_variance(self, gray: np.ndarray) -> float:
        """
        计算拉普拉斯方差（清晰度指标）
        
        使用纯 numpy 实现，避免依赖 cv2
        """
        # 拉普拉斯核
        kernel = np.array([[0, 1, 0],
                           [1, -4, 1],
                           [0, 1, 0]], dtype=np.float32)
        
        # 简单卷积实现
        h, w = gray.shape
        if h < 3 or w < 3:
            return 0.0
        
        # 使用滑动窗口计算拉普拉斯
        laplacian = np.zeros((h - 2, w - 2), dtype=np.float32)
        for i in range(3):
            for j in range(3):
                laplacian += kernel[i, j] * gray[i:h-2+i, j:w-2+j]
        
        return float(np.var(laplacian))
    
    def get_depth_at_point(self, x: int, y: int, depth_image: np.ndarray) -> float:
        """
        获取指定点的深度值
        
        Args:
            x, y: 像素坐标
            depth_image: 深度图像
            
        Returns:
            深度值（米），无效返回 0
        """
        if 0 <= x < depth_image.shape[1] and 0 <= y < depth_image.shape[0]:
            depth_mm = depth_image[y, x]
            return depth_mm / 1000.0
        return 0.0
    
    def get_depth_at_points(self, points: np.ndarray, depth_image: np.ndarray) -> np.ndarray:
        """
        批量获取多个点的深度值（向量化优化）
        
        相比逐点查询，性能提升约 10-100 倍。
        
        Args:
            points: 像素坐标数组，形状为 (N, 2)，每行为 [x, y]
            depth_image: 深度图像 (H, W)
            
        Returns:
            深度值数组（米），形状为 (N,)，无效点返回 0
        """
        if len(points) == 0:
            return np.array([], dtype=np.float32)
        
        points = np.asarray(points, dtype=np.int32)
        h, w = depth_image.shape[:2]
        
        # 提取 x, y 坐标
        x_coords = points[:, 0]
        y_coords = points[:, 1]
        
        # 创建有效性掩码
        valid_mask = (
            (x_coords >= 0) & (x_coords < w) &
            (y_coords >= 0) & (y_coords < h)
        )
        
        # 初始化结果数组
        depths = np.zeros(len(points), dtype=np.float32)
        
        # 只对有效点进行查询
        if np.any(valid_mask):
            valid_x = x_coords[valid_mask]
            valid_y = y_coords[valid_mask]
            depths[valid_mask] = depth_image[valid_y, valid_x] / 1000.0
        
        return depths
    
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
        h, w = depth_image.shape[:2]
        
        # 裁剪到有效范围
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(w, x + width)
        y2 = min(h, y + height)
        
        if x1 >= x2 or y1 >= y2:
            return 0.0
        
        # 提取区域
        region = depth_image[y1:y2, x1:x2].astype(np.float32)
        
        # 过滤无效值（0 表示无效深度）
        valid_depths = region[region > 0]
        
        if len(valid_depths) == 0:
            return 0.0
        
        # 根据方法聚合
        if method == 'mean':
            depth_mm = np.mean(valid_depths)
        elif method == 'median':
            depth_mm = np.median(valid_depths)
        elif method == 'min':
            depth_mm = np.min(valid_depths)
        elif method == 'max':
            depth_mm = np.max(valid_depths)
        else:
            depth_mm = np.median(valid_depths)
        
        return float(depth_mm) / 1000.0
    
    def get_intrinsics(self) -> Optional[dict]:
        """
        获取相机内参
        
        Returns:
            内参字典，包含 fx, fy, cx, cy, coeffs
        """
        if self._profile is None:
            return None
        
        try:
            color_stream = self._profile.get_stream(rs.stream.color)
            intrinsics = color_stream.as_video_stream_profile().get_intrinsics()
            
            return {
                'width': intrinsics.width,
                'height': intrinsics.height,
                'fx': intrinsics.fx,
                'fy': intrinsics.fy,
                'cx': intrinsics.ppx,
                'cy': intrinsics.ppy,
                'coeffs': intrinsics.coeffs
            }
        except Exception as e:
            logger.error(f"获取内参失败: {e}")
            return None
    
    def close(self):
        """关闭相机"""
        if self._pipeline is not None:
            try:
                self._pipeline.stop()
                logger.info("相机已关闭")
            except Exception as e:
                logger.error(f"关闭相机时出错: {e}")
            finally:
                self._pipeline = None
                self._profile = None
                self._device = None
                self._depth_sensor = None
                self._color_sensor = None
                self._align = None
        
        self._status = CameraStatus.DISCONNECTED
    
    def __enter__(self):
        """上下文管理器入口"""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        return False
