"""
视觉伺服主控制器

整合所有功能模块，提供统一的控制接口
"""

import threading
import time
import logging
from typing import Optional, Callable, Tuple, List

from .modes import ServoMode, TrackingState, TargetSwitchStrategy, ServoConfig, ServoStatus
from .tracker import TargetTrackingMixin
from .centering import CenteringMixin
from .scanning import ScanningMixin
from .face_tracking import FaceTrackingMixin

from ..detector import ObjectDetector, DetectionResult, TargetInfo
from ..processor import ImageProcessor, PositionAdjustment
from ..face_recognition import FaceRecognizer, FaceInfo
from ...camera.controller import CameraController, ImagePair
from ...comm.manager import CommManager
from ...comm.protocol import Command, CommandType
from ...control.pid import PIDController
from ...control.kalman import KalmanFilter, TargetTracker

logger = logging.getLogger(__name__)


class VisualServoController(
    TargetTrackingMixin,
    CenteringMixin,
    ScanningMixin,
    FaceTrackingMixin
):
    """
    视觉伺服控制器
    
    将相机图像处理与电机控制结合，实现：
    - 自动目标跟踪（带 PID 控制）
    - 目标位置预测（卡尔曼滤波）
    - 多目标管理和切换
    - 扫描搜索
    - 人脸跟踪
    """
    
    def __init__(
        self,
        camera: CameraController,
        detector: ObjectDetector,
        comm: CommManager,
        config: ServoConfig = None
    ):
        self._camera = camera
        self._detector = detector
        self._comm = comm
        self._config = config or ServoConfig()
        
        # 检测相机类型并调整参数
        self._camera_type = self._detect_camera_type()
        self._adjust_config_for_camera()
        
        # 图像处理器
        cam_config = camera.get_config()
        self._processor = ImageProcessor(
            image_width=cam_config.width,
            image_height=cam_config.height
        )
        self._image_center = (cam_config.width / 2, cam_config.height / 2)
        
        # PID 控制器
        self._pan_pid = PIDController(self._config.pan_pid)
        self._tilt_pid = PIDController(self._config.tilt_pid)
        self._rail_pid = PIDController(self._config.rail_pid)
        
        # 设置 PID 目标为图像中心
        self._pan_pid.set_setpoint(self._image_center[0])
        self._tilt_pid.set_setpoint(self._image_center[1])
        self._rail_pid.set_setpoint(self._config.target_distance)
        
        # 卡尔曼滤波器
        self._kalman = KalmanFilter(self._config.kalman)
        self._target_tracker = TargetTracker(self._config.kalman)
        
        # 状态
        self._mode = ServoMode.IDLE
        self._tracking_state = TrackingState.NO_TARGET
        self._current_target: Optional[TargetInfo] = None
        self._current_track_id: Optional[int] = None
        self._last_adjustment: Optional[PositionAdjustment] = None
        
        # 跟踪历史
        self._target_history: List[TargetInfo] = []
        self._last_target_time = 0.0
        self._acquire_count = 0
        self._last_switch_time = 0.0
        
        # 多目标管理
        self._all_targets: List[TargetInfo] = []
        self._target_index = 0
        
        # 扫描状态
        self._scan_positions: List[Tuple[float, float]] = []
        self._scan_index = 0
        
        # 输出平滑
        self._last_pan_output = 0.0
        self._last_tilt_output = 0.0
        
        # 控制线程
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # 回调
        self._on_target_callback: Optional[Callable[[TargetInfo], None]] = None
        self._on_lost_callback: Optional[Callable[[], None]] = None
        self._on_centered_callback: Optional[Callable[[TargetInfo], None]] = None
        self._on_switch_callback: Optional[Callable[[TargetInfo, TargetInfo], None]] = None
        
        # 性能统计
        self._frame_count = 0
        self._last_fps_time = time.time()
        self._current_fps = 0.0
        
        # 预测位置
        self._predicted_position: Optional[Tuple[float, float]] = None
        
        # 人脸识别器
        self._face_recognizer: Optional[FaceRecognizer] = None
        self._current_face: Optional[FaceInfo] = None
        self._target_face_name: Optional[str] = None
    
    # ==================== 生命周期方法 ====================
    
    def start(self, mode: ServoMode = ServoMode.TRACKING):
        """启动视觉伺服"""
        if self._running:
            return
        
        self._mode = mode
        self._running = True
        self._reset_controllers()
        self._thread = threading.Thread(target=self._control_loop, daemon=True)
        self._thread.start()
        logger.info(f"视觉伺服已启动，模式: {mode.value}")
    
    def stop(self):
        """停止视觉伺服"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._mode = ServoMode.IDLE
        self._send_stop_command()
        logger.info("视觉伺服已停止")
    
    def set_mode(self, mode: ServoMode):
        """设置伺服模式"""
        with self._lock:
            old_mode = self._mode
            self._mode = mode
            
            if mode == ServoMode.SCANNING:
                self._init_scan_pattern()
            elif mode == ServoMode.IDLE:
                self._send_stop_command()
            
            if mode != old_mode:
                self._reset_controllers()
            
            logger.info(f"伺服模式切换: {old_mode.value} -> {mode.value}")
    
    def _reset_controllers(self):
        """重置所有控制器"""
        self._pan_pid.reset()
        self._tilt_pid.reset()
        self._rail_pid.reset()
        self._kalman.reset()
        self._target_tracker.reset()
        self._last_pan_output = 0.0
        self._last_tilt_output = 0.0
        self._acquire_count = 0
    
    def _detect_camera_type(self) -> str:
        """
        检测相机类型
        
        Returns:
            相机类型: "realsense", "orbbec", "unknown"
        """
        try:
            # 尝试获取相机类型属性
            if hasattr(self._camera, 'camera_type'):
                camera_type = self._camera.camera_type
                logger.info(f"检测到相机类型: {camera_type}")
                return camera_type
            
            # 尝试从类名推断
            class_name = self._camera.__class__.__name__.lower()
            if 'orbbec' in class_name:
                logger.info("从类名推断相机类型: orbbec")
                return "orbbec"
            elif 'realsense' in class_name:
                logger.info("从类名推断相机类型: realsense")
                return "realsense"
            
            logger.warning("无法检测相机类型，使用默认参数")
            return "unknown"
        except Exception as e:
            logger.error(f"检测相机类型失败: {e}")
            return "unknown"
    
    def _adjust_config_for_camera(self):
        """
        根据相机类型调整配置参数
        
        Orbbec 相机特性：
        - 最小工作距离: 0.6m (vs RealSense 0.3m)
        - 最大工作距离: 6.0m (vs RealSense 8.0m)
        - 深度置信度: 0.7 (vs RealSense 0.8)
        - 滤波窗口: 5×5 (vs RealSense 3×3)
        """
        if self._camera_type == "orbbec":
            logger.info("应用 Orbbec 相机参数配置")
            
            # 调整工作距离范围
            # 注意：这些参数可能在 ServoConfig 中没有直接对应，
            # 但我们可以通过调整 target_distance 和相关容差来适配
            
            # 如果目标距离小于 Orbbec 最小距离，调整到安全值
            if hasattr(self._config, 'target_distance'):
                if self._config.target_distance < 0.6:
                    old_distance = self._config.target_distance
                    self._config.target_distance = 1.0  # 设置为 1m 作为安全默认值
                    logger.warning(
                        f"目标距离 {old_distance}m 小于 Orbbec 最小距离 0.6m，"
                        f"已调整为 {self._config.target_distance}m"
                    )
                elif self._config.target_distance > 6.0:
                    old_distance = self._config.target_distance
                    self._config.target_distance = 5.0  # 设置为 5m 作为安全默认值
                    logger.warning(
                        f"目标距离 {old_distance}m 超过 Orbbec 最大距离 6.0m，"
                        f"已调整为 {self._config.target_distance}m"
                    )
            
            # 记录相机参数特性（用于调试和日志）
            self._camera_params = {
                'min_distance': 0.6,
                'max_distance': 6.0,
                'depth_confidence': 0.7,
                'filter_size': 5,
                'depth_resolution': (640, 480),
                'color_resolution': (1920, 1080)
            }
            
            logger.info(f"Orbbec 相机参数: {self._camera_params}")
            
        elif self._camera_type == "realsense":
            logger.info("应用 RealSense 相机参数配置")
            
            self._camera_params = {
                'min_distance': 0.3,
                'max_distance': 8.0,
                'depth_confidence': 0.8,
                'filter_size': 3,
                'depth_resolution': (1280, 720),
                'color_resolution': (1280, 720)
            }
            
            logger.info(f"RealSense 相机参数: {self._camera_params}")
        
        else:
            logger.info("使用默认相机参数配置")
            
            self._camera_params = {
                'min_distance': 0.3,
                'max_distance': 8.0,
                'depth_confidence': 0.8,
                'filter_size': 3,
                'depth_resolution': (1280, 720),
                'color_resolution': (1280, 720)
            }
    
    # ==================== 主控制循环 ====================
    
    def _control_loop(self):
        """主控制循环"""
        interval = 1.0 / self._config.update_rate
        
        while self._running:
            loop_start = time.time()
            
            try:
                # 采集图像
                image_pair, error = self._camera.capture(wait_frames=1)
                if image_pair is None:
                    logger.warning(f"图像采集失败: {error}")
                    time.sleep(interval)
                    continue
                
                # 目标检测
                result = self._detector.detect(image_pair.rgb, image_pair.depth)
                
                # 更新多目标跟踪器
                if result.targets:
                    detections = [
                        (t.center_x, t.center_y, t.class_id)
                        for t in result.targets
                    ]
                    self._target_tracker.update(detections)
                
                # 根据模式处理
                with self._lock:
                    if self._mode == ServoMode.TRACKING:
                        self._process_tracking(result, image_pair)
                    elif self._mode == ServoMode.SCANNING:
                        self._process_scanning(result, image_pair)
                    elif self._mode == ServoMode.CENTERING:
                        self._process_centering(result, image_pair)
                    elif self._mode == ServoMode.MULTI_TARGET:
                        self._process_multi_target(result, image_pair)
                    elif self._mode == ServoMode.FACE_TRACKING:
                        self._process_face_tracking(image_pair)
                
                # 更新 FPS
                self._update_fps()
                
            except Exception as e:
                logger.error(f"控制循环错误: {e}", exc_info=True)
            
            # 控制循环频率
            elapsed = time.time() - loop_start
            if elapsed < interval:
                time.sleep(interval - elapsed)
    
    # ==================== 通信方法 ====================
    
    def _send_velocity_command(self, pan: float, tilt: float, rail: float = 0):
        """发送速度控制指令"""
        pan = max(-self._config.max_pan_speed, min(self._config.max_pan_speed, pan))
        tilt = max(-self._config.max_tilt_speed, min(self._config.max_tilt_speed, tilt))
        rail = max(-self._config.max_rail_speed, min(self._config.max_rail_speed, rail))
        
        if abs(pan) < 0.5:
            pan = 0
        if abs(tilt) < 0.5:
            tilt = 0
        if abs(rail) < 1.0:
            rail = 0
        
        if pan == 0 and tilt == 0 and rail == 0:
            return
        
        cmd = Command(
            cmd_type=CommandType.SET_VELOCITY,
            data={'pan': pan, 'tilt': tilt, 'rail': rail}
        )
        self._comm.send_command(cmd, wait_response=False)
    
    def _send_stop_command(self):
        """发送停止指令"""
        cmd = Command(cmd_type=CommandType.STOP)
        self._comm.send_command(cmd, wait_response=False)
    
    def _move_to_position(self, pan: float, tilt: float, rail: float = None):
        """移动到指定位置"""
        data = {'pan': pan, 'tilt': tilt}
        if rail is not None:
            data['rail'] = rail
        
        cmd = Command(cmd_type=CommandType.MOVE_ABSOLUTE, data=data)
        self._comm.send_command(cmd, wait_response=True)
    
    def _update_fps(self):
        """更新 FPS"""
        self._frame_count += 1
        now = time.time()
        elapsed = now - self._last_fps_time
        if elapsed >= 1.0:
            self._current_fps = self._frame_count / elapsed
            self._frame_count = 0
            self._last_fps_time = now
    
    # ==================== 状态查询方法 ====================
    
    def get_status(self) -> ServoStatus:
        """获取当前伺服状态"""
        with self._lock:
            return ServoStatus(
                mode=self._mode,
                tracking_state=self._tracking_state,
                target=self._current_target,
                adjustment=self._last_adjustment,
                fps=self._current_fps,
                last_update=self._last_target_time,
                pid_error=(self._pan_pid.get_error(), self._tilt_pid.get_error()),
                predicted_position=self._predicted_position,
                tracked_targets=len(self._all_targets)
            )
    
    def get_current_target(self) -> Optional[TargetInfo]:
        """获取当前跟踪目标"""
        with self._lock:
            return self._current_target
    
    def is_tracking(self) -> bool:
        """检查是否正在跟踪目标"""
        with self._lock:
            return (self._tracking_state == TrackingState.LOCKED and
                    self._current_target is not None)
    
    def get_all_targets(self) -> List[TargetInfo]:
        """获取所有检测到的目标"""
        with self._lock:
            return self._all_targets.copy()
    
    def get_target_count(self) -> int:
        """获取当前目标数量"""
        with self._lock:
            return len(self._all_targets)
    
    # ==================== 回调设置方法 ====================
    
    def on_target_acquired(self, callback: Callable[[TargetInfo], None]):
        """设置目标捕获回调"""
        self._on_target_callback = callback
    
    def on_target_lost(self, callback: Callable[[], None]):
        """设置目标丢失回调"""
        self._on_lost_callback = callback
    
    def on_target_centered(self, callback: Callable[[TargetInfo], None]):
        """设置目标居中回调"""
        self._on_centered_callback = callback
    
    def on_switch_callback(self, callback: Callable[[TargetInfo, TargetInfo], None]):
        """设置目标切换回调"""
        self._on_switch_callback = callback
    
    # ==================== 配置方法 ====================
    
    def set_config(self, config: ServoConfig):
        """设置伺服配置"""
        with self._lock:
            self._config = config
            self._pan_pid.set_config(config.pan_pid)
            self._tilt_pid.set_config(config.tilt_pid)
            self._rail_pid.set_config(config.rail_pid)
            self._kalman.set_config(config.kalman)
            self._rail_pid.set_setpoint(config.target_distance)
    
    def get_config(self) -> ServoConfig:
        """获取当前配置"""
        return self._config
    
    def set_gains(
        self,
        pan_kp: float = None, pan_ki: float = None, pan_kd: float = None,
        tilt_kp: float = None, tilt_ki: float = None, tilt_kd: float = None
    ):
        """设置 PID 增益"""
        with self._lock:
            if any(v is not None for v in [pan_kp, pan_ki, pan_kd]):
                self._pan_pid.set_gains(pan_kp, pan_ki, pan_kd)
            if any(v is not None for v in [tilt_kp, tilt_ki, tilt_kd]):
                self._tilt_pid.set_gains(tilt_kp, tilt_ki, tilt_kd)
    
    def set_tolerance(self, tolerance: int):
        """设置居中容差"""
        self._config.center_tolerance = tolerance
    
    def set_target_distance(self, distance: float, tolerance: float = None):
        """设置目标距离"""
        self._config.target_distance = distance
        self._rail_pid.set_setpoint(distance)
        if tolerance is not None:
            self._config.distance_tolerance = tolerance
    
    def set_switch_strategy(self, strategy: TargetSwitchStrategy):
        """设置目标切换策略"""
        self._config.switch_strategy = strategy
        logger.info(f"切换策略设置为: {strategy.value}")
    
    # ==================== 跟踪控制方法 ====================
    
    def track_target(self, target_class: str = None):
        """开始跟踪目标"""
        if target_class:
            self._detector.set_target_class(target_class)
        self.start(ServoMode.TRACKING)
    
    def switch_to_next_target(self) -> bool:
        """切换到下一个目标"""
        with self._lock:
            if len(self._all_targets) < 2:
                return False
            
            if time.time() - self._last_switch_time < self._config.switch_cooldown:
                logger.warning("切换冷却中")
                return False
            
            self._target_index = (self._target_index + 1) % len(self._all_targets)
            new_target = self._all_targets[self._target_index]
            
            old_target = self._current_target
            self._current_target = new_target
            self._last_switch_time = time.time()
            
            self._kalman.initialize(new_target.center_x, new_target.center_y)
            
            if self._on_switch_callback and old_target:
                self._on_switch_callback(old_target, new_target)
            
            logger.info(f"切换到目标: {new_target.class_name}")
            return True
    
    def switch_to_target(self, target_id: int) -> bool:
        """切换到指定目标"""
        with self._lock:
            for i, target in enumerate(self._all_targets):
                if target.id == target_id:
                    if time.time() - self._last_switch_time < self._config.switch_cooldown:
                        logger.warning("切换冷却中")
                        return False
                    
                    old_target = self._current_target
                    self._current_target = target
                    self._target_index = i
                    self._last_switch_time = time.time()
                    
                    self._kalman.initialize(target.center_x, target.center_y)
                    
                    if self._on_switch_callback and old_target:
                        self._on_switch_callback(old_target, target)
                    
                    logger.info(f"切换到目标 ID {target_id}: {target.class_name}")
                    return True
            
            logger.warning(f"未找到目标 ID: {target_id}")
            return False
    
    # ==================== Web 接口方法 ====================
    
    def get_web_status(self) -> dict:
        """获取 Web 界面显示用的状态信息"""
        with self._lock:
            status = {
                'mode': self._mode.value,
                'tracking_state': self._tracking_state.value,
                'fps': round(self._current_fps, 1),
                'target_count': len(self._all_targets),
                'is_tracking': self._tracking_state == TrackingState.LOCKED,
                'is_centered': self.is_target_centered(),
                'camera_type': self._camera_type,
                'camera_params': self._camera_params if hasattr(self, '_camera_params') else {},
                'pid_error': {
                    'pan': round(self._pan_pid.get_error(), 1),
                    'tilt': round(self._tilt_pid.get_error(), 1)
                }
            }
            
            if self._current_target:
                status['current_target'] = {
                    'id': self._current_target.id,
                    'class': self._current_target.class_name,
                    'confidence': round(self._current_target.confidence, 2),
                    'center': [
                        round(self._current_target.center_x, 1),
                        round(self._current_target.center_y, 1)
                    ],
                    'distance': round(self._current_target.distance, 1) if self._current_target.distance > 0 else None
                }
            
            if self._predicted_position:
                status['predicted_position'] = [
                    round(self._predicted_position[0], 1),
                    round(self._predicted_position[1], 1)
                ]
            
            if self._all_targets:
                status['all_targets'] = [
                    {
                        'id': t.id,
                        'class': t.class_name,
                        'confidence': round(t.confidence, 2),
                        'center': [round(t.center_x, 1), round(t.center_y, 1)]
                    }
                    for t in self._all_targets
                ]
            
            return status
    
    def handle_web_command(self, command: str, params: dict = None) -> dict:
        """处理来自 Web 界面的命令"""
        params = params or {}
        
        try:
            if command == 'start_tracking':
                self.track_target(params.get('target_class'))
                return {'success': True, 'message': '开始跟踪'}
            
            elif command == 'stop':
                self.stop()
                return {'success': True, 'message': '已停止'}
            
            elif command == 'scan':
                self.scan_for_target(params.get('target_class'))
                return {'success': True, 'message': '开始扫描'}
            
            elif command == 'center':
                success = self.center_on_target(timeout=params.get('timeout', 5.0))
                return {'success': success, 'message': '居中完成' if success else '居中失败'}
            
            elif command == 'switch_target':
                target_id = params.get('target_id')
                if target_id is not None:
                    success = self.switch_to_target(target_id)
                else:
                    success = self.switch_to_next_target()
                return {'success': success, 'message': '切换成功' if success else '切换失败'}
            
            elif command == 'set_mode':
                mode_str = params.get('mode', 'idle')
                mode = ServoMode(mode_str)
                self.set_mode(mode)
                return {'success': True, 'message': f'模式设置为 {mode_str}'}
            
            elif command == 'set_gains':
                self.set_gains(
                    pan_kp=params.get('pan_kp'),
                    pan_ki=params.get('pan_ki'),
                    pan_kd=params.get('pan_kd'),
                    tilt_kp=params.get('tilt_kp'),
                    tilt_ki=params.get('tilt_ki'),
                    tilt_kd=params.get('tilt_kd')
                )
                return {'success': True, 'message': 'PID 增益已更新'}
            
            elif command == 'set_strategy':
                strategy_str = params.get('strategy', 'nearest')
                strategy = TargetSwitchStrategy(strategy_str)
                self.set_switch_strategy(strategy)
                return {'success': True, 'message': f'切换策略设置为 {strategy_str}'}
            
            elif command == 'capture':
                image_pair = self.capture_when_centered(timeout=params.get('timeout', 10.0))
                return {
                    'success': image_pair is not None,
                    'message': '拍摄成功' if image_pair else '拍摄失败'
                }
            
            else:
                return {'success': False, 'message': f'未知命令: {command}'}
        
        except Exception as e:
            logger.error(f"Web 命令执行错误: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}
    
    # ==================== 调试方法 ====================
    
    def get_debug_info(self) -> dict:
        """获取调试信息"""
        with self._lock:
            pan_p, pan_i, pan_d = self._pan_pid.get_terms()
            tilt_p, tilt_i, tilt_d = self._tilt_pid.get_terms()
            
            return {
                'mode': self._mode.value,
                'tracking_state': self._tracking_state.value,
                'fps': self._current_fps,
                'camera_type': self._camera_type,
                'camera_params': self._camera_params if hasattr(self, '_camera_params') else {},
                'kalman_initialized': self._kalman.is_initialized(),
                'pan_pid': {
                    'error': self._pan_pid.get_error(),
                    'p_term': pan_p,
                    'i_term': pan_i,
                    'd_term': pan_d,
                    'integral': self._pan_pid.get_integral()
                },
                'tilt_pid': {
                    'error': self._tilt_pid.get_error(),
                    'p_term': tilt_p,
                    'i_term': tilt_i,
                    'd_term': tilt_d,
                    'integral': self._tilt_pid.get_integral()
                },
                'target_history_length': len(self._target_history),
                'tracked_targets': len(self._all_targets),
                'last_output': {
                    'pan': self._last_pan_output,
                    'tilt': self._last_tilt_output
                }
            }
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.stop()
        return False
