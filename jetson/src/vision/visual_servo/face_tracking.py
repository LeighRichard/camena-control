"""
人脸跟踪逻辑

提供人脸跟踪相关的 Mixin 类
"""

import logging
from typing import Optional, List

from .modes import ServoMode, TrackingState
from ..detector import TargetInfo
from ..face_recognition import FaceRecognizer, FaceInfo
from ..processor import PositionAdjustment
from ...camera.controller import ImagePair

logger = logging.getLogger(__name__)


class FaceTrackingMixin:
    """
    人脸跟踪 Mixin
    
    提供人脸跟踪相关的方法，需要与 VisualServoController 一起使用
    """
    
    def _process_face_tracking(self, image_pair: ImagePair):
        """处理人脸跟踪模式"""
        if not self._face_recognizer:
            logger.warning("人脸识别器未设置，切换到普通跟踪模式")
            self._mode = ServoMode.TRACKING
            return
        
        # 人脸检测和识别
        face_result = self._face_recognizer.detect_and_recognize(
            image_pair.rgb,
            image_pair.depth
        )
        
        if face_result.faces:
            face = self._select_face(face_result.faces)
            
            # 更新卡尔曼滤波器
            if not self._kalman.is_initialized():
                self._kalman.initialize(face.center_x, face.center_y)
            else:
                self._kalman.update(face.center_x, face.center_y)
            
            filtered_x, filtered_y = self._kalman.get_position()
            
            # 更新跟踪状态
            self._current_face = face
            self._last_target_time = __import__('time').time()
            
            if self._tracking_state != TrackingState.LOCKED:
                self._acquire_count += 1
                if self._acquire_count >= self._config.acquire_frames:
                    self._tracking_state = TrackingState.LOCKED
                    self._acquire_count = 0
                    logger.info(f"人脸锁定: {face.name} (置信度: {face.confidence:.2f})")
                    if self._on_target_callback:
                        target_info = self._face_to_target_info(face)
                        self._on_target_callback(target_info)
            
            # PID 控制
            pan_output = self._pan_pid.compute(filtered_x)
            tilt_output = -self._tilt_pid.compute(filtered_y)
            
            # 平滑
            alpha = self._config.smoothing_factor
            pan_output = alpha * pan_output + (1 - alpha) * self._last_pan_output
            tilt_output = alpha * tilt_output + (1 - alpha) * self._last_tilt_output
            self._last_pan_output = pan_output
            self._last_tilt_output = tilt_output
            
            # 检查是否居中
            pan_error = abs(self._pan_pid.get_error())
            tilt_error = abs(self._tilt_pid.get_error())
            
            if pan_error < self._config.center_tolerance and tilt_error < self._config.center_tolerance:
                self._last_adjustment = PositionAdjustment(
                    pan_delta=0, tilt_delta=0, rail_delta=0, target_in_center=True
                )
                if self._on_centered_callback:
                    target_info = self._face_to_target_info(face)
                    self._on_centered_callback(target_info)
            else:
                self._send_velocity_command(pan_output, tilt_output, 0)
                self._last_adjustment = PositionAdjustment(
                    pan_delta=pan_output, tilt_delta=tilt_output,
                    rail_delta=0, target_in_center=False
                )
        else:
            self._current_face = None
            self._handle_no_target()
    
    def _select_face(self, faces: List[FaceInfo]) -> FaceInfo:
        """选择要跟踪的人脸"""
        # 优先选择已知人脸
        known_faces = [f for f in faces if f.name != "Unknown"]
        if known_faces:
            return max(known_faces, key=lambda f: f.confidence)
        
        # 否则选择最大的人脸
        return max(faces, key=lambda f: f.area)
    
    def _face_to_target_info(self, face: FaceInfo) -> TargetInfo:
        """将 FaceInfo 转换为 TargetInfo"""
        x, y, w, h = face.bounding_box
        return TargetInfo(
            id=face.id,
            class_id=0,
            class_name=f"face:{face.name}",
            confidence=face.confidence,
            bbox=(x, y, x + w, y + h),
            center_x=face.center_x,
            center_y=face.center_y,
            area=face.area,
            distance=face.distance
        )
    
    def set_face_recognizer(self, recognizer: FaceRecognizer):
        """设置人脸识别器"""
        self._face_recognizer = recognizer
        logger.info("人脸识别器已设置")
    
    def start_face_tracking(self, target_name: str = None):
        """
        开始人脸跟踪
        
        Args:
            target_name: 指定要跟踪的人名（可选）
        """
        if not self._face_recognizer:
            logger.error("人脸识别器未设置")
            return
        
        self._target_face_name = target_name
        self.start(ServoMode.FACE_TRACKING)
        logger.info(f"开始人脸跟踪" + (f": {target_name}" if target_name else ""))
    
    def get_current_face(self) -> Optional[FaceInfo]:
        """获取当前跟踪的人脸"""
        with self._lock:
            return self._current_face
    
    def get_face_tracking_status(self) -> dict:
        """获取人脸跟踪状态"""
        with self._lock:
            status = {
                'mode': self._mode.value,
                'is_face_tracking': self._mode == ServoMode.FACE_TRACKING,
                'tracking_state': self._tracking_state.value,
                'current_face': None
            }
            
            if self._current_face:
                status['current_face'] = {
                    'id': self._current_face.id,
                    'name': self._current_face.name,
                    'confidence': round(self._current_face.confidence, 2),
                    'center': [
                        round(self._current_face.center_x, 1),
                        round(self._current_face.center_y, 1)
                    ],
                    'distance': round(self._current_face.distance, 1) if self._current_face.distance > 0 else None
                }
            
            return status
