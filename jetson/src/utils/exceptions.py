"""
自定义异常类 - 统一异常处理

提供细化的异常类型，便于错误处理和调试
"""


class CameraControlError(Exception):
    """相机控制系统基础异常"""
    pass


# ============================================================================
# 相机相关异常
# ============================================================================

class CameraError(CameraControlError):
    """相机相关错误"""
    pass


class CameraConnectionError(CameraError):
    """相机连接错误"""
    pass


class CameraConfigError(CameraError):
    """相机配置错误"""
    pass


class CameraCaptureError(CameraError):
    """图像采集错误"""
    pass


class CameraStreamError(CameraError):
    """视频流错误"""
    pass


# ============================================================================
# 通信相关异常
# ============================================================================

class CommunicationError(CameraControlError):
    """通信相关错误"""
    pass


class SerialConnectionError(CommunicationError):
    """串口连接错误"""
    pass


class ProtocolError(CommunicationError):
    """协议错误"""
    pass


class CommandTimeoutError(CommunicationError):
    """命令超时错误"""
    pass


class ResponseError(CommunicationError):
    """响应错误"""
    pass


class CRCError(ProtocolError):
    """CRC 校验错误"""
    pass


class FrameError(ProtocolError):
    """帧格式错误"""
    pass


# ============================================================================
# 检测相关异常
# ============================================================================

class DetectionError(CameraControlError):
    """目标检测相关错误"""
    pass


class ModelLoadError(DetectionError):
    """模型加载错误"""
    pass


class InferenceError(DetectionError):
    """推理错误"""
    pass


class NoTargetError(DetectionError):
    """无目标错误"""
    pass


# ============================================================================
# 控制相关异常
# ============================================================================

class ControlError(CameraControlError):
    """控制相关错误"""
    pass


class MotionError(ControlError):
    """运动控制错误"""
    pass


class LimitError(ControlError):
    """限位错误"""
    pass


class EmergencyStopError(ControlError):
    """急停错误"""
    pass


class CalibrationError(ControlError):
    """校准错误"""
    pass


# ============================================================================
# 配置相关异常
# ============================================================================

class ConfigError(CameraControlError):
    """配置相关错误"""
    pass


class ConfigValidationError(ConfigError):
    """配置验证错误"""
    pass


class ConfigFileError(ConfigError):
    """配置文件错误"""
    pass


# ============================================================================
# 状态相关异常
# ============================================================================

class StateError(CameraControlError):
    """状态相关错误"""
    pass


class InvalidStateError(StateError):
    """无效状态错误"""
    pass


class StateTransitionError(StateError):
    """状态转换错误"""
    pass


# ============================================================================
# 调度相关异常
# ============================================================================

class SchedulerError(CameraControlError):
    """调度相关错误"""
    pass


class PathConfigError(SchedulerError):
    """路径配置错误"""
    pass


class TaskExecutionError(SchedulerError):
    """任务执行错误"""
    pass


# ============================================================================
# 网络相关异常
# ============================================================================

class NetworkError(CameraControlError):
    """网络相关错误"""
    pass


class AuthenticationError(NetworkError):
    """认证错误"""
    pass


class ConnectionLostError(NetworkError):
    """连接丢失错误"""
    pass


# ============================================================================
# 辅助函数
# ============================================================================

def format_error(error: Exception, include_traceback: bool = False) -> str:
    """
    格式化错误信息
    
    Args:
        error: 异常对象
        include_traceback: 是否包含堆栈跟踪
        
    Returns:
        格式化的错误字符串
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    result = f"[{error_type}] {error_msg}"
    
    if include_traceback:
        import traceback
        tb = traceback.format_exc()
        result += f"\n{tb}"
    
    return result


def is_recoverable(error: Exception) -> bool:
    """
    判断错误是否可恢复
    
    Args:
        error: 异常对象
        
    Returns:
        是否可恢复
    """
    # 不可恢复的错误类型
    non_recoverable = (
        EmergencyStopError,
        ModelLoadError,
        ConfigValidationError,
    )
    
    return not isinstance(error, non_recoverable)
