# 系统监控快速入门

## 5 分钟快速开始

### 1. 运行示例

```bash
cd jetson
python examples/monitoring_example.py
```

你会看到：
```
系统监控已启动
CPU: 45.2%, 内存: 62.5%, 温度: 55.0°C
```

### 2. 集成到你的代码

```python
from monitoring.system_monitor import SystemMonitor, MonitorConfig
from monitoring.alert_manager import AlertManager, AlertType

# 创建监控器
monitor = SystemMonitor(MonitorConfig(interval=5.0))

# 创建告警管理器
alert_manager = AlertManager()

# 设置告警回调
def on_alert(rule, metrics):
    alert_manager.send_alert(
        type=AlertType.SYSTEM,
        level=rule.level.value,
        title=rule.name,
        message=f"{rule.metric} 超过阈值"
    )

monitor.set_alert_callback(on_alert)
monitor.start()
```

### 3. 通过 Web API 访问

启动主程序后，访问：

```bash
# 获取当前指标
curl http://localhost:8080/api/monitoring/metrics

# 获取告警列表
curl http://localhost:8080/api/monitoring/alerts

# 获取告警统计
curl http://localhost:8080/api/monitoring/alerts/statistics
```

## 常用配置

### 调整阈值

编辑 `config/monitoring.yaml`：

```yaml
cpu:
  warning: 70.0      # CPU 警告阈值
  critical: 90.0     # CPU 严重阈值

memory:
  warning: 75.0
  critical: 90.0

temperature:
  warning: 70.0
  critical: 85.0
```

### 启用邮件通知

```yaml
alerts:
  enabled_channels:
    - log
    - email
  
  email:
    smtp_server: "smtp.gmail.com"
    smtp_port: 587
    username: "your-email@gmail.com"
    password: "your-app-password"
    to_addresses:
      - "admin@example.com"
```

### 启用 Webhook

```yaml
alerts:
  enabled_channels:
    - log
    - webhook
  
  webhook:
    url: "http://your-server.com/webhook"
    method: "POST"
```

## 监控指标说明

| 指标 | 说明 | 单位 | 正常范围 |
|------|------|------|---------|
| cpu_percent | CPU 使用率 | % | 0-100 |
| memory_percent | 内存使用率 | % | 0-100 |
| cpu_temp | CPU 温度 | °C | 30-70 |
| disk_percent | 磁盘使用率 | % | 0-100 |
| process_count | 进程数 | 个 | 50-200 |

## 告警级别

- **INFO** - 信息性消息
- **WARNING** - 警告，需要关注
- **ERROR** - 错误，需要处理
- **CRITICAL** - 严重，立即处理

## 常见问题

### Q: 如何停止监控？

```python
monitor.stop()
```

### Q: 如何查看历史数据？

```python
history = monitor.get_history(count=10)  # 最近 10 条
for metrics in history:
    print(f"CPU: {metrics.cpu_percent}%")
```

### Q: 如何自定义告警规则？

```python
from monitoring.system_monitor import AlertRule, AlertLevel

rule = AlertRule(
    name="自定义规则",
    metric="cpu_percent",
    threshold=80.0,
    level=AlertLevel.WARNING,
    duration=60.0  # 持续 60 秒后告警
)

monitor.add_rule(rule)
```

### Q: 如何解决告警？

```python
# 通过 API
curl -X POST http://localhost:8080/api/monitoring/alerts/<alert_id>/resolve \
  -H "Content-Type: application/json" \
  -d '{"message": "已处理"}'

# 通过代码
alert_manager.resolve_alert(alert_id, "已处理")
```

## 性能影响

- CPU 占用: < 1%
- 内存占用: < 10 MB
- 对系统性能几乎无影响

## 更多信息

详细文档请参考：[MONITORING.md](MONITORING.md)
