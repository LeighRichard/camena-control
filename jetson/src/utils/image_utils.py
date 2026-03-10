"""
图像处理工具函数 - 提取公共图像处理逻辑

提供常用的图像处理和计算函数
"""

import numpy as np
from typing import Tuple, Optional, List
from dataclasses import dataclass


@dataclass
class BoundingBox:
    """边界框"""
    x: int
    y: int
    width: int
    height: int
    
    @property
    def x1(self) -> int:
        return self.x
    
    @property
    def y1(self) -> int:
        return self.y
    
    @property
    def x2(self) -> int:
        return self.x + self.width
    
    @property
    def y2(self) -> int:
        return self.y + self.height
    
    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)
    
    @property
    def area(self) -> int:
        return self.width * self.height
    
    def to_xyxy(self) -> Tuple[int, int, int, int]:
        """转换为 (x1, y1, x2, y2) 格式"""
        return (self.x, self.y, self.x + self.width, self.y + self.height)
    
    def to_xywh(self) -> Tuple[int, int, int, int]:
        """转换为 (x, y, w, h) 格式"""
        return (self.x, self.y, self.width, self.height)
    
    @classmethod
    def from_xyxy(cls, x1: int, y1: int, x2: int, y2: int) -> 'BoundingBox':
        """从 (x1, y1, x2, y2) 格式创建"""
        return cls(x1, y1, x2 - x1, y2 - y1)
    
    @classmethod
    def from_center(cls, cx: float, cy: float, width: int, height: int) -> 'BoundingBox':
        """从中心点和尺寸创建"""
        x = int(cx - width / 2)
        y = int(cy - height / 2)
        return cls(x, y, width, height)


def calculate_center(bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
    """
    计算边界框中心点
    
    Args:
        bbox: (x, y, w, h) 格式的边界框
        
    Returns:
        (cx, cy) 中心点坐标
    """
    x, y, w, h = bbox
    return (x + w / 2, y + h / 2)


def calculate_area(bbox: Tuple[int, int, int, int]) -> int:
    """
    计算边界框面积
    
    Args:
        bbox: (x, y, w, h) 格式的边界框
        
    Returns:
        面积
    """
    _, _, w, h = bbox
    return w * h


def calculate_iou(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
    """
    计算两个边界框的 IoU (Intersection over Union)
    
    Args:
        box1: (x, y, w, h) 格式的边界框
        box2: (x, y, w, h) 格式的边界框
        
    Returns:
        IoU 值 (0-1)
    """
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2
    
    # 转换为 xyxy 格式
    box1_x1, box1_y1, box1_x2, box1_y2 = x1, y1, x1 + w1, y1 + h1
    box2_x1, box2_y1, box2_x2, box2_y2 = x2, y2, x2 + w2, y2 + h2
    
    # 计算交集
    inter_x1 = max(box1_x1, box2_x1)
    inter_y1 = max(box1_y1, box2_y1)
    inter_x2 = min(box1_x2, box2_x2)
    inter_y2 = min(box1_y2, box2_y2)
    
    inter_width = max(0, inter_x2 - inter_x1)
    inter_height = max(0, inter_y2 - inter_y1)
    inter_area = inter_width * inter_height
    
    # 计算并集
    area1 = w1 * h1
    area2 = w2 * h2
    union_area = area1 + area2 - inter_area
    
    if union_area == 0:
        return 0.0
    
    return inter_area / union_area


def calculate_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """
    计算两点之间的欧氏距离
    
    Args:
        p1: 第一个点 (x, y)
        p2: 第二个点 (x, y)
        
    Returns:
        距离
    """
    return np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def point_in_bbox(point: Tuple[float, float], bbox: Tuple[int, int, int, int]) -> bool:
    """
    检查点是否在边界框内
    
    Args:
        point: (x, y) 点坐标
        bbox: (x, y, w, h) 边界框
        
    Returns:
        是否在边界框内
    """
    px, py = point
    x, y, w, h = bbox
    return x <= px <= x + w and y <= py <= y + h


def clamp_point(point: Tuple[float, float], width: int, height: int) -> Tuple[float, float]:
    """
    将点限制在图像范围内
    
    Args:
        point: (x, y) 点坐标
        width: 图像宽度
        height: 图像高度
        
    Returns:
        限制后的点坐标
    """
    x = max(0, min(width - 1, point[0]))
    y = max(0, min(height - 1, point[1]))
    return (x, y)


def clamp_bbox(bbox: Tuple[int, int, int, int], width: int, height: int) -> Tuple[int, int, int, int]:
    """
    将边界框限制在图像范围内
    
    Args:
        bbox: (x, y, w, h) 边界框
        width: 图像宽度
        height: 图像高度
        
    Returns:
        限制后的边界框
    """
    x, y, w, h = bbox
    
    # 限制左上角
    x = max(0, x)
    y = max(0, y)
    
    # 限制右下角
    x2 = min(width, x + w)
    y2 = min(height, y + h)
    
    return (x, y, x2 - x, y2 - y)


def scale_bbox(bbox: Tuple[int, int, int, int], scale: float) -> Tuple[int, int, int, int]:
    """
    缩放边界框（保持中心不变）
    
    Args:
        bbox: (x, y, w, h) 边界框
        scale: 缩放比例
        
    Returns:
        缩放后的边界框
    """
    x, y, w, h = bbox
    cx, cy = x + w / 2, y + h / 2
    
    new_w = int(w * scale)
    new_h = int(h * scale)
    new_x = int(cx - new_w / 2)
    new_y = int(cy - new_h / 2)
    
    return (new_x, new_y, new_w, new_h)


def expand_bbox(bbox: Tuple[int, int, int, int], margin: int) -> Tuple[int, int, int, int]:
    """
    扩展边界框
    
    Args:
        bbox: (x, y, w, h) 边界框
        margin: 扩展边距（像素）
        
    Returns:
        扩展后的边界框
    """
    x, y, w, h = bbox
    return (x - margin, y - margin, w + 2 * margin, h + 2 * margin)


def calculate_brightness(image: np.ndarray) -> float:
    """
    计算图像亮度
    
    Args:
        image: RGB 或灰度图像
        
    Returns:
        平均亮度 (0-255)
    """
    if len(image.shape) == 3:
        # RGB 图像，转换为灰度
        gray = np.mean(image, axis=2)
    else:
        gray = image
    
    return float(np.mean(gray))


def calculate_contrast(image: np.ndarray) -> float:
    """
    计算图像对比度
    
    Args:
        image: RGB 或灰度图像
        
    Returns:
        对比度（标准差）
    """
    if len(image.shape) == 3:
        gray = np.mean(image, axis=2)
    else:
        gray = image
    
    return float(np.std(gray))


def calculate_sharpness(image: np.ndarray) -> float:
    """
    计算图像清晰度（使用拉普拉斯算子）
    
    Args:
        image: RGB 或灰度图像
        
    Returns:
        清晰度分数
    """
    if len(image.shape) == 3:
        gray = np.mean(image, axis=2).astype(np.float32)
    else:
        gray = image.astype(np.float32)
    
    # 简单的拉普拉斯算子
    laplacian = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    
    # 使用卷积计算
    from scipy import ndimage
    try:
        response = ndimage.convolve(gray, laplacian)
        return float(np.var(response))
    except ImportError:
        # 如果没有 scipy，使用简单方法
        return float(np.var(gray))


def resize_image(image: np.ndarray, width: int, height: int) -> np.ndarray:
    """
    调整图像大小
    
    Args:
        image: 输入图像
        width: 目标宽度
        height: 目标高度
        
    Returns:
        调整后的图像
    """
    try:
        import cv2
        return cv2.resize(image, (width, height))
    except ImportError:
        # 简单的最近邻插值
        h, w = image.shape[:2]
        x_ratio = w / width
        y_ratio = h / height
        
        if len(image.shape) == 3:
            result = np.zeros((height, width, image.shape[2]), dtype=image.dtype)
        else:
            result = np.zeros((height, width), dtype=image.dtype)
        
        for i in range(height):
            for j in range(width):
                src_x = int(j * x_ratio)
                src_y = int(i * y_ratio)
                result[i, j] = image[src_y, src_x]
        
        return result


def crop_image(image: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
    """
    裁剪图像
    
    Args:
        image: 输入图像
        bbox: (x, y, w, h) 裁剪区域
        
    Returns:
        裁剪后的图像
    """
    x, y, w, h = bbox
    h_img, w_img = image.shape[:2]
    
    # 限制范围
    x = max(0, x)
    y = max(0, y)
    x2 = min(w_img, x + w)
    y2 = min(h_img, y + h)
    
    return image[y:y2, x:x2].copy()


def normalize_image(image: np.ndarray) -> np.ndarray:
    """
    归一化图像到 0-1 范围
    
    Args:
        image: 输入图像
        
    Returns:
        归一化后的图像
    """
    return image.astype(np.float32) / 255.0


def denormalize_image(image: np.ndarray) -> np.ndarray:
    """
    反归一化图像到 0-255 范围
    
    Args:
        image: 归一化的图像
        
    Returns:
        反归一化后的图像
    """
    return (image * 255).astype(np.uint8)


def depth_to_meters(depth_mm: np.ndarray) -> np.ndarray:
    """
    将深度图从毫米转换为米
    
    Args:
        depth_mm: 毫米单位的深度图
        
    Returns:
        米单位的深度图
    """
    return depth_mm.astype(np.float32) / 1000.0


def meters_to_depth(depth_m: np.ndarray) -> np.ndarray:
    """
    将深度图从米转换为毫米
    
    Args:
        depth_m: 米单位的深度图
        
    Returns:
        毫米单位的深度图
    """
    return (depth_m * 1000).astype(np.uint16)


def get_depth_at_point(depth_image: np.ndarray, x: int, y: int, window_size: int = 5) -> float:
    """
    获取指定点的深度值（使用窗口中值滤波）
    
    Args:
        depth_image: 深度图
        x: X 坐标
        y: Y 坐标
        window_size: 窗口大小
        
    Returns:
        深度值（米）
    """
    h, w = depth_image.shape[:2]
    
    # 限制坐标范围
    x = max(0, min(w - 1, x))
    y = max(0, min(h - 1, y))
    
    # 计算窗口范围
    half = window_size // 2
    x1 = max(0, x - half)
    y1 = max(0, y - half)
    x2 = min(w, x + half + 1)
    y2 = min(h, y + half + 1)
    
    # 获取窗口内的深度值
    window = depth_image[y1:y2, x1:x2]
    
    # 过滤无效值
    valid = window[window > 0]
    
    if len(valid) == 0:
        return 0.0
    
    # 返回中值（转换为米）
    return float(np.median(valid)) / 1000.0


def pixel_to_camera(
    pixel: Tuple[float, float],
    depth: float,
    fx: float, fy: float,
    cx: float, cy: float
) -> Tuple[float, float, float]:
    """
    将像素坐标转换为相机坐标
    
    Args:
        pixel: (u, v) 像素坐标
        depth: 深度值（米）
        fx, fy: 焦距
        cx, cy: 主点
        
    Returns:
        (x, y, z) 相机坐标（米）
    """
    u, v = pixel
    z = depth
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    return (x, y, z)


def camera_to_pixel(
    point: Tuple[float, float, float],
    fx: float, fy: float,
    cx: float, cy: float
) -> Tuple[float, float]:
    """
    将相机坐标转换为像素坐标
    
    Args:
        point: (x, y, z) 相机坐标（米）
        fx, fy: 焦距
        cx, cy: 主点
        
    Returns:
        (u, v) 像素坐标
    """
    x, y, z = point
    if z == 0:
        return (cx, cy)
    
    u = x * fx / z + cx
    v = y * fy / z + cy
    return (u, v)
