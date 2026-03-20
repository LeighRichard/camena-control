"""
奥比中光相机控制器 - ROS OpenNI2
使用 ROS openni2_camera 节点获取深度和彩色图像

这是最可靠的方法，因为 ROS openni2_camera 已经封装了 OpenNI2
"""

from typing import Optional, Tuple
from enum import Enum
import numpy as np
import time
import logging
import os
import threading
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


# 尝试导入 ROS
try:
    import rospy
    from sensor_msgs.msg import Image
    from cv_bridge import CvBridge
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False
    rospy = None
    logger.warning("ROS 未安装，此控制器不可用")


class OrbbecControllerROSOpenNI2(BaseCameraController):
    """
    奥比中光相机控制器 - ROS OpenNI2
    
    使用 ROS openni2_camera 节点获取深度和彩色图像
    """
    
    DEFAULT_COLOR_WIDTH = 640
    DEFAULT_COLOR_HEIGHT = 480
    DEFAULT_DEPTH_WIDTH = 640
    DEFAULT_DEPTH_HEIGHT = 480
    DEFAULT_FPS = 30
    DEFAULT_WAIT_FRAMES = 5
    
    def __init__(self):
        self._status = CameraStatus.DISCONNECTED
        self._camera_config = CameraConfig(
            width=self.DEFAULT_COLOR_WIDTH,
            height=self.DEFAULT_COLOR_HEIGHT,
            fps=self.DEFAULT_FPS
        )
        self._last_error = ""
        self._device_info = {}
        
        # ROS 相关
        self._cv_bridge = None
        self._color_sub = None
        self._depth_sub = None
        self._latest_color = None
        self._latest_depth = None
        self._lock = threading.Lock()
        
        # 进程
        self._roscore_proc = None
        self._openni2_proc = None
        
        # Spin 线程
        self._spin_thread = None
        self._spinning = False
        
        # 深度处理器
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
        return "orbbec-ros-openni2"
    
    @property
    def camera_model(self) -> str:
        return self._device_info.get('name', 'Orbbec Camera (ROS OpenNI2)')
    
    def _check_ros_master(self) -> bool:
        """检查 ROS master 是否运行"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', 11311))
            sock.close()
            return result == 0
        except:
            return False
    
    def _start_roscore(self) -> bool:
        """启动 roscore"""
        if self._check_ros_master():
            logger.info("ROS master 已运行")
            return True
        
        logger.info("启动 roscore...")
        self._roscore_proc = subprocess.Popen(
            ['roscore'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # 等待启动
        for _ in range(30):
            if self._check_ros_master():
                logger.info("roscore 已启动")
                return True
            time.sleep(0.5)
        
        logger.error("roscore 启动超时")
        return False
    
    def _start_openni2_node(self) -> bool:
        """启动 openni2_camera 节点"""
        logger.info("启动 openni2_camera 节点...")
        
        # 先检查是否已有节点在运行
        try:
            result = subprocess.run(['rostopic', 'list'], capture_output=True, text=True, timeout=5)
            if '/camera/depth/image_raw' in result.stdout or '/camera/depth_registered/image_raw' in result.stdout:
                logger.info("openni2_camera 节点已在运行")
                return True
        except:
            pass
        
        # 尝试不同的启动方式
        launch_commands = [
            ['roslaunch', 'openni2_launch', 'openni2.launch'],
            ['roslaunch', 'openni2_camera', 'camera.launch'],
            ['rosrun', 'openni2_camera', 'openni2_camera_node'],
        ]
        
        for cmd in launch_commands:
            try:
                logger.info(f"尝试: {' '.join(cmd)}")
                self._openni2_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # 等待话题发布
                for _ in range(40):
                    try:
                        result = subprocess.run(['rostopic', 'list'], capture_output=True, text=True, timeout=2)
                        topics = result.stdout
                        if '/camera/depth/image_raw' in topics or '/camera/depth_registered/image_raw' in topics:
                            logger.info(f"✓ openni2_camera 节点已启动")
                            return True
                        # 也检查彩色话题
                        if '/camera/color/image_raw' in topics or '/camera/rgb/image_raw' in topics:
                            logger.info(f"✓ openni2_camera 节点已启动 (彩色)")
                            return True
                    except:
                        pass
                    time.sleep(0.5)
                
                # 这个命令不行，终止并尝试下一个
                if self._openni2_proc:
                    self._openni2_proc.terminate()
                    self._openni2_proc.wait(timeout=3)
                    self._openni2_proc = None
                    
            except FileNotFoundError:
                logger.debug(f"命令不存在: {cmd[0]}")
                continue
            except Exception as e:
                logger.debug(f"启动失败: {e}")
                continue
        
        logger.error("openni2_camera 节点启动失败")
        return False
    
    def _color_callback(self, msg):
        """彩色图像回调"""
        try:
            cv_image = self._cv_bridge.imgmsg_to_cv2(msg, "bgr8")
            with self._lock:
                self._latest_color = cv_image.copy()
        except Exception as e:
            logger.debug(f"彩色回调错误: {e}")
    
    def _depth_callback(self, msg):
        """深度图像回调"""
        try:
            # 深度图通常是 16UC1
            cv_image = self._cv_bridge.imgmsg_to_cv2(msg, "passthrough")
            with self._lock:
                self._latest_depth = cv_image.copy()
        except Exception as e:
            logger.debug(f"深度回调错误: {e}")
    
    def _spin_loop(self):
        """ROS spin 循环"""
        while self._spinning:
            try:
                rospy.spin_once(timeout_sec=0.1)
            except:
                pass
            time.sleep(0.01)
    
    def initialize(self) -> Tuple[bool, str]:
        """初始化相机"""
        if not ROS_AVAILABLE:
            return False, "ROS 未安装"
        
        self._status = CameraStatus.INITIALIZING
        
        try:
            # 启动 roscore
            if not self._start_roscore():
                self._status = CameraStatus.ERROR
                return False, "roscore 启动失败"
            
            # 启动 openni2_camera 节点
            if not self._start_openni2_node():
                self._status = CameraStatus.ERROR
                return False, "openni2_camera 节点启动失败"
            
            # 初始化 ROS 节点（匿名，不阻塞）
            try:
                if not rospy.core.is_initialized():
                    rospy.init_node('orbbec_camera_client', anonymous=True, disable_signals=True)
            except:
                pass
            
            # 创建 CvBridge
            self._cv_bridge = CvBridge()
            
            # 订阅话题
            # 尝试不同的话题名称
            color_topics = [
                '/camera/color/image_raw',
                '/camera/rgb/image_raw',
                '/camera/image_raw'
            ]
            depth_topics = [
                '/camera/depth/image_raw',
                '/camera/depth_registered/image_raw',
                '/camera/depth/image'
            ]
            
            # 找到可用的话题
            result = subprocess.run(['rostopic', 'list'], capture_output=True, text=True, timeout=5)
            available_topics = result.stdout.split('\n')
            
            # 订阅彩色话题
            for topic in color_topics:
                if topic in available_topics:
                    try:
                        self._color_sub = rospy.Subscriber(topic, Image, self._color_callback, queue_size=1)
                        logger.info(f"✓ 订阅彩色话题: {topic}")
                        break
                    except Exception as e:
                        logger.debug(f"订阅 {topic} 失败: {e}")
            
            # 订阅深度话题
            for topic in depth_topics:
                if topic in available_topics:
                    try:
                        self._depth_sub = rospy.Subscriber(topic, Image, self._depth_callback, queue_size=1)
                        logger.info(f"✓ 订阅深度话题: {topic}")
                        break
                    except Exception as e:
                        logger.debug(f"订阅 {topic} 失败: {e}")
            
            if self._color_sub is None and self._depth_sub is None:
                self._status = CameraStatus.ERROR
                return False, "没有可用的相机话题"
            
            # 启动 spin 线程
            self._spinning = True
            self._spin_thread = threading.Thread(target=self._spin_loop, daemon=True)
            self._spin_thread.start()
            
            self._status = CameraStatus.READY
            self._device_info = {'name': 'Orbbec Camera (ROS OpenNI2)'}
            logger.info("✓ 相机初始化成功")
            return True, ""
            
        except Exception as e:
            self._status = CameraStatus.ERROR
            self._last_error = str(e)
            logger.error(f"相机初始化失败: {e}")
            return False, str(e)
    
    def capture(self, wait_frames: int = None, position: Tuple[float, float, float] = None) -> Tuple[Optional[ImagePair], str]:
        """采集图像"""
        if self._status != CameraStatus.READY:
            return None, f"相机未就绪: {self._status.value}"
        
        if wait_frames is None:
            wait_frames = self.DEFAULT_WAIT_FRAMES
        
        self._status = CameraStatus.CAPTURING
        
        try:
            # 等待帧
            time.sleep(wait_frames * 0.033)
            
            # 获取图像
            with self._lock:
                color = self._latest_color.copy() if self._latest_color is not None else None
                depth = self._latest_depth.copy() if self._latest_depth is not None else None
            
            if color is None and depth is None:
                self._status = CameraStatus.READY
                return None, "未收到图像数据"
            
            image_pair = ImagePair(
                rgb=color,
                depth=depth,
                timestamp=time.time(),
                position=position
            )
            
            self._status = CameraStatus.READY
            return image_pair, ""
            
        except Exception as e:
            self._status = CameraStatus.READY
            logger.error(f"采集失败: {e}")
            return None, str(e)
    
    def close(self):
        """关闭相机"""
        # 停止 spin
        self._spinning = False
        if self._spin_thread:
            self._spin_thread.join(timeout=2)
            self._spin_thread = None
        
        # 取消订阅
        if self._color_sub:
            self._color_sub.unregister()
            self._color_sub = None
        if self._depth_sub:
            self._depth_sub.unregister()
            self._depth_sub = None
        
        # 停止节点
        if self._openni2_proc:
            self._openni2_proc.terminate()
            self._openni2_proc.wait(timeout=5)
            self._openni2_proc = None
        
        # 停止 roscore
        if self._roscore_proc:
            self._roscore_proc.terminate()
            self._roscore_proc.wait(timeout=5)
            self._roscore_proc = None
        
        self._status = CameraStatus.DISCONNECTED
        logger.info("相机已关闭")
    
    def get_depth_at_position(self, x: int, y: int, depth_image: np.ndarray = None) -> float:
        """获取指定位置深度"""
        if depth_image is None:
            with self._lock:
                if self._latest_depth is None:
                    return 0.0
                depth_image = self._latest_depth
        
        if 0 <= y < depth_image.shape[0] and 0 <= x < depth_image.shape[1]:
            return float(depth_image[y, x]) / 1000.0
        return 0.0
    
    def configure(self, config: CameraConfig) -> Tuple[bool, str]:
        self._camera_config = config
        return True, ""
    
    def get_config(self) -> CameraConfig:
        return self._camera_config
    
    def get_status(self) -> str:
        return self._status.value
    
    def get_intrinsics(self) -> Optional[dict]:
        return {
            'fx': 525.0, 'fy': 525.0,
            'cx': self.DEFAULT_DEPTH_WIDTH / 2,
            'cy': self.DEFAULT_DEPTH_HEIGHT / 2,
            'coeffs': [0, 0, 0, 0, 0]
        }
    
    def get_depth_at_point(self, x: int, y: int, depth_image: np.ndarray = None) -> float:
        return self.get_depth_at_position(x, y, depth_image)
    
    def get_depth_in_region(self, x: int, y: int, width: int, height: int, 
                           depth_image: np.ndarray = None, method: str = 'median') -> float:
        if depth_image is None:
            with self._lock:
                if self._latest_depth is None:
                    return 0.0
                depth_image = self._latest_depth
        
        return self._depth_processor.get_depth_in_region(
            center_x=x + width // 2,
            center_y=y + height // 2,
            width=width, height=height,
            depth_image=depth_image, method=method
        )
