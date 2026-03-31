#!/usr/bin/env python3
"""
相机位置控制系统 - 主入口

启动方式：
    python main.py                  # 默认启动
    python main.py --config config.yaml  # 指定配置文件
    python main.py --web-only       # 仅启动 Web 服务
    python main.py --no-camera      # 不启动相机（调试用）
"""

import argparse
import signal
import sys
import time
import logging
import os
from pathlib import Path

# ==============================================================================
# 1. 核心修复：强制注入 OpenNI2 环境变量
# 必须在导入任何包含 C/C++ 扩展的视觉库（如 cv2, openni2）之前执行
# ==============================================================================
redist_path = os.getenv('OPENNI2_REDIST', '/home/richard/OpenNI-Linux-Arm64-2.3/Redist')
os.environ['OPENNI2_REDIST'] = redist_path

# 动态追加 LD_LIBRARY_PATH，确保底层 C 库能正确链接，解决 undefined symbol 报错
current_ld_path = os.getenv('LD_LIBRARY_PATH', '')
if redist_path not in current_ld_path:
    os.environ['LD_LIBRARY_PATH'] = f"{redist_path}:{current_ld_path}".strip(':')

# 注意：此处移除了 openni2.initialize() 和 Device.open_any()。
# 硬件资源的独占式打开，必须交由 CameraControlSystem 内部的 Camera 类来管理。
# ==============================================================================

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.logging_config import setup_logging
from src.utils.config import SystemConfig, load_config
from src.utils.config_validator import ConfigValidator

logger = logging.getLogger(__name__)


class CameraControlSystem:
    """相机位置控制系统主类"""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self._running = False
        
        # 组件实例
        self.camera = None
        self.comm = None
        self.detector = None
        self.face_recognizer = None
        self.visual_servo = None
        self.state_manager = None
        self.scheduler = None
        self.web_server = None
        self.system_monitor = None
        self.alert_manager = None
    
    def initialize(self):
        """初始化所有组件"""
        logger.info("=" * 50)
        logger.info("相机位置控制系统启动中...")
        logger.info("=" * 50)
        
        # 验证配置文件
        logger.info("验证配置参数...")
        try:
            # 将配置对象转换为字典
            config_dict = {
                'camera': self.config.camera.__dict__ if hasattr(self.config, 'camera') else {},
                'serial': self.config.serial.__dict__ if hasattr(self.config, 'serial') else {},
                'detection': self.config.detection.__dict__ if hasattr(self.config, 'detection') else {},
                'web': self.config.web.__dict__ if hasattr(self.config, 'web') else {},
            }
            warnings = ConfigValidator.validate_all(config_dict)
            if warnings:
                logger.warning(f"配置验证发现 {len(warnings)} 个警告:")
                for warning in warnings:
                    logger.warning(f"  ⚠️  {warning}")
            else:
                logger.info("✅ 配置验证通过")
        except Exception as e:
            logger.warning(f"配置验证跳过: {e}")
        logger.info("=" * 50)
        
        try:
            self._init_state_manager()
            
            if self.config.camera.enabled:
                self._init_camera()
            
            if self.config.comm.enabled:
                self._init_comm()
            
            if self.config.detection.enabled:
                self._init_detector()
            
            if self.config.face_recognition.enabled:
                self._init_face_recognizer()
            
            if self.config.visual_servo.enabled:
                self._init_visual_servo()
            
            if self.config.scheduler.enabled:
                self._init_scheduler()
            
            self._init_monitoring()
            
            if self.config.web.enabled:
                self._init_web_server()
            
            logger.info("=" * 50)
            logger.info("系统初始化完成")
            logger.info("=" * 50)
            return True
            
        except Exception as e:
            logger.error(f"系统初始化失败: {e}", exc_info=True)
            return False
    
    def _init_state_manager(self):
        """初始化状态管理器"""
        from state.manager import StateManager
        self.state_manager = StateManager()
        logger.info("✓ 状态管理器已初始化")
    
    def _init_camera(self):
        """初始化相机"""
        from camera.factory import CameraFactory
        from camera.base_controller import CameraConfig
        
        camera_type = getattr(self.config.camera, 'type', 'auto')
        
        if camera_type == 'orbbec' or (camera_type == 'auto' and hasattr(self.config.camera, 'orbbec')):
            orbbec_cfg = self.config.camera.orbbec
            cam_config = CameraConfig(
                width=orbbec_cfg.color.width,
                height=orbbec_cfg.color.height,
                fps=orbbec_cfg.color.fps,
                enable_depth=True
            )
        elif camera_type == 'realsense' or (camera_type == 'auto' and hasattr(self.config.camera, 'realsense')):
            rs_cfg = self.config.camera.realsense
            cam_config = CameraConfig(
                width=rs_cfg.width,
                height=rs_cfg.height,
                fps=rs_cfg.fps,
                enable_depth=rs_cfg.enable_depth
            )
        else:
            cam_config = CameraConfig(
                width=self.config.camera.width,
                height=self.config.camera.height,
                fps=self.config.camera.fps,
                enable_depth=self.config.camera.enable_depth
            )
        
        self.camera = CameraFactory.create_camera(camera_type, cam_config)
        
        if self.camera is None:
            error = f"无法创建相机 (类型: {camera_type})"
            logger.warning(f"✗ {error}")
            if not self.config.camera.required:
                logger.info("  相机非必需，继续运行")
            else:
                raise RuntimeError(error)
            return
        
        success, error = self.camera.initialize()
        
        if success:
            logger.info(f"✓ 相机已启动: {self.camera.camera_type} - {self.camera.camera_model}")
            logger.info(f"  分辨率: {cam_config.width}x{cam_config.height}@{cam_config.fps}fps")
        else:
            logger.warning(f"✗ 相机启动失败: {error}")
            if not self.config.camera.required:
                logger.info("  相机非必需，继续运行")
                self.camera = None
            else:
                raise RuntimeError(f"相机启动失败: {error}")
    
    def _init_comm(self):
        """初始化串口通信"""
        from comm.manager import CommManager, CommConfig
        
        comm_config = CommConfig(
            port=self.config.comm.port,
            baudrate=self.config.comm.baudrate
        )
        
        self.comm = CommManager(config=comm_config)
        
        success = self.comm.connect()
        if success:
            logger.info(f"✓ 串口已连接 ({self.config.comm.port})")
        else:
            logger.warning(f"✗ 串口连接失败")
            if not self.config.comm.required:
                logger.info("  串口非必需，继续运行")
            else:
                raise RuntimeError("串口连接失败")
    
    def _init_detector(self):
        """初始化目标检测器"""
        from vision.detector import ObjectDetector, DetectionConfig
        
        det_config = DetectionConfig(
            model_path=self.config.detection.model_path,
            threshold=self.config.detection.confidence_threshold,
            nms_threshold=self.config.detection.nms_threshold
        )
        
        self.detector = ObjectDetector(det_config)
        logger.info("✓ 目标检测器已初始化")
    
    def _init_face_recognizer(self):
        """初始化人脸识别器"""
        from vision.face_recognition import FaceRecognizer, FaceRecognitionConfig
        
        face_config = FaceRecognitionConfig(
            database_path=self.config.face_recognition.database_path,
            detection_threshold=self.config.face_recognition.detection_threshold,
            recognition_threshold=self.config.face_recognition.recognition_threshold,
            backend=self.config.face_recognition.backend
        )
        
        self.face_recognizer = FaceRecognizer(face_config)
        logger.info(f"✓ 人脸识别器已初始化 (后端: {self.face_recognizer.get_backend()})")
        
    def _init_visual_servo(self):
        """初始化视觉伺服控制器"""
        if not self.camera or not self.comm or not self.detector:
            logger.warning("✗ 视觉伺服需要相机、串口和检测器，跳过初始化")
            return
        
        from vision.visual_servo import VisualServoController, ServoConfig
        
        servo_config = ServoConfig(
            center_tolerance=self.config.visual_servo.center_tolerance,
            max_pan_speed=self.config.visual_servo.max_pan_speed,
            max_tilt_speed=self.config.visual_servo.max_tilt_speed
        )
        
        self.visual_servo = VisualServoController(
            camera=self.camera,
            detector=self.detector,
            comm=self.comm,
            config=servo_config
        )
        
        if self.face_recognizer:
            self.visual_servo.set_face_recognizer(self.face_recognizer)
        
        logger.info("✓ 视觉伺服控制器已初始化")
    
    def _init_scheduler(self):
        """初始化任务调度器"""
        from scheduler.task_scheduler import TaskScheduler
        self.scheduler = TaskScheduler()
        logger.info("✓ 任务调度器已初始化")
    
    def _init_monitoring(self):
        """初始化系统监控"""
        from monitoring.system_monitor import SystemMonitor, MonitorConfig
        from monitoring.alert_manager import AlertManager, AlertType
        
        self.alert_manager = AlertManager(max_history=1000)
        monitor_config = MonitorConfig(
            interval=5.0, cpu_warning=70.0, cpu_critical=90.0,
            memory_warning=75.0, memory_critical=90.0,
            temp_warning=70.0, temp_critical=85.0,
            disk_warning=80.0, disk_critical=95.0,
            alert_duration=30.0, history_size=100
        )
        self.system_monitor = SystemMonitor(monitor_config)
        
        def on_alert(rule, metrics):
            self.alert_manager.send_alert(
                type=AlertType.SYSTEM, level=rule.level.value, title=rule.name,
                message=f"{rule.metric} = {getattr(metrics, rule.metric, 'N/A')}",
                source="system_monitor", metadata={'metric': rule.metric}
            )
        
        self.system_monitor.set_alert_callback(on_alert)
        self.system_monitor.start()
        logger.info("✓ 系统监控已启动")
    
    def _init_web_server(self):
        """初始化 Web 服务器"""
        from web.app import WebServer, WebConfig
        
        web_config = WebConfig(
            host=self.config.web.host,
            port=self.config.web.port,
            enable_auth=self.config.web.enable_auth
        )
        self.web_server = WebServer(web_config)
        
        self.web_server.inject_dependencies(
            state_manager=self.state_manager,
            camera_controller=self.camera,
            comm_manager=self.comm,
            task_scheduler=self.scheduler,
            object_detector=self.detector
        )
        
        if self.face_recognizer and self.web_server.app:
            self.web_server.app.face_recognizer = self.face_recognizer
        if self.visual_servo and self.web_server.app:
            self.web_server.app.visual_servo = self.visual_servo
        if self.system_monitor and self.web_server.app:
            self.web_server.app.system_monitor = self.system_monitor
        if self.alert_manager and self.web_server.app:
            self.web_server.app.alert_manager = self.alert_manager
        
        logger.info(f"✓ Web 服务器已初始化 (http://{web_config.host}:{web_config.port})")
    
    def start(self):
        """启动系统"""
        self._running = True
        
        if self.web_server:
            self.web_server.run(threaded=True)
            if self.camera:
                self.web_server.start_video_capture(self._capture_frame)
        
        logger.info("系统已启动，按 Ctrl+C 停止")
        
        try:
            while self._running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        
        self.stop()
    
    def _capture_frame(self):
        """采集视频帧（修改版：支持彩色与深度的组合推流）"""
        if not self.camera:
            return None
        
        try:
            import cv2
            import numpy as np
            
            image_pair, _ = self.camera.capture(wait_frames=1)
            if image_pair is None:
                return None
            
            # 提取并转换彩色图
            color_img = cv2.cvtColor(image_pair.rgb, cv2.COLOR_RGB2BGR)
            
            # 如果存在深度数据，将其转换为伪彩色，以便在 Web 上直观查看
            if hasattr(image_pair, 'depth') and image_pair.depth is not None:
                # 归一化深度图以进行渲染 (0-255)
                depth_norm = cv2.normalize(image_pair.depth, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                # 应用伪彩色映射 (Jet风格)
                depth_colormap = cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)
                
                # 将尺寸对齐并水平拼接 (左彩色，右深度)
                color_resized = cv2.resize(color_img, (640, 480))
                depth_resized = cv2.resize(depth_colormap, (640, 480))
                output_img = np.hstack((color_resized, depth_resized))
            else:
                # 降级：只有彩色图
                output_img = color_img
            
            # 压缩为 JPEG 流
            _, jpeg = cv2.imencode('.jpg', output_img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return jpeg.tobytes()
            
        except Exception as e:
            logger.error(f"视频流推流异常: {e}")
            return None
    
    def stop(self):
        """停止系统"""
        logger.info("正在停止系统...")
        self._running = False
        
        if self.visual_servo: self.visual_servo.stop()
        if self.scheduler: self.scheduler.stop()
        if self.system_monitor: self.system_monitor.stop()
        if self.web_server: self.web_server.stop()
        if self.camera: self.camera.close()
        if self.comm: self.comm.disconnect()
        
        logger.info("系统已停止")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="相机位置控制系统")
    parser.add_argument("--config", "-c", default="config/system_config.yaml", help="配置文件路径")
    parser.add_argument("--web-only", action="store_true", help="仅启动 Web 服务")
    parser.add_argument("--no-camera", action="store_true", help="不启动相机")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    args = parser.parse_args()
    
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(level=log_level)
    
    config_path = Path(__file__).parent / args.config
    config = load_config(config_path)
    
    if args.web_only:
        config.camera.enabled = False
        config.comm.enabled = False
        config.detection.enabled = False
        config.visual_servo.enabled = False
    if args.no_camera:
        config.camera.enabled = False
        config.camera.required = False
    
    system = CameraControlSystem(config)
    
    def signal_handler(sig, frame):
        logger.info("收到终止信号")
        system.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    if system.initialize():
        system.start()
    else:
        logger.error("系统初始化失败，退出")
        sys.exit(1)


if __name__ == "__main__":
    main()
