"""
模型管理器 - 深度学习模型下载、转换、量化工具

功能：
1. 模型下载 - 从官方源下载预训练模型
2. 模型转换 - ONNX → TensorRT
3. 模型量化 - FP32 → FP16/INT8
4. 模型管理 - 列表、删除、信息查询
5. 性能测试 - 推理速度和内存占用测试
"""

import os
import json
import time
import shutil
import hashlib
import logging
import subprocess
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Callable
from urllib.request import urlretrieve
from urllib.error import URLError

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """模型类型"""
    YOLO_DETECTION = "yolo_detection"       # YOLO 目标检测
    FACE_DETECTION = "face_detection"       # 人脸检测
    FACE_RECOGNITION = "face_recognition"   # 人脸识别
    CUSTOM = "custom"                       # 自定义模型


class ModelStatus(Enum):
    """模型状态"""
    NOT_DOWNLOADED = "not_downloaded"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    CONVERTING = "converting"
    READY = "ready"
    ERROR = "error"


@dataclass
class ModelInfo:
    """模型信息"""
    name: str                               # 模型名称
    model_type: ModelType                   # 模型类型
    version: str = "1.0"                    # 版本
    description: str = ""                   # 描述
    
    # 文件信息
    onnx_path: Optional[str] = None         # ONNX 文件路径
    engine_path: Optional[str] = None       # TensorRT 引擎路径
    
    # 下载信息
    download_url: Optional[str] = None      # 下载 URL
    file_size_mb: float = 0.0               # 文件大小 (MB)
    md5_hash: Optional[str] = None          # MD5 校验
    
    # 模型参数
    input_size: Tuple[int, int] = (640, 640)  # 输入尺寸
    num_classes: int = 80                   # 类别数
    class_names: List[str] = field(default_factory=list)
    
    # 状态
    status: ModelStatus = ModelStatus.NOT_DOWNLOADED
    precision: str = "fp32"                 # fp32, fp16, int8
    
    # 性能指标
    inference_time_ms: float = 0.0          # 推理时间
    memory_usage_mb: float = 0.0            # 内存占用
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'model_type': self.model_type.value,
            'version': self.version,
            'description': self.description,
            'onnx_path': self.onnx_path,
            'engine_path': self.engine_path,
            'download_url': self.download_url,
            'file_size_mb': self.file_size_mb,
            'input_size': self.input_size,
            'num_classes': self.num_classes,
            'class_names': self.class_names,
            'status': self.status.value,
            'precision': self.precision,
            'inference_time_ms': self.inference_time_ms,
            'memory_usage_mb': self.memory_usage_mb
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ModelInfo':
        data = data.copy()
        if 'model_type' in data:
            data['model_type'] = ModelType(data['model_type'])
        if 'status' in data:
            data['status'] = ModelStatus(data['status'])
        if 'input_size' in data:
            data['input_size'] = tuple(data['input_size'])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# 预定义模型库
PREDEFINED_MODELS: Dict[str, ModelInfo] = {
    # YOLOv5 系列
    'yolov5n': ModelInfo(
        name='yolov5n',
        model_type=ModelType.YOLO_DETECTION,
        version='7.0',
        description='YOLOv5 Nano - 最轻量级，适合边缘设备',
        download_url='https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.onnx',
        file_size_mb=4.0,
        input_size=(640, 640),
        num_classes=80
    ),
    'yolov5s': ModelInfo(
        name='yolov5s',
        model_type=ModelType.YOLO_DETECTION,
        version='7.0',
        description='YOLOv5 Small - 平衡速度和精度',
        download_url='https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx',
        file_size_mb=14.0,
        input_size=(640, 640),
        num_classes=80
    ),
    'yolov5m': ModelInfo(
        name='yolov5m',
        model_type=ModelType.YOLO_DETECTION,
        version='7.0',
        description='YOLOv5 Medium - 更高精度',
        download_url='https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5m.onnx',
        file_size_mb=42.0,
        input_size=(640, 640),
        num_classes=80
    ),
    
    # YOLOv8 系列
    'yolov8n': ModelInfo(
        name='yolov8n',
        model_type=ModelType.YOLO_DETECTION,
        version='8.0',
        description='YOLOv8 Nano - 最新架构，轻量级',
        download_url='https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.onnx',
        file_size_mb=6.3,
        input_size=(640, 640),
        num_classes=80
    ),
    'yolov8s': ModelInfo(
        name='yolov8s',
        model_type=ModelType.YOLO_DETECTION,
        version='8.0',
        description='YOLOv8 Small - 最新架构，平衡版',
        download_url='https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8s.onnx',
        file_size_mb=22.5,
        input_size=(640, 640),
        num_classes=80
    ),
}

# COCO 80 类别名称
COCO_CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck',
    'boat', 'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench',
    'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra',
    'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
    'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
    'skateboard', 'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
    'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
    'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
    'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
    'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
    'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier',
    'toothbrush'
]


class ModelManager:
    """
    模型管理器
    
    提供模型的完整生命周期管理：
    - 下载预训练模型
    - ONNX → TensorRT 转换
    - FP16/INT8 量化
    - 性能测试
    """
    
    def __init__(self, models_dir: str = "models"):
        self._models_dir = Path(models_dir)
        self._models_dir.mkdir(parents=True, exist_ok=True)
        
        # 子目录
        self._onnx_dir = self._models_dir / "onnx"
        self._engine_dir = self._models_dir / "engines"
        self._onnx_dir.mkdir(exist_ok=True)
        self._engine_dir.mkdir(exist_ok=True)
        
        # 模型注册表
        self._registry_file = self._models_dir / "registry.json"
        self._models: Dict[str, ModelInfo] = {}
        
        # 加载注册表
        self._load_registry()
        
        # 检查 TensorRT 可用性
        self._tensorrt_available = self._check_tensorrt()
    
    def _check_tensorrt(self) -> bool:
        """检查 TensorRT 是否可用"""
        try:
            import tensorrt
            return True
        except ImportError:
            logger.warning("TensorRT 不可用，模型转换功能将受限")
            return False
    
    def _load_registry(self):
        """加载模型注册表"""
        if self._registry_file.exists():
            try:
                with open(self._registry_file, 'r') as f:
                    data = json.load(f)
                for name, info in data.items():
                    self._models[name] = ModelInfo.from_dict(info)
                logger.info(f"加载了 {len(self._models)} 个已注册模型")
            except Exception as e:
                logger.error(f"加载注册表失败: {e}")
    
    def _save_registry(self):
        """保存模型注册表"""
        try:
            data = {name: info.to_dict() for name, info in self._models.items()}
            with open(self._registry_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存注册表失败: {e}")

    # ==================== 模型列表和查询 ====================
    
    def list_available_models(self) -> List[ModelInfo]:
        """列出所有可下载的预定义模型"""
        models = []
        for name, info in PREDEFINED_MODELS.items():
            # 检查是否已下载
            info_copy = ModelInfo.from_dict(info.to_dict())
            if name in self._models:
                info_copy.status = self._models[name].status
                info_copy.engine_path = self._models[name].engine_path
                info_copy.onnx_path = self._models[name].onnx_path
            models.append(info_copy)
        return models
    
    def list_installed_models(self) -> List[ModelInfo]:
        """列出所有已安装的模型"""
        return list(self._models.values())
    
    def get_model_info(self, name: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        if name in self._models:
            return self._models[name]
        if name in PREDEFINED_MODELS:
            return PREDEFINED_MODELS[name]
        return None
    
    def get_ready_models(self) -> List[ModelInfo]:
        """获取所有可用的模型（已转换为 TensorRT）"""
        return [m for m in self._models.values() if m.status == ModelStatus.READY]
    
    # ==================== 模型下载 ====================
    
    def download_model(
        self, 
        name: str, 
        progress_callback: Callable[[float], None] = None
    ) -> Tuple[bool, str]:
        """
        下载预定义模型
        
        Args:
            name: 模型名称
            progress_callback: 进度回调函数 (0.0 - 1.0)
            
        Returns:
            (成功标志, 消息)
        """
        if name not in PREDEFINED_MODELS:
            return False, f"未知模型: {name}"
        
        model_info = ModelInfo.from_dict(PREDEFINED_MODELS[name].to_dict())
        
        if not model_info.download_url:
            return False, f"模型 {name} 没有下载链接"
        
        # 目标路径
        onnx_path = self._onnx_dir / f"{name}.onnx"
        
        # 检查是否已存在
        if onnx_path.exists():
            model_info.onnx_path = str(onnx_path)
            model_info.status = ModelStatus.DOWNLOADED
            self._models[name] = model_info
            self._save_registry()
            return True, f"模型已存在: {onnx_path}"
        
        # 开始下载
        model_info.status = ModelStatus.DOWNLOADING
        self._models[name] = model_info
        
        logger.info(f"开始下载模型: {name} from {model_info.download_url}")
        
        try:
            def report_progress(block_num, block_size, total_size):
                if progress_callback and total_size > 0:
                    progress = min(1.0, block_num * block_size / total_size)
                    progress_callback(progress)
            
            urlretrieve(
                model_info.download_url, 
                str(onnx_path),
                reporthook=report_progress
            )
            
            # 验证文件
            if not onnx_path.exists():
                return False, "下载失败：文件不存在"
            
            file_size = onnx_path.stat().st_size / (1024 * 1024)
            
            model_info.onnx_path = str(onnx_path)
            model_info.file_size_mb = file_size
            model_info.status = ModelStatus.DOWNLOADED
            model_info.class_names = COCO_CLASSES
            self._models[name] = model_info
            self._save_registry()
            
            logger.info(f"模型下载完成: {name} ({file_size:.1f}MB)")
            return True, f"下载成功: {onnx_path}"
            
        except URLError as e:
            model_info.status = ModelStatus.ERROR
            self._models[name] = model_info
            self._save_registry()
            return False, f"下载失败: {e}"
        except Exception as e:
            model_info.status = ModelStatus.ERROR
            self._models[name] = model_info
            self._save_registry()
            return False, f"下载错误: {e}"
    
    def download_from_url(
        self, 
        url: str, 
        name: str,
        model_type: ModelType = ModelType.CUSTOM,
        progress_callback: Callable[[float], None] = None
    ) -> Tuple[bool, str]:
        """
        从自定义 URL 下载模型
        
        Args:
            url: 下载链接
            name: 模型名称
            model_type: 模型类型
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 消息)
        """
        onnx_path = self._onnx_dir / f"{name}.onnx"
        
        model_info = ModelInfo(
            name=name,
            model_type=model_type,
            download_url=url,
            status=ModelStatus.DOWNLOADING
        )
        self._models[name] = model_info
        
        try:
            def report_progress(block_num, block_size, total_size):
                if progress_callback and total_size > 0:
                    progress = min(1.0, block_num * block_size / total_size)
                    progress_callback(progress)
            
            urlretrieve(url, str(onnx_path), reporthook=report_progress)
            
            file_size = onnx_path.stat().st_size / (1024 * 1024)
            
            model_info.onnx_path = str(onnx_path)
            model_info.file_size_mb = file_size
            model_info.status = ModelStatus.DOWNLOADED
            self._models[name] = model_info
            self._save_registry()
            
            return True, f"下载成功: {onnx_path}"
            
        except Exception as e:
            model_info.status = ModelStatus.ERROR
            self._save_registry()
            return False, f"下载失败: {e}"
    
    # ==================== 模型转换 ====================
    
    def convert_to_tensorrt(
        self,
        name: str,
        use_fp16: bool = True,
        use_int8: bool = False,
        max_workspace_size: int = 1 << 30,
        progress_callback: Callable[[str], None] = None
    ) -> Tuple[bool, str]:
        """
        将 ONNX 模型转换为 TensorRT 引擎
        
        Args:
            name: 模型名称
            use_fp16: 使用 FP16 量化
            use_int8: 使用 INT8 量化（需要校准数据）
            max_workspace_size: 最大工作空间
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 消息)
        """
        if not self._tensorrt_available:
            return False, "TensorRT 不可用"
        
        if name not in self._models:
            return False, f"模型未下载: {name}"
        
        model_info = self._models[name]
        
        if not model_info.onnx_path or not Path(model_info.onnx_path).exists():
            return False, f"ONNX 文件不存在: {model_info.onnx_path}"
        
        # 确定精度后缀
        precision = "fp16" if use_fp16 else ("int8" if use_int8 else "fp32")
        engine_path = self._engine_dir / f"{name}_{precision}.engine"
        
        model_info.status = ModelStatus.CONVERTING
        self._save_registry()
        
        if progress_callback:
            progress_callback("正在加载 ONNX 模型...")
        
        try:
            import tensorrt as trt
            
            TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
            
            # 创建 builder
            builder = trt.Builder(TRT_LOGGER)
            network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
            network = builder.create_network(network_flags)
            
            # 解析 ONNX
            if progress_callback:
                progress_callback("正在解析 ONNX 模型...")
            
            parser = trt.OnnxParser(network, TRT_LOGGER)
            
            with open(model_info.onnx_path, 'rb') as f:
                if not parser.parse(f.read()):
                    errors = [parser.get_error(i) for i in range(parser.num_errors)]
                    model_info.status = ModelStatus.ERROR
                    self._save_registry()
                    return False, f"ONNX 解析失败: {errors}"
            
            # 配置 builder
            if progress_callback:
                progress_callback("正在配置 TensorRT...")
            
            config = builder.create_builder_config()
            config.max_workspace_size = max_workspace_size
            
            # 设置精度
            if use_fp16 and builder.platform_has_fast_fp16:
                config.set_flag(trt.BuilderFlag.FP16)
                logger.info("启用 FP16 量化")
            elif use_int8 and builder.platform_has_fast_int8:
                config.set_flag(trt.BuilderFlag.INT8)
                logger.info("启用 INT8 量化")
            
            # 设置输入形状
            profile = builder.create_optimization_profile()
            input_name = network.get_input(0).name
            input_shape = (1, 3, *model_info.input_size)
            profile.set_shape(input_name, min=input_shape, opt=input_shape, max=input_shape)
            config.add_optimization_profile(profile)
            
            # 构建引擎
            if progress_callback:
                progress_callback("正在构建 TensorRT 引擎（可能需要几分钟）...")
            
            logger.info(f"开始构建 TensorRT 引擎: {name} (precision={precision})")
            engine = builder.build_engine(network, config)
            
            if engine is None:
                model_info.status = ModelStatus.ERROR
                self._save_registry()
                return False, "TensorRT 引擎构建失败"
            
            # 序列化保存
            if progress_callback:
                progress_callback("正在保存引擎文件...")
            
            with open(engine_path, 'wb') as f:
                f.write(engine.serialize())
            
            # 更新模型信息
            engine_size = engine_path.stat().st_size / (1024 * 1024)
            model_info.engine_path = str(engine_path)
            model_info.precision = precision
            model_info.memory_usage_mb = engine_size
            model_info.status = ModelStatus.READY
            self._models[name] = model_info
            self._save_registry()
            
            msg = f"转换成功: {engine_path} ({engine_size:.1f}MB, {precision})"
            logger.info(msg)
            
            if progress_callback:
                progress_callback("转换完成！")
            
            return True, msg
            
        except Exception as e:
            model_info.status = ModelStatus.ERROR
            self._save_registry()
            logger.error(f"模型转换失败: {e}")
            return False, f"转换失败: {e}"

    # ==================== 性能测试 ====================
    
    def benchmark_model(
        self, 
        name: str, 
        num_iterations: int = 100,
        warmup_iterations: int = 10
    ) -> Tuple[bool, Dict]:
        """
        测试模型性能
        
        Args:
            name: 模型名称
            num_iterations: 测试迭代次数
            warmup_iterations: 预热迭代次数
            
        Returns:
            (成功标志, 性能指标字典)
        """
        if name not in self._models:
            return False, {'error': f'模型未找到: {name}'}
        
        model_info = self._models[name]
        
        if model_info.status != ModelStatus.READY:
            return False, {'error': f'模型未就绪: {model_info.status.value}'}
        
        if not self._tensorrt_available:
            return False, {'error': 'TensorRT 不可用'}
        
        try:
            import tensorrt as trt
            import pycuda.driver as cuda
            import pycuda.autoinit
            import numpy as np
            
            # 加载引擎
            TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
            
            with open(model_info.engine_path, 'rb') as f:
                engine_data = f.read()
            
            runtime = trt.Runtime(TRT_LOGGER)
            engine = runtime.deserialize_cuda_engine(engine_data)
            context = engine.create_execution_context()
            stream = cuda.Stream()
            
            # 分配缓冲区
            bindings = []
            inputs = []
            outputs = []
            
            for binding in engine:
                size = trt.volume(engine.get_binding_shape(binding))
                dtype = trt.nptype(engine.get_binding_dtype(binding))
                host_mem = cuda.pagelocked_empty(size, dtype)
                device_mem = cuda.mem_alloc(host_mem.nbytes)
                bindings.append(int(device_mem))
                
                if engine.binding_is_input(binding):
                    inputs.append({'host': host_mem, 'device': device_mem})
                else:
                    outputs.append({'host': host_mem, 'device': device_mem})
            
            # 创建随机输入
            input_shape = (1, 3, *model_info.input_size)
            input_data = np.random.randn(*input_shape).astype(np.float32)
            np.copyto(inputs[0]['host'], input_data.ravel())
            
            # 预热
            for _ in range(warmup_iterations):
                cuda.memcpy_htod_async(inputs[0]['device'], inputs[0]['host'], stream)
                context.execute_async_v2(bindings=bindings, stream_handle=stream.handle)
                cuda.memcpy_dtoh_async(outputs[0]['host'], outputs[0]['device'], stream)
                stream.synchronize()
            
            # 正式测试
            times = []
            for _ in range(num_iterations):
                start = time.time()
                cuda.memcpy_htod_async(inputs[0]['device'], inputs[0]['host'], stream)
                context.execute_async_v2(bindings=bindings, stream_handle=stream.handle)
                cuda.memcpy_dtoh_async(outputs[0]['host'], outputs[0]['device'], stream)
                stream.synchronize()
                times.append((time.time() - start) * 1000)
            
            # 计算统计
            times = np.array(times)
            results = {
                'model_name': name,
                'precision': model_info.precision,
                'input_size': model_info.input_size,
                'iterations': num_iterations,
                'avg_time_ms': float(np.mean(times)),
                'min_time_ms': float(np.min(times)),
                'max_time_ms': float(np.max(times)),
                'std_time_ms': float(np.std(times)),
                'fps': float(1000 / np.mean(times)),
                'engine_size_mb': model_info.memory_usage_mb
            }
            
            # 更新模型信息
            model_info.inference_time_ms = results['avg_time_ms']
            self._save_registry()
            
            return True, results
            
        except Exception as e:
            return False, {'error': str(e)}
    
    # ==================== 模型删除 ====================
    
    def delete_model(self, name: str, delete_files: bool = True) -> Tuple[bool, str]:
        """
        删除模型
        
        Args:
            name: 模型名称
            delete_files: 是否删除文件
            
        Returns:
            (成功标志, 消息)
        """
        if name not in self._models:
            return False, f"模型未找到: {name}"
        
        model_info = self._models[name]
        
        if delete_files:
            # 删除 ONNX 文件
            if model_info.onnx_path and Path(model_info.onnx_path).exists():
                Path(model_info.onnx_path).unlink()
                logger.info(f"删除 ONNX 文件: {model_info.onnx_path}")
            
            # 删除引擎文件
            if model_info.engine_path and Path(model_info.engine_path).exists():
                Path(model_info.engine_path).unlink()
                logger.info(f"删除引擎文件: {model_info.engine_path}")
        
        # 从注册表移除
        del self._models[name]
        self._save_registry()
        
        return True, f"模型已删除: {name}"
    
    def clear_all(self, confirm: bool = False) -> Tuple[bool, str]:
        """
        清除所有模型
        
        Args:
            confirm: 确认删除
            
        Returns:
            (成功标志, 消息)
        """
        if not confirm:
            return False, "需要确认才能删除所有模型"
        
        count = len(self._models)
        
        # 删除所有文件
        for model_info in self._models.values():
            if model_info.onnx_path and Path(model_info.onnx_path).exists():
                Path(model_info.onnx_path).unlink()
            if model_info.engine_path and Path(model_info.engine_path).exists():
                Path(model_info.engine_path).unlink()
        
        self._models.clear()
        self._save_registry()
        
        return True, f"已删除 {count} 个模型"
    
    # ==================== 快捷方法 ====================
    
    def setup_default_model(
        self, 
        model_name: str = 'yolov5s',
        use_fp16: bool = True,
        progress_callback: Callable[[str], None] = None
    ) -> Tuple[bool, str]:
        """
        一键设置默认模型（下载 + 转换）
        
        Args:
            model_name: 模型名称
            use_fp16: 使用 FP16 量化
            progress_callback: 进度回调
            
        Returns:
            (成功标志, 消息)
        """
        # 检查是否已就绪
        if model_name in self._models:
            model_info = self._models[model_name]
            if model_info.status == ModelStatus.READY:
                return True, f"模型已就绪: {model_info.engine_path}"
        
        # 下载
        if progress_callback:
            progress_callback(f"正在下载 {model_name}...")
        
        success, msg = self.download_model(model_name)
        if not success:
            return False, msg
        
        # 转换
        if self._tensorrt_available:
            success, msg = self.convert_to_tensorrt(
                model_name, 
                use_fp16=use_fp16,
                progress_callback=progress_callback
            )
            if not success:
                return False, msg
        else:
            return True, f"模型已下载（TensorRT 不可用，跳过转换）: {msg}"
        
        return True, f"模型设置完成: {model_name}"
    
    def get_best_model_path(self, model_type: ModelType = ModelType.YOLO_DETECTION) -> Optional[str]:
        """
        获取最佳可用模型路径
        
        优先返回 TensorRT 引擎，其次 ONNX
        
        Args:
            model_type: 模型类型
            
        Returns:
            模型路径，无可用模型返回 None
        """
        # 优先查找已就绪的 TensorRT 模型
        for model in self._models.values():
            if model.model_type == model_type and model.status == ModelStatus.READY:
                return model.engine_path
        
        # 其次查找已下载的 ONNX 模型
        for model in self._models.values():
            if model.model_type == model_type and model.status == ModelStatus.DOWNLOADED:
                return model.onnx_path
        
        return None
    
    # ==================== 状态查询 ====================
    
    def get_status(self) -> Dict:
        """获取管理器状态"""
        return {
            'models_dir': str(self._models_dir),
            'tensorrt_available': self._tensorrt_available,
            'total_models': len(self._models),
            'ready_models': len([m for m in self._models.values() if m.status == ModelStatus.READY]),
            'downloaded_models': len([m for m in self._models.values() if m.status == ModelStatus.DOWNLOADED]),
            'available_predefined': len(PREDEFINED_MODELS)
        }
    
    def is_tensorrt_available(self) -> bool:
        """检查 TensorRT 是否可用"""
        return self._tensorrt_available
