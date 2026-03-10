"""
配置文件验证工具 - 在系统启动时验证配置参数的有效性
"""

import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_camera_config(config: Dict[str, Any]) -> List[str]:
        """
        验证相机配置
        
        Args:
            config: 相机配置字典
            
        Returns:
            警告信息列表
        """
        warnings = []
        
        # 支持的分辨率（RealSense D415）
        supported_widths = [640, 848, 1280, 1920]
        supported_heights = [360, 480, 720, 1080]
        supported_fps = [6, 15, 30, 60]
        
        width = config.get('width', 1280)
        height = config.get('height', 720)
        fps = config.get('fps', 30)
        
        if width not in supported_widths:
            warnings.append(
                f"相机宽度 {width} 可能不被支持，"
                f"建议使用: {supported_widths}"
            )
        
        if height not in supported_heights:
            warnings.append(
                f"相机高度 {height} 可能不被支持，"
                f"建议使用: {supported_heights}"
            )
        
        if fps not in supported_fps:
            warnings.append(
                f"相机帧率 {fps} 可能不被支持，"
                f"建议使用: {supported_fps}"
            )
        
        return warnings
    
    @staticmethod
    def validate_comm_config(config: Dict[str, Any]) -> List[str]:
        """
        验证通信配置
        
        Args:
            config: 通信配置字典
            
        Returns:
            警告信息列表
        """
        warnings = []
        
        baudrate = config.get('baudrate', 115200)
        timeout = config.get('timeout', 1.0)
        
        # 检查波特率
        common_baudrates = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
        if baudrate not in common_baudrates:
            warnings.append(
                f"波特率 {baudrate} 不常见，"
                f"请确认与 STM32 配置一致"
            )
        
        # 检查超时
        if timeout < 0.1:
            warnings.append(
                f"通信超时 {timeout}s 过短，可能导致通信失败"
            )
        elif timeout > 5.0:
            warnings.append(
                f"通信超时 {timeout}s 过长，可能影响响应速度"
            )
        
        return warnings
    
    @staticmethod
    def validate_visual_servo_config(config: Dict[str, Any]) -> List[str]:
        """
        验证视觉伺服配置（包括运动参数）
        
        Args:
            config: 视觉伺服配置字典
            
        Returns:
            警告信息列表
        """
        warnings = []
        
        # 导入单位转换模块
        try:
            from ..comm.unit_converter import MotionValidator
        except ImportError:
            logger.warning("无法导入 unit_converter 模块，跳过运动参数验证")
            return warnings
        
        # 检查 Pan 速度
        max_pan_speed = config.get('max_pan_speed')
        if max_pan_speed is not None:
            valid, error = MotionValidator.validate_speed(max_pan_speed, 'pan')
            if not valid:
                warnings.append(error)
        
        # 检查 Tilt 速度
        max_tilt_speed = config.get('max_tilt_speed')
        if max_tilt_speed is not None:
            valid, error = MotionValidator.validate_speed(max_tilt_speed, 'tilt')
            if not valid:
                warnings.append(error)
        
        # 检查 Rail 速度
        max_rail_speed = config.get('max_rail_speed')
        if max_rail_speed is not None:
            valid, error = MotionValidator.validate_speed(max_rail_speed, 'rail')
            if not valid:
                warnings.append(error)
        
        # 检查居中容差
        center_tolerance = config.get('center_tolerance', 30)
        if center_tolerance < 5:
            warnings.append(
                f"居中容差 {center_tolerance} 像素过小，"
                f"可能导致频繁调整"
            )
        elif center_tolerance > 100:
            warnings.append(
                f"居中容差 {center_tolerance} 像素过大，"
                f"可能影响跟踪精度"
            )
        
        return warnings
    
    @staticmethod
    def validate_web_config(config: Dict[str, Any]) -> List[str]:
        """
        验证 Web 服务配置
        
        Args:
            config: Web 配置字典
            
        Returns:
            警告信息列表
        """
        warnings = []
        
        port = config.get('port', 8080)
        host = config.get('host', '0.0.0.0')
        ssl_config = config.get('ssl', {})
        
        # 检查端口
        if port < 1024 and port != 80 and port != 443:
            warnings.append(
                f"端口 {port} 需要 root 权限，"
                f"建议使用 1024 以上的端口"
            )
        
        # 检查 SSL 配置
        if ssl_config.get('enabled', False):
            cert_file = ssl_config.get('cert_file')
            key_file = ssl_config.get('key_file')
            
            if cert_file and not Path(cert_file).exists():
                warnings.append(
                    f"SSL 证书文件不存在: {cert_file}"
                )
            
            if key_file and not Path(key_file).exists():
                warnings.append(
                    f"SSL 私钥文件不存在: {key_file}"
                )
        else:
            if host == '0.0.0.0':
                warnings.append(
                    "Web 服务未启用 HTTPS，"
                    "在公网环境下存在安全风险"
                )
        
        # 检查视频参数
        video_fps = config.get('video_fps', 15)
        video_quality = config.get('video_quality', 80)
        
        if video_fps > 30:
            warnings.append(
                f"视频帧率 {video_fps} 过高，"
                f"可能增加网络带宽和 CPU 负载"
            )
        
        if video_quality > 95:
            warnings.append(
                f"视频质量 {video_quality} 过高，"
                f"可能增加网络带宽"
            )
        elif video_quality < 50:
            warnings.append(
                f"视频质量 {video_quality} 过低，"
                f"可能影响图像清晰度"
            )
        
        return warnings
    
    @staticmethod
    def validate_detection_config(config: Dict[str, Any]) -> List[str]:
        """
        验证目标检测配置
        
        Args:
            config: 检测配置字典
            
        Returns:
            警告信息列表
        """
        warnings = []
        
        model_path = config.get('model_path')
        confidence_threshold = config.get('confidence_threshold', 0.5)
        nms_threshold = config.get('nms_threshold', 0.45)
        
        # 检查模型文件
        if model_path and not Path(model_path).exists():
            warnings.append(
                f"检测模型文件不存在: {model_path}"
            )
        
        # 检查阈值
        if confidence_threshold < 0.3:
            warnings.append(
                f"置信度阈值 {confidence_threshold} 过低，"
                f"可能产生大量误检"
            )
        elif confidence_threshold > 0.8:
            warnings.append(
                f"置信度阈值 {confidence_threshold} 过高，"
                f"可能漏检目标"
            )
        
        if nms_threshold < 0.3:
            warnings.append(
                f"NMS 阈值 {nms_threshold} 过低，"
                f"可能过度抑制重叠框"
            )
        elif nms_threshold > 0.7:
            warnings.append(
                f"NMS 阈值 {nms_threshold} 过高，"
                f"可能保留过多重叠框"
            )
        
        return warnings
    
    @staticmethod
    def validate_face_recognition_config(config: Dict[str, Any]) -> List[str]:
        """
        验证人脸识别配置
        
        Args:
            config: 人脸识别配置字典
            
        Returns:
            警告信息列表
        """
        warnings = []
        
        database_path = config.get('database_path')
        detection_threshold = config.get('detection_threshold', 0.5)
        recognition_threshold = config.get('recognition_threshold', 0.6)
        
        # 检查数据库路径
        if database_path and not Path(database_path).exists():
            warnings.append(
                f"人脸数据库路径不存在: {database_path}，"
                f"将自动创建"
            )
        
        # 检查阈值
        if detection_threshold < 0.3:
            warnings.append(
                f"人脸检测阈值 {detection_threshold} 过低，"
                f"可能产生误检"
            )
        
        if recognition_threshold < 0.4:
            warnings.append(
                f"人脸识别阈值 {recognition_threshold} 过低，"
                f"可能产生误识别"
            )
        elif recognition_threshold > 0.8:
            warnings.append(
                f"人脸识别阈值 {recognition_threshold} 过高，"
                f"可能无法识别已注册人脸"
            )
        
        return warnings
    
    @staticmethod
    def validate_all(config: Dict[str, Any]) -> List[str]:
        """
        验证所有配置
        
        Args:
            config: 完整配置字典
            
        Returns:
            所有警告信息列表
        """
        all_warnings = []
        
        # 验证相机配置
        if 'camera' in config:
            warnings = ConfigValidator.validate_camera_config(config['camera'])
            all_warnings.extend([f"[相机] {w}" for w in warnings])
        
        # 验证通信配置
        if 'comm' in config:
            warnings = ConfigValidator.validate_comm_config(config['comm'])
            all_warnings.extend([f"[通信] {w}" for w in warnings])
        
        # 验证视觉伺服配置
        if 'visual_servo' in config:
            warnings = ConfigValidator.validate_visual_servo_config(config['visual_servo'])
            all_warnings.extend([f"[视觉伺服] {w}" for w in warnings])
        
        # 验证 Web 配置
        if 'web' in config:
            warnings = ConfigValidator.validate_web_config(config['web'])
            all_warnings.extend([f"[Web服务] {w}" for w in warnings])
        
        # 验证检测配置
        if 'detection' in config:
            warnings = ConfigValidator.validate_detection_config(config['detection'])
            all_warnings.extend([f"[目标检测] {w}" for w in warnings])
        
        # 验证人脸识别配置
        if 'face_recognition' in config:
            warnings = ConfigValidator.validate_face_recognition_config(config['face_recognition'])
            all_warnings.extend([f"[人脸识别] {w}" for w in warnings])
        
        return all_warnings


def validate_config_file(config_path: str) -> List[str]:
    """
    验证配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        警告信息列表
    """
    import yaml
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        warnings = ConfigValidator.validate_all(config)
        
        if warnings:
            logger.warning(f"配置文件验证发现 {len(warnings)} 个警告:")
            for warning in warnings:
                logger.warning(f"  - {warning}")
        else:
            logger.info("配置文件验证通过，未发现问题")
        
        return warnings
        
    except Exception as e:
        logger.error(f"配置文件验证失败: {e}")
        return [f"配置文件读取错误: {e}"]
