"""
居中控制逻辑

提供目标居中相关的 Mixin 类
"""

import time
import logging
from typing import Optional

from .modes import ServoMode, TrackingState
from ..detector import DetectionResult
from ..processor import PositionAdjustment
from ...camera.controller import ImagePair

logger = logging.getLogger(__name__)


class CenteringMixin:
    """
    居中控制 Mixin
    
    提供目标居中相关的方法，需要与 VisualServoController 一起使用
    """
    
    def _process_centering(self, result: DetectionResult, image_pair: ImagePair):
        """处理居中模式"""
        if result.selected_target:
            target = result.selected_target
            
            # 使用 PID 控制
            pan_output = self._pan_pid.compute(target.center_x)
            tilt_output = -self._tilt_pid.compute(target.center_y)
            
            pan_error = abs(self._pan_pid.get_error())
            tilt_error = abs(self._tilt_pid.get_error())
            
            if pan_error < self._config.center_tolerance and tilt_error < self._config.center_tolerance:
                logger.info("目标已居中")
                self._mode = ServoMode.IDLE
                self._send_stop_command()
                if self._on_centered_callback:
                    self._on_centered_callback(target)
            else:
                self._send_velocity_command(pan_output, tilt_output, 0)
        else:
            logger.warning("居中模式下未检测到目标")
            self._mode = ServoMode.IDLE
            self._send_stop_command()
    
    def center_on_target(self, timeout: float = 5.0) -> bool:
        """
        将目标居中（阻塞直到完成或超时）
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否成功居中
        """
        if not self._running:
            self.start(ServoMode.CENTERING)
        else:
            self.set_mode(ServoMode.CENTERING)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_target_centered():
                return True
            if self._mode == ServoMode.IDLE:
                return self.is_target_centered()
            time.sleep(0.1)
        
        logger.warning("居中超时")
        return False
    
    def is_target_centered(self, tolerance: int = None) -> bool:
        """
        检查目标是否居中
        
        Args:
            tolerance: 容差（像素），None 使用配置值
            
        Returns:
            是否居中
        """
        if tolerance is None:
            tolerance = self._config.center_tolerance
        
        with self._lock:
            if self._current_target is None:
                return False
            
            pan_error = abs(self._pan_pid.get_error())
            tilt_error = abs(self._tilt_pid.get_error())
            
            return pan_error < tolerance and tilt_error < tolerance
    
    def capture_when_centered(self, timeout: float = 10.0) -> Optional[ImagePair]:
        """
        当目标居中时拍摄
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            拍摄的图像对，失败返回 None
        """
        if self.center_on_target(timeout):
            image_pair, error = self._camera.capture(wait_frames=2)
            if image_pair:
                logger.info("目标居中拍摄成功")
                return image_pair
            else:
                logger.error(f"拍摄失败: {error}")
        return None
