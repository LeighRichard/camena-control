"""
目标跟踪逻辑

提供目标跟踪相关的 Mixin 类
"""

import time
import logging
from typing import Optional, List, Tuple

from .modes import TrackingState, TargetSwitchStrategy
from ..detector import DetectionResult, TargetInfo
from ..processor import PositionAdjustment

logger = logging.getLogger(__name__)


class TargetTrackingMixin:
    """
    目标跟踪 Mixin
    
    提供目标跟踪相关的方法，需要与 VisualServoController 一起使用
    """
    
    def _process_tracking(self, result: DetectionResult, image_pair):
        """处理跟踪模式"""
        self._all_targets = result.targets
        
        if result.selected_target:
            target = result.selected_target
            
            # 更新卡尔曼滤波器
            if not self._kalman.is_initialized():
                self._kalman.initialize(target.center_x, target.center_y)
            else:
                self._kalman.update(target.center_x, target.center_y)
            
            # 获取滤波后的位置
            filtered_x, filtered_y = self._kalman.get_position()
            
            # 预测未来位置
            if self._config.prediction_enabled:
                self._predicted_position = self._kalman.predict_position(
                    self._config.prediction_time
                )
            
            # 更新跟踪状态
            self._update_tracking_state(target)
            
            self._current_target = target
            self._last_target_time = time.time()
            self._target_history.append(target)
            if len(self._target_history) > 30:
                self._target_history.pop(0)
            
            # 使用 PID 控制计算输出
            control_x = self._predicted_position[0] if self._predicted_position else filtered_x
            control_y = self._predicted_position[1] if self._predicted_position else filtered_y
            
            pan_output = self._pan_pid.compute(control_x)
            tilt_output = -self._tilt_pid.compute(control_y)  # Y 轴反向
            
            # 输出平滑
            alpha = self._config.smoothing_factor
            pan_output = alpha * pan_output + (1 - alpha) * self._last_pan_output
            tilt_output = alpha * tilt_output + (1 - alpha) * self._last_tilt_output
            self._last_pan_output = pan_output
            self._last_tilt_output = tilt_output
            
            # 深度控制
            rail_output = 0.0
            if target.distance > 0:
                rail_output = self._rail_pid.compute(target.distance)
            
            # 检查是否在死区内
            pan_error = abs(self._pan_pid.get_error())
            tilt_error = abs(self._tilt_pid.get_error())
            
            if pan_error < self._config.center_tolerance and tilt_error < self._config.center_tolerance:
                self._last_adjustment = PositionAdjustment(
                    pan_delta=0, tilt_delta=0, rail_delta=0, target_in_center=True
                )
                if self._on_centered_callback:
                    self._on_centered_callback(target)
            else:
                self._send_velocity_command(pan_output, tilt_output, rail_output)
                self._last_adjustment = PositionAdjustment(
                    pan_delta=pan_output, tilt_delta=tilt_output,
                    rail_delta=rail_output, target_in_center=False
                )
        else:
            self._handle_no_target()
    
    def _process_tracking_target(self, target: TargetInfo):
        """处理单个目标的跟踪"""
        # 更新卡尔曼滤波器
        if not self._kalman.is_initialized():
            self._kalman.initialize(target.center_x, target.center_y)
        else:
            self._kalman.update(target.center_x, target.center_y)
        
        filtered_x, filtered_y = self._kalman.get_position()
        
        # PID 控制
        pan_output = self._pan_pid.compute(filtered_x)
        tilt_output = -self._tilt_pid.compute(filtered_y)
        
        # 平滑
        alpha = self._config.smoothing_factor
        pan_output = alpha * pan_output + (1 - alpha) * self._last_pan_output
        tilt_output = alpha * tilt_output + (1 - alpha) * self._last_tilt_output
        self._last_pan_output = pan_output
        self._last_tilt_output = tilt_output
        
        # 发送指令
        self._send_velocity_command(pan_output, tilt_output, 0)
    
    def _update_tracking_state(self, target: TargetInfo):
        """更新跟踪状态"""
        if self._tracking_state == TrackingState.NO_TARGET:
            self._acquire_count += 1
            if self._acquire_count >= self._config.acquire_frames:
                self._tracking_state = TrackingState.LOCKED
                self._acquire_count = 0
                logger.info(f"目标锁定: {target.class_name} (置信度: {target.confidence:.2f})")
                if self._on_target_callback:
                    self._on_target_callback(target)
            else:
                self._tracking_state = TrackingState.ACQUIRING
        elif self._tracking_state == TrackingState.LOST:
            self._tracking_state = TrackingState.ACQUIRING
            self._acquire_count = 1
        else:
            self._tracking_state = TrackingState.LOCKED
    
    def _handle_no_target(self):
        """处理无目标情况"""
        self._acquire_count = 0
        
        if self._tracking_state == TrackingState.LOCKED:
            # 使用预测位置继续跟踪
            if self._config.prediction_enabled and self._kalman.is_initialized():
                pred_x, pred_y = self._kalman.predict()
                self._predicted_position = (pred_x, pred_y)
                
                pan_output = self._pan_pid.compute(pred_x)
                tilt_output = -self._tilt_pid.compute(pred_y)
                self._send_velocity_command(pan_output * 0.5, tilt_output * 0.5, 0)
            
            # 检查是否超时
            if time.time() - self._last_target_time > self._config.lost_timeout:
                self._tracking_state = TrackingState.LOST
                self._kalman.reset()
                logger.warning("目标丢失")
                if self._on_lost_callback:
                    self._on_lost_callback()
        elif self._tracking_state == TrackingState.LOST:
            self._tracking_state = TrackingState.NO_TARGET
            self._current_target = None
            self._send_stop_command()
    
    def _select_target_by_strategy(self, targets: List[TargetInfo]) -> Optional[TargetInfo]:
        """根据策略选择目标"""
        if not targets:
            return None
        
        strategy = self._config.switch_strategy
        
        if strategy == TargetSwitchStrategy.MANUAL:
            if self._current_target:
                for t in targets:
                    if t.id == self._current_target.id:
                        return t
            return targets[0]
        
        elif strategy == TargetSwitchStrategy.NEAREST:
            valid = [t for t in targets if t.distance > 0]
            if valid:
                return min(valid, key=lambda t: t.distance)
            cx, cy = self._image_center
            return min(targets, key=lambda t: (t.center_x - cx)**2 + (t.center_y - cy)**2)
        
        elif strategy == TargetSwitchStrategy.LARGEST:
            return max(targets, key=lambda t: t.area)
        
        elif strategy == TargetSwitchStrategy.ROUND_ROBIN:
            self._target_index = (self._target_index + 1) % len(targets)
            return targets[self._target_index]
        
        elif strategy == TargetSwitchStrategy.PRIORITY:
            priority_classes = self._config.priority_classes
            for cls in priority_classes:
                for t in targets:
                    if t.class_name == cls:
                        return t
            return targets[0]
        
        return targets[0]
    
    def _process_multi_target(self, result: DetectionResult, image_pair):
        """处理多目标模式"""
        self._all_targets = result.targets
        
        if not result.targets:
            self._handle_no_target()
            return
        
        target = self._select_target_by_strategy(result.targets)
        
        if target:
            if self._current_target and target.id != self._current_target.id:
                if time.time() - self._last_switch_time > self._config.switch_cooldown:
                    old_target = self._current_target
                    self._current_target = target
                    self._last_switch_time = time.time()
                    self._tracking_state = TrackingState.SWITCHING
                    self._kalman.initialize(target.center_x, target.center_y)
                    
                    if self._on_switch_callback:
                        self._on_switch_callback(old_target, target)
                    
                    logger.info(f"切换目标: {old_target.class_name} -> {target.class_name}")
            else:
                self._current_target = target
            
            self._process_tracking_target(target)
