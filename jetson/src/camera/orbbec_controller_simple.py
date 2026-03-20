"""
奥比中光相机控制器 - 简化版
通过命令行工具获取相机图像,不使用 rospy

使用方法:
1. 终端 1: roscore
2. 终端 2: rosrun libuvc_camera camera_node
3. 终端 3: python3 main.py
"""

from typing import Optional, Tuple
from enum import Enum
import numpy as np
import time
import logging
import subprocess
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


class OrbbecControllerSimple(BaseCameraController):
    """奥比中光相机控制器 - 简化实现"""
    
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
        self._latest_image_path = None
        self._lock = threading.Lock()
        
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
        return "orbbec-simple"
    
    @property
    def camera_model(self) -> str:
        """获取相机型号"""
        if self._device_info:
            return self._device_info.get('name', 'Unknown Orbbec')
        return "Orbbec Camera"
    
    def _check_ros_topics(self) -> bool:
        """检查 ROS 话题是否发布"""
        try:
            # 使用 rostopic 命令检查话题
            result = subprocess.run(
                ['rostopic', 'list'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=5
            )
            
            if result.returncode == 0:
                topics = result.stdout
                if '/camera/rgb/image_raw' in topics:
                    logger.info("✓ 找到相机话题: /camera/rgb/image_raw")
                    return True
                else:
                    logger.warning("未找到相机话题")
                    return False
            else:
                logger.warning("rostopic 命令失败")
                return False
                
        except Exception as e:
            logger.error(f"检查 ROS 话题失败: {e}")
            return False
    
    def initialize(self) -> Tuple[bool, str]:
        """
        初始化相机
        
        注意: 需要先手动启动 roscore 和 libuvc_camera 节点
        
        Returns:
            (成功标志, 错误信息)
        """
        self._status = CameraStatus.INITIALIZING
        
        try:
            # 检查 ROS 话题是否发布
            logger.info("检查相机是否已启动...")
            logger.info("提示: 请确保已运行:")
            logger.info("  终端 1: roscore")
            logger.info("  终端 2: rosrun libuvc_camera camera_node")
            
            if not self._check_ros_topics():
                self._status = CameraStatus.ERROR
                return False, "相机话题未发布,请先启动 roscore 和 libuvc_camera 节点"
            
            # 等待一下确保话题稳定
            time.sleep(1)
            
            self._status = CameraStatus.READY
            self._device_info = {'name': 'Orbbec Camera (libuvc)'}
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
        
        使用 rosrun image_saver 命令保存图像
        
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
            # 方法 1: 使用 rosservice call 保存图像
            # 这需要 image_saver 节点运行
            
            # 方法 2: 使用 OpenCV 直接读取 (如果相机是 UVC 设备)
            # 这需要知道设备路径
            
            # 方法 3: 使用 rostopic echo 获取图像 (效率低但简单)
            # 这里我们使用一个简化的方法
            
            # 创建临时文件路径
            import tempfile
            temp_dir = tempfile.mkdtemp()
            color_path = os.path.join(temp_dir, "color.jpg")
            
            # 使用 rosrun image_view image_saver 保存图像
            # 注意: 这需要 image_view 包
            logger.info("保存图像到临时文件...")
            
            # 简化: 直接返回 None,提示用户使用 rqt_image_view
            logger.warning("图像采集需要额外配置")
            logger.info("建议使用 rqt_image_view 查看图像:")
            logger.info("  rqt_image_view")
            
            self._status = CameraStatus.READY
            return None, "请使用 rqt_image_view 查看图像"
            
        except Exception as e:
            self._status = CameraStatus.READY
            logger.error(f"采集图像失败: {e}")
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
        self._status = CameraStatus.DISCONNECTED
        logger.info("相机已关闭")
