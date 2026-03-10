#!/usr/bin/env python3
"""
系统监控示例

演示如何使用系统监控器和告警管理器
"""

import sys
import time
import logging
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from monitoring.system_monitor import SystemMonitor, MonitorConfig, AlertRule, AlertLevel
from monitoring.alert_manager import AlertManager, AlertType, AlertChannel

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("系统监控示例")
    logger.info("=" * 50)
    
    # 1. 创建告警管理器
    alert_manager = AlertManager(max_history=100)
    
    # 配置 Webhook 通知（可选）
    # alert_manager.configure_channel(
    #     AlertChannel.WEBHOOK,
    #     {
    #         'url': 'http://localhost:8080/api/monitoring/webhook',
    #         'method': 'POST',
    #         'headers': {'Content-Type': 'application/json'}
    #     }
    # )
    
    # 2. 创建系统监控器
    config = MonitorConfig(
        interval=2.0,           # 每 2 秒采集一次
        cpu_warning=50.0,       # CPU 警告阈值降低以便测试
        cpu_critical=70.0,
        memory_warning=60.0,
        memory_critical=80.0,
        temp_warning=60.0,
        temp_critical=75.0,
        alert_duration=5.0      # 持续 5 秒后告警
    )
    
    monitor = SystemMonitor(config)
    
    # 3. 设置回调
    def on_metrics(metrics):
        """指标回调"""
        logger.info(f"CPU: {metrics.cpu_percent:.1f}%, "
                   f"内存: {metrics.memory_percent:.1f}%, "
                   f"温度: {metrics.cpu_temp}°C")
    
    def on_alert(rule, metrics):
        """告警回调"""
        # 发送到告警管理器
        alert_manager.send_alert(
            type=AlertType.SYSTEM,
            level=rule.level.value,
            title=rule.name,
            message=f"{rule.metric} = {getattr(metrics, rule.metric, 'N/A')}, 阈值 = {rule.threshold}",
            source="system_monitor",
            metadata={
                'metric': rule.metric,
                'value': getattr(metrics, rule.metric, None),
                'threshold': rule.threshold
            }
        )
    
    monitor.set_metrics_callback(on_metrics)
    monitor.set_alert_callback(on_alert)
    
    # 4. 启动监控
    monitor.start()
    
    logger.info("监控已启动，按 Ctrl+C 停止")
    logger.info("提示：可以运行一些 CPU 密集型任务来触发告警")
    
    try:
        # 主循环
        while True:
            time.sleep(1)
            
            # 每 10 秒显示一次统计
            if int(time.time()) % 10 == 0:
                logger.info("-" * 50)
                logger.info("告警统计:")
                stats = alert_manager.get_statistics()
                logger.info(f"  总告警数: {stats['total']}")
                logger.info(f"  活动告警: {stats['active']}")
                logger.info(f"  已解决: {stats['resolved']}")
                logger.info(f"  按级别: {stats['by_level']}")
                
                # 显示活动告警
                active_alerts = alert_manager.get_active_alerts()
                if active_alerts:
                    logger.info("  活动告警列表:")
                    for alert in active_alerts:
                        logger.info(f"    - [{alert.level}] {alert.title}")
                
                time.sleep(1)  # 避免重复打印
    
    except KeyboardInterrupt:
        logger.info("\n收到停止信号")
    
    finally:
        # 5. 停止监控
        monitor.stop()
        
        # 显示最终统计
        logger.info("=" * 50)
        logger.info("最终统计:")
        stats = alert_manager.get_statistics()
        logger.info(f"总告警数: {stats['total']}")
        logger.info(f"按级别: {stats['by_level']}")
        logger.info(f"按类型: {stats['by_type']}")
        
        # 显示最近的告警
        recent_alerts = alert_manager.get_alert_history(count=5)
        if recent_alerts:
            logger.info("\n最近 5 条告警:")
            for alert in recent_alerts:
                logger.info(f"  [{alert.level}] {alert.title} - {alert.message}")
        
        logger.info("=" * 50)


if __name__ == "__main__":
    main()
