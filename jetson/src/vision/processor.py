"""
图像处理器模块 - 图像质量评估和位置计算
"""

from dataclasses import dataclass
from typing import Tuple, Optional, List
import numpy as np
import math

from .detector import TargetInfo


@dataclass
class QualityMetrics:
    """图像质量指标"""
    brightness_score: float     # 亮度评分 (0-1)
    contrast_score: float       # 对比度评分 (0-1)
    sharpness_score: float      # 清晰度评分 (0-1)
    is_acceptable: bool         # 是否达到可接受质量


@dataclass
class PositionAdjustment:
    """位置调整量"""
    pan_delta: float            # 水平角度调整 (度)
    tilt_delta: float           # 俯仰角度调整 (度)
    rail_delta: float           # 滑轨位置调整 (mm)
    target_in_center: bool      # 目标是否已在中心
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'pan_delta': self.pan_delta,
            'tilt_delta': self.tilt_delta,
            'rail_delta': self.rail_delta,
            'target_in_center': self.target_in_center
        }


@dataclass
class CameraIntrinsics:
    """相机内参"""
    fx: float                   # X 方向焦距
    fy: float                   # Y 方向焦距
    cx: float                   # 主点 X
    cy: float                   # 主点 Y
    width: int                  # 图像宽度
    height: int                 # 图像高度
    
    @classmethod
    def d415_default(cls, width: int = 1280, height: int = 720) -> 'CameraIntrinsics':
        """D415 默认内参（近似值）"""
        # D415 在 1280x720 分辨率下的典型内参
        fx = 920.0 * width / 1280
        fy = 920.0 * height / 720
        cx = width / 2
        cy = height / 2
        return cls(fx=fx, fy=fy, cx=cx, cy=cy, width=width, height=height)


class ImageProcessor:
    """
    图像处理器
    
    负责：
    - 图像质量评估
    - 目标位置到云台/滑轨调整量的计算
    - 图像叠加层绘制
    """
    
    # 质量阈值
    MIN_BRIGHTNESS = 0.3
    MIN_CONTRAST = 0.3
    MIN_SHARPNESS = 0.3
    
    def __init__(
        self, 
        image_width: int = 1280, 
        image_height: int = 720,
        intrinsics: CameraIntrinsics = None
    ):
        self._width = image_width
        self._height = image_height
        self._center_x = image_width / 2
        self._center_y = image_height / 2
        
        # 相机内参
        if intrinsics is None:
            self._intrinsics = CameraIntrinsics.d415_default(image_width, image_height)
        else:
            self._intrinsics = intrinsics
        
        # D415 视场角（度）
        self._fov_h = 69.4      # 水平视场角
        self._fov_v = 42.5      # 垂直视场角
    
    def evaluate_quality(self, image: np.ndarray) -> QualityMetrics:
        """
        评估图像质量
        
        Args:
            image: RGB 或灰度图像
            
        Returns:
            质量指标
        """
        # 转换为灰度
        if len(image.shape) == 3:
            gray = (0.299 * image[:, :, 0] + 
                    0.587 * image[:, :, 1] + 
                    0.114 * image[:, :, 2])
        else:
            gray = image.astype(np.float32)
        
        # 亮度评估（目标亮度 128）
        mean_brightness = np.mean(gray)
        brightness_score = 1.0 - abs(mean_brightness - 128) / 128
        brightness_score = max(0, min(1, brightness_score))
        
        # 对比度评估
        std_dev = np.std(gray)
        contrast_score = min(std_dev / 64, 1.0)
        
        # 清晰度评估（拉普拉斯方差）
        sharpness = self._laplacian_variance(gray)
        # 归一化到 0-1（假设 1000 为最大清晰度）
        sharpness_score = min(sharpness / 1000, 1.0)
        
        is_acceptable = (
            brightness_score >= self.MIN_BRIGHTNESS and
            contrast_score >= self.MIN_CONTRAST and
            sharpness_score >= self.MIN_SHARPNESS
        )
        
        return QualityMetrics(
            brightness_score=brightness_score,
            contrast_score=contrast_score,
            sharpness_score=sharpness_score,
            is_acceptable=is_acceptable
        )
    
    def _laplacian_variance(self, gray: np.ndarray) -> float:
        """计算拉普拉斯方差"""
        h, w = gray.shape[:2]
        if h < 3 or w < 3:
            return 0.0
        
        # 拉普拉斯核
        kernel = np.array([[0, 1, 0],
                           [1, -4, 1],
                           [0, 1, 0]], dtype=np.float32)
        
        # 卷积
        laplacian = np.zeros((h - 2, w - 2), dtype=np.float32)
        for i in range(3):
            for j in range(3):
                laplacian += kernel[i, j] * gray[i:h-2+i, j:w-2+j]
        
        return float(np.var(laplacian))
    
    def calculate_position_adjustment(
        self, 
        target_x: float, 
        target_y: float,
        target_distance: float = 0,
        tolerance_pixels: int = 50
    ) -> PositionAdjustment:
        """
        计算位置调整量
        
        将目标在图像中的位置偏移转换为云台角度调整量。
        
        Args:
            target_x: 目标中心 X (像素)
            target_y: 目标中心 Y (像素)
            target_distance: 目标距离 (mm)，用于滑轨调整
            tolerance_pixels: 容差像素，在此范围内认为已居中
            
        Returns:
            位置调整量
        """
        # 计算像素偏移
        dx = target_x - self._center_x
        dy = target_y - self._center_y
        
        # 检查是否已在中心
        if abs(dx) < tolerance_pixels and abs(dy) < tolerance_pixels:
            return PositionAdjustment(
                pan_delta=0.0,
                tilt_delta=0.0,
                rail_delta=0.0,
                target_in_center=True
            )
        
        # 像素偏移转角度偏移
        # 使用视场角计算
        pan_delta = (dx / self._width) * self._fov_h
        tilt_delta = -(dy / self._height) * self._fov_v  # Y 轴反向
        
        # 滑轨调整（可选，基于深度）
        rail_delta = 0.0
        # 如果需要保持特定距离，可以计算滑轨调整
        # rail_delta = target_distance - desired_distance
        
        return PositionAdjustment(
            pan_delta=pan_delta,
            tilt_delta=tilt_delta,
            rail_delta=rail_delta,
            target_in_center=False
        )
    
    def calculate_adjustment_from_target(
        self,
        target: TargetInfo,
        tolerance_pixels: int = 50
    ) -> PositionAdjustment:
        """
        从目标信息计算位置调整量
        
        Args:
            target: 目标信息
            tolerance_pixels: 容差像素
            
        Returns:
            位置调整量
        """
        return self.calculate_position_adjustment(
            target_x=target.center_x,
            target_y=target.center_y,
            target_distance=target.distance,
            tolerance_pixels=tolerance_pixels
        )
    
    def pixel_to_angle(self, pixel_x: float, pixel_y: float) -> Tuple[float, float]:
        """
        像素坐标转角度偏移
        
        Args:
            pixel_x, pixel_y: 像素坐标
            
        Returns:
            (水平角度, 垂直角度) 相对于图像中心
        """
        dx = pixel_x - self._center_x
        dy = pixel_y - self._center_y
        
        angle_h = math.atan2(dx, self._intrinsics.fx) * 180 / math.pi
        angle_v = math.atan2(dy, self._intrinsics.fy) * 180 / math.pi
        
        return angle_h, -angle_v  # Y 轴反向
    
    def pixel_to_3d(
        self, 
        pixel_x: float, 
        pixel_y: float, 
        depth_mm: float
    ) -> Tuple[float, float, float]:
        """
        像素坐标和深度转 3D 坐标
        
        Args:
            pixel_x, pixel_y: 像素坐标
            depth_mm: 深度值（毫米）
            
        Returns:
            (X, Y, Z) 相机坐标系下的 3D 坐标（毫米）
        """
        z = depth_mm
        x = (pixel_x - self._intrinsics.cx) * z / self._intrinsics.fx
        y = (pixel_y - self._intrinsics.cy) * z / self._intrinsics.fy
        
        return x, y, z
    
    def draw_overlay(
        self, 
        image: np.ndarray,
        targets: List[TargetInfo],
        selected_id: Optional[int] = None,
        draw_crosshair: bool = True,
        draw_info: bool = True
    ) -> np.ndarray:
        """
        在图像上绘制叠加层
        
        使用纯 numpy 实现，避免依赖 OpenCV
        
        Args:
            image: 原始图像 (H, W, 3)
            targets: 目标列表
            selected_id: 选中的目标 ID
            draw_crosshair: 是否绘制中心十字线
            draw_info: 是否绘制目标信息
            
        Returns:
            带叠加层的图像
        """
        # 复制图像
        output = image.copy()
        h, w = output.shape[:2]
        
        # 绘制中心十字线
        if draw_crosshair:
            cx, cy = w // 2, h // 2
            # 水平线
            output[cy-1:cy+2, cx-30:cx+30] = [0, 255, 0]
            # 垂直线
            output[cy-30:cy+30, cx-1:cx+2] = [0, 255, 0]
        
        # 绘制目标边界框
        for target in targets:
            x, y, bw, bh = target.bounding_box
            
            # 选择颜色
            if target.id == selected_id:
                color = [255, 0, 0]  # 红色表示选中
                thickness = 3
            else:
                color = [0, 255, 255]  # 黄色表示其他目标
                thickness = 2
            
            # 绘制边界框（简单实现）
            self._draw_rect(output, x, y, bw, bh, color, thickness)
            
            # 绘制目标中心点
            cx, cy = int(target.center_x), int(target.center_y)
            if 2 <= cx < w - 2 and 2 <= cy < h - 2:
                output[cy-2:cy+3, cx-2:cx+3] = color
        
        return output
    
    def _draw_rect(
        self, 
        image: np.ndarray, 
        x: int, y: int, 
        w: int, h: int, 
        color: List[int], 
        thickness: int = 1
    ):
        """绘制矩形"""
        img_h, img_w = image.shape[:2]
        
        # 裁剪到图像边界
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(img_w, x + w), min(img_h, y + h)
        
        # 上边
        if y1 >= 0 and y1 < img_h:
            image[y1:min(y1+thickness, img_h), x1:x2] = color
        # 下边
        if y2 - thickness >= 0 and y2 <= img_h:
            image[max(0, y2-thickness):y2, x1:x2] = color
        # 左边
        if x1 >= 0 and x1 < img_w:
            image[y1:y2, x1:min(x1+thickness, img_w)] = color
        # 右边
        if x2 - thickness >= 0 and x2 <= img_w:
            image[y1:y2, max(0, x2-thickness):x2] = color
    
    def set_intrinsics(self, intrinsics: CameraIntrinsics):
        """设置相机内参"""
        self._intrinsics = intrinsics
        self._width = intrinsics.width
        self._height = intrinsics.height
        self._center_x = intrinsics.cx
        self._center_y = intrinsics.cy
    
    def get_intrinsics(self) -> CameraIntrinsics:
        """获取相机内参"""
        return self._intrinsics
