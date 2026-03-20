"""
PID 控制器模块 - 用于视觉伺服的精确控制
"""

import time
from dataclasses import dataclass
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class PIDConfig:
    """PID 配置"""
    kp: float = 1.0             # 比例增益
    ki: float = 0.0             # 积分增益
    kd: float = 0.0             # 微分增益
    
    # 输出限制
    output_min: float = -100.0
    output_max: float = 100.0
    
    # 积分限制（防止积分饱和）
    integral_min: float = -50.0
    integral_max: float = 50.0
    
    # 死区
    deadband: float = 0.0
    
    # 微分滤波系数 (0-1, 越小滤波越强)
    derivative_filter: float = 0.1
    
    # 采样时间（秒），0 表示自动计算
    sample_time: float = 0.0


class PIDController:
    """
    PID 控制器
    
    特性：
    - 积分抗饱和
    - 微分滤波
    - 死区处理
    - 输出限幅
    - 自动/手动切换
    """
    
    def __init__(self, config: PIDConfig = None):
        self._config = config or PIDConfig()
        
        # 状态变量
        self._integral = 0.0
        self._last_error = 0.0
        self._last_derivative = 0.0
        self._last_time = 0.0
        self._last_output = 0.0
        
        # 设定点
        self._setpoint = 0.0
        
        # 模式
        self._enabled = True
        self._auto_mode = True
    
    def compute(self, measurement: float, dt: float = None) -> float:
        """
        计算 PID 输出
        
        Args:
            measurement: 当前测量值
            dt: 时间间隔（秒），None 自动计算
            
        Returns:
            控制输出
        """
        if not self._enabled:
            return self._last_output
        
        # 计算时间间隔
        current_time = time.time()
        if dt is None:
            if self._last_time > 0:
                dt = current_time - self._last_time
            else:
                dt = self._config.sample_time if self._config.sample_time > 0 else 0.1
        self._last_time = current_time
        
        # 防止 dt 过小或过大
        dt = max(0.001, min(1.0, dt))
        
        # 计算误差
        error = self._setpoint - measurement
        
        # 死区处理
        if abs(error) < self._config.deadband:
            error = 0.0
        
        # 比例项
        p_term = self._config.kp * error
        
        # 积分项（带抗饱和）
        self._integral += error * dt
        self._integral = max(self._config.integral_min, 
                            min(self._config.integral_max, self._integral))
        i_term = self._config.ki * self._integral
        
        # 微分项（带滤波）
        if dt > 0:
            derivative = (error - self._last_error) / dt
            # 低通滤波
            alpha = self._config.derivative_filter
            filtered_derivative = alpha * derivative + (1 - alpha) * self._last_derivative
            self._last_derivative = filtered_derivative
            d_term = self._config.kd * filtered_derivative
        else:
            d_term = 0.0
        
        self._last_error = error
        
        # 计算输出
        output = p_term + i_term + d_term
        
        # 输出限幅
        output = max(self._config.output_min, min(self._config.output_max, output))
        
        self._last_output = output
        return output
    
    def set_setpoint(self, setpoint: float):
        """设置目标值"""
        self._setpoint = setpoint
    
    def get_setpoint(self) -> float:
        """获取目标值"""
        return self._setpoint
    
    def reset(self):
        """重置控制器状态"""
        self._integral = 0.0
        self._last_error = 0.0
        self._last_derivative = 0.0
        self._last_time = 0.0
        self._last_output = 0.0
    
    def set_config(self, config: PIDConfig):
        """设置配置"""
        self._config = config
    
    def get_config(self) -> PIDConfig:
        """获取配置"""
        return self._config
    
    def set_gains(self, kp: float = None, ki: float = None, kd: float = None):
        """设置 PID 增益"""
        if kp is not None:
            self._config.kp = kp
        if ki is not None:
            self._config.ki = ki
        if kd is not None:
            self._config.kd = kd
    
    def set_output_limits(self, min_val: float, max_val: float):
        """设置输出限制"""
        self._config.output_min = min_val
        self._config.output_max = max_val
    
    def enable(self, enabled: bool = True):
        """启用/禁用控制器"""
        self._enabled = enabled
        if not enabled:
            self.reset()
    
    def is_enabled(self) -> bool:
        """检查是否启用"""
        return self._enabled
    
    def get_terms(self) -> Tuple[float, float, float]:
        """获取 P、I、D 各项的值（用于调试）"""
        p = self._config.kp * self._last_error
        i = self._config.ki * self._integral
        d = self._config.kd * self._last_derivative
        return p, i, d
    
    def get_error(self) -> float:
        """获取当前误差"""
        return self._last_error
    
    def get_integral(self) -> float:
        """获取积分值"""
        return self._integral


class DualAxisPID:
    """
    双轴 PID 控制器（用于云台控制）
    """
    
    def __init__(
        self,
        pan_config: PIDConfig = None,
        tilt_config: PIDConfig = None
    ):
        # 默认配置
        if pan_config is None:
            pan_config = PIDConfig(
                kp=0.8, ki=0.1, kd=0.05,
                output_min=-30, output_max=30,
                deadband=2.0
            )
        if tilt_config is None:
            tilt_config = PIDConfig(
                kp=0.6, ki=0.08, kd=0.04,
                output_min=-20, output_max=20,
                deadband=2.0
            )
        
        self._pan_pid = PIDController(pan_config)
        self._tilt_pid = PIDController(tilt_config)
        
        # 设定点（图像中心）
        self._center_x = 640.0
        self._center_y = 360.0
    
    def set_image_center(self, center_x: float, center_y: float):
        """设置图像中心（目标位置）"""
        self._center_x = center_x
        self._center_y = center_y
        self._pan_pid.set_setpoint(center_x)
        self._tilt_pid.set_setpoint(center_y)
    
    def compute(self, target_x: float, target_y: float, dt: float = None) -> Tuple[float, float]:
        """
        计算双轴控制输出
        
        Args:
            target_x: 目标 X 坐标（像素）
            target_y: 目标 Y 坐标（像素）
            dt: 时间间隔
            
        Returns:
            (pan_output, tilt_output) 控制输出
        """
        # 注意：PID 计算的是误差，所以输入是当前位置
        pan_output = self._pan_pid.compute(target_x, dt)
        tilt_output = -self._tilt_pid.compute(target_y, dt)  # Y 轴反向
        
        return pan_output, tilt_output
    
    def reset(self):
        """重置两个控制器"""
        self._pan_pid.reset()
        self._tilt_pid.reset()
    
    def enable(self, enabled: bool = True):
        """启用/禁用"""
        self._pan_pid.enable(enabled)
        self._tilt_pid.enable(enabled)
    
    def set_pan_gains(self, kp: float = None, ki: float = None, kd: float = None):
        """设置水平轴增益"""
        self._pan_pid.set_gains(kp, ki, kd)
    
    def set_tilt_gains(self, kp: float = None, ki: float = None, kd: float = None):
        """设置俯仰轴增益"""
        self._tilt_pid.set_gains(kp, ki, kd)
    
    @property
    def pan_pid(self) -> PIDController:
        return self._pan_pid
    
    @property
    def tilt_pid(self) -> PIDController:
        return self._tilt_pid
