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
import io
import ctypes
from pathlib import Path

# Preload libgomp globally to mitigate Jetson static TLS issues before cv2 loads.
try:
    ctypes.CDLL("/usr/lib/aarch64-linux-gnu/libgomp.so.1", mode=ctypes.RTLD_GLOBAL)
except Exception:
    pass

# Preload heavy native modules early to avoid libgomp static TLS conflicts at runtime.
try:
    import cv2
    _CV2_IMPORT_ERROR = None
except Exception as e:
    cv2 = None
    _CV2_IMPORT_ERROR = str(e)

try:
    import numpy as np
    _NP_IMPORT_ERROR = None
except Exception as e:
    np = None
    _NP_IMPORT_ERROR = str(e)

try:
    from PIL import Image
except Exception:
    Image = None
redist_path = os.getenv('OPENNI2_REDIST', '/home/richard/OpenNI-Linux-Arm64-2.3/Redist')
os.environ['OPENNI2_REDIST'] = redist_path
current_ld_path = os.getenv('LD_LIBRARY_PATH', '')
if redist_path and redist_path not in current_ld_path:
    os.environ['LD_LIBRARY_PATH'] = f"{redist_path}:{current_ld_path}".strip(':')

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
        self._cv2_cap = None
        self._cv2_failed = False
        self._capture_import_warned = False
    
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
                'comm': self.config.comm.__dict__ if hasattr(self.config, 'comm') else {},
                'detection': self.config.detection.__dict__ if hasattr(self.config, 'detection') else {},
                'visual_servo': self.config.visual_servo.__dict__ if hasattr(self.config, 'visual_servo') else {},
                'face_recognition': self.config.face_recognition.__dict__ if hasattr(self.config, 'face_recognition') else {},
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
        current_status = ""
        try:
            current_status = str(self.camera.get_status() or "").lower()
        except Exception:
            current_status = ""

        if current_status in ("ready", "capturing"):
            success, error = True, ""
            logger.info("Camera controller already initialized by factory, skipping duplicate initialize.")
        else:
            success, error = self.camera.initialize()
        
        if success:
            if not self._probe_camera_stream():
                warn_msg = "camera initialized but no depth frames received in warmup probe"
                logger.warning(f"Camera warmup probe failed: {warn_msg}")
            logger.info(f"✓ 相机已启动: {self.camera.camera_type} - {self.camera.camera_model}")
            logger.info(f"  分辨率: {cam_config.width}x{cam_config.height}@{cam_config.fps}fps")
        else:
            logger.warning(f"✗ 相机启动失败: {error}")
            if not self.config.camera.required:
                logger.info("  相机非必需，继续运行")
                self.camera = None
            else:
                raise RuntimeError(f"相机启动失败: {error}")
    
    def _probe_camera_stream(self) -> bool:
        """Quick warmup probe to verify depth frames are available."""
        if not self.camera:
            return False

        for _ in range(5):
            try:
                image_pair, _ = self.camera.capture(wait_frames=1)
                if image_pair is not None and getattr(image_pair, "depth", None) is not None:
                    return True
            except Exception:
                pass
            time.sleep(0.05)
        return False

    def _init_comm(self):
        """初始化串口通信"""
        from comm.manager import CommManager, CommConfig
        
        comm_config = CommConfig(
            port=self.config.comm.port,
            baudrate=self.config.comm.baudrate,
            timeout=self.config.comm.timeout,
            trace_protocol=self.config.comm.trace_protocol,
            trace_frames_hex=self.config.comm.trace_frames_hex,
            trace_history_size=self.config.comm.trace_history_size,
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
        success, message = self.detector.load_model()
        if hasattr(self.detector, "_last_load_error"):
            self.detector._last_load_error = None if success else message

        detector_status = (
            self.detector.get_runtime_status()
            if hasattr(self.detector, "get_runtime_status")
            else {}
        )

        if success:
            engine = detector_status.get("inference_engine") or "unknown"
            model_path = detector_status.get("model_path") or "(unset)"
            logger.info(f"✓ 目标检测器已初始化: {engine} [{model_path}]")
        else:
            logger.warning(f"✗ 目标检测模型加载失败: {message}")
    
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
        detector_loaded = (
            self.detector.is_loaded()
            if self.detector and hasattr(self.detector, "is_loaded")
            else False
        )
        if not self.camera or not self.comm or not self.detector or not detector_loaded:
            logger.warning("✗ 视觉伺服需要相机、串口和已加载的检测器，跳过初始化")
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
        
        # Web 路由会通过 comm_manager 直接下发运动与配置命令到 STM32。
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
        return self._capture_frame_mixed()

    def _capture_frame_mixed(self):
        if not self.camera:
            return None

        try:
            if np is None:
                if not self._capture_import_warned:
                    logger.error(f"NumPy import failed in capture path: {_NP_IMPORT_ERROR}")
                    self._capture_import_warned = True
                return None

            # If OpenCV is unavailable (e.g. libgomp static TLS issue), keep stream alive
            # with depth-only JPEG frames encoded by Pillow.
            if cv2 is None:
                if not self._capture_import_warned:
                    logger.error(
                        "OpenCV import failed in capture path: %s. "
                        "Hint: export LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libgomp.so.1",
                        _CV2_IMPORT_ERROR,
                    )
                    self._capture_import_warned = True
                return self._capture_frame_depth_only_fallback()

            if self._cv2_cap is None and not self._cv2_failed:
                logger.info("Searching UVC color camera for mixed stream...")
                for index in range(5):
                    cap = cv2.VideoCapture(index)
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                            self._cv2_cap = cap
                            logger.info(f"UVC color stream attached at /dev/video{index}")
                            break
                    cap.release()

                if self._cv2_cap is None:
                    self._cv2_failed = True
                    logger.warning("No UVC color stream available, fallback to depth-only preview.")

            color_img = None
            if self._cv2_cap is not None and self._cv2_cap.isOpened():
                ret, frame = self._cv2_cap.read()
                if ret and frame is not None:
                    color_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            image_pair, _ = self.camera.capture(wait_frames=1)
            depth_img = image_pair.depth if image_pair is not None else None

            if image_pair is not None and color_img is not None:
                image_pair.rgb = color_img

            output_img = None
            if color_img is not None and depth_img is not None:
                color_bgr = cv2.cvtColor(color_img, cv2.COLOR_RGB2BGR)
                depth_norm = cv2.normalize(depth_img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                depth_color = cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)
                h1 = color_bgr.shape[0]
                h2, w2 = depth_color.shape[:2]
                if h1 != h2:
                    depth_color = cv2.resize(depth_color, (int(w2 * (h1 / h2)), h1))
                output_img = np.hstack((color_bgr, depth_color))
            elif color_img is not None:
                output_img = cv2.cvtColor(color_img, cv2.COLOR_RGB2BGR)
            elif depth_img is not None:
                depth_norm = cv2.normalize(depth_img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                output_img = cv2.applyColorMap(depth_norm, cv2.COLORMAP_JET)
                cv2.putText(
                    output_img,
                    "COLOR DOWN, DEPTH ONLY",
                    (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 255),
                    2,
                )

            if output_img is None:
                output_img = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(
                    output_img,
                    "WAITING FOR CAMERA FRAMES",
                    (20, 240),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 255),
                    2,
                )

            success, jpeg = cv2.imencode(".jpg", output_img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return jpeg.tobytes() if success else None
        except Exception as e:
            if not hasattr(self, "_capture_error_logged"):
                logger.error(f"Mixed capture failed (logged once): {e}")
                self._capture_error_logged = True
            return None

    def _capture_frame_depth_only_fallback(self):
        """Depth-only JPEG fallback when OpenCV fails to load."""
        if np is None or Image is None:
            return None

        try:
            image_pair, _ = self.camera.capture(wait_frames=1)
            depth_img = image_pair.depth if image_pair is not None else None

            if depth_img is None:
                rgb = np.zeros((480, 640, 3), dtype=np.uint8)
            else:
                depth = depth_img.astype(np.float32)
                max_val = float(depth.max()) if depth.size else 0.0
                if max_val > 0:
                    depth8 = (depth / max_val * 255.0).astype(np.uint8)
                else:
                    depth8 = np.zeros_like(depth, dtype=np.uint8)
                rgb = np.stack([depth8, depth8, depth8], axis=-1)

            with io.BytesIO() as buf:
                Image.fromarray(rgb, mode="RGB").save(buf, format="JPEG", quality=75)
                return buf.getvalue()
        except Exception as e:
            if not hasattr(self, "_capture_fallback_error_logged"):
                logger.error(f"Depth-only fallback capture failed (logged once): {e}")
                self._capture_fallback_error_logged = True
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
            self.camera.close()
        if self._cv2_cap:
            self._cv2_cap.release()
            self._cv2_cap = None
        
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
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化并启动
    if system.initialize():
        system.start()
    else:
        logger.error("系统初始化失败，退出")
        sys.exit(1)


if __name__ == "__main__":
    main()
