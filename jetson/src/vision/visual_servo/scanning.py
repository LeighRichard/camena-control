"""
扫描模式逻辑

提供扫描搜索目标相关的 Mixin 类
"""

import time
import logging
from typing import List, Tuple

from .modes import ServoMode, TrackingState
from ..detector import DetectionResult

logger = logging.getLogger(__name__)


class ScanningMixin:
    """
    扫描模式 Mixin
    
    提供扫描搜索目标相关的方法，需要与 VisualServoController 一起使用
    """
    
    def _init_scan_pattern(self):
        """初始化扫描模式"""
        self._scan_positions: List[Tuple[float, float]] = []
        pan_min, pan_max = self._config.scan_pan_range
        tilt_min, tilt_max = self._config.scan_tilt_range
        step = self._config.scan_step
        
        # 蛇形扫描
        tilt = tilt_min
        direction = 1
        while tilt <= tilt_max:
            if direction > 0:
                pan = pan_min
                while pan <= pan_max:
                    self._scan_positions.append((pan, tilt))
                    pan += step
            else:
                pan = pan_max
                while pan >= pan_min:
                    self._scan_positions.append((pan, tilt))
                    pan -= step
            tilt += step
            direction *= -1
        
        self._scan_index = 0
        logger.info(f"扫描模式初始化: {len(self._scan_positions)} 个位置")
    
    def _process_scanning(self, result: DetectionResult, image_pair):
        """处理扫描模式"""
        if result.selected_target:
            logger.info(f"扫描发现目标: {result.selected_target.class_name}")
            self._mode = ServoMode.TRACKING
            self._tracking_state = TrackingState.ACQUIRING
            self._acquire_count = 1
            self._kalman.initialize(
                result.selected_target.center_x,
                result.selected_target.center_y
            )
            return
        
        # 继续扫描
        if not self._scan_positions:
            self._init_scan_pattern()
        
        if self._scan_index < len(self._scan_positions):
            pan, tilt = self._scan_positions[self._scan_index]
            self._move_to_position(pan, tilt)
            self._scan_index += 1
            time.sleep(self._config.scan_dwell_time)
        else:
            self._scan_index = 0
            logger.info("扫描周期完成，重新开始")
    
    def scan_for_target(self, target_class: str = None):
        """
        扫描寻找目标
        
        Args:
            target_class: 指定要寻找的目标类别（可选）
        """
        if target_class:
            self._detector.set_target_class(target_class)
        
        self.start(ServoMode.SCANNING)
