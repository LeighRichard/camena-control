"""
任务调度器模块 - 自动拍摄任务调度

实现：
- 路径配置解析和序列化
- 自动拍摄流程控制
- 拍摄时序管理（停止→等待稳定→拍摄→确认→运动）
"""

from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any, Tuple
from enum import Enum
import time
import json
import logging
import asyncio

logger = logging.getLogger(__name__)


class TaskState(Enum):
    """任务状态"""
    IDLE = "idle"               # 空闲
    RUNNING = "running"         # 运行中
    PAUSED = "paused"           # 已暂停
    COMPLETED = "completed"     # 已完成
    ERROR = "error"             # 错误
    MOVING = "moving"           # 移动中
    SETTLING = "settling"       # 等待稳定
    CAPTURING = "capturing"     # 拍摄中


class CaptureMode(Enum):
    """拍摄模式"""
    AUTO = "auto"               # 自动模式（按路径顺序）
    MANUAL = "manual"           # 手动模式（用户触发）
    DETECTION = "detection"     # 检测模式（跟随目标）


@dataclass
class PathPoint:
    """路径点"""
    pan: float                  # 水平角度 (度)
    tilt: float                 # 俯仰角度 (度)
    rail: float                 # 滑轨位置 (mm)
    settle_time: float = 0.5    # 振动衰减等待时间 (秒)
    capture_frames: int = 5     # 滚动快门稳定帧数
    label: str = ""             # 点位标签（可选）
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'pan': self.pan,
            'tilt': self.tilt,
            'rail': self.rail,
            'settle_time': self.settle_time,
            'capture_frames': self.capture_frames,
            'label': self.label
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PathPoint':
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def __eq__(self, other):
        if not isinstance(other, PathPoint):
            return False
        return (self.pan == other.pan and 
                self.tilt == other.tilt and 
                self.rail == other.rail)


@dataclass
class PathConfig:
    """路径配置"""
    name: str                           # 配置名称
    points: List[PathPoint]             # 路径点列表
    description: str = ""               # 描述
    loop: bool = False                  # 是否循环执行
    delay_between_points: float = 0.0   # 点位间额外延迟 (秒)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'name': self.name,
            'points': [p.to_dict() for p in self.points],
            'description': self.description,
            'loop': self.loop,
            'delay_between_points': self.delay_between_points
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PathConfig':
        """从字典创建"""
        points = [PathPoint.from_dict(p) for p in data.get('points', [])]
        return cls(
            name=data.get('name', ''),
            points=points,
            description=data.get('description', ''),
            loop=data.get('loop', False),
            delay_between_points=data.get('delay_between_points', 0.0)
        )
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PathConfig':
        """从 JSON 字符串创建"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def validate(self) -> Tuple[bool, str]:
        """验证配置"""
        if not self.name:
            return False, "配置名称不能为空"
        if not self.points:
            return False, "路径点列表不能为空"
        
        for i, point in enumerate(self.points):
            if not -180 <= point.pan <= 180:
                return False, f"点 {i}: pan 角度超出范围 (-180 到 180)"
            if not -90 <= point.tilt <= 90:
                return False, f"点 {i}: tilt 角度超出范围 (-90 到 90)"
            if point.rail < 0:
                return False, f"点 {i}: rail 位置不能为负"
            if point.settle_time < 0:
                return False, f"点 {i}: settle_time 不能为负"
            if point.capture_frames < 1:
                return False, f"点 {i}: capture_frames 至少为 1"
        
        return True, ""


@dataclass
class TaskProgress:
    """任务进度"""
    state: TaskState                    # 当前状态
    current_point: int                  # 当前点位索引
    total_points: int                   # 总点位数
    captured_count: int                 # 已拍摄数量
    error_message: str = ""             # 错误信息
    elapsed_time: float = 0.0           # 已用时间 (秒)
    estimated_remaining: float = 0.0    # 预计剩余时间 (秒)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'state': self.state.value,
            'current_point': self.current_point,
            'total_points': self.total_points,
            'captured_count': self.captured_count,
            'error_message': self.error_message,
            'elapsed_time': self.elapsed_time,
            'estimated_remaining': self.estimated_remaining,
            'progress_percent': self.progress_percent
        }
    
    @property
    def progress_percent(self) -> float:
        """进度百分比"""
        if self.total_points == 0:
            return 0.0
        return (self.captured_count / self.total_points) * 100


@dataclass
class CaptureResult:
    """拍摄结果"""
    success: bool
    point_index: int
    point: PathPoint
    timestamp: float
    image_path: Optional[str] = None
    error_message: str = ""


class TaskScheduler:
    """
    任务调度器
    
    负责：
    - 路径配置管理
    - 自动拍摄流程控制
    - 拍摄时序管理
    """
    
    # 默认超时时间
    MOVE_TIMEOUT = 30.0         # 移动超时 (秒)
    CAPTURE_TIMEOUT = 10.0      # 拍摄超时 (秒)
    
    def __init__(self):
        self._path_config: Optional[PathConfig] = None
        self._state = TaskState.IDLE
        self._current_point = 0
        self._captured_count = 0
        self._error_message = ""
        self._start_time: Optional[float] = None
        self._capture_results: List[CaptureResult] = []
        self._mode = CaptureMode.AUTO
        
        # 回调函数
        self._on_move: Optional[Callable[[PathPoint], Tuple[bool, str]]] = None
        self._on_wait_stable: Optional[Callable[[float], bool]] = None
        self._on_capture: Optional[Callable[[PathPoint, int], Tuple[bool, str, Optional[str]]]] = None
        self._on_progress: Optional[Callable[[TaskProgress], None]] = None
        self._on_complete: Optional[Callable[[List[CaptureResult]], None]] = None
        
        # 控制标志
        self._stop_requested = False
        self._pause_requested = False
    
    def load_path(self, config: PathConfig) -> Tuple[bool, str]:
        """
        加载路径配置
        
        Args:
            config: 路径配置
            
        Returns:
            (成功标志, 错误信息)
        """
        # 验证配置
        valid, error = config.validate()
        if not valid:
            return False, error
        
        self._path_config = config
        self._current_point = 0
        self._captured_count = 0
        self._capture_results = []
        self._state = TaskState.IDLE
        self._error_message = ""
        
        logger.info(f"加载路径配置: {config.name}, {len(config.points)} 个点位")
        return True, ""
    
    def load_path_from_json(self, json_str: str) -> Tuple[bool, str]:
        """从 JSON 字符串加载路径配置"""
        try:
            config = PathConfig.from_json(json_str)
            return self.load_path(config)
        except json.JSONDecodeError as e:
            return False, f"JSON 解析错误: {e}"
        except Exception as e:
            return False, f"加载配置失败: {e}"
    
    def load_path_from_file(self, file_path: str) -> Tuple[bool, str]:
        """从文件加载路径配置"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json_str = f.read()
            return self.load_path_from_json(json_str)
        except FileNotFoundError:
            return False, f"文件不存在: {file_path}"
        except Exception as e:
            return False, f"读取文件失败: {e}"
    
    def save_path_to_file(self, file_path: str) -> Tuple[bool, str]:
        """保存路径配置到文件"""
        if self._path_config is None:
            return False, "未加载路径配置"
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self._path_config.to_json())
            return True, ""
        except Exception as e:
            return False, f"保存文件失败: {e}"
    
    def start(self) -> Tuple[bool, str]:
        """开始自动拍摄"""
        if self._path_config is None:
            return False, "未加载路径配置"
        
        if self._state == TaskState.RUNNING:
            return False, "任务已在运行"
        
        self._state = TaskState.RUNNING
        self._current_point = 0
        self._captured_count = 0
        self._capture_results = []
        self._start_time = time.time()
        self._stop_requested = False
        self._pause_requested = False
        self._error_message = ""
        
        logger.info(f"开始自动拍摄: {self._path_config.name}")
        self._notify_progress()
        return True, ""
    
    def pause(self) -> Tuple[bool, str]:
        """暂停任务"""
        if self._state not in [TaskState.RUNNING, TaskState.MOVING, 
                               TaskState.SETTLING, TaskState.CAPTURING]:
            return False, "任务未在运行"
        
        self._pause_requested = True
        self._state = TaskState.PAUSED
        logger.info("任务已暂停")
        self._notify_progress()
        return True, ""
    
    def resume(self) -> Tuple[bool, str]:
        """恢复任务"""
        if self._state != TaskState.PAUSED:
            return False, "任务未暂停"
        
        self._pause_requested = False
        self._state = TaskState.RUNNING
        logger.info("任务已恢复")
        self._notify_progress()
        return True, ""
    
    def stop(self) -> Tuple[bool, str]:
        """停止任务"""
        self._stop_requested = True
        self._state = TaskState.IDLE
        logger.info("任务已停止")
        self._notify_progress()
        return True, ""
    
    def get_progress(self) -> TaskProgress:
        """获取任务进度"""
        total = len(self._path_config.points) if self._path_config else 0
        
        elapsed = 0.0
        estimated_remaining = 0.0
        
        if self._start_time is not None:
            elapsed = time.time() - self._start_time
            
            # 估算剩余时间
            if self._captured_count > 0:
                avg_time_per_point = elapsed / self._captured_count
                remaining_points = total - self._captured_count
                estimated_remaining = avg_time_per_point * remaining_points
        
        return TaskProgress(
            state=self._state,
            current_point=self._current_point,
            total_points=total,
            captured_count=self._captured_count,
            error_message=self._error_message,
            elapsed_time=elapsed,
            estimated_remaining=estimated_remaining
        )
    
    def get_capture_results(self) -> List[CaptureResult]:
        """获取拍摄结果列表"""
        return self._capture_results.copy()
    
    def get_current_point(self) -> Optional[PathPoint]:
        """获取当前点位"""
        if self._path_config is None:
            return None
        if self._current_point >= len(self._path_config.points):
            return None
        return self._path_config.points[self._current_point]
    
    def set_mode(self, mode: CaptureMode):
        """设置拍摄模式"""
        self._mode = mode
    
    def get_mode(self) -> CaptureMode:
        """获取拍摄模式"""
        return self._mode
    
    def set_callbacks(
        self,
        on_move: Optional[Callable[[PathPoint], Tuple[bool, str]]] = None,
        on_wait_stable: Optional[Callable[[float], bool]] = None,
        on_capture: Optional[Callable[[PathPoint, int], Tuple[bool, str, Optional[str]]]] = None,
        on_progress: Optional[Callable[[TaskProgress], None]] = None,
        on_complete: Optional[Callable[[List[CaptureResult]], None]] = None
    ):
        """
        设置回调函数
        
        Args:
            on_move: 移动回调 (point) -> (success, error)
            on_wait_stable: 等待稳定回调 (settle_time) -> is_stable
            on_capture: 拍摄回调 (point, frames) -> (success, error, image_path)
            on_progress: 进度回调 (progress)
            on_complete: 完成回调 (results)
        """
        if on_move is not None:
            self._on_move = on_move
        if on_wait_stable is not None:
            self._on_wait_stable = on_wait_stable
        if on_capture is not None:
            self._on_capture = on_capture
        if on_progress is not None:
            self._on_progress = on_progress
        if on_complete is not None:
            self._on_complete = on_complete
    
    def _notify_progress(self):
        """通知进度更新"""
        if self._on_progress is not None:
            try:
                self._on_progress(self.get_progress())
            except Exception as e:
                logger.error(f"进度回调错误: {e}")
    
    async def execute_step(self) -> Tuple[bool, str]:
        """
        执行一步（移动 + 等待稳定 + 拍摄）
        
        Returns:
            (成功标志, 错误信息)
        """
        if self._path_config is None:
            return False, "未加载路径配置"
        
        if self._current_point >= len(self._path_config.points):
            return False, "已完成所有点位"
        
        point = self._path_config.points[self._current_point]
        
        # 1. 移动到目标位置
        self._state = TaskState.MOVING
        self._notify_progress()
        
        if self._on_move is not None:
            try:
                success, error = self._on_move(point)
                if not success:
                    self._error_message = f"移动失败: {error}"
                    self._state = TaskState.ERROR
                    return False, self._error_message
            except Exception as e:
                self._error_message = f"移动异常: {e}"
                self._state = TaskState.ERROR
                return False, self._error_message
        
        # 检查停止/暂停请求
        if self._stop_requested:
            return False, "任务已停止"
        if self._pause_requested:
            return False, "任务已暂停"
        
        # 2. 等待振动衰减
        self._state = TaskState.SETTLING
        self._notify_progress()
        
        if self._on_wait_stable is not None:
            try:
                is_stable = self._on_wait_stable(point.settle_time)
                if not is_stable:
                    logger.warning(f"点 {self._current_point}: 稳定等待超时")
            except Exception as e:
                logger.warning(f"等待稳定异常: {e}")
        else:
            # 默认等待
            await asyncio.sleep(point.settle_time)
        
        # 检查停止/暂停请求
        if self._stop_requested:
            return False, "任务已停止"
        if self._pause_requested:
            return False, "任务已暂停"
        
        # 3. 拍摄
        self._state = TaskState.CAPTURING
        self._notify_progress()
        
        image_path = None
        if self._on_capture is not None:
            try:
                success, error, image_path = self._on_capture(point, point.capture_frames)
                if not success:
                    self._error_message = f"拍摄失败: {error}"
                    # 记录失败结果
                    self._capture_results.append(CaptureResult(
                        success=False,
                        point_index=self._current_point,
                        point=point,
                        timestamp=time.time(),
                        error_message=error
                    ))
                    # 继续下一个点位，不中断任务
                    logger.warning(f"点 {self._current_point} 拍摄失败: {error}")
            except Exception as e:
                logger.error(f"拍摄异常: {e}")
                self._capture_results.append(CaptureResult(
                    success=False,
                    point_index=self._current_point,
                    point=point,
                    timestamp=time.time(),
                    error_message=str(e)
                ))
        
        # 记录成功结果
        if image_path is not None or self._on_capture is None:
            self._capture_results.append(CaptureResult(
                success=True,
                point_index=self._current_point,
                point=point,
                timestamp=time.time(),
                image_path=image_path
            ))
            self._captured_count += 1
        
        # 4. 移动到下一个点位
        self._current_point += 1
        
        # 点位间延迟
        if self._path_config.delay_between_points > 0:
            await asyncio.sleep(self._path_config.delay_between_points)
        
        self._state = TaskState.RUNNING
        self._notify_progress()
        
        return True, ""
    
    async def run(self) -> Tuple[bool, str]:
        """
        运行完整的自动拍摄流程
        
        Returns:
            (成功标志, 错误信息)
        """
        if self._path_config is None:
            return False, "未加载路径配置"
        
        # 开始任务
        success, error = self.start()
        if not success:
            return False, error
        
        # 执行所有点位
        while self._current_point < len(self._path_config.points):
            # 检查停止请求
            if self._stop_requested:
                return False, "任务已停止"
            
            # 检查暂停请求
            while self._pause_requested:
                await asyncio.sleep(0.1)
                if self._stop_requested:
                    return False, "任务已停止"
            
            # 执行一步
            success, error = await self.execute_step()
            if not success and self._state == TaskState.ERROR:
                return False, error
        
        # 检查是否循环
        if self._path_config.loop and not self._stop_requested:
            self._current_point = 0
            return await self.run()
        
        # 完成
        self._state = TaskState.COMPLETED
        self._notify_progress()
        
        # 调用完成回调
        if self._on_complete is not None:
            try:
                self._on_complete(self._capture_results)
            except Exception as e:
                logger.error(f"完成回调错误: {e}")
        
        logger.info(f"自动拍摄完成: 成功 {self._captured_count}/{len(self._path_config.points)}")
        return True, ""
    
    def execute_step_sync(self) -> Tuple[bool, str]:
        """
        同步执行一步（用于非异步环境）
        
        Returns:
            (成功标志, 错误信息)
        """
        import asyncio
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.execute_step())
