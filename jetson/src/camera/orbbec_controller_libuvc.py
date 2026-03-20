"""
奥比中光相机控制器 - libuvc_camera 后端
通过 ROS libuvc_camera 节点获取相机数据

这是经过验证可以工作的方法!
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

# 尝试导入 ROS 相关库
try:
    import rospy
    from sensor_msgs.msg import Image
    from cv_bridge import CvBridge
    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False
    rospy = None
    Image = None

# 尝试导入 cv_bridge
try:
    from cv_bridge import CvBridge
    CV_BRIDGE_AVAILABLE = True
except ImportError:
    CV_BRIDGE_AVAILABLE = False
    CvBridge = None


class CameraStatus(Enum):
    """相机状态"""
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    READY = "ready"
    CAPTURING = "capturing"
    ERROR = "error"


class OrbbecControllerLibUVC(BaseCameraController):
    """奥比中光相机控制器 - libuvc_camera 实现 (已验证可工作)"""
    
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
        self._ros_process = None
        self._roscore_process = None
        self._status = CameraStatus.DISCONNECTED
        self._camera_config = CameraConfig(
            width=self.DEFAULT_COLOR_WIDTH,
            height=self.DEFAULT_COLOR_HEIGHT,
            fps=self.DEFAULT_FPS
        )
        self._last_error = ""
        self._device_info = {}
        self._cv_bridge = None
        self._latest_color_image = None
        self._latest_depth_image = None
        self._color_subscriber = None
        self._depth_subscriber = None
        self._lock = threading.Lock()
        self._ros_node_initialized = False
        
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
        return "orbbec-libuvc"
    
    @property
    def camera_model(self) -> str:
        """获取相机型号"""
        if self._device_info:
            return self._device_info.get('name', 'Unknown Orbbec (libuvc)')
        return "Orbbec (libuvc_camera)"
    
    def _check_ros_available(self) -> bool:
        """检查 ROS 和 libuvc_camera 是否可用"""
        try:
            # 检查 ROS 环境
            if 'ROS_DISTRO' not in os.environ:
                logger.warning("ROS 环境未设置")
                return False
            
            # 检查 catkin_ws
            catkin_ws = os.path.expanduser("~/catkin_ws/devel/setup.bash")
            if not os.path.exists(catkin_ws):
                logger.warning(f"catkin_ws 未找到: {catkin_ws}")
                return False
            
            # 检查 libuvc_camera 包
            result = subprocess.run(
                ['rospack', 'find', 'libuvc_camera'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.info(f"libuvc_camera 可用: {result.stdout.strip()}")
                return True
            else:
                logger.warning("libuvc_camera 包未找到")
                return False
                
        except Exception as e:
            logger.error(f"检查 ROS 失败: {e}")
            return False
    
    def _color_callback(self, msg):
        """彩色图像回调"""
        try:
            if self._cv_bridge and CV_BRIDGE_AVAILABLE:
                cv_image = self._cv_bridge.imgmsg_to_cv2(msg, "bgr8")
                with self._lock:
                    self._latest_color_image = cv_image
        except Exception as e:
            logger.error(f"彩色图像回调失败: {e}")
    
    def _depth_callback(self, msg):
        """深度图像回调"""
        try:
            if self._cv_bridge and CV_BRIDGE_AVAILABLE:
                cv_image = self._cv_bridge.imgmsg_to_cv2(msg, "passthrough")
                with self._lock:
                    self._latest_depth_image = cv_image
        except Exception as e:
            logger.error(f"深度图像回调失败: {e}")
    
    def initialize(self) -> Tuple[bool, str]:
        """
        初始化奥比中光相机 (使用 libuvc_camera)
        
        Returns:
            (成功标志, 错误信息)
        """
        self._status = CameraStatus.INITIALIZING
        
        try:
            # 检查 ROS 是否可用
            if not ROS_AVAILABLE:
                self._status = CameraStatus.ERROR
                return False, "ROS Python 库未安装,请确保已安装 rospy"
            
            if not self._check_ros_available():
                self._status = CameraStatus.ERROR
                return False, "libuvc_camera 不可用,请确保已安装并设置 ROS 环境"
            
            # 检查 cv_bridge
            if not CV_BRIDGE_AVAILABLE:
                self._status = CameraStatus.ERROR
                return False, "cv_bridge 未安装,请运行: sudo apt-get install ros-melodic-cv-bridge"
            
            # 初始化 cv_bridge
            self._cv_bridge = CvBridge()
            
            # 设置 catkin_ws 环境
            catkin_ws = os.path.expanduser("~/catkin_ws/devel/setup.bash")
            env = os.environ.copy()
            env['ROS_PACKAGE_PATH'] = f"{os.path.expanduser('~/catkin_ws/src')}:{env.get('ROS_PACKAGE_PATH', '')}"
            
            # 检查 roscore 是否运行
            logger.info("检查 ROS master...")
            roscore_running = False
            try:
                result = subprocess.run(
                    ['rosnode', 'list'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=3
                )
                if result.returncode == 0:
                    roscore_running = True
                    logger.info("ROS master 已运行")
            except Exception:
                pass
            
            # 如果 roscore 没有运行，启动它
            if not roscore_running:
                logger.info("启动 roscore...")
                self._roscore_process = subprocess.Popen(
                    ['roscore'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                # 等待 roscore 启动
                time.sleep(3)
                logger.info("roscore 已启动")
            
            # 启动 libuvc_camera 节点
            logger.info("启动 libuvc_camera 节点...")
            
            # 使用 subprocess 启动 ROS 节点
            self._ros_process = subprocess.Popen(
                ['rosrun', 'libuvc_camera', 'camera_node'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            
            # 等待节点启动 (带超时)
            logger.info("等待节点启动...")
            max_wait = 10  # 最多等待 10 秒
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                # 检查进程是否退出
                if self._ros_process.poll() is not None:
                    # 进程已退出,读取错误信息
                    stdout, stderr = self._ros_process.communicate(timeout=1)
                    error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "未知错误"
                    self._status = CameraStatus.ERROR
                    logger.error(f"libuvc_camera 节点启动失败: {error_msg}")
                    return False, f"节点启动失败: {error_msg[:200]}"
                
                # 检查是否有输出 (说明节点已启动)
                time.sleep(0.5)
                
            # 最终检查进程状态
            if self._ros_process.poll() is not None:
                stdout, stderr = self._ros_process.communicate(timeout=1)
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "未知错误"
                self._status = CameraStatus.ERROR
                return False, f"节点启动失败: {error_msg[:200]}"
            
            logger.info("libuvc_camera 节点已启动")
            
            # 初始化 ROS 节点（如果还没有初始化）
            if not self._ros_node_initialized:
                try:
                    # 直接初始化 ROS 节点（匿名模式允许重复调用）
                    rospy.init_node('orbbec_libuvc_controller', anonymous=True, disable_signals=True)
                    self._ros_node_initialized = True
                    logger.info("ROS 节点已初始化")
                except rospy.exceptions.ROSInitException as e:
                    # 节点已存在，忽略错误
                    logger.info(f"ROS 节点已存在: {e}")
                    self._ros_node_initialized = True
                except Exception as e:
                    logger.warning(f"ROS 节点初始化警告: {e}")
                    self._ros_node_initialized = True
            
            # 订阅相机话题
            logger.info("订阅相机话题...")
            
            # 尝试多个可能的彩色图像话题（按优先级排序）
            color_topics = [
                '/image_raw',              # libuvc_camera 默认话题
                '/camera/color/image_raw',
                '/camera/rgb/image_raw',
                '/camera/image_raw',
            ]
            
            depth_topics = [
                '/depth/image_raw',
                '/camera/depth/image_raw',
                '/camera/depth/image',
            ]
            
            # 获取已发布的话题列表
            try:
                published_topics = [t[0] for t in rospy.get_published_topics()]
                logger.info(f"已发布的话题: {published_topics}")
            except Exception as e:
                logger.warning(f"获取话题列表失败: {e}")
                published_topics = []
            
            # 订阅彩色图像
            for topic in color_topics:
                if topic in published_topics:
                    try:
                        self._color_subscriber = rospy.Subscriber(
                            topic, Image, self._color_callback, queue_size=1
                        )
                        logger.info(f"✓ 已订阅彩色图像话题: {topic}")
                        break
                    except Exception as e:
                        logger.warning(f"订阅 {topic} 失败: {e}")
            
            # 如果没有找到已发布的话题，订阅默认话题（等待发布者）
            if self._color_subscriber is None:
                default_topic = '/image_raw'
                self._color_subscriber = rospy.Subscriber(
                    default_topic, Image, self._color_callback, queue_size=1
                )
                logger.info(f"已订阅默认彩色图像话题: {default_topic} (等待发布者)")
            
            # 订阅深度图像
            for topic in depth_topics:
                try:
                    topics_list = rospy.get_published_topics()
                    if any(topic in t[0] for t in topics_list):
                        self._depth_subscriber = rospy.Subscriber(
                            topic, Image, self._depth_callback, queue_size=1
                        )
                        logger.info(f"✓ 已订阅深度图像话题: {topic}")
                        break
                except Exception as e:
                    logger.debug(f"订阅 {topic} 失败: {e}")
            
            logger.info("✓ 相机节点已启动，话题已订阅")
            
            self._status = CameraStatus.READY
            self._device_info = {'name': 'Orbbec Camera (libuvc)'}
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
        
        if wait_frames is None:
            wait_frames = self.DEFAULT_WAIT_FRAMES
        
        self._status = CameraStatus.CAPTURING
        
        try:
            # 等待新帧
            time.sleep(wait_frames * 0.033)  # 约 30fps
            
            # 获取最新图像
            with self._lock:
                if self._latest_color_image is None:
                    self._status = CameraStatus.READY
                    return None, "未收到彩色图像数据"
                
                # 复制图像
                color_image = self._latest_color_image.copy()
                depth_image = self._latest_depth_image.copy() if self._latest_depth_image is not None else None
            
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
        # 取消订阅
        if self._color_subscriber is not None:
            try:
                self._color_subscriber.unregister()
                logger.info("彩色图像订阅已取消")
            except Exception as e:
                logger.error(f"取消彩色图像订阅时出错: {e}")
            finally:
                self._color_subscriber = None
        
        if self._depth_subscriber is not None:
            try:
                self._depth_subscriber.unregister()
                logger.info("深度图像订阅已取消")
            except Exception as e:
                logger.error(f"取消深度图像订阅时出错: {e}")
            finally:
                self._depth_subscriber = None
        
        # 停止 ROS 节点
        if self._ros_process is not None:
            try:
                self._ros_process.terminate()
                self._ros_process.wait(timeout=5)
                logger.info("libuvc_camera 节点已停止")
            except Exception as e:
                logger.error(f"停止 ROS 节点时出错: {e}")
                self._ros_process.kill()
            finally:
                self._ros_process = None
        
        # 停止 roscore（如果是我们启动的）
        if self._roscore_process is not None:
            try:
                self._roscore_process.terminate()
                self._roscore_process.wait(timeout=3)
                logger.info("roscore 已停止")
            except Exception as e:
                logger.error(f"停止 roscore 时出错: {e}")
                if self._roscore_process.poll() is None:
                    self._roscore_process.kill()
            finally:
                self._roscore_process = None
        
        self._status = CameraStatus.DISCONNECTED
