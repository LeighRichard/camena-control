"""
统一配置管理模块

支持：
- YAML 配置文件加载
- 环境变量覆盖
- 默认值
- 配置验证（使用 Pydantic 或简单验证）
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# 导入配置验证模块
try:
    from .config_models import (
        validate_config, ConfigValidationError,
        PYDANTIC_AVAILABLE
    )
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False
    PYDANTIC_AVAILABLE = False
    logger.warning("配置验证模块不可用，将跳过验证")


@dataclass
class CameraConfig:
    """相机配置"""
    enabled: bool = True
    required: bool = False
    width: int = 1280
    height: int = 720
    fps: int = 30
    enable_depth: bool = True
    serial_number: Optional[str] = None


@dataclass
class CommConfig:
    """串口通信配置"""
    enabled: bool = True
    required: bool = False
    port: str = "/dev/ttyUSB0"
    baudrate: int = 115200
    timeout: float = 1.0


@dataclass
class DetectionConfig:
    """目标检测配置"""
    enabled: bool = True
    model_path: str = "models/yolov5s.engine"
    confidence_threshold: float = 0.5
    nms_threshold: float = 0.45
    target_classes: list = field(default_factory=list)


@dataclass
class FaceRecognitionConfig:
    """人脸识别配置"""
    enabled: bool = True
    database_path: str = "face_database"
    detection_threshold: float = 0.5
    recognition_threshold: float = 0.6
    backend: str = "auto"  # auto, insightface, face_recognition


@dataclass
class VisualServoConfig:
    """视觉伺服配置"""
    enabled: bool = True
    center_tolerance: int = 30
    max_pan_speed: float = 30.0
    max_tilt_speed: float = 20.0
    max_rail_speed: float = 50.0
    prediction_enabled: bool = True


@dataclass
class SchedulerConfig:
    """调度器配置"""
    enabled: bool = True
    default_path: Optional[str] = None


@dataclass
class SSLConfig:
    """SSL/TLS 配置"""
    enabled: bool = False
    cert_file: str = "certs/cert.pem"
    key_file: str = "certs/key.pem"


@dataclass
class WebConfig:
    """Web 服务配置"""
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080
    enable_auth: bool = False
    video_fps: int = 15
    video_quality: int = 80
    ssl: SSLConfig = field(default_factory=SSLConfig)


@dataclass
class SystemConfig:
    """系统总配置"""
    camera: CameraConfig = field(default_factory=CameraConfig)
    comm: CommConfig = field(default_factory=CommConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    face_recognition: FaceRecognitionConfig = field(default_factory=FaceRecognitionConfig)
    visual_servo: VisualServoConfig = field(default_factory=VisualServoConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    web: WebConfig = field(default_factory=WebConfig)


def load_config(config_path: Path = None, validate: bool = True) -> SystemConfig:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径，None 使用默认配置
        validate: 是否验证配置（需要 config_models 模块）
        
    Returns:
        系统配置对象
        
    Raises:
        ConfigValidationError: 配置验证失败时抛出（仅当 validate=True）
    """
    config = SystemConfig()
    data = {}
    
    if config_path and config_path.exists():
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            # 验证配置
            if validate and VALIDATION_AVAILABLE and data:
                try:
                    validated = validate_config(data)
                    logger.info(f"配置验证通过 (Pydantic: {PYDANTIC_AVAILABLE})")
                except ConfigValidationError as e:
                    logger.error(f"配置验证失败: {e}")
                    raise
            
            if data:
                config = _parse_config(data)
                logger.info(f"已加载配置文件: {config_path}")
        except ImportError:
            logger.warning("PyYAML 未安装，使用默认配置")
        except ConfigValidationError:
            raise  # 重新抛出验证错误
        except Exception as e:
            logger.warning(f"加载配置文件失败: {e}，使用默认配置")
    else:
        logger.info("使用默认配置")
    
    # 环境变量覆盖
    config = _apply_env_overrides(config)
    
    return config


def _parse_config(data: Dict[str, Any]) -> SystemConfig:
    """解析配置字典"""
    config = SystemConfig()
    
    if 'camera' in data:
        config.camera = CameraConfig(**{
            k: v for k, v in data['camera'].items() 
            if k in CameraConfig.__dataclass_fields__
        })
    
    if 'comm' in data:
        config.comm = CommConfig(**{
            k: v for k, v in data['comm'].items()
            if k in CommConfig.__dataclass_fields__
        })
    
    if 'detection' in data:
        config.detection = DetectionConfig(**{
            k: v for k, v in data['detection'].items()
            if k in DetectionConfig.__dataclass_fields__
        })
    
    if 'face_recognition' in data:
        config.face_recognition = FaceRecognitionConfig(**{
            k: v for k, v in data['face_recognition'].items()
            if k in FaceRecognitionConfig.__dataclass_fields__
        })
    
    if 'visual_servo' in data:
        config.visual_servo = VisualServoConfig(**{
            k: v for k, v in data['visual_servo'].items()
            if k in VisualServoConfig.__dataclass_fields__
        })
    
    if 'scheduler' in data:
        config.scheduler = SchedulerConfig(**{
            k: v for k, v in data['scheduler'].items()
            if k in SchedulerConfig.__dataclass_fields__
        })
    
    if 'web' in data:
        web_data = data['web'].copy()
        ssl_data = web_data.pop('ssl', {})
        config.web = WebConfig(**{
            k: v for k, v in web_data.items()
            if k in WebConfig.__dataclass_fields__
        })
        if ssl_data:
            config.web.ssl = SSLConfig(**{
                k: v for k, v in ssl_data.items()
                if k in SSLConfig.__dataclass_fields__
            })
    
    return config


def _apply_env_overrides(config: SystemConfig) -> SystemConfig:
    """应用环境变量覆盖"""
    # 相机
    if os.getenv('CAMERA_ENABLED'):
        config.camera.enabled = os.getenv('CAMERA_ENABLED').lower() == 'true'
    if os.getenv('CAMERA_WIDTH'):
        config.camera.width = int(os.getenv('CAMERA_WIDTH'))
    if os.getenv('CAMERA_HEIGHT'):
        config.camera.height = int(os.getenv('CAMERA_HEIGHT'))
    
    # 串口
    if os.getenv('COMM_PORT'):
        config.comm.port = os.getenv('COMM_PORT')
    if os.getenv('COMM_BAUDRATE'):
        config.comm.baudrate = int(os.getenv('COMM_BAUDRATE'))
    
    # Web
    if os.getenv('WEB_PORT'):
        config.web.port = int(os.getenv('WEB_PORT'))
    if os.getenv('WEB_HOST'):
        config.web.host = os.getenv('WEB_HOST')
    
    # 人脸识别
    if os.getenv('FACE_DB_PATH'):
        config.face_recognition.database_path = os.getenv('FACE_DB_PATH')
    
    return config


def save_config(config: SystemConfig, config_path: Path):
    """
    保存配置到文件
    
    Args:
        config: 系统配置对象
        config_path: 保存路径
    """
    try:
        import yaml
        from dataclasses import asdict
        
        data = asdict(config)
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"配置已保存: {config_path}")
    except ImportError:
        logger.error("PyYAML 未安装，无法保存配置")
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
