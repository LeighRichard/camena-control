# 系统监控和告警文档

## 概述

系统监控模块提供实时的系统资源监控和智能告警功能，帮助及时发现和处理系统异常。

## 功能特性

### 1. 系统监控 (SystemMonitor)

实时监控以下系统指标：

- **CPU**
  - 使用率 (%)
  - 频率 (MHz)
  - 核心数

- **内存**
  - 使用率 (%)
  - 已用内存 (MB)
  - 可用内存 (MB)
  - 总内存 (MB)

- **温度** (Jetson Nano 特定)
  - CPU 温度 (°C)
  - GPU 温度 (°C)
  - 各热区温度

- **磁盘**
  - 使用率 (%)
  - 已用空间 (GB)
  - 总空间 (GB)

- **网络**
  - 发送流量 (MB)
  - 接收流量 (MB)

- **进程**
  - 进程数量

### 2. 告警管理 (AlertManager)

智能告警系统，支持：

- **多级别告警**
  - INFO - 信息
  - WARNING - 警告
  - ERROR - 错误
  - CRITICAL - 严重

- **多类型告警**
  - SYSTEM - 系统告警
  - HARDWARE - 硬件告警
  - NETWORK - 网络告警
  - APPLICATION - 应用告警

- **多渠道通知**
  - LOG - 日志记录
  - EMAIL - 邮件通知
  - WEBHOOK - Webhook 回调
  - DESKTOP - 桌面通知
  - SMS - 短信通知（待实现）

- **智能特性**
  - 告警去重（防止重复告警）
  - 告警聚合
  - 告警恢复通知
  - 历史记录和统计

## 快速开始

### 1. 基本使用

```python
from monitoring.system_monitor import SystemMonitor, MonitorConfig
from monitoring.alert_manager import AlertManager, AlertType

# 创建告警管理器
alert_manager = AlertManager()

# 创建系统监控器
config = MonitorConfig(
    interval=5.0,           # 监控间隔 5 秒
    cpu_warning=70.0,       # CPU 警告阈值
    cpu_critical=90.0,      # CPU 严重阈值
    memory_warning=75.0,
    memory_critical=90.0,
    temp_warning=70.0,
    temp_critical=85.0
)

monitor = SystemMonitor(config)

# 设置告警回调
def on_alert(rule, metrics):
    alert_manager.send_alert(
        type=AlertType.SYSTEM,
        level=rule.level.value,
        title=rule.name,
        message=f"{rule.metric} 超过阈值",
        source="system_monitor"
    )

monitor.set_alert_callback(on_alert)

# 启动监控
monitor.start()
```

### 2. 配置文件

编辑 `config/monitoring.yaml`：

```yaml
monitoring:
  interval: 5.0
  history_size: 100
  alert_duration: 30.0

cpu:
  warning: 70.0
  critical: 90.0

memory:
  warning: 75.0
  critical: 90.0

temperature:
  warning: 70.0
  critical: 85.0

alerts:
  enabled_channels:
    - log
    - webhook
  
  webhook:
    url: "http://localhost:8080/api/monitoring/webhook"
```

### 3. 运行示例

```bash
cd jetson
python examples/monitoring_example.py
```

## API 参考

### SystemMonitor

#### 初始化

```python
monitor = SystemMonitor(config: MonitorConfig)
```

#### 方法

- `start()` - 启动监控
- `stop()` - 停止监控
- `get_current_metrics()` - 获取当前指标
- `get_history(count=None)` - 获取历史指标
- `add_rule(rule)` - 添加告警规则
- `remove_rule(name)` - 删除告警规则
- `get_rules()` - 获取所有规则
- `add_handler(handler)` - 添加告警处理器
- `set_metrics_callback(callback)` - 设置指标回调
- `set_alert_callback(callback)` - 设置告警回调
- `get_status()` - 获取监控状态

#### 配置参数

```python
@dataclass
class MonitorConfig:
    interval: float = 5.0           # 监控间隔（秒）
    cpu_warning: float = 70.0       # CPU 警告阈值 (%)
    cpu_critical: float = 90.0      # CPU 严重阈值 (%)
    memory_warning: float = 75.0    # 内存警告阈值 (%)
    memory_critical: float = 90.0   # 内存严重阈值 (%)
    temp_warning: float = 70.0      # 温度警告阈值 (°C)
    temp_critical: float = 85.0     # 温度严重阈值 (°C)
    disk_warning: float = 80.0      # 磁盘警告阈值 (%)
    disk_critical: float = 95.0     # 磁盘严重阈值 (%)
    alert_duration: float = 30.0    # 告警持续时间（秒）
    history_size: int = 100         # 历史记录数
```

### AlertManager

#### 初始化

```python
alert_manager = AlertManager(max_history: int = 1000)
```

#### 方法

- `send_alert(type, level, title, message, source, metadata)` - 发送告警
- `resolve_alert(alert_id, message)` - 解决告警
- `get_active_alerts()` - 获取活动告警
- `get_alert_history(count, level)` - 获取告警历史
- `get_alert_by_id(alert_id)` - 根据 ID 获取告警
- `get_statistics()` - 获取告警统计
- `clear_history()` - 清空历史记录
- `configure_channel(channel, config)` - 配置通知渠道
- `enable_channel(channel)` - 启用通知渠道
- `disable_channel(channel)` - 禁用通知渠道
- `set_alert_callback(callback)` - 设置告警回调
- `set_resolve_callback(callback)` - 设置恢复回调

#### 通知渠道配置

**邮件通知**

```python
alert_manager.configure_channel(
    AlertChannel.EMAIL,
    {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'username': 'your-email@gmail.com',
        'password': 'your-app-password',
        'to_addresses': ['admin@example.com']
    }
)
```

**Webhook 通知**

```python
alert_manager.configure_channel(
    AlertChannel.WEBHOOK,
    {
        'url': 'http://localhost:8080/api/monitoring/webhook',
        'method': 'POST',
        'headers': {'Content-Type': 'application/json'}
    }
)
```

## Web API

### 获取当前指标

```http
GET /api/monitoring/metrics
Authorization: Bearer <token>
```

响应：

```json
{
  "timestamp": 1234567890.0,
  "cpu": {
    "percent": 45.2,
    "freq": 1479.0,
    "count": 4
  },
  "memory": {
    "percent": 62.5,
    "used_mb": 2500.0,
    "total_mb": 4000.0,
    "available_mb": 1500.0
  },
  "temperature": {
    "cpu": 55.0,
    "gpu": 52.0,
    "zones": {
      "CPU": 55.0,
      "GPU": 52.0
    }
  },
  "disk": {
    "percent": 45.0,
    "used_gb": 45.0,
    "total_gb": 100.0
  },
  "network": {
    "sent_mb": 123.4,
    "recv_mb": 456.7
  },
  "process_count": 156
}
```

### 获取指标历史

```http
GET /api/monitoring/history?count=10
Authorization: Bearer <token>
```

### 获取监控状态

```http
GET /api/monitoring/status
Authorization: Bearer <token>
```

### 获取告警列表

```http
GET /api/monitoring/alerts?active=true&level=critical
Authorization: Bearer <token>
```

响应：

```json
{
  "count": 2,
  "alerts": [
    {
      "id": "alert_1_1234567890",
      "type": "system",
      "level": "critical",
      "title": "CPU 使用率严重",
      "message": "cpu_percent = 95.2, 阈值 = 90.0",
      "timestamp": 1234567890.0,
      "source": "system_monitor",
      "metadata": {
        "metric": "cpu_percent",
        "value": 95.2,
        "threshold": 90.0
      },
      "resolved": false,
      "resolved_at": null
    }
  ]
}
```

### 解决告警

```http
POST /api/monitoring/alerts/<alert_id>/resolve
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "已手动处理"
}
```

### 获取告警统计

```http
GET /api/monitoring/alerts/statistics
Authorization: Bearer <token>
```

响应：

```json
{
  "total": 150,
  "active": 2,
  "resolved": 148,
  "by_level": {
    "info": 50,
    "warning": 80,
    "error": 15,
    "critical": 5
  },
  "by_type": {
    "system": 120,
    "hardware": 20,
    "network": 10
  }
}
```

### 清空告警历史

```http
POST /api/monitoring/alerts/clear
Authorization: Bearer <token>
```

## 自定义告警规则

### 添加自定义规则

```python
from monitoring.system_monitor import AlertRule, AlertLevel

# 创建自定义规则
custom_rule = AlertRule(
    name="进程数过多",
    metric="process_count",
    threshold=200,
    level=AlertLevel.WARNING,
    duration=60.0  # 持续 60 秒后告警
)

# 添加到监控器
monitor.add_rule(custom_rule)
```

### 自定义告警处理器

```python
from monitoring.system_monitor import AlertHandler

class CustomAlertHandler(AlertHandler):
    def handle(self, rule, metrics):
        # 自定义处理逻辑
        print(f"自定义处理: {rule.name}")
        # 例如：发送到自定义系统

# 添加处理器
monitor.add_handler(CustomAlertHandler())
```

## 最佳实践

### 1. 阈值设置

- **CPU**: 警告 70%, 严重 90%
- **内存**: 警告 75%, 严重 90%
- **温度**: 警告 70°C, 严重 85°C (Jetson Nano)
- **磁盘**: 警告 80%, 严重 95%

### 2. 告警持续时间

设置合理的 `alert_duration` 避免瞬时波动触发告警：

- CPU/内存: 30-60 秒
- 温度: 30 秒
- 磁盘: 0 秒（立即告警）

### 3. 监控间隔

根据需求调整 `interval`：

- 开发/测试: 2-5 秒
- 生产环境: 5-10 秒
- 低功耗模式: 30-60 秒

### 4. 告警去重

默认去重窗口为 300 秒（5 分钟），可在配置文件中调整：

```yaml
alerts:
  dedup_window: 300
```

### 5. 历史记录

合理设置历史记录数量：

- 监控器历史: 100 条（约 8-16 分钟）
- 告警历史: 1000 条

## 故障排查

### 1. 温度读取失败

**问题**: 无法读取 Jetson Nano 温度

**解决**:
```bash
# 检查温度文件是否存在
ls /sys/devices/virtual/thermal/thermal_zone*/temp

# 检查权限
sudo chmod 644 /sys/devices/virtual/thermal/thermal_zone*/temp
```

### 2. 邮件通知失败

**问题**: 邮件发送失败

**解决**:
- 检查 SMTP 服务器配置
- 使用应用专用密码（Gmail）
- 检查防火墙设置

### 3. 告警过多

**问题**: 收到大量重复告警

**解决**:
- 增加 `alert_duration`
- 调整阈值
- 增加 `dedup_window`

## 性能影响

系统监控对性能的影响很小：

- CPU 占用: < 1%
- 内存占用: < 10 MB
- 监控间隔 5 秒时，几乎无感知

## 集成到主程序

监控模块已自动集成到 `main.py`，启动系统时会自动启动监控：

```bash
python main.py
```

查看监控日志：

```
✓ 系统监控已启动
```

## 示例代码

完整示例请参考：

- `examples/monitoring_example.py` - 基本使用示例
- `tests/test_monitoring_properties.py` - 单元测试示例

## 相关文档

- [系统配置文档](../config/system_config.yaml)
- [监控配置文档](../config/monitoring.yaml)
- [Web API 文档](../README.md#web-api)
