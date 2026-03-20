"""
系统监控器 - CPU/内存/温度监控

功能：
1. 实时监控系统资源使用情况
2. 温度监控（Jetson Nano 特定）
3. 磁盘空间监控
4. 进程监控
5. 异常告警
"""

import psutil
import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, List, Dict, Any
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"           # 信息
    WARNING = "warning"     # 警告
    ERROR = "error"         # 错误
    CRITICAL = "critical"   # 严重


@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: float
    
    # CPU
    cpu_percent: float              # CPU 使用率 (%)
    cpu_freq: float                 # CPU 频率 (MHz)
    cpu_count: int                  # CPU 核心数
    
    # 内存
    memory_percent: float           # 内存使用率 (%)
    memory_used: float              # 已用内存 (MB)
    memory_total: float             # 总内存 (MB)
    memory_available: float         # 可用内存 (MB)
    
    # 温度
    cpu_temp: Optional[float] = None        # CPU 温度 (°C)
    gpu_temp: Optional[float] = None        # GPU 温度 (°C)
    thermal_zone_temps: Dict[str, float] = field(default_factory=dict)
    
    # 磁盘
    disk_percent: float = 0.0       # 磁盘使用率 (%)
    disk_used: float = 0.0          # 已用磁盘 (GB)
    disk_total: float = 0.0         # 总磁盘 (GB)
    
    # 网络
    network_sent: float = 0.0       # 发送字节数 (MB)
    network_recv: float = 0.0       # 接收字节数 (MB)
    
    # 进程
    process_count: int = 0          # 进程数
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'timestamp': self.timestamp,
            'cpu': {
                'percent': self.cpu_percent,
                'freq': self.cpu_freq,
                'count': self.cpu_count
            },
            'memory': {
                'percent': self.memory_percent,
                'used_mb': self.memory_used,
                'total_mb': self.memory_total,
                'available_mb': self.memory_available
            },
            'temperature': {
                'cpu': self.cpu_temp,
                'gpu': self.gpu_temp,
                'zones': self.thermal_zone_temps
            },
            'disk': {
                'percent': self.disk_percent,
                'used_gb': self.disk_used,
                'total_gb': self.disk_total
            },
            'network': {
                'sent_mb': self.network_sent,
                'recv_mb': self.network_recv
            },
            'process_count': self.process_count
        }


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    metric: str                     # 指标名称
    threshold: float                # 阈值
    level: AlertLevel               # 告警级别
    duration: float = 0.0           # 持续时间（秒），0 表示立即告警
    enabled: bool = True            # 是否启用
    
    # 内部状态
    _trigger_time: Optional[float] = None
    _triggered: bool = False
    
    def check(self, value: float, current_time: float) -> bool:
        """
        检查是否触发告警
        
        Args:
            value: 当前值
            current_time: 当前时间
            
        Returns:
            是否触发告警
        """
        if not self.enabled:
            return False
        
        if value >= self.threshold:
            if self._trigger_time is None:
                self._trigger_time = current_time
            
            # 检查是否超过持续时间
            if current_time - self._trigger_time >= self.duration:
                if not self._triggered:
                    self._triggered = True
                    return True
        else:
            # 恢复正常
            self._trigger_time = None
            self._triggered = False
        
        return False
    
    def reset(self):
        """重置告警状态"""
        self._trigger_time = None
        self._triggered = False


@dataclass
class MonitorConfig:
    """监控配置"""
    # 监控间隔
    interval: float = 5.0           # 监控间隔（秒）
    
    # CPU 告警阈值
    cpu_warning: float = 70.0       # CPU 警告阈值 (%)
    cpu_critical: float = 90.0      # CPU 严重阈值 (%)
    
    # 内存告警阈值
    memory_warning: float = 75.0    # 内存警告阈值 (%)
    memory_critical: float = 90.0   # 内存严重阈值 (%)
    
    # 温度告警阈值
    temp_warning: float = 70.0      # 温度警告阈值 (°C)
    temp_critical: float = 85.0     # 温度严重阈值 (°C)
    
    # 磁盘告警阈值
    disk_warning: float = 80.0      # 磁盘警告阈值 (%)
    disk_critical: float = 95.0     # 磁盘严重阈值 (%)
    
    # 告警持续时间
    alert_duration: float = 30.0    # 告警持续时间（秒）
    
    # 历史记录
    history_size: int = 100         # 保留的历史记录数


def check_memory_usage(
    warning_threshold: float = 75.0,
    critical_threshold: float = 90.0
) -> Dict[str, Any]:
    """
    检查内存使用情况
    
    快速检查当前内存使用率，用于在关键操作前进行资源检查。
    
    Args:
        warning_threshold: 警告阈值 (%)
        critical_threshold: 严重阈值 (%)
        
    Returns:
        包含内存状态的字典:
        - percent: 使用率 (%)
        - used_mb: 已用内存 (MB)
        - available_mb: 可用内存 (MB)
        - total_mb: 总内存 (MB)
        - status: 'ok' | 'warning' | 'critical'
        - message: 状态描述
        
    Example:
        >>> mem = check_memory_usage()
        >>> if mem['status'] == 'critical':
        ...     logger.error(mem['message'])
        ...     # 执行内存清理或降级操作
    """
    mem = psutil.virtual_memory()
    percent = mem.percent
    used_mb = mem.used / (1024 * 1024)
    available_mb = mem.available / (1024 * 1024)
    total_mb = mem.total / (1024 * 1024)
    
    if percent >= critical_threshold:
        status = 'critical'
        message = f"内存使用率严重: {percent:.1f}% (可用: {available_mb:.0f}MB)"
        logger.critical(message)
    elif percent >= warning_threshold:
        status = 'warning'
        message = f"内存使用率警告: {percent:.1f}% (可用: {available_mb:.0f}MB)"
        logger.warning(message)
    else:
        status = 'ok'
        message = f"内存使用正常: {percent:.1f}%"
    
    return {
        'percent': percent,
        'used_mb': used_mb,
        'available_mb': available_mb,
        'total_mb': total_mb,
        'status': status,
        'message': message
    }


def get_process_memory(pid: int = None) -> Dict[str, float]:
    """
    获取进程内存使用情况
    
    Args:
        pid: 进程 ID，None 表示当前进程
        
    Returns:
        包含进程内存信息的字典:
        - rss_mb: 常驻内存 (MB)
        - vms_mb: 虚拟内存 (MB)
        - percent: 内存占用百分比
    """
    try:
        if pid is None:
            process = psutil.Process()
        else:
            process = psutil.Process(pid)
        
        mem_info = process.memory_info()
        mem_percent = process.memory_percent()
        
        return {
            'rss_mb': mem_info.rss / (1024 * 1024),
            'vms_mb': mem_info.vms / (1024 * 1024),
            'percent': mem_percent
        }
    except psutil.NoSuchProcess:
        logger.error(f"进程不存在: {pid}")
        return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0}
    except Exception as e:
        logger.error(f"获取进程内存失败: {e}")
        return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0}


class AlertHandler:
    """告警处理器基类"""
    
    def handle(self, rule: AlertRule, metrics: SystemMetrics):
        """处理告警"""
        raise NotImplementedError


class LogAlertHandler(AlertHandler):
    """日志告警处理器"""
    
    def handle(self, rule: AlertRule, metrics: SystemMetrics):
        """记录告警到日志"""
        msg = f"[{rule.level.value.upper()}] {rule.name}: {rule.metric} = {getattr(metrics, rule.metric, 'N/A')}, 阈值 = {rule.threshold}"
        
        if rule.level == AlertLevel.CRITICAL:
            logger.critical(msg)
        elif rule.level == AlertLevel.ERROR:
            logger.error(msg)
        elif rule.level == AlertLevel.WARNING:
            logger.warning(msg)
        else:
            logger.info(msg)


class SystemMonitor:
    """
    系统监控器
    
    监控 CPU、内存、温度、磁盘等系统资源
    """
    
    def __init__(self, config: MonitorConfig = None):
        self._config = config or MonitorConfig()
        
        # 告警规则
        self._rules: List[AlertRule] = []
        self._init_default_rules()
        
        # 告警处理器
        self._handlers: List[AlertHandler] = [LogAlertHandler()]
        
        # 监控状态
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # 历史数据
        self._history: List[SystemMetrics] = []
        
        # 当前指标
        self._current_metrics: Optional[SystemMetrics] = None
        
        # 回调
        self._on_metrics_callback: Optional[Callable[[SystemMetrics], None]] = None
        self._on_alert_callback: Optional[Callable[[AlertRule, SystemMetrics], None]] = None
        
        # 网络统计基准
        self._net_io_base = psutil.net_io_counters()
    
    def _init_default_rules(self):
        """初始化默认告警规则"""
        self._rules = [
            # CPU 告警
            AlertRule(
                name="CPU 使用率警告",
                metric="cpu_percent",
                threshold=self._config.cpu_warning,
                level=AlertLevel.WARNING,
                duration=self._config.alert_duration
            ),
            AlertRule(
                name="CPU 使用率严重",
                metric="cpu_percent",
                threshold=self._config.cpu_critical,
                level=AlertLevel.CRITICAL,
                duration=self._config.alert_duration
            ),
            
            # 内存告警
            AlertRule(
                name="内存使用率警告",
                metric="memory_percent",
                threshold=self._config.memory_warning,
                level=AlertLevel.WARNING,
                duration=self._config.alert_duration
            ),
            AlertRule(
                name="内存使用率严重",
                metric="memory_percent",
                threshold=self._config.memory_critical,
                level=AlertLevel.CRITICAL,
                duration=self._config.alert_duration
            ),
            
            # 温度告警
            AlertRule(
                name="CPU 温度警告",
                metric="cpu_temp",
                threshold=self._config.temp_warning,
                level=AlertLevel.WARNING,
                duration=self._config.alert_duration
            ),
            AlertRule(
                name="CPU 温度严重",
                metric="cpu_temp",
                threshold=self._config.temp_critical,
                level=AlertLevel.CRITICAL,
                duration=self._config.alert_duration
            ),
            
            # 磁盘告警
            AlertRule(
                name="磁盘使用率警告",
                metric="disk_percent",
                threshold=self._config.disk_warning,
                level=AlertLevel.WARNING,
                duration=0.0  # 磁盘空间立即告警
            ),
            AlertRule(
                name="磁盘使用率严重",
                metric="disk_percent",
                threshold=self._config.disk_critical,
                level=AlertLevel.CRITICAL,
                duration=0.0
            ),
        ]
    
    def start(self):
        """启动监控"""
        if self._running:
            logger.warning("系统监控已在运行")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("系统监控已启动")
    
    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("系统监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                # 采集指标
                metrics = self._collect_metrics()
                
                with self._lock:
                    self._current_metrics = metrics
                    
                    # 保存历史
                    self._history.append(metrics)
                    if len(self._history) > self._config.history_size:
                        self._history.pop(0)
                
                # 检查告警
                self._check_alerts(metrics)
                
                # 回调
                if self._on_metrics_callback:
                    self._on_metrics_callback(metrics)
                
            except Exception as e:
                logger.error(f"监控循环错误: {e}", exc_info=True)
            
            time.sleep(self._config.interval)
    
    def _collect_metrics(self) -> SystemMetrics:
        """采集系统指标"""
        current_time = time.time()
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 0
        cpu_count = psutil.cpu_count()
        
        # 内存
        mem = psutil.virtual_memory()
        memory_percent = mem.percent
        memory_used = mem.used / (1024 * 1024)  # MB
        memory_total = mem.total / (1024 * 1024)
        memory_available = mem.available / (1024 * 1024)
        
        # 温度
        cpu_temp, gpu_temp, thermal_zones = self._read_temperatures()
        
        # 磁盘
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used = disk.used / (1024 * 1024 * 1024)  # GB
        disk_total = disk.total / (1024 * 1024 * 1024)
        
        # 网络
        net_io = psutil.net_io_counters()
        network_sent = (net_io.bytes_sent - self._net_io_base.bytes_sent) / (1024 * 1024)  # MB
        network_recv = (net_io.bytes_recv - self._net_io_base.bytes_recv) / (1024 * 1024)
        
        # 进程
        process_count = len(psutil.pids())
        
        return SystemMetrics(
            timestamp=current_time,
            cpu_percent=cpu_percent,
            cpu_freq=cpu_freq,
            cpu_count=cpu_count,
            memory_percent=memory_percent,
            memory_used=memory_used,
            memory_total=memory_total,
            memory_available=memory_available,
            cpu_temp=cpu_temp,
            gpu_temp=gpu_temp,
            thermal_zone_temps=thermal_zones,
            disk_percent=disk_percent,
            disk_used=disk_used,
            disk_total=disk_total,
            network_sent=network_sent,
            network_recv=network_recv,
            process_count=process_count
        )
    
    def _read_temperatures(self) -> tuple:
        """
        读取温度信息
        
        Returns:
            (cpu_temp, gpu_temp, thermal_zones)
        """
        cpu_temp = None
        gpu_temp = None
        thermal_zones = {}
        
        try:
            # 尝试读取 Jetson Nano 温度
            # Jetson Nano 温度文件位置
            temp_files = {
                'CPU': '/sys/devices/virtual/thermal/thermal_zone0/temp',
                'GPU': '/sys/devices/virtual/thermal/thermal_zone1/temp',
                'AUX': '/sys/devices/virtual/thermal/thermal_zone2/temp',
                'PLL': '/sys/devices/virtual/thermal/thermal_zone3/temp',
            }
            
            for zone_name, temp_file in temp_files.items():
                temp_path = Path(temp_file)
                if temp_path.exists():
                    try:
                        with open(temp_path, 'r') as f:
                            temp = float(f.read().strip()) / 1000.0  # 转换为摄氏度
                            thermal_zones[zone_name] = temp
                            
                            if zone_name == 'CPU':
                                cpu_temp = temp
                            elif zone_name == 'GPU':
                                gpu_temp = temp
                    except Exception as e:
                        logger.debug(f"读取温度失败 {zone_name}: {e}")
            
            # 如果没有读取到，尝试使用 psutil
            if cpu_temp is None:
                temps = psutil.sensors_temperatures()
                if temps:
                    # 尝试找到 CPU 温度
                    for name, entries in temps.items():
                        for entry in entries:
                            if 'cpu' in entry.label.lower() or 'core' in entry.label.lower():
                                cpu_temp = entry.current
                                break
                        if cpu_temp:
                            break
        
        except Exception as e:
            logger.debug(f"读取温度信息失败: {e}")
        
        return cpu_temp, gpu_temp, thermal_zones
    
    def _check_alerts(self, metrics: SystemMetrics):
        """检查告警"""
        current_time = time.time()
        
        for rule in self._rules:
            try:
                # 获取指标值
                value = getattr(metrics, rule.metric, None)
                if value is None:
                    continue
                
                # 检查是否触发
                if rule.check(value, current_time):
                    logger.info(f"触发告警: {rule.name}")
                    
                    # 调用处理器
                    for handler in self._handlers:
                        try:
                            handler.handle(rule, metrics)
                        except Exception as e:
                            logger.error(f"告警处理器错误: {e}")
                    
                    # 回调
                    if self._on_alert_callback:
                        self._on_alert_callback(rule, metrics)
            
            except Exception as e:
                logger.error(f"检查告警规则失败 {rule.name}: {e}")
    
    # ==================== 公共接口 ====================
    
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """获取当前指标"""
        with self._lock:
            return self._current_metrics
    
    def get_history(self, count: int = None) -> List[SystemMetrics]:
        """获取历史指标"""
        with self._lock:
            if count is None:
                return self._history.copy()
            else:
                return self._history[-count:]
    
    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        with self._lock:
            self._rules.append(rule)
    
    def remove_rule(self, name: str):
        """删除告警规则"""
        with self._lock:
            self._rules = [r for r in self._rules if r.name != name]
    
    def get_rules(self) -> List[AlertRule]:
        """获取所有告警规则"""
        with self._lock:
            return self._rules.copy()
    
    def add_handler(self, handler: AlertHandler):
        """添加告警处理器"""
        self._handlers.append(handler)
    
    def set_metrics_callback(self, callback: Callable[[SystemMetrics], None]):
        """设置指标回调"""
        self._on_metrics_callback = callback
    
    def set_alert_callback(self, callback: Callable[[AlertRule, SystemMetrics], None]):
        """设置告警回调"""
        self._on_alert_callback = callback
    
    def get_status(self) -> dict:
        """获取监控状态"""
        with self._lock:
            return {
                'running': self._running,
                'interval': self._config.interval,
                'rules_count': len(self._rules),
                'handlers_count': len(self._handlers),
                'history_size': len(self._history),
                'current_metrics': self._current_metrics.to_dict() if self._current_metrics else None
            }
