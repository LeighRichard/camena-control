"""
视频流服务模块 - 提供 MJPEG 视频流和帧处理

实现：
- MJPEG 视频流生成
- 目标检测框叠加
- 中心十字线绘制
- 状态信息叠加
"""

from typing import Optional, List, Tuple, Callable
from dataclasses import dataclass, field
import threading
import time
import logging
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OverlayConfig:
    """叠加层配置"""
    show_crosshair: bool = True
    show_detection_boxes: bool = True
    show_target_info: bool = True
    show_status_bar: bool = True
    crosshair_color: Tuple[int, int, int] = (0, 255, 0)  # BGR
    crosshair_size: int = 30
    crosshair_thickness: int = 2
    box_color_normal: Tuple[int, int, int] = (255, 255, 0)  # 青色
    box_color_selected: Tuple[int, int, int] = (0, 255, 0)  # 绿色
    box_thickness: int = 2
    font_scale: float = 0.5
    font_thickness: int = 1


@dataclass
class DetectionTarget:
    """检测目标信息"""
    id: int
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    center: Tuple[int, int]
    depth: Optional[float] = None
    selected: bool = False


@dataclass
class StreamStatus:
    """流状态信息"""
    fps: float = 0.0
    frame_count: int = 0
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # pan, tilt, rail
    is_moving: bool = False
    is_capturing: bool = False
    target_mode: str = "auto"


class FrameProcessor:
    """帧处理器 - 负责叠加信息到视频帧"""
    
    def __init__(self, config: Optional[OverlayConfig] = None):
        self.config = config or OverlayConfig()
    
    def draw_crosshair(self, frame: np.ndarray) -> np.ndarray:
        """绘制中心十字线"""
        if not self.config.show_crosshair:
            return frame
        
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        size = self.config.crosshair_size
        color = self.config.crosshair_color
        thickness = self.config.crosshair_thickness
        
        # 水平线
        frame[cy, cx - size:cx + size + 1] = color
        # 垂直线
        frame[cy - size:cy + size + 1, cx] = color
        
        # 加粗（如果 thickness > 1）
        if thickness > 1:
            for i in range(1, thickness):
                if cy - i >= 0:
                    frame[cy - i, cx - size:cx + size + 1] = color
                if cy + i < h:
                    frame[cy + i, cx - size:cx + size + 1] = color
                if cx - i >= 0:
                    frame[cy - size:cy + size + 1, cx - i] = color
                if cx + i < w:
                    frame[cy - size:cy + size + 1, cx + i] = color
        
        return frame
    
    def draw_detection_box(
        self, 
        frame: np.ndarray, 
        target: DetectionTarget
    ) -> np.ndarray:
        """绘制检测框"""
        if not self.config.show_detection_boxes:
            return frame
        
        x, y, w, h = target.bbox
        color = self.config.box_color_selected if target.selected else self.config.box_color_normal
        thickness = self.config.box_thickness
        
        # 绘制矩形框
        frame[y:y+thickness, x:x+w] = color  # 上边
        frame[y+h-thickness:y+h, x:x+w] = color  # 下边
        frame[y:y+h, x:x+thickness] = color  # 左边
        frame[y:y+h, x+w-thickness:x+w] = color  # 右边
        
        return frame
    
    def draw_target_label(
        self, 
        frame: np.ndarray, 
        target: DetectionTarget
    ) -> np.ndarray:
        """绘制目标标签"""
        if not self.config.show_target_info:
            return frame
        
        x, y, _, _ = target.bbox
        
        # 构建标签文本
        label = f"#{target.id} {target.class_name} {target.confidence:.0%}"
        if target.depth:
            label += f" {target.depth:.2f}m"
        
        # 简单文本渲染（不依赖 OpenCV）
        # 在框上方绘制背景条
        label_height = 16
        label_width = len(label) * 7
        
        if y >= label_height:
            # 背景
            frame[y-label_height:y, x:x+label_width] = (0, 0, 0)
        
        return frame
    
    def draw_status_bar(
        self, 
        frame: np.ndarray, 
        status: StreamStatus
    ) -> np.ndarray:
        """绘制状态栏"""
        if not self.config.show_status_bar:
            return frame
        
        h, w = frame.shape[:2]
        bar_height = 24
        
        # 底部状态栏背景
        frame[h-bar_height:h, :] = (40, 40, 40)
        
        return frame
    
    def process_frame(
        self, 
        frame: np.ndarray,
        targets: Optional[List[DetectionTarget]] = None,
        status: Optional[StreamStatus] = None
    ) -> np.ndarray:
        """
        处理帧，添加所有叠加层
        
        Args:
            frame: 原始帧 (BGR numpy array)
            targets: 检测目标列表
            status: 流状态信息
            
        Returns:
            处理后的帧
        """
        # 复制帧避免修改原始数据
        output = frame.copy()
        
        # 绘制检测框
        if targets:
            for target in targets:
                output = self.draw_detection_box(output, target)
                output = self.draw_target_label(output, target)
        
        # 绘制中心十字线
        output = self.draw_crosshair(output)
        
        # 绘制状态栏
        if status:
            output = self.draw_status_bar(output, status)
        
        return output


class VideoStreamService:
    """视频流服务"""
    
    def __init__(
        self,
        fps: int = 15,
        quality: int = 80,
        overlay_config: Optional[OverlayConfig] = None
    ):
        self.fps = fps
        self.quality = quality
        self.frame_processor = FrameProcessor(overlay_config)
        
        self._running = False
        self._thread = None
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[bytes] = None
        self._latest_raw_frame: Optional[np.ndarray] = None
        
        # 回调函数
        self._capture_callback: Optional[Callable] = None
        self._targets_callback: Optional[Callable] = None
        self._status_callback: Optional[Callable] = None
        
        # 统计
        self._frame_count = 0
        self._fps_actual = 0.0
        self._last_fps_time = time.time()
        self._fps_frame_count = 0
    
    def set_capture_callback(self, callback: Callable[[], Optional[np.ndarray]]):
        """设置帧采集回调"""
        self._capture_callback = callback
    
    def set_targets_callback(self, callback: Callable[[], List[DetectionTarget]]):
        """设置目标获取回调"""
        self._targets_callback = callback
    
    def set_status_callback(self, callback: Callable[[], StreamStatus]):
        """设置状态获取回调"""
        self._status_callback = callback
    
    def encode_jpeg(self, frame: np.ndarray) -> Optional[bytes]:
        """
        将帧编码为 JPEG
        
        使用纯 Python 实现简单的 JPEG 编码
        实际部署时应使用 turbojpeg 或 PIL
        """
        try:
            # 尝试使用 PIL
            from PIL import Image
            import io
            
            # BGR to RGB
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                rgb_frame = frame[:, :, ::-1]
            else:
                rgb_frame = frame
            
            img = Image.fromarray(rgb_frame)
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=self.quality)
            return buffer.getvalue()
        except ImportError:
            pass
        
        try:
            # 尝试使用 OpenCV
            import cv2
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
            return jpeg.tobytes()
        except ImportError:
            pass
        
        # 回退：返回简单的 PPM 格式（不是 JPEG，但可用于测试）
        logger.warning("无法编码 JPEG，使用 PPM 格式")
        h, w = frame.shape[:2]
        header = f"P6\n{w} {h}\n255\n".encode()
        if len(frame.shape) == 3:
            rgb = frame[:, :, ::-1]  # BGR to RGB
        else:
            rgb = np.stack([frame] * 3, axis=-1)
        return header + rgb.tobytes()
    
    def _capture_loop(self):
        """采集循环"""
        frame_interval = 1.0 / self.fps
        
        while self._running:
            start_time = time.time()
            
            try:
                # 采集帧
                raw_frame = None
                if self._capture_callback:
                    raw_frame = self._capture_callback()
                
                if raw_frame is not None:
                    # 获取目标和状态
                    targets = None
                    status = None
                    
                    if self._targets_callback:
                        targets = self._targets_callback()
                    
                    if self._status_callback:
                        status = self._status_callback()
                    
                    # 处理帧
                    processed = self.frame_processor.process_frame(
                        raw_frame, targets, status
                    )
                    
                    # 编码
                    jpeg = self.encode_jpeg(processed)
                    
                    if jpeg:
                        with self._frame_lock:
                            self._latest_frame = jpeg
                            self._latest_raw_frame = raw_frame
                        
                        self._frame_count += 1
                        self._fps_frame_count += 1
                
                # 计算实际 FPS
                now = time.time()
                if now - self._last_fps_time >= 1.0:
                    self._fps_actual = self._fps_frame_count / (now - self._last_fps_time)
                    self._fps_frame_count = 0
                    self._last_fps_time = now
                
            except Exception as e:
                logger.error(f"视频采集错误: {e}")
            
            # 控制帧率
            elapsed = time.time() - start_time
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def start(self):
        """启动视频流服务"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info(f"视频流服务已启动，目标帧率: {self.fps} FPS")
    
    def stop(self):
        """停止视频流服务"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("视频流服务已停止")
    
    def get_frame(self) -> Optional[bytes]:
        """获取最新的 JPEG 帧"""
        with self._frame_lock:
            return self._latest_frame
    
    def get_raw_frame(self) -> Optional[np.ndarray]:
        """获取最新的原始帧"""
        with self._frame_lock:
            return self._latest_raw_frame
    
    def generate_mjpeg(self):
        """
        生成 MJPEG 流
        
        Yields:
            MJPEG 帧数据
        """
        frame_interval = 1.0 / self.fps
        
        while self._running:
            frame = self.get_frame()
            
            if frame:
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
                )
            
            time.sleep(frame_interval)
    
    @property
    def actual_fps(self) -> float:
        """获取实际帧率"""
        return self._fps_actual
    
    @property
    def frame_count(self) -> int:
        """获取总帧数"""
        return self._frame_count
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running
