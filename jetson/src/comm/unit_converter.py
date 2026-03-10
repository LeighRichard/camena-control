"""
单位转换工具模块 - 处理 Jetson 和 STM32 之间的单位转换

Jetson 使用人类友好的单位（度、毫米），STM32 使用步进电机的步数。
本模块提供双向转换功能和参数验证。
"""

from typing import Tuple
import logging

logger = logging.getLogger(__name__)


# 硬件参数常量（与 STM32 motion.h 保持一致）
STEPS_PER_REV_PAN = 3200    # Pan 轴每圈步数 (200 步 × 16 细分)
STEPS_PER_REV_TILT = 3200   # Tilt 轴每圈步数
STEPS_PER_MM_RAIL = 80      # Rail 轴每毫米步数

# STM32 硬件限制（步/秒）
MAX_SPEED_PAN_STEPS = 1000   # Pan 轴最大速度
MAX_SPEED_TILT_STEPS = 800   # Tilt 轴最大速度
MAX_SPEED_RAIL_STEPS = 500   # Rail 轴最大速度

# STM32 硬件限制（步/秒²）
MAX_ACCEL_PAN_STEPS = 500    # Pan 轴最大加速度
MAX_ACCEL_TILT_STEPS = 400   # Tilt 轴最大加速度
MAX_ACCEL_RAIL_STEPS = 300   # Rail 轴最大加速度

# 运动范围限制
PAN_MIN_ANGLE = -180.0
PAN_MAX_ANGLE = 180.0
TILT_MIN_ANGLE = -90.0
TILT_MAX_ANGLE = 90.0
RAIL_MIN_POS = 0.0
RAIL_MAX_POS = 500.0


class UnitConverter:
    """单位转换器"""
    
    @staticmethod
    def degrees_to_steps(degrees: float, axis: str) -> int:
        """
        将角度转换为步数
        
        Args:
            degrees: 角度值
            axis: 轴名称 ('pan' 或 'tilt')
            
        Returns:
            步数（整数）
        """
        if axis == 'pan':
            steps_per_rev = STEPS_PER_REV_PAN
        elif axis == 'tilt':
            steps_per_rev = STEPS_PER_REV_TILT
        else:
            raise ValueError(f"不支持的轴: {axis}")
        
        return int((degrees / 360.0) * steps_per_rev)
    
    @staticmethod
    def steps_to_degrees(steps: int, axis: str) -> float:
        """
        将步数转换为角度
        
        Args:
            steps: 步数
            axis: 轴名称 ('pan' 或 'tilt')
            
        Returns:
            角度值（浮点数）
        """
        if axis == 'pan':
            steps_per_rev = STEPS_PER_REV_PAN
        elif axis == 'tilt':
            steps_per_rev = STEPS_PER_REV_TILT
        else:
            raise ValueError(f"不支持的轴: {axis}")
        
        return (steps / steps_per_rev) * 360.0
    
    @staticmethod
    def mm_to_steps(mm: float) -> int:
        """
        将毫米转换为步数（Rail 轴）
        
        Args:
            mm: 毫米值
            
        Returns:
            步数（整数）
        """
        return int(mm * STEPS_PER_MM_RAIL)
    
    @staticmethod
    def steps_to_mm(steps: int) -> float:
        """
        将步数转换为毫米（Rail 轴）
        
        Args:
            steps: 步数
            
        Returns:
            毫米值（浮点数）
        """
        return steps / STEPS_PER_MM_RAIL
    
    @staticmethod
    def speed_to_steps(speed: float, axis: str) -> int:
        """
        将速度转换为步/秒
        
        Args:
            speed: 速度值（度/秒 或 mm/秒）
            axis: 轴名称 ('pan', 'tilt', 'rail')
            
        Returns:
            步/秒（整数）
        """
        if axis in ['pan', 'tilt']:
            return UnitConverter.degrees_to_steps(speed, axis)
        elif axis == 'rail':
            return UnitConverter.mm_to_steps(speed)
        else:
            raise ValueError(f"不支持的轴: {axis}")
    
    @staticmethod
    def steps_to_speed(steps_per_sec: int, axis: str) -> float:
        """
        将步/秒转换为速度
        
        Args:
            steps_per_sec: 步/秒
            axis: 轴名称 ('pan', 'tilt', 'rail')
            
        Returns:
            速度值（度/秒 或 mm/秒）
        """
        if axis in ['pan', 'tilt']:
            return UnitConverter.steps_to_degrees(steps_per_sec, axis)
        elif axis == 'rail':
            return UnitConverter.steps_to_mm(steps_per_sec)
        else:
            raise ValueError(f"不支持的轴: {axis}")
    
    @staticmethod
    def accel_to_steps(accel: float, axis: str) -> int:
        """
        将加速度转换为步/秒²
        
        Args:
            accel: 加速度值（度/秒² 或 mm/秒²）
            axis: 轴名称 ('pan', 'tilt', 'rail')
            
        Returns:
            步/秒²（整数）
        """
        if axis in ['pan', 'tilt']:
            return UnitConverter.degrees_to_steps(accel, axis)
        elif axis == 'rail':
            return UnitConverter.mm_to_steps(accel)
        else:
            raise ValueError(f"不支持的轴: {axis}")
    
    @staticmethod
    def steps_to_accel(steps_per_sec2: int, axis: str) -> float:
        """
        将步/秒²转换为加速度
        
        Args:
            steps_per_sec2: 步/秒²
            axis: 轴名称 ('pan', 'tilt', 'rail')
            
        Returns:
            加速度值（度/秒² 或 mm/秒²）
        """
        if axis in ['pan', 'tilt']:
            return UnitConverter.steps_to_degrees(steps_per_sec2, axis)
        elif axis == 'rail':
            return UnitConverter.steps_to_mm(steps_per_sec2)
        else:
            raise ValueError(f"不支持的轴: {axis}")


class MotionValidator:
    """运动参数验证器"""
    
    @staticmethod
    def validate_position(position: float, axis: str) -> Tuple[bool, str]:
        """
        验证位置是否在有效范围内
        
        Args:
            position: 位置值（度 或 mm）
            axis: 轴名称 ('pan', 'tilt', 'rail')
            
        Returns:
            (是否有效, 错误信息)
        """
        if axis == 'pan':
            if not (PAN_MIN_ANGLE <= position <= PAN_MAX_ANGLE):
                return False, f"Pan 位置 {position}° 超出范围 [{PAN_MIN_ANGLE}, {PAN_MAX_ANGLE}]"
        elif axis == 'tilt':
            if not (TILT_MIN_ANGLE <= position <= TILT_MAX_ANGLE):
                return False, f"Tilt 位置 {position}° 超出范围 [{TILT_MIN_ANGLE}, {TILT_MAX_ANGLE}]"
        elif axis == 'rail':
            if not (RAIL_MIN_POS <= position <= RAIL_MAX_POS):
                return False, f"Rail 位置 {position}mm 超出范围 [{RAIL_MIN_POS}, {RAIL_MAX_POS}]"
        else:
            return False, f"不支持的轴: {axis}"
        
        return True, ""
    
    @staticmethod
    def validate_speed(speed: float, axis: str) -> Tuple[bool, str]:
        """
        验证速度是否在 STM32 硬件限制内
        
        Args:
            speed: 速度值（度/秒 或 mm/秒）
            axis: 轴名称 ('pan', 'tilt', 'rail')
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            speed_steps = UnitConverter.speed_to_steps(speed, axis)
        except ValueError as e:
            return False, str(e)
        
        if axis == 'pan':
            max_steps = MAX_SPEED_PAN_STEPS
            if speed_steps > max_steps:
                max_speed = UnitConverter.steps_to_speed(max_steps, axis)
                return False, (f"Pan 速度 {speed}°/s ({speed_steps} 步/s) "
                             f"超出 STM32 限制 ({max_steps} 步/s = {max_speed:.2f}°/s)")
        elif axis == 'tilt':
            max_steps = MAX_SPEED_TILT_STEPS
            if speed_steps > max_steps:
                max_speed = UnitConverter.steps_to_speed(max_steps, axis)
                return False, (f"Tilt 速度 {speed}°/s ({speed_steps} 步/s) "
                             f"超出 STM32 限制 ({max_steps} 步/s = {max_speed:.2f}°/s)")
        elif axis == 'rail':
            max_steps = MAX_SPEED_RAIL_STEPS
            if speed_steps > max_steps:
                max_speed = UnitConverter.steps_to_speed(max_steps, axis)
                return False, (f"Rail 速度 {speed}mm/s ({speed_steps} 步/s) "
                             f"超出 STM32 限制 ({max_steps} 步/s = {max_speed:.2f}mm/s)")
        else:
            return False, f"不支持的轴: {axis}"
        
        return True, ""
    
    @staticmethod
    def validate_acceleration(accel: float, axis: str) -> Tuple[bool, str]:
        """
        验证加速度是否在 STM32 硬件限制内
        
        Args:
            accel: 加速度值（度/秒² 或 mm/秒²）
            axis: 轴名称 ('pan', 'tilt', 'rail')
            
        Returns:
            (是否有效, 错误信息)
        """
        try:
            accel_steps = UnitConverter.accel_to_steps(accel, axis)
        except ValueError as e:
            return False, str(e)
        
        if axis == 'pan':
            max_steps = MAX_ACCEL_PAN_STEPS
            if accel_steps > max_steps:
                max_accel = UnitConverter.steps_to_accel(max_steps, axis)
                return False, (f"Pan 加速度 {accel}°/s² ({accel_steps} 步/s²) "
                             f"超出 STM32 限制 ({max_steps} 步/s² = {max_accel:.2f}°/s²)")
        elif axis == 'tilt':
            max_steps = MAX_ACCEL_TILT_STEPS
            if accel_steps > max_steps:
                max_accel = UnitConverter.steps_to_accel(max_steps, axis)
                return False, (f"Tilt 加速度 {accel}°/s² ({accel_steps} 步/s²) "
                             f"超出 STM32 限制 ({max_steps} 步/s² = {max_accel:.2f}°/s²)")
        elif axis == 'rail':
            max_steps = MAX_ACCEL_RAIL_STEPS
            if accel_steps > max_steps:
                max_accel = UnitConverter.steps_to_accel(max_steps, axis)
                return False, (f"Rail 加速度 {accel}mm/s² ({accel_steps} 步/s²) "
                             f"超出 STM32 限制 ({max_steps} 步/s² = {max_accel:.2f}mm/s²)")
        else:
            return False, f"不支持的轴: {axis}"
        
        return True, ""
    
    @staticmethod
    def validate_motion_params(position: float, speed: float, accel: float, axis: str) -> Tuple[bool, str]:
        """
        验证完整的运动参数
        
        Args:
            position: 位置值
            speed: 速度值
            accel: 加速度值
            axis: 轴名称
            
        Returns:
            (是否有效, 错误信息)
        """
        # 验证位置
        valid, error = MotionValidator.validate_position(position, axis)
        if not valid:
            return False, error
        
        # 验证速度
        valid, error = MotionValidator.validate_speed(speed, axis)
        if not valid:
            return False, error
        
        # 验证加速度
        valid, error = MotionValidator.validate_acceleration(accel, axis)
        if not valid:
            return False, error
        
        return True, ""


def validate_config_motion_params(config: dict) -> list:
    """
    验证配置文件中的运动参数
    
    Args:
        config: 配置字典
        
    Returns:
        警告信息列表
    """
    warnings = []
    
    # 检查 visual_servo 配置
    if 'visual_servo' in config:
        vs_config = config['visual_servo']
        
        # 检查 Pan 速度
        if 'max_pan_speed' in vs_config:
            speed = vs_config['max_pan_speed']
            valid, error = MotionValidator.validate_speed(speed, 'pan')
            if not valid:
                warnings.append(f"配置警告: {error}")
        
        # 检查 Tilt 速度
        if 'max_tilt_speed' in vs_config:
            speed = vs_config['max_tilt_speed']
            valid, error = MotionValidator.validate_speed(speed, 'tilt')
            if not valid:
                warnings.append(f"配置警告: {error}")
        
        # 检查 Rail 速度
        if 'max_rail_speed' in vs_config:
            speed = vs_config['max_rail_speed']
            valid, error = MotionValidator.validate_speed(speed, 'rail')
            if not valid:
                warnings.append(f"配置警告: {error}")
    
    return warnings


# 便捷函数
def deg_to_steps(degrees: float, axis: str) -> int:
    """角度转步数（便捷函数）"""
    return UnitConverter.degrees_to_steps(degrees, axis)


def steps_to_deg(steps: int, axis: str) -> float:
    """步数转角度（便捷函数）"""
    return UnitConverter.steps_to_degrees(steps, axis)


def mm_to_steps(mm: float) -> int:
    """毫米转步数（便捷函数）"""
    return UnitConverter.mm_to_steps(mm)


def steps_to_mm(steps: int) -> float:
    """步数转毫米（便捷函数）"""
    return UnitConverter.steps_to_mm(steps)
