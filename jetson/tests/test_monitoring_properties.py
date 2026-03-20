"""
系统监控模块属性测试

使用 Hypothesis 进行基于属性的测试
"""

import pytest
import time
import sys
from pathlib import Path
from hypothesis import given, strategies as st, settings, assume
from hypothesis import HealthCheck

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from monitoring.system_monitor import (
    SystemMonitor, MonitorConfig, AlertRule, AlertLevel,
    SystemMetrics, AlertHandler
)
from monitoring.alert_manager import (
    AlertManager, Alert, AlertType, AlertChannel
)


# ==================== SystemMonitor 测试 ====================

class TestSystemMonitor:
    """系统监控器测试"""
    
    def test_monitor_initialization(self):
        """测试监控器初始化"""
        config = MonitorConfig()
        monitor = SystemMonitor(config)
        
        assert monitor._config == config
        assert not monitor._running
        assert len(monitor._rules) > 0  # 应该有默认规则
        assert len(monitor._handlers) > 0  # 应该有默认处理器
    
    @given(
        interval=st.floats(min_value=0.1, max_value=10.0),
        cpu_warning=st.floats(min_value=50.0, max_value=80.0),
        cpu_critical=st.floats(min_value=80.0, max_value=100.0)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_monitor_config_properties(self, interval, cpu_warning, cpu_critical):
        """测试监控配置属性"""
        assume(cpu_warning < cpu_critical)
        
        config = MonitorConfig(
            interval=interval,
            cpu_warning=cpu_warning,
            cpu_critical=cpu_critical
        )
        
        assert config.interval == interval
        assert config.cpu_warning == cpu_warning
        assert config.cpu_critical == cpu_critical
        assert config.cpu_warning < config.cpu_critical
    
    def test_monitor_start_stop(self):
        """测试监控启动和停止"""
        config = MonitorConfig(interval=0.5)
        monitor = SystemMonitor(config)
        
        # 启动
        monitor.start()
        assert monitor._running
        assert monitor._thread is not None
        assert monitor._thread.is_alive()
        
        # 等待采集一些数据（增加等待时间）
        time.sleep(2.0)
        
        # 检查是否有指标
        metrics = monitor.get_current_metrics()
        assert metrics is not None
        assert metrics.cpu_percent >= 0
        assert metrics.memory_percent >= 0
        
        # 停止
        monitor.stop()
        assert not monitor._running
    
    def test_metrics_collection(self):
        """测试指标采集"""
        config = MonitorConfig(interval=0.5)
        monitor = SystemMonitor(config)
        
        monitor.start()
        time.sleep(1.5)  # 等待采集几次
        monitor.stop()
        
        # 检查历史记录
        history = monitor.get_history()
        assert len(history) > 0
        
        # 检查指标完整性
        for metrics in history:
            assert isinstance(metrics, SystemMetrics)
            assert metrics.cpu_percent >= 0
            assert metrics.cpu_percent <= 100
            assert metrics.memory_percent >= 0
            assert metrics.memory_percent <= 100
            assert metrics.cpu_count > 0
            assert metrics.memory_total > 0
    
    def test_metrics_callback(self):
        """测试指标回调"""
        config = MonitorConfig(interval=0.5)
        monitor = SystemMonitor(config)
        
        callback_called = []
        
        def on_metrics(metrics):
            callback_called.append(metrics)
        
        monitor.set_metrics_callback(on_metrics)
        monitor.start()
        time.sleep(1.5)
        monitor.stop()
        
        assert len(callback_called) > 0
        assert all(isinstance(m, SystemMetrics) for m in callback_called)
    
    def test_alert_rule_check(self):
        """测试告警规则检查"""
        rule = AlertRule(
            name="测试规则",
            metric="cpu_percent",
            threshold=50.0,
            level=AlertLevel.WARNING,
            duration=0.0  # 立即触发
        )
        
        current_time = time.time()
        
        # 低于阈值
        assert not rule.check(40.0, current_time)
        
        # 超过阈值
        assert rule.check(60.0, current_time)
        
        # 再次检查（已触发，不应重复）
        assert not rule.check(60.0, current_time)
        
        # 恢复正常
        rule.check(40.0, current_time)
        
        # 再次超过阈值
        assert rule.check(60.0, current_time)
    
    def test_alert_rule_duration(self):
        """测试告警持续时间"""
        rule = AlertRule(
            name="测试规则",
            metric="cpu_percent",
            threshold=50.0,
            level=AlertLevel.WARNING,
            duration=1.0  # 持续 1 秒
        )
        
        current_time = time.time()
        
        # 第一次超过阈值
        assert not rule.check(60.0, current_time)
        
        # 0.5 秒后，还未达到持续时间
        assert not rule.check(60.0, current_time + 0.5)
        
        # 1.5 秒后，达到持续时间
        assert rule.check(60.0, current_time + 1.5)
    
    def test_custom_alert_handler(self):
        """测试自定义告警处理器"""
        config = MonitorConfig(interval=0.5)
        monitor = SystemMonitor(config)
        
        handled_alerts = []
        
        class TestHandler(AlertHandler):
            def handle(self, rule, metrics):
                handled_alerts.append((rule, metrics))
        
        monitor.add_handler(TestHandler())
        
        # 添加一个容易触发的规则
        rule = AlertRule(
            name="测试告警",
            metric="cpu_percent",
            threshold=0.0,  # 总是触发
            level=AlertLevel.INFO,
            duration=0.0
        )
        monitor.add_rule(rule)
        
        monitor.start()
        time.sleep(1.5)
        monitor.stop()
        
        # 应该有告警被处理
        assert len(handled_alerts) > 0
    
    @given(
        threshold=st.floats(min_value=0.0, max_value=100.0),
        duration=st.floats(min_value=0.0, max_value=10.0)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_alert_rule_properties(self, threshold, duration):
        """测试告警规则属性"""
        rule = AlertRule(
            name="属性测试",
            metric="cpu_percent",
            threshold=threshold,
            level=AlertLevel.WARNING,
            duration=duration
        )
        
        assert rule.threshold == threshold
        assert rule.duration == duration
        assert rule.enabled
        
        # 重置应该清除状态
        rule._triggered = True
        rule._trigger_time = time.time()
        rule.reset()
        assert not rule._triggered
        assert rule._trigger_time is None


# ==================== AlertManager 测试 ====================

class TestAlertManager:
    """告警管理器测试"""
    
    def test_alert_manager_initialization(self):
        """测试告警管理器初始化"""
        manager = AlertManager(max_history=100)
        
        assert manager._max_history == 100
        assert len(manager._alerts) == 0
        assert len(manager._active_alerts) == 0
        assert AlertChannel.LOG in manager._enabled_channels
    
    def test_send_alert(self):
        """测试发送告警"""
        manager = AlertManager()
        
        alert = manager.send_alert(
            type=AlertType.SYSTEM,
            level="warning",
            title="测试告警",
            message="这是一条测试告警",
            source="test"
        )
        
        assert alert is not None
        assert alert.type == AlertType.SYSTEM
        assert alert.level == "warning"
        assert alert.title == "测试告警"
        assert not alert.resolved
        
        # 检查活动告警
        active = manager.get_active_alerts()
        assert len(active) == 1
        assert active[0].id == alert.id
    
    def test_resolve_alert(self):
        """测试解决告警"""
        manager = AlertManager()
        
        alert = manager.send_alert(
            type=AlertType.SYSTEM,
            level="error",
            title="测试错误",
            message="测试消息",
            source="test"
        )
        
        # 解决告警
        manager.resolve_alert(alert.id, "已修复")
        
        # 检查告警状态
        resolved_alert = manager.get_alert_by_id(alert.id)
        assert resolved_alert is None  # 已从活动告警中移除
        
        # 检查历史记录
        history = manager.get_alert_history()
        assert len(history) == 1
        assert history[0].resolved
        assert history[0].resolved_at is not None
    
    def test_alert_deduplication(self):
        """测试告警去重"""
        manager = AlertManager()
        manager._dedup_window = 2.0  # 2 秒去重窗口
        
        # 发送第一条告警
        alert1 = manager.send_alert(
            type=AlertType.SYSTEM,
            level="warning",
            title="重复告警",
            message="消息1",
            source="test"
        )
        assert alert1 is not None
        
        # 立即发送相同告警（应该被去重）
        alert2 = manager.send_alert(
            type=AlertType.SYSTEM,
            level="warning",
            title="重复告警",
            message="消息2",
            source="test"
        )
        assert alert2 is None
        
        # 等待去重窗口过期
        time.sleep(2.5)
        
        # 再次发送（应该成功）
        alert3 = manager.send_alert(
            type=AlertType.SYSTEM,
            level="warning",
            title="重复告警",
            message="消息3",
            source="test"
        )
        assert alert3 is not None
    
    def test_alert_statistics(self):
        """测试告警统计"""
        manager = AlertManager()
        
        # 发送不同级别的告警
        manager.send_alert(AlertType.SYSTEM, "info", "信息1", "消息", "test")
        manager.send_alert(AlertType.SYSTEM, "warning", "警告1", "消息", "test")
        manager.send_alert(AlertType.SYSTEM, "warning", "警告2", "消息", "test")
        manager.send_alert(AlertType.SYSTEM, "error", "错误1", "消息", "test")
        manager.send_alert(AlertType.HARDWARE, "critical", "严重1", "消息", "test")
        
        stats = manager.get_statistics()
        
        assert stats['total'] == 5
        assert stats['active'] == 5
        assert stats['resolved'] == 0
        assert stats['by_level']['info'] == 1
        assert stats['by_level']['warning'] == 2
        assert stats['by_level']['error'] == 1
        assert stats['by_level']['critical'] == 1
        assert stats['by_type']['system'] == 4
        assert stats['by_type']['hardware'] == 1
    
    def test_alert_history_filter(self):
        """测试告警历史过滤"""
        manager = AlertManager()
        
        # 发送不同级别的告警
        manager.send_alert(AlertType.SYSTEM, "info", "信息", "消息", "test")
        manager.send_alert(AlertType.SYSTEM, "warning", "警告", "消息", "test")
        manager.send_alert(AlertType.SYSTEM, "error", "错误", "消息", "test")
        
        # 过滤 warning 级别
        warnings = manager.get_alert_history(level="warning")
        assert len(warnings) == 1
        assert warnings[0].level == "warning"
        
        # 限制数量
        recent = manager.get_alert_history(count=2)
        assert len(recent) == 2
    
    def test_clear_history(self):
        """测试清空历史"""
        manager = AlertManager()
        
        # 发送一些告警
        for i in range(5):
            manager.send_alert(
                AlertType.SYSTEM,
                "info",
                f"告警{i}",
                "消息",
                "test"
            )
        
        assert len(manager.get_alert_history()) == 5
        
        # 清空历史
        manager.clear_history()
        assert len(manager.get_alert_history()) == 0
    
    def test_alert_callback(self):
        """测试告警回调"""
        manager = AlertManager()
        
        callback_alerts = []
        
        def on_alert(alert):
            callback_alerts.append(alert)
        
        manager.set_alert_callback(on_alert)
        
        # 发送告警
        manager.send_alert(
            AlertType.SYSTEM,
            "warning",
            "测试",
            "消息",
            "test"
        )
        
        assert len(callback_alerts) == 1
        assert callback_alerts[0].title == "测试"
    
    def test_resolve_callback(self):
        """测试解决回调"""
        manager = AlertManager()
        
        resolved_alerts = []
        
        def on_resolve(alert):
            resolved_alerts.append(alert)
        
        manager.set_resolve_callback(on_resolve)
        
        # 发送并解决告警
        alert = manager.send_alert(
            AlertType.SYSTEM,
            "error",
            "测试",
            "消息",
            "test"
        )
        manager.resolve_alert(alert.id)
        
        assert len(resolved_alerts) == 1
        assert resolved_alerts[0].id == alert.id
    
    @given(
        alert_count=st.integers(min_value=1, max_value=20),
        max_history=st.integers(min_value=5, max_value=50)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_alert_history_limit(self, alert_count, max_history):
        """测试告警历史数量限制"""
        assume(alert_count > 0)
        assume(max_history > 0)
        
        manager = AlertManager(max_history=max_history)
        
        # 发送多条告警
        for i in range(alert_count):
            manager.send_alert(
                AlertType.SYSTEM,
                "info",
                f"告警{i}",
                "消息",
                "test"
            )
        
        history = manager.get_alert_history()
        
        # 历史记录不应超过限制
        assert len(history) <= max_history
        
        # 如果发送的告警少于限制，应该全部保留
        if alert_count <= max_history:
            assert len(history) == alert_count


# ==================== 集成测试 ====================

class TestMonitoringIntegration:
    """监控系统集成测试"""
    
    def test_monitor_with_alert_manager(self):
        """测试监控器与告警管理器集成"""
        alert_manager = AlertManager()
        
        config = MonitorConfig(
            interval=0.5,
            cpu_warning=0.0,  # 设置为 0 以便触发
            alert_duration=0.0
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
        time.sleep(1.5)
        monitor.stop()
        
        # 应该有告警产生
        alerts = alert_manager.get_alert_history()
        assert len(alerts) > 0
        
        # 检查告警内容
        for alert in alerts:
            assert alert.type == AlertType.SYSTEM
            assert alert.source == "system_monitor"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
