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
from pathlib import Path

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
            # 1. 初始化状态管理器
            self._init_state_manager()
            
            # 2. 初始化相机
            if self.config.camera.enabled:
                self._init_camera()
            
            # 3. 初始化串口通信
            if self.config.comm.enabled:
                self._init_comm()
            
            # 4. 初始化目标检测器
            if self.config.detection.enabled:
                self._init_detector()
            
            # 5. 初始化人脸识别
            if self.config.face_recognition.enabled:
                self._init_face_recognizer()
            
            # 6. 初始化视觉伺服
            if self.config.visual_servo.enabled:
                self._init_visual_servo()
            
            # 7. 初始化任务调度器
            if self.config.scheduler.enabled:
                self._init_scheduler()
            
            # 8. 初始化系统监控
            self._init_monitoring()
            
            # 9. 初始化 Web 服务器
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
        
        # 获取相机类型配置
        camera_type = getattr(self.config.camera, 'type', 'auto')
        
        # 根据相机类型准备配置
        if camera_type == 'orbbec' or (camera_type == 'auto' and hasattr(self.config.camera, 'orbbec')):
            # 使用 Orbbec 配置
            orbbec_cfg = self.config.camera.orbbec
            cam_config = CameraConfig(
                width=orbbec_cfg.color.width,
                height=orbbec_cfg.color.height,
                fps=orbbec_cfg.color.fps,
                enable_depth=True
            )
        elif camera_type == 'realsense' or (camera_type == 'auto' and hasattr(self.config.camera, 'realsense')):
            # 使用 RealSense 配置
            rs_cfg = self.config.camera.realsense
            cam_config = CameraConfig(
                width=rs_cfg.width,
                height=rs_cfg.height,
                fps=rs_cfg.fps,
                enable_depth=rs_cfg.enable_depth
            )
        else:
            # 使用通用配置（向后兼容）
            cam_config = CameraConfig(
                width=self.config.camera.width,
                height=self.config.camera.height,
                fps=self.config.camera.fps,
                enable_depth=self.config.camera.enable_depth
            )
        
        # 使用工厂创建相机
        self.camera = CameraFactory.create_camera(camera_type, cam_config)
        
        if self.camera is None:
            error = f"无法创建相机 (类型: {camera_type})"
            logger.warning(f"✗ {error}")
            if not self.config.camera.required:
                logger.info("  相机非必需，继续运行")
            else:
                raise RuntimeError(error)
            return
        
        # 初始化相机
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
        from comm.manager import CommManager
        
        self.comm = CommManager(
            port=self.config.comm.port,
            baudrate=self.config.comm.baudrate
        )
        
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
            confidence_threshold=self.config.detection.confidence_threshold,
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
        
        # 显示已注册人脸
        names = self.face_recognizer.get_registered_names()
        if names:
            logger.info(f"  已注册人脸: {', '.join(names)}")
    
    def _init_visual_servo(self):
        """初始化视觉伺服控制器"""
        if not self.camera or not self.comm:
            logger.warning("✗ 视觉伺服需要相机和串口，跳过初始化")
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
        
        # 如果启用了人脸识别，注入到视觉伺服
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
        
        # 创建告警管理器
        self.alert_manager = AlertManager(max_history=1000)
        
        # 创建系统监控器
        monitor_config = MonitorConfig(
            interval=5.0,
            cpu_warning=70.0,
            cpu_critical=90.0,
            memory_warning=75.0,
            memory_critical=90.0,
            temp_warning=70.0,
            temp_critical=85.0,
            disk_warning=80.0,
            disk_critical=95.0,
            alert_duration=30.0,
            history_size=100
        )
        
        self.system_monitor = SystemMonitor(monitor_config)
        
        # 设置告警回调
        def on_alert(rule, metrics):
            """告警回调 - 发送到告警管理器"""
            self.alert_manager.send_alert(
                type=AlertType.SYSTEM,
                level=rule.level.value,
                title=rule.name,
                message=f"{rule.metric} = {getattr(metrics, rule.metric, 'N/A')}, 阈值 = {rule.threshold}",
                source="system_monitor",
                metadata={
                    'metric': rule.metric,
                    'value': getattr(metrics, rule.metric, None),
                    'threshold': rule.threshold
                }
            )
        
        self.system_monitor.set_alert_callback(on_alert)
        
        # 启动监控
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
        
        # 注入依赖
        self.web_server.inject_dependencies(
            state_manager=self.state_manager,
            camera_controller=self.camera,
            comm_manager=self.comm,
            task_scheduler=self.scheduler,
            object_detector=self.detector
        )
        
        # 注入人脸识别器
        if self.face_recognizer and self.web_server.app:
            self.web_server.app.face_recognizer = self.face_recognizer
        
        # 注入视觉伺服
        if self.visual_servo and self.web_server.app:
            self.web_server.app.visual_servo = self.visual_servo
        
        # 注入监控组件
        if self.system_monitor and self.web_server.app:
            self.web_server.app.system_monitor = self.system_monitor
        
        if self.alert_manager and self.web_server.app:
            self.web_server.app.alert_manager = self.alert_manager
        
        logger.info(f"✓ Web 服务器已初始化 (http://{web_config.host}:{web_config.port})")
    
    def start(self):
        """启动系统"""
        self._running = True
        
        # 启动 Web 服务器
        if self.web_server:
            self.web_server.run(threaded=True)
            
            # 启动视频采集
            if self.camera:
                self.web_server.start_video_capture(self._capture_frame)
        
        logger.info("系统已启动，按 Ctrl+C 停止")
        
        # 主循环
        try:
            while self._running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        
        self.stop()
    
    def _capture_frame(self):
        """采集视频帧（用于 Web 流）"""
        if not self.camera:
            return None
        
        try:
            import cv2
            image_pair, _ = self.camera.capture(wait_frames=1)
            if image_pair is None:
                return None
            
            # 转换为 JPEG
            _, jpeg = cv2.imencode(
                '.jpg', 
                cv2.cvtColor(image_pair.rgb, cv2.COLOR_RGB2BGR),
                [cv2.IMWRITE_JPEG_QUALITY, 80]
            )
            return jpeg.tobytes()
        except Exception:
            return None
    
    def stop(self):
        """停止系统"""
        logger.info("正在停止系统...")
        self._running = False
        
        # 停止视觉伺服
        if self.visual_servo:
            self.visual_servo.stop()
        
        # 停止调度器
        if self.scheduler:
            self.scheduler.stop()
        
        # 停止系统监控
        if self.system_monitor:
            self.system_monitor.stop()
        
        # 停止 Web 服务器
        if self.web_server:
            self.web_server.stop()
        
        # 停止相机
        if self.camera:
            self.camera.stop()
        
        # 断开串口
        if self.comm:
            self.comm.disconnect()
        
        logger.info("系统已停止")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="相机位置控制系统")
    parser.add_argument(
        "--config", "-c",
        default="config/system_config.yaml",
        help="配置文件路径"
    )
    parser.add_argument(
        "--web-only",
        action="store_true",
        help="仅启动 Web 服务"
    )
    parser.add_argument(
        "--no-camera",
        action="store_true",
        help="不启动相机（调试用）"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式"
    )
    
    args = parser.parse_args()
    
    # 设置日志
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(level=log_level)
    
    # 加载配置
    config_path = Path(__file__).parent / args.config
    config = load_config(config_path)
    
    # 应用命令行参数
    if args.web_only:
        config.camera.enabled = False
        config.comm.enabled = False
        config.detection.enabled = False
        config.visual_servo.enabled = False
    
    if args.no_camera:
        config.camera.enabled = False
        config.camera.required = False
    
    # 创建并启动系统
    system = CameraControlSystem(config)
    
    # 设置信号处理
    def signal_handler(sig, frame):
        logger.info("收到终止信号")
        system.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化并启动
    if system.initialize():
        system.start()
    else:
        logger.error("系统初始化失败，退出")
        sys.exit(1)


if __name__ == "__main__":
    main()
