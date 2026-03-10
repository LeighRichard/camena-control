"""
卡尔曼滤波器模块 - 用于目标位置预测和平滑
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, List
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class KalmanConfig:
    """卡尔曼滤波器配置"""
    # 过程噪声
    process_noise_pos: float = 1.0      # 位置过程噪声
    process_noise_vel: float = 10.0     # 速度过程噪声
    
    # 测量噪声
    measurement_noise: float = 5.0      # 测量噪声
    
    # 初始不确定性
    initial_uncertainty: float = 100.0


class KalmanFilter:
    """
    卡尔曼滤波器（2D 位置 + 速度）
    
    状态向量: [x, y, vx, vy]
    测量向量: [x, y]
    
    用于：
    - 平滑目标位置
    - 预测目标运动
    - 处理检测丢失
    """
    
    def __init__(self, config: KalmanConfig = None):
        self._config = config or KalmanConfig()
        
        # 状态向量 [x, y, vx, vy]
        self._state = np.zeros(4)
        
        # 状态协方差矩阵
        self._P = np.eye(4) * self._config.initial_uncertainty
        
        # 状态转移矩阵（将在 predict 中根据 dt 更新）
        self._F = np.eye(4)
        
        # 测量矩阵
        self._H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        
        # 过程噪声协方差
        self._Q = np.diag([
            self._config.process_noise_pos,
            self._config.process_noise_pos,
            self._config.process_noise_vel,
            self._config.process_noise_vel
        ])
        
        # 测量噪声协方差
        self._R = np.eye(2) * self._config.measurement_noise
        
        # 时间戳
        self._last_time = 0.0
        self._initialized = False
    
    def initialize(self, x: float, y: float, vx: float = 0, vy: float = 0):
        """
        初始化滤波器状态
        
        Args:
            x, y: 初始位置
            vx, vy: 初始速度
        """
        self._state = np.array([x, y, vx, vy])
        self._P = np.eye(4) * self._config.initial_uncertainty
        self._last_time = time.time()
        self._initialized = True
    
    def predict(self, dt: float = None) -> Tuple[float, float]:
        """
        预测步骤
        
        Args:
            dt: 时间间隔（秒），None 自动计算
            
        Returns:
            预测的 (x, y) 位置
        """
        if not self._initialized:
            return 0.0, 0.0
        
        # 计算时间间隔
        current_time = time.time()
        if dt is None:
            dt = current_time - self._last_time if self._last_time > 0 else 0.1
        self._last_time = current_time
        
        dt = max(0.001, min(1.0, dt))
        
        # 更新状态转移矩阵
        self._F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        
        # 预测状态
        self._state = self._F @ self._state
        
        # 预测协方差
        self._P = self._F @ self._P @ self._F.T + self._Q
        
        return self._state[0], self._state[1]
    
    def update(self, x: float, y: float) -> Tuple[float, float]:
        """
        更新步骤（使用测量值校正）
        
        Args:
            x, y: 测量位置
            
        Returns:
            校正后的 (x, y) 位置
        """
        if not self._initialized:
            self.initialize(x, y)
            return x, y
        
        # 测量向量
        z = np.array([x, y])
        
        # 计算卡尔曼增益
        S = self._H @ self._P @ self._H.T + self._R
        K = self._P @ self._H.T @ np.linalg.inv(S)
        
        # 更新状态
        y_residual = z - self._H @ self._state
        self._state = self._state + K @ y_residual
        
        # 更新协方差
        I = np.eye(4)
        self._P = (I - K @ self._H) @ self._P
        
        return self._state[0], self._state[1]
    
    def get_position(self) -> Tuple[float, float]:
        """获取当前位置估计"""
        return self._state[0], self._state[1]
    
    def get_velocity(self) -> Tuple[float, float]:
        """获取当前速度估计"""
        return self._state[2], self._state[3]
    
    def get_state(self) -> np.ndarray:
        """获取完整状态向量"""
        return self._state.copy()
    
    def predict_position(self, dt: float) -> Tuple[float, float]:
        """
        预测未来位置（不更新内部状态）
        
        Args:
            dt: 预测时间（秒）
            
        Returns:
            预测的 (x, y) 位置
        """
        if not self._initialized:
            return 0.0, 0.0
        
        pred_x = self._state[0] + self._state[2] * dt
        pred_y = self._state[1] + self._state[3] * dt
        
        return pred_x, pred_y
    
    def reset(self):
        """重置滤波器"""
        self._state = np.zeros(4)
        self._P = np.eye(4) * self._config.initial_uncertainty
        self._last_time = 0.0
        self._initialized = False
    
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized
    
    def set_config(self, config: KalmanConfig):
        """设置配置"""
        self._config = config
        self._Q = np.diag([
            config.process_noise_pos,
            config.process_noise_pos,
            config.process_noise_vel,
            config.process_noise_vel
        ])
        self._R = np.eye(2) * config.measurement_noise


class TargetTracker:
    """
    目标跟踪器
    
    结合卡尔曼滤波和目标关联，实现：
    - 多目标跟踪
    - 目标丢失处理
    - 目标重识别
    """
    
    def __init__(self, config: KalmanConfig = None):
        self._config = config or KalmanConfig()
        
        # 当前跟踪的目标
        self._tracked_targets: dict = {}  # id -> KalmanFilter
        self._target_ages: dict = {}      # id -> 帧数
        self._target_hits: dict = {}      # id -> 连续检测次数
        
        # 跟踪参数
        self._max_age = 30                # 最大丢失帧数
        self._min_hits = 3                # 最小确认帧数
        self._iou_threshold = 0.3         # 关联 IoU 阈值
        self._distance_threshold = 100.0  # 关联距离阈值（像素）
        
        # ID 计数器
        self._next_id = 1
    
    def update(self, detections: List[Tuple[float, float, int]]) -> List[Tuple[int, float, float, float, float]]:
        """
        更新跟踪器
        
        Args:
            detections: 检测列表 [(x, y, class_id), ...]
            
        Returns:
            跟踪结果 [(track_id, x, y, vx, vy), ...]
        """
        # 预测所有跟踪目标
        predictions = {}
        for track_id, kf in self._tracked_targets.items():
            pred_x, pred_y = kf.predict()
            predictions[track_id] = (pred_x, pred_y)
        
        # 关联检测和跟踪
        matched, unmatched_dets, unmatched_tracks = self._associate(
            detections, predictions
        )
        
        # 更新匹配的跟踪
        for det_idx, track_id in matched:
            x, y, _ = detections[det_idx]
            self._tracked_targets[track_id].update(x, y)
            self._target_ages[track_id] = 0
            self._target_hits[track_id] = min(
                self._target_hits.get(track_id, 0) + 1,
                self._min_hits + 10
            )
        
        # 处理未匹配的检测（创建新跟踪）
        for det_idx in unmatched_dets:
            x, y, class_id = detections[det_idx]
            track_id = self._next_id
            self._next_id += 1
            
            kf = KalmanFilter(self._config)
            kf.initialize(x, y)
            
            self._tracked_targets[track_id] = kf
            self._target_ages[track_id] = 0
            self._target_hits[track_id] = 1
        
        # 处理未匹配的跟踪（增加年龄）
        for track_id in unmatched_tracks:
            self._target_ages[track_id] = self._target_ages.get(track_id, 0) + 1
        
        # 删除过期跟踪
        tracks_to_remove = [
            track_id for track_id, age in self._target_ages.items()
            if age > self._max_age
        ]
        for track_id in tracks_to_remove:
            del self._tracked_targets[track_id]
            del self._target_ages[track_id]
            if track_id in self._target_hits:
                del self._target_hits[track_id]
        
        # 返回确认的跟踪结果
        results = []
        for track_id, kf in self._tracked_targets.items():
            if self._target_hits.get(track_id, 0) >= self._min_hits:
                x, y = kf.get_position()
                vx, vy = kf.get_velocity()
                results.append((track_id, x, y, vx, vy))
        
        return results
    
    def _associate(
        self,
        detections: List[Tuple[float, float, int]],
        predictions: dict
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        关联检测和预测
        
        使用简单的距离匹配
        """
        if not detections or not predictions:
            unmatched_dets = list(range(len(detections)))
            unmatched_tracks = list(predictions.keys())
            return [], unmatched_dets, unmatched_tracks
        
        # 计算距离矩阵
        det_positions = np.array([(d[0], d[1]) for d in detections])
        track_ids = list(predictions.keys())
        pred_positions = np.array([predictions[tid] for tid in track_ids])
        
        # 计算欧氏距离
        distances = np.zeros((len(detections), len(track_ids)))
        for i, det_pos in enumerate(det_positions):
            for j, pred_pos in enumerate(pred_positions):
                distances[i, j] = np.sqrt(
                    (det_pos[0] - pred_pos[0])**2 + 
                    (det_pos[1] - pred_pos[1])**2
                )
        
        # 贪婪匹配
        matched = []
        matched_dets = set()
        matched_tracks = set()
        
        # 按距离排序
        indices = np.argsort(distances.flatten())
        for idx in indices:
            det_idx = idx // len(track_ids)
            track_idx = idx % len(track_ids)
            
            if det_idx in matched_dets or track_idx in matched_tracks:
                continue
            
            if distances[det_idx, track_idx] < self._distance_threshold:
                matched.append((det_idx, track_ids[track_idx]))
                matched_dets.add(det_idx)
                matched_tracks.add(track_idx)
        
        unmatched_dets = [i for i in range(len(detections)) if i not in matched_dets]
        unmatched_tracks = [track_ids[i] for i in range(len(track_ids)) if i not in matched_tracks]
        
        return matched, unmatched_dets, unmatched_tracks
    
    def get_track(self, track_id: int) -> Optional[KalmanFilter]:
        """获取指定跟踪"""
        return self._tracked_targets.get(track_id)
    
    def get_all_tracks(self) -> dict:
        """获取所有跟踪"""
        return self._tracked_targets.copy()
    
    def get_confirmed_tracks(self) -> List[int]:
        """获取已确认的跟踪 ID"""
        return [
            track_id for track_id, hits in self._target_hits.items()
            if hits >= self._min_hits
        ]
    
    def predict_all(self, dt: float) -> dict:
        """
        预测所有目标的未来位置
        
        Args:
            dt: 预测时间
            
        Returns:
            {track_id: (pred_x, pred_y)}
        """
        predictions = {}
        for track_id, kf in self._tracked_targets.items():
            if self._target_hits.get(track_id, 0) >= self._min_hits:
                predictions[track_id] = kf.predict_position(dt)
        return predictions
    
    def reset(self):
        """重置跟踪器"""
        self._tracked_targets.clear()
        self._target_ages.clear()
        self._target_hits.clear()
        self._next_id = 1
    
    def set_parameters(
        self,
        max_age: int = None,
        min_hits: int = None,
        distance_threshold: float = None
    ):
        """设置跟踪参数"""
        if max_age is not None:
            self._max_age = max_age
        if min_hits is not None:
            self._min_hits = min_hits
        if distance_threshold is not None:
            self._distance_threshold = distance_threshold
