"""
配置验证模型模块

使用 Pydantic 进行配置文件验证，确保配置项的有效性。
支持：
- 类型验证
- 范围验证
- 自定义验证规则
- 详细的错误信息
"""

from typing import Optional, List, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# 尝试导入 Pydantic，如果不可用则使用简单验证
try:
    from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    logger.warning("Pydantic 未安装，将使用简单验证模式")


class ConfigValidationError(Exception):
    """配置验证错误"""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"配置验证失败: {'; '.join(errors)}")


if PYDANTIC_AVAILABLE:
    # ==================== Pydantic 模型 ====================
    
    class CameraConfigModel(BaseModel):
        """相机配置验证模型"""
        enabled: bool = True
        required: bool = False
        width: int = Field(default=1280, ge=320, le=4096)
        height: int = Field(default=720, ge=240, le=2160)
        fps: int = Field(default=30, ge=1, le=120)
        enable_depth: bool = True
        serial_number: Optional[str] = None
        
        @field_validator('width')
        def validate_width(cls, v):
            supported = [320, 424, 480, 640, 848, 960, 1280, 1920, 3840]
            if v not in supported:
                # 允许自定义分辨率，但给出警告
                logger.warning(f"非标准分辨率宽度: {v}，建议使用: {supported}")
            return v
        
        @field_validator('height')
        def validate_height(cls, v):
            supported = [180, 240, 270, 360, 480, 540, 720, 1080, 2160]
            if v not in supported:
                logger.warning(f"非标准分辨率高度: {v}，建议使用: {supported}")
            return v
        
        @field_validator('fps')
        def validate_fps(cls, v):
            supported = [6, 15, 30, 60, 90]
            if v not in supported:
                logger.warning(f"非标准帧率: {v}，建议使用: {supported}")
            return v
        
        model_config = ConfigDict(extra="ignore")  # 忽略额外字段
    
    
    class CommConfigModel(BaseModel):
        """串口通信配置验证模型"""
        enabled: bool = True
        required: bool = False
        port: str = "/dev/ttyUSB0"
        baudrate: int = Field(default=115200, ge=9600, le=4000000)
        timeout: float = Field(default=1.0, ge=0.1, le=30.0)
        
        @field_validator('baudrate')
        def validate_baudrate(cls, v):
            standard = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
            if v not in standard:
                logger.warning(f"非标准波特率: {v}，建议使用: {standard}")
            return v
        
        @field_validator('port')
        def validate_port(cls, v):
            if not v:
                raise ValueError("串口端口不能为空")
            return v
        
        model_config = ConfigDict(extra="ignore")


    class DetectionConfigModel(BaseModel):
        """目标检测配置验证模型"""
        enabled: bool = True
        model_path: str = "models/yolov5s.engine"
        confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
        nms_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
        target_classes: List[str] = Field(default_factory=list)

        @field_validator('confidence_threshold', 'nms_threshold')
        @classmethod
        def validate_threshold(cls, v, info):
            if v < 0.1:
                logger.warning(f"{info.field_name} 值过低 ({v})，可能导致过多误检")
            if v > 0.9:
                logger.warning(f"{info.field_name} 值过高 ({v})，可能导致漏检")
            return v

        model_config = ConfigDict(extra='ignore')
    
    
    class FaceRecognitionConfigModel(BaseModel):
        """人脸识别配置验证模型"""
        enabled: bool = True
        database_path: str = "face_database"
        detection_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
        recognition_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
        backend: str = "auto"
        
        @field_validator('backend')
        def validate_backend(cls, v):
            supported = ['auto', 'insightface', 'face_recognition', 'dlib', 'opencv']
            if v not in supported:
                raise ValueError(f"不支持的后端: {v}，支持: {supported}")
            return v
        
        model_config = ConfigDict(extra="ignore")
    
    
    class VisualServoConfigModel(BaseModel):
        """视觉伺服配置验证模型"""
        enabled: bool = True
        center_tolerance: int = Field(default=30, ge=1, le=200)
        max_pan_speed: float = Field(default=30.0, ge=1.0, le=180.0)
        max_tilt_speed: float = Field(default=20.0, ge=1.0, le=90.0)
        max_rail_speed: float = Field(default=50.0, ge=1.0, le=500.0)
        prediction_enabled: bool = True
        
        model_config = ConfigDict(extra="ignore")
    
    
    class SchedulerConfigModel(BaseModel):
        """调度器配置验证模型"""
        enabled: bool = True
        default_path: Optional[str] = None
        
        model_config = ConfigDict(extra="ignore")
    
    
    class SSLConfigModel(BaseModel):
        """SSL/TLS 配置验证模型"""
        enabled: bool = False
        cert_file: str = "certs/cert.pem"
        key_file: str = "certs/key.pem"
        
        model_config = ConfigDict(extra="ignore")
    
    
    class WebConfigModel(BaseModel):
        """Web 服务配置验证模型"""
        enabled: bool = True
        host: str = "0.0.0.0"
        port: int = Field(default=8080, ge=1, le=65535)
        enable_auth: bool = False
        video_fps: int = Field(default=15, ge=1, le=60)
        video_quality: int = Field(default=80, ge=10, le=100)
        ssl: SSLConfigModel = Field(default_factory=SSLConfigModel)
        
        @field_validator('host')
        def validate_host(cls, v):
            if not v:
                raise ValueError("主机地址不能为空")
            return v
        
        @field_validator('port')
        def validate_port(cls, v):
            if v < 1024 and v != 80 and v != 443:
                logger.warning(f"端口 {v} 小于 1024，可能需要 root 权限")
            return v
        
        model_config = ConfigDict(extra="ignore")
    
    
    class SystemConfigModel(BaseModel):
        """系统总配置验证模型"""
        camera: CameraConfigModel = Field(default_factory=CameraConfigModel)
        comm: CommConfigModel = Field(default_factory=CommConfigModel)
        detection: DetectionConfigModel = Field(default_factory=DetectionConfigModel)
        face_recognition: FaceRecognitionConfigModel = Field(default_factory=FaceRecognitionConfigModel)
        visual_servo: VisualServoConfigModel = Field(default_factory=VisualServoConfigModel)
        scheduler: SchedulerConfigModel = Field(default_factory=SchedulerConfigModel)
        web: WebConfigModel = Field(default_factory=WebConfigModel)
        
        model_config = ConfigDict(extra="ignore")


else:
    # ==================== 简单验证模式（无 Pydantic）====================
    
    @dataclass
    class CameraConfigModel:
        enabled: bool = True
        required: bool = False
        width: int = 1280
        height: int = 720
        fps: int = 30
        enable_depth: bool = True
        serial_number: Optional[str] = None
    
    @dataclass
    class CommConfigModel:
        enabled: bool = True
        required: bool = False
        port: str = "/dev/ttyUSB0"
        baudrate: int = 115200
        timeout: float = 1.0
    
    @dataclass
    class DetectionConfigModel:
        enabled: bool = True
        model_path: str = "models/yolov5s.engine"
        confidence_threshold: float = 0.5
        nms_threshold: float = 0.45
        target_classes: List[str] = field(default_factory=list)
    
    @dataclass
    class FaceRecognitionConfigModel:
        enabled: bool = True
        database_path: str = "face_database"
        detection_threshold: float = 0.5
        recognition_threshold: float = 0.6
        backend: str = "auto"
    
    @dataclass
    class VisualServoConfigModel:
        enabled: bool = True
        center_tolerance: int = 30
        max_pan_speed: float = 30.0
        max_tilt_speed: float = 20.0
        max_rail_speed: float = 50.0
        prediction_enabled: bool = True
    
    @dataclass
    class SchedulerConfigModel:
        enabled: bool = True
        default_path: Optional[str] = None
    
    @dataclass
    class SSLConfigModel:
        enabled: bool = False
        cert_file: str = "certs/cert.pem"
        key_file: str = "certs/key.pem"
    
    @dataclass
    class WebConfigModel:
        enabled: bool = True
        host: str = "0.0.0.0"
        port: int = 8080
        enable_auth: bool = False
        video_fps: int = 15
        video_quality: int = 80
        ssl: SSLConfigModel = field(default_factory=SSLConfigModel)
    
    @dataclass
    class SystemConfigModel:
        camera: CameraConfigModel = field(default_factory=CameraConfigModel)
        comm: CommConfigModel = field(default_factory=CommConfigModel)
        detection: DetectionConfigModel = field(default_factory=DetectionConfigModel)
        face_recognition: FaceRecognitionConfigModel = field(default_factory=FaceRecognitionConfigModel)
        visual_servo: VisualServoConfigModel = field(default_factory=VisualServoConfigModel)
        scheduler: SchedulerConfigModel = field(default_factory=SchedulerConfigModel)
        web: WebConfigModel = field(default_factory=WebConfigModel)


def validate_config(data: dict) -> SystemConfigModel:
    """
    验证配置数据
    
    Args:
        data: 配置字典
        
    Returns:
        验证后的配置模型
        
    Raises:
        ConfigValidationError: 配置验证失败
    """
    if PYDANTIC_AVAILABLE:
        try:
            return SystemConfigModel(**data)
        except Exception as e:
            # 提取 Pydantic 验证错误
            errors = []
            if hasattr(e, 'errors'):
                for err in e.errors():
                    loc = '.'.join(str(x) for x in err['loc'])
                    msg = err['msg']
                    errors.append(f"{loc}: {msg}")
            else:
                errors.append(str(e))
            raise ConfigValidationError(errors)
    else:
        # 简单验证模式
        errors = []
        
        # 验证相机配置
        if 'camera' in data:
            cam = data['camera']
            if cam.get('width', 1280) < 320:
                errors.append("camera.width: 宽度不能小于 320")
            if cam.get('height', 720) < 240:
                errors.append("camera.height: 高度不能小于 240")
            if cam.get('fps', 30) < 1:
                errors.append("camera.fps: 帧率不能小于 1")
        
        # 验证串口配置
        if 'comm' in data:
            comm = data['comm']
            if not comm.get('port'):
                errors.append("comm.port: 串口端口不能为空")
            if comm.get('baudrate', 115200) < 9600:
                errors.append("comm.baudrate: 波特率不能小于 9600")
        
        # 验证 Web 配置
        if 'web' in data:
            web = data['web']
            port = web.get('port', 8080)
            if port < 1 or port > 65535:
                errors.append(f"web.port: 端口 {port} 超出有效范围 (1-65535)")
        
        if errors:
            raise ConfigValidationError(errors)
        
        # 构建配置对象
        return _build_simple_config(data)


def _build_simple_config(data: dict) -> SystemConfigModel:
    """构建简单配置对象"""
    config = SystemConfigModel()
    
    if 'camera' in data:
        config.camera = CameraConfigModel(**{
            k: v for k, v in data['camera'].items()
            if hasattr(CameraConfigModel, k)
        })
    
    if 'comm' in data:
        config.comm = CommConfigModel(**{
            k: v for k, v in data['comm'].items()
            if hasattr(CommConfigModel, k)
        })
    
    if 'detection' in data:
        config.detection = DetectionConfigModel(**{
            k: v for k, v in data['detection'].items()
            if hasattr(DetectionConfigModel, k)
        })
    
    if 'face_recognition' in data:
        config.face_recognition = FaceRecognitionConfigModel(**{
            k: v for k, v in data['face_recognition'].items()
            if hasattr(FaceRecognitionConfigModel, k)
        })
    
    if 'visual_servo' in data:
        config.visual_servo = VisualServoConfigModel(**{
            k: v for k, v in data['visual_servo'].items()
            if hasattr(VisualServoConfigModel, k)
        })
    
    if 'scheduler' in data:
        config.scheduler = SchedulerConfigModel(**{
            k: v for k, v in data['scheduler'].items()
            if hasattr(SchedulerConfigModel, k)
        })
    
    if 'web' in data:
        web_data = data['web'].copy()
        ssl_data = web_data.pop('ssl', {})
        config.web = WebConfigModel(**{
            k: v for k, v in web_data.items()
            if hasattr(WebConfigModel, k)
        })
        if ssl_data:
            config.web.ssl = SSLConfigModel(**ssl_data)
    
    return config
