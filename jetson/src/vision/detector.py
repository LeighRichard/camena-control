"""
目标检测器模块 - 使用深度学习进行农作物目标检测

支持 YOLOv5/YOLOv8 + TensorRT 推理
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum
import numpy as np
import time
import logging
import os

logger = logging.getLogger(__name__)

# 尝试导入 TensorRT 相关库
try:
    import tensorrt as trt
    import pycuda.driver as cuda
    import pycuda.autoinit
    TENSORRT_AVAILABLE = True
except ImportError:
    TENSORRT_AVAILABLE = False
    logger.warning("TensorRT 不可用，将使用模拟模式")


class SelectionStrategy(Enum):
    """目标选择策略"""
    NEAREST = "nearest"         # 最近优先（距离最近）
    LARGEST = "largest"         # 最大优先（面积最大）
    CENTER = "center"           # 中心优先（最接近图像中心）
    CONFIDENCE = "confidence"   # 置信度优先


@dataclass
class TargetInfo:
    """目标信息"""
    id: int                     # 目标编号（唯一标识）
    center_x: float             # 目标中心 X (像素)
    center_y: float             # 目标中心 Y (像素)
    distance: float             # 目标距离 (mm)，0 表示未知
    bounding_box: Tuple[int, int, int, int]  # (x, y, w, h)
    confidence: float           # 检测置信度 (0-1)
    class_name: str             # 类别名称
    class_id: int               # 类别 ID
    
    @property
    def area(self) -> int:
        """边界框面积"""
        return self.bounding_box[2] * self.bounding_box[3]
    
    @property
    def x1y1x2y2(self) -> Tuple[int, int, int, int]:
        """转换为 (x1, y1, x2, y2) 格式"""
        x, y, w, h = self.bounding_box
        return (x, y, x + w, y + h)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'center_x': self.center_x,
            'center_y': self.center_y,
            'distance': self.distance,
            'bounding_box': self.bounding_box,
            'confidence': self.confidence,
            'class_name': self.class_name,
            'class_id': self.class_id
        }


@dataclass
class DetectionConfig:
    """检测配置"""
    model_path: str = ""                    # 模型文件路径
    threshold: float = 0.5                  # 置信度阈值
    nms_threshold: float = 0.45             # NMS 阈值
    target_classes: List[str] = field(default_factory=list)  # 目标类别过滤
    selection_strategy: SelectionStrategy = SelectionStrategy.NEAREST
    roi: Optional[Tuple[int, int, int, int]] = None  # 感兴趣区域 (x, y, w, h)
    input_size: Tuple[int, int] = (640, 640)  # 模型输入尺寸
    use_fp16: bool = True                   # 使用 FP16 量化（减少约 50% 内存）
    max_workspace_size: int = 1 << 30       # TensorRT 最大工作空间 (1GB)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'model_path': self.model_path,
            'threshold': self.threshold,
            'nms_threshold': self.nms_threshold,
            'target_classes': self.target_classes,
            'selection_strategy': self.selection_strategy.value,
            'roi': self.roi,
            'input_size': self.input_size,
            'use_fp16': self.use_fp16,
            'max_workspace_size': self.max_workspace_size
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DetectionConfig':
        """从字典创建"""
        if 'selection_strategy' in data and isinstance(data['selection_strategy'], str):
            data['selection_strategy'] = SelectionStrategy(data['selection_strategy'])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DetectionResult:
    """检测结果"""
    targets: List[TargetInfo]               # 所有检测到的目标
    selected_target: Optional[TargetInfo]   # 根据策略选中的目标
    inference_time: float                   # 推理时间 (ms)
    preprocess_time: float = 0.0            # 预处理时间 (ms)
    postprocess_time: float = 0.0           # 后处理时间 (ms)
    
    @property
    def total_time(self) -> float:
        """总处理时间"""
        return self.preprocess_time + self.inference_time + self.postprocess_time
    
    @property
    def target_count(self) -> int:
        """目标数量"""
        return len(self.targets)


class ObjectDetector:
    """
    目标检测器 (YOLOv5/YOLOv8 + TensorRT)
    
    支持：
    - TensorRT 加速推理
    - 多目标检测和跟踪
    - 多种目标选择策略
    - 模拟模式（用于测试）
    """
    
    # COCO 类别名称（默认）
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
    
    def __init__(self, config: DetectionConfig = None):
        self._config = config or DetectionConfig()
        self._model = None
        self._context = None
        self._stream = None
        self._bindings = None
        self._target_counter = 0
        self._class_names = self.COCO_CLASSES.copy()
        self._is_loaded = False
        self._simulation_mode = False
    
    def load_model(self, model_path: str = None) -> Tuple[bool, str]:
        """
        加载 TensorRT 模型
        
        Args:
            model_path: 模型文件路径（.engine 或 .trt）
            
        Returns:
            (成功标志, 错误信息)
        """
        if model_path:
            self._config.model_path = model_path
        
        if not self._config.model_path:
            # 启用模拟模式
            self._simulation_mode = True
            self._is_loaded = True
            logger.info("未指定模型路径，启用模拟模式")
            return True, ""
        
        if not os.path.exists(self._config.model_path):
            return False, f"模型文件不存在: {self._config.model_path}"
        
        if not TENSORRT_AVAILABLE:
            # TensorRT 不可用，启用模拟模式
            self._simulation_mode = True
            self._is_loaded = True
            logger.warning("TensorRT 不可用，启用模拟模式")
            return True, ""
        
        try:
            # 加载 TensorRT 引擎
            TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
            
            with open(self._config.model_path, 'rb') as f:
                engine_data = f.read()
            
            runtime = trt.Runtime(TRT_LOGGER)
            self._model = runtime.deserialize_cuda_engine(engine_data)
            
            if self._model is None:
                return False, "无法反序列化 TensorRT 引擎"
            
            # 创建执行上下文
            self._context = self._model.create_execution_context()
            
            # 创建 CUDA 流
            self._stream = cuda.Stream()
            
            # 分配输入输出缓冲区
            self._allocate_buffers()
            
            self._is_loaded = True
            self._simulation_mode = False
            logger.info(f"TensorRT 模型加载成功: {self._config.model_path}")
            return True, ""
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False, str(e)
    
    def _allocate_buffers(self):
        """分配 CUDA 缓冲区"""
        self._bindings = []
        self._inputs = []
        self._outputs = []
        
        for binding in self._model:
            size = trt.volume(self._model.get_binding_shape(binding))
            dtype = trt.nptype(self._model.get_binding_dtype(binding))
            
            # 分配主机和设备内存
            host_mem = cuda.pagelocked_empty(size, dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)
            
            self._bindings.append(int(device_mem))
            
            if self._model.binding_is_input(binding):
                self._inputs.append({'host': host_mem, 'device': device_mem})
            else:
                self._outputs.append({'host': host_mem, 'device': device_mem})
    
    def detect(self, image: np.ndarray, depth: np.ndarray = None) -> DetectionResult:
        """
        检测目标
        
        Args:
            image: RGB 图像 (H, W, 3)
            depth: 深度图像 (H, W)，可选
            
        Returns:
            检测结果
        """
        if not self._is_loaded:
            return DetectionResult(
                targets=[],
                selected_target=None,
                inference_time=0.0
            )
        
        start_time = time.time()
        
        # 预处理
        preprocess_start = time.time()
        input_tensor = self._preprocess(image)
        preprocess_time = (time.time() - preprocess_start) * 1000
        
        # 推理
        inference_start = time.time()
        if self._simulation_mode:
            raw_output = self._simulate_inference(image)
        else:
            raw_output = self._inference(input_tensor)
        inference_time = (time.time() - inference_start) * 1000
        
        # 后处理
        postprocess_start = time.time()
        targets = self._postprocess(raw_output, image.shape[:2], depth)
        postprocess_time = (time.time() - postprocess_start) * 1000
        
        # 选择目标
        selected = self.select_target(targets, self._config.selection_strategy)
        
        return DetectionResult(
            targets=targets,
            selected_target=selected,
            inference_time=inference_time,
            preprocess_time=preprocess_time,
            postprocess_time=postprocess_time
        )
    
    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        预处理图像
        
        Args:
            image: RGB 图像
            
        Returns:
            预处理后的张量
        """
        h, w = image.shape[:2]
        input_h, input_w = self._config.input_size
        
        # 计算缩放比例（保持宽高比）
        scale = min(input_w / w, input_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        
        # 简单的最近邻缩放
        resized = self._resize_image(image, new_w, new_h)
        
        # 创建填充后的图像
        padded = np.full((input_h, input_w, 3), 114, dtype=np.uint8)
        pad_x = (input_w - new_w) // 2
        pad_y = (input_h - new_h) // 2
        padded[pad_y:pad_y+new_h, pad_x:pad_x+new_w] = resized
        
        # 归一化并转换为 NCHW 格式
        tensor = padded.astype(np.float32) / 255.0
        tensor = tensor.transpose(2, 0, 1)  # HWC -> CHW
        tensor = np.expand_dims(tensor, 0)  # 添加 batch 维度
        
        return tensor
    
    def _resize_image(self, image: np.ndarray, new_w: int, new_h: int) -> np.ndarray:
        """
        图像缩放（双线性插值）
        
        优先使用 OpenCV，如果不可用则使用 NumPy 向量化操作。
        相比纯 Python 循环，性能提升约 100-1000 倍。
        
        Args:
            image: 输入图像 (H, W, 3)
            new_w: 目标宽度
            new_h: 目标高度
            
        Returns:
            缩放后的图像
        """
        # 优先使用 OpenCV（最快）
        try:
            import cv2
            return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        except ImportError:
            pass
        
        # 回退到 NumPy 向量化实现（比纯循环快约 100 倍）
        h, w = image.shape[:2]
        
        # 创建目标坐标网格
        y_indices = np.arange(new_h)
        x_indices = np.arange(new_w)
        
        # 计算源图像中的对应坐标
        src_y = y_indices * (h / new_h)
        src_x = x_indices * (w / new_w)
        
        # 创建网格
        src_y_grid, src_x_grid = np.meshgrid(src_y, src_x, indexing='ij')
        
        # 计算四个邻近像素的坐标
        y0 = np.floor(src_y_grid).astype(np.int32)
        x0 = np.floor(src_x_grid).astype(np.int32)
        y1 = np.minimum(y0 + 1, h - 1)
        x1 = np.minimum(x0 + 1, w - 1)
        
        # 计算插值权重
        dy = src_y_grid - y0
        dx = src_x_grid - x0
        
        # 扩展维度以支持 RGB 通道
        dy = dy[:, :, np.newaxis]
        dx = dx[:, :, np.newaxis]
        
        # 双线性插值
        resized = (
            (1 - dx) * (1 - dy) * image[y0, x0] +
            dx * (1 - dy) * image[y0, x1] +
            (1 - dx) * dy * image[y1, x0] +
            dx * dy * image[y1, x1]
        ).astype(np.uint8)
        
        return resized
    
    def _inference(self, input_tensor: np.ndarray) -> np.ndarray:
        """TensorRT 推理"""
        # 复制输入到设备
        np.copyto(self._inputs[0]['host'], input_tensor.ravel())
        cuda.memcpy_htod_async(
            self._inputs[0]['device'],
            self._inputs[0]['host'],
            self._stream
        )
        
        # 执行推理
        self._context.execute_async_v2(
            bindings=self._bindings,
            stream_handle=self._stream.handle
        )
        
        # 复制输出到主机
        cuda.memcpy_dtoh_async(
            self._outputs[0]['host'],
            self._outputs[0]['device'],
            self._stream
        )
        
        # 同步
        self._stream.synchronize()
        
        return self._outputs[0]['host']
    
    def _simulate_inference(self, image: np.ndarray) -> List[List[float]]:
        """
        模拟推理（用于测试）
        
        生成随机但合理的检测结果
        """
        h, w = image.shape[:2]
        
        # 随机生成 0-3 个目标
        num_targets = np.random.randint(0, 4)
        
        detections = []
        for _ in range(num_targets):
            # 随机边界框
            box_w = np.random.randint(50, min(200, w // 2))
            box_h = np.random.randint(50, min(200, h // 2))
            x = np.random.randint(0, w - box_w)
            y = np.random.randint(0, h - box_h)
            
            # 随机类别和置信度
            class_id = np.random.randint(0, len(self._class_names))
            confidence = np.random.uniform(0.5, 0.95)
            
            # [x1, y1, x2, y2, confidence, class_id]
            detections.append([x, y, x + box_w, y + box_h, confidence, class_id])
        
        return detections
    
    def _postprocess(
        self, 
        raw_output: Any, 
        image_shape: Tuple[int, int],
        depth: np.ndarray = None
    ) -> List[TargetInfo]:
        """
        后处理检测结果
        
        Args:
            raw_output: 原始输出
            image_shape: 原始图像尺寸 (H, W)
            depth: 深度图像
            
        Returns:
            目标列表
        """
        targets = []
        h, w = image_shape
        
        # 处理模拟模式的输出
        if self._simulation_mode:
            detections = raw_output
        else:
            # 解析 YOLO 输出格式
            detections = self._parse_yolo_output(raw_output, w, h)
        
        # 应用 NMS
        detections = self._nms(detections, self._config.nms_threshold)
        
        for det in detections:
            x1, y1, x2, y2, conf, class_id = det[:6]
            
            # 过滤低置信度
            if conf < self._config.threshold:
                continue
            
            # 类别过滤
            class_id = int(class_id)
            class_name = self._class_names[class_id] if class_id < len(self._class_names) else f"class_{class_id}"
            
            if self._config.target_classes and class_name not in self._config.target_classes:
                continue
            
            # 计算中心点
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            
            # 获取深度（智能处理分辨率差异）
            distance = 0.0
            if depth is not None:
                distance = self._get_depth_smart(center_x, center_y, depth, w, h)
            
            # 创建目标信息
            self._target_counter += 1
            target = TargetInfo(
                id=self._target_counter,
                center_x=center_x,
                center_y=center_y,
                distance=distance,
                bounding_box=(int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                confidence=float(conf),
                class_name=class_name,
                class_id=class_id
            )
            targets.append(target)
        
        return targets
    
    def _parse_yolo_output(self, output: np.ndarray, img_w: int, img_h: int) -> List[List[float]]:
        """解析 YOLO 输出"""
        # YOLO 输出格式: [batch, num_boxes, 5 + num_classes]
        # 5 = [x, y, w, h, objectness]
        
        detections = []
        
        # 简化处理：假设输出已经是 [num_boxes, 6] 格式
        if len(output.shape) == 1:
            num_boxes = len(output) // 6
            output = output.reshape(num_boxes, 6)
        
        input_h, input_w = self._config.input_size
        scale = min(input_w / img_w, input_h / img_h)
        pad_x = (input_w - img_w * scale) / 2
        pad_y = (input_h - img_h * scale) / 2
        
        for box in output:
            x1, y1, x2, y2, conf, class_id = box
            
            # 转换回原始图像坐标
            x1 = (x1 - pad_x) / scale
            y1 = (y1 - pad_y) / scale
            x2 = (x2 - pad_x) / scale
            y2 = (y2 - pad_y) / scale
            
            # 裁剪到图像边界
            x1 = max(0, min(x1, img_w))
            y1 = max(0, min(y1, img_h))
            x2 = max(0, min(x2, img_w))
            y2 = max(0, min(y2, img_h))
            
            detections.append([x1, y1, x2, y2, conf, class_id])
        
        return detections
    
    def _nms(self, detections: List[List[float]], threshold: float) -> List[List[float]]:
        """非极大值抑制"""
        if not detections:
            return []
        
        # 按置信度排序
        detections = sorted(detections, key=lambda x: x[4], reverse=True)
        
        keep = []
        while detections:
            best = detections.pop(0)
            keep.append(best)
            
            detections = [
                det for det in detections
                if self._iou(best[:4], det[:4]) < threshold
            ]
        
        return keep
    
    def _iou(self, box1: List[float], box2: List[float]) -> float:
        """计算 IoU"""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        
        union = area1 + area2 - inter
        
        return inter / union if union > 0 else 0
    
    def _get_depth_smart(
        self,
        center_x: float,
        center_y: float,
        depth_image: np.ndarray,
        color_w: int,
        color_h: int
    ) -> float:
        """
        智能深度查询，自动处理分辨率差异
        
        Args:
            center_x: 目标中心 X（彩色图坐标）
            center_y: 目标中心 Y（彩色图坐标）
            depth_image: 深度图像 (H, W)，单位：毫米
            color_w: 彩色图宽度
            color_h: 彩色图高度
            
        Returns:
            深度值（毫米），无效返回 0.0
        """
        depth_h, depth_w = depth_image.shape[:2]
        
        # 检查分辨率是否匹配
        if depth_w == color_w and depth_h == color_h:
            # 分辨率匹配，直接查询
            cx, cy = int(center_x), int(center_y)
            if 0 <= cx < depth_w and 0 <= cy < depth_h:
                return float(depth_image[cy, cx])
            return 0.0
        
        # 分辨率不匹配，需要坐标转换和滤波
        # 计算缩放比例
        scale_x = depth_w / color_w
        scale_y = depth_h / color_h
        
        # 转换到深度图坐标
        depth_x = int(center_x * scale_x)
        depth_y = int(center_y * scale_y)
        
        # 边界检查
        if not (0 <= depth_x < depth_w and 0 <= depth_y < depth_h):
            return 0.0
        
        # 使用 5×5 区域中值滤波（适配 Orbbec 相机）
        filter_size = 5
        half_size = filter_size // 2
        
        x1 = max(0, depth_x - half_size)
        y1 = max(0, depth_y - half_size)
        x2 = min(depth_w, depth_x + half_size + 1)
        y2 = min(depth_h, depth_y + half_size + 1)
        
        if x1 >= x2 or y1 >= y2:
            return 0.0
        
        # 提取区域
        region = depth_image[y1:y2, x1:x2].astype(np.float32)
        
        # 过滤无效值（0 表示无效深度）
        valid_depths = region[region > 0]
        
        if len(valid_depths) == 0:
            return 0.0
        
        # 返回中值
        return float(np.median(valid_depths))
    
    def select_target(
        self, 
        targets: List[TargetInfo], 
        strategy: SelectionStrategy = None,
        image_center: Tuple[float, float] = None
    ) -> Optional[TargetInfo]:
        """
        根据策略选择目标
        
        Args:
            targets: 目标列表
            strategy: 选择策略，None 使用配置中的策略
            image_center: 图像中心坐标，用于 CENTER 策略
            
        Returns:
            选中的目标，无目标返回 None
        """
        if not targets:
            return None
        
        if strategy is None:
            strategy = self._config.selection_strategy
        
        if image_center is None:
            image_center = (640, 360)  # 默认 1280x720 的中心
        
        if strategy == SelectionStrategy.NEAREST:
            # 最近优先（需要有效深度）
            valid_targets = [t for t in targets if t.distance > 0]
            if valid_targets:
                return min(valid_targets, key=lambda t: t.distance)
            # 如果没有有效深度，回退到中心优先
            strategy = SelectionStrategy.CENTER
        
        if strategy == SelectionStrategy.LARGEST:
            return max(targets, key=lambda t: t.area)
        
        if strategy == SelectionStrategy.CENTER:
            cx, cy = image_center
            return min(targets, key=lambda t: (t.center_x - cx)**2 + (t.center_y - cy)**2)
        
        if strategy == SelectionStrategy.CONFIDENCE:
            return max(targets, key=lambda t: t.confidence)
        
        return targets[0]
    
    def set_config(self, config: DetectionConfig):
        """设置配置"""
        self._config = config
    
    def get_config(self) -> DetectionConfig:
        """获取配置"""
        return self._config
    
    def set_class_names(self, names: List[str]):
        """设置类别名称"""
        self._class_names = names
    
    def get_class_names(self) -> List[str]:
        """获取类别名称"""
        return self._class_names
    
    def is_loaded(self) -> bool:
        """检查模型是否已加载"""
        return self._is_loaded
    
    def is_simulation_mode(self) -> bool:
        """检查是否为模拟模式"""
        return self._simulation_mode
    
    def reset_target_counter(self):
        """重置目标计数器"""
        self._target_counter = 0
    
    def unload(self):
        """卸载模型"""
        self._model = None
        self._context = None
        self._stream = None
        self._bindings = None
        self._is_loaded = False
        self._simulation_mode = False
    
    @staticmethod
    def convert_onnx_to_tensorrt(
        onnx_path: str,
        engine_path: str,
        use_fp16: bool = True,
        max_workspace_size: int = 1 << 30,
        input_shape: Tuple[int, int, int, int] = (1, 3, 640, 640)
    ) -> Tuple[bool, str]:
        """
        将 ONNX 模型转换为 TensorRT 引擎
        
        支持 FP16 量化，可减少约 50% 内存占用并提升推理速度。
        
        Args:
            onnx_path: ONNX 模型路径
            engine_path: 输出 TensorRT 引擎路径
            use_fp16: 是否使用 FP16 量化
            max_workspace_size: 最大工作空间大小 (bytes)
            input_shape: 输入形状 (batch, channels, height, width)
            
        Returns:
            (成功标志, 错误信息或成功消息)
            
        Example:
            >>> success, msg = ObjectDetector.convert_onnx_to_tensorrt(
            ...     'yolov5s.onnx',
            ...     'yolov5s_fp16.engine',
            ...     use_fp16=True
            ... )
        """
        if not TENSORRT_AVAILABLE:
            return False, "TensorRT 不可用，无法进行模型转换"
        
        if not os.path.exists(onnx_path):
            return False, f"ONNX 模型不存在: {onnx_path}"
        
        try:
            TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
            
            # 创建 builder
            builder = trt.Builder(TRT_LOGGER)
            network_flags = 1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
            network = builder.create_network(network_flags)
            
            # 解析 ONNX
            parser = trt.OnnxParser(network, TRT_LOGGER)
            
            with open(onnx_path, 'rb') as f:
                if not parser.parse(f.read()):
                    errors = [parser.get_error(i) for i in range(parser.num_errors)]
                    return False, f"ONNX 解析失败: {errors}"
            
            # 配置 builder
            config = builder.create_builder_config()
            config.max_workspace_size = max_workspace_size
            
            # 启用 FP16 量化
            if use_fp16 and builder.platform_has_fast_fp16:
                config.set_flag(trt.BuilderFlag.FP16)
                logger.info("启用 FP16 量化模式")
            elif use_fp16:
                logger.warning("平台不支持快速 FP16，使用 FP32")
            
            # 设置输入形状
            profile = builder.create_optimization_profile()
            input_name = network.get_input(0).name
            profile.set_shape(
                input_name,
                min=input_shape,
                opt=input_shape,
                max=input_shape
            )
            config.add_optimization_profile(profile)
            
            # 构建引擎
            logger.info(f"开始构建 TensorRT 引擎 (FP16={use_fp16})...")
            engine = builder.build_engine(network, config)
            
            if engine is None:
                return False, "TensorRT 引擎构建失败"
            
            # 序列化并保存
            with open(engine_path, 'wb') as f:
                f.write(engine.serialize())
            
            # 获取引擎大小
            engine_size_mb = os.path.getsize(engine_path) / (1024 * 1024)
            
            msg = f"TensorRT 引擎已保存: {engine_path} ({engine_size_mb:.1f}MB, FP16={use_fp16})"
            logger.info(msg)
            return True, msg
            
        except Exception as e:
            logger.error(f"模型转换失败: {e}")
            return False, str(e)
    
    def get_memory_usage(self) -> Dict[str, float]:
        """
        获取模型内存使用情况
        
        Returns:
            包含内存信息的字典:
            - model_size_mb: 模型大小 (MB)
            - estimated_gpu_mb: 估计 GPU 内存占用 (MB)
        """
        result = {
            'model_size_mb': 0.0,
            'estimated_gpu_mb': 0.0
        }
        
        if self._config.model_path and os.path.exists(self._config.model_path):
            result['model_size_mb'] = os.path.getsize(self._config.model_path) / (1024 * 1024)
            # GPU 内存估计（模型大小 + 输入输出缓冲区）
            input_size = self._config.input_size
            buffer_size = input_size[0] * input_size[1] * 3 * 4 / (1024 * 1024)  # FP32 输入
            result['estimated_gpu_mb'] = result['model_size_mb'] + buffer_size * 2
        
        return result
