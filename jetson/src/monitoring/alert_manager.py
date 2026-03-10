"""
告警管理器 - 多渠道告警通知

功能：
1. 告警记录和历史
2. 多渠道通知（日志、邮件、Webhook、桌面通知）
3. 告警去重和聚合
4. 告警恢复通知
"""

import time
import logging
import threading
import requests
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable
from enum import Enum
from collections import deque
import json

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """告警类型"""
    SYSTEM = "system"           # 系统告警
    HARDWARE = "hardware"       # 硬件告警
    NETWORK = "network"         # 网络告警
    APPLICATION = "application" # 应用告警


class AlertChannel(Enum):
    """告警渠道"""
    LOG = "log"                 # 日志
    EMAIL = "email"             # 邮件
    WEBHOOK = "webhook"         # Webhook
    DESKTOP = "desktop"         # 桌面通知
    SMS = "sms"                 # 短信


@dataclass
class Alert:
    """告警信息"""
    id: str                     # 告警 ID
    type: AlertType             # 告警类型
    level: str                  # 告警级别 (info/warning/error/critical)
    title: str                  # 告警标题
    message: str                # 告警消息
    timestamp: float            # 时间戳
    source: str = "system"      # 告警来源
    metadata: Dict = field(default_factory=dict)  # 元数据
    resolved: bool = False      # 是否已解决
    resolved_at: Optional[float] = None  # 解决时间
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'type': self.type.value,
            'level': self.level,
            'title': self.title,
            'message': self.message,
            'timestamp': self.timestamp,
            'source': self.source,
            'metadata': self.metadata,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at
        }


class AlertManager:
    """
    告警管理器
    
    管理告警的生成、通知、记录和恢复
    """
    
    def __init__(self, max_history: int = 1000):
        self._max_history = max_history
        
        # 告警历史
        self._alerts: deque = deque(maxlen=max_history)
        self._active_alerts: Dict[str, Alert] = {}  # id -> Alert
        
        # 告警计数
        self._alert_counter = 0
        self._lock = threading.Lock()
        
        # 通知渠道配置
        self._channels: Dict[AlertChannel, dict] = {}
        self._enabled_channels: List[AlertChannel] = [AlertChannel.LOG]
        
        # 回调
        self._on_alert_callback: Optional[Callable[[Alert], None]] = None
        self._on_resolve_callback: Optional[Callable[[Alert], None]] = None
        
        # 去重配置
        self._dedup_window = 300  # 去重时间窗口（秒）
        self._recent_alerts: Dict[str, float] = {}  # 指纹 -> 时间戳
    
    def configure_channel(self, channel: AlertChannel, config: dict):
        """
        配置告警渠道
        
        Args:
            channel: 渠道类型
            config: 配置信息
                - EMAIL: {'smtp_server', 'smtp_port', 'username', 'password', 'to_addresses'}
                - WEBHOOK: {'url', 'method', 'headers'}
                - DESKTOP: {'app_name'}
        """
        self._channels[channel] = config
        if channel not in self._enabled_channels:
            self._enabled_channels.append(channel)
        logger.info(f"配置告警渠道: {channel.value}")
    
    def enable_channel(self, channel: AlertChannel):
        """启用告警渠道"""
        if channel not in self._enabled_channels:
            self._enabled_channels.append(channel)
    
    def disable_channel(self, channel: AlertChannel):
        """禁用告警渠道"""
        if channel in self._enabled_channels:
            self._enabled_channels.remove(channel)
    
    def send_alert(
        self,
        type: AlertType,
        level: str,
        title: str,
        message: str,
        source: str = "system",
        metadata: Dict = None
    ) -> Alert:
        """
        发送告警
        
        Args:
            type: 告警类型
            level: 告警级别
            title: 标题
            message: 消息
            source: 来源
            metadata: 元数据
            
        Returns:
            Alert 对象
        """
        # 生成告警指纹（用于去重）
        fingerprint = f"{type.value}:{level}:{title}"
        
        # 检查去重
        current_time = time.time()
        if fingerprint in self._recent_alerts:
            last_time = self._recent_alerts[fingerprint]
            if current_time - last_time < self._dedup_window:
                logger.debug(f"告警去重: {fingerprint}")
                return None
        
        # 更新去重记录
        self._recent_alerts[fingerprint] = current_time
        
        # 清理过期的去重记录
        expired = [k for k, v in self._recent_alerts.items() 
                  if current_time - v > self._dedup_window]
        for k in expired:
            del self._recent_alerts[k]
        
        # 创建告警
        with self._lock:
            self._alert_counter += 1
            alert_id = f"alert_{self._alert_counter}_{int(current_time)}"
        
        alert = Alert(
            id=alert_id,
            type=type,
            level=level,
            title=title,
            message=message,
            timestamp=current_time,
            source=source,
            metadata=metadata or {}
        )
        
        # 保存告警
        with self._lock:
            self._alerts.append(alert)
            self._active_alerts[alert_id] = alert
        
        # 发送通知
        self._notify(alert)
        
        # 回调
        if self._on_alert_callback:
            try:
                self._on_alert_callback(alert)
            except Exception as e:
                logger.error(f"告警回调错误: {e}")
        
        logger.info(f"发送告警: [{level}] {title}")
        return alert
    
    def resolve_alert(self, alert_id: str, message: str = None):
        """
        解决告警
        
        Args:
            alert_id: 告警 ID
            message: 解决消息
        """
        with self._lock:
            if alert_id not in self._active_alerts:
                logger.warning(f"告警不存在: {alert_id}")
                return
            
            alert = self._active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = time.time()
            
            if message:
                alert.metadata['resolve_message'] = message
            
            # 从活动告警中移除
            del self._active_alerts[alert_id]
        
        # 发送恢复通知
        self._notify_resolve(alert)
        
        # 回调
        if self._on_resolve_callback:
            try:
                self._on_resolve_callback(alert)
            except Exception as e:
                logger.error(f"告警恢复回调错误: {e}")
        
        logger.info(f"告警已解决: {alert.title}")
    
    def _notify(self, alert: Alert):
        """发送告警通知"""
        for channel in self._enabled_channels:
            try:
                if channel == AlertChannel.LOG:
                    self._notify_log(alert)
                elif channel == AlertChannel.EMAIL:
                    self._notify_email(alert)
                elif channel == AlertChannel.WEBHOOK:
                    self._notify_webhook(alert)
                elif channel == AlertChannel.DESKTOP:
                    self._notify_desktop(alert)
            except Exception as e:
                logger.error(f"通知失败 [{channel.value}]: {e}")
    
    def _notify_resolve(self, alert: Alert):
        """发送恢复通知"""
        for channel in self._enabled_channels:
            try:
                if channel == AlertChannel.LOG:
                    logger.info(f"[恢复] {alert.title}")
                elif channel == AlertChannel.WEBHOOK:
                    self._notify_webhook_resolve(alert)
            except Exception as e:
                logger.error(f"恢复通知失败 [{channel.value}]: {e}")
    
    def _notify_log(self, alert: Alert):
        """日志通知"""
        msg = f"[{alert.level.upper()}] {alert.title}: {alert.message}"
        
        if alert.level == 'critical':
            logger.critical(msg)
        elif alert.level == 'error':
            logger.error(msg)
        elif alert.level == 'warning':
            logger.warning(msg)
        else:
            logger.info(msg)
    
    def _notify_email(self, alert: Alert):
        """邮件通知"""
        if AlertChannel.EMAIL not in self._channels:
            return
        
        config = self._channels[AlertChannel.EMAIL]
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = config['username']
            msg['To'] = ', '.join(config['to_addresses'])
            msg['Subject'] = f"[{alert.level.upper()}] {alert.title}"
            
            body = f"""
告警信息：

类型: {alert.type.value}
级别: {alert.level}
标题: {alert.title}
消息: {alert.message}
来源: {alert.source}
时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert.timestamp))}

元数据:
{json.dumps(alert.metadata, indent=2, ensure_ascii=False)}
"""
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # 发送邮件
            with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
                server.starttls()
                server.login(config['username'], config['password'])
                server.send_message(msg)
            
            logger.info(f"邮件通知已发送: {alert.title}")
        
        except Exception as e:
            logger.error(f"邮件通知失败: {e}")
    
    def _notify_webhook(self, alert: Alert):
        """Webhook 通知"""
        if AlertChannel.WEBHOOK not in self._channels:
            return
        
        config = self._channels[AlertChannel.WEBHOOK]
        
        try:
            payload = {
                'event': 'alert',
                'alert': alert.to_dict()
            }
            
            response = requests.post(
                config['url'],
                json=payload,
                headers=config.get('headers', {}),
                timeout=10
            )
            response.raise_for_status()
            
            logger.info(f"Webhook 通知已发送: {alert.title}")
        
        except Exception as e:
            logger.error(f"Webhook 通知失败: {e}")
    
    def _notify_webhook_resolve(self, alert: Alert):
        """Webhook 恢复通知"""
        if AlertChannel.WEBHOOK not in self._channels:
            return
        
        config = self._channels[AlertChannel.WEBHOOK]
        
        try:
            payload = {
                'event': 'alert_resolved',
                'alert': alert.to_dict()
            }
            
            response = requests.post(
                config['url'],
                json=payload,
                headers=config.get('headers', {}),
                timeout=10
            )
            response.raise_for_status()
        
        except Exception as e:
            logger.error(f"Webhook 恢复通知失败: {e}")
    
    def _notify_desktop(self, alert: Alert):
        """桌面通知"""
        if AlertChannel.DESKTOP not in self._channels:
            return
        
        try:
            # 尝试使用 notify-send (Linux)
            import subprocess
            subprocess.run([
                'notify-send',
                f"[{alert.level.upper()}] {alert.title}",
                alert.message
            ], check=False)
        
        except Exception as e:
            logger.debug(f"桌面通知失败: {e}")
    
    # ==================== 查询接口 ====================
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活动告警"""
        with self._lock:
            return list(self._active_alerts.values())
    
    def get_alert_history(self, count: int = None, level: str = None) -> List[Alert]:
        """
        获取告警历史
        
        Args:
            count: 返回数量
            level: 过滤级别
            
        Returns:
            告警列表
        """
        with self._lock:
            alerts = list(self._alerts)
        
        # 过滤级别
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        # 限制数量
        if count:
            alerts = alerts[-count:]
        
        return alerts
    
    def get_alert_by_id(self, alert_id: str) -> Optional[Alert]:
        """根据 ID 获取告警"""
        with self._lock:
            return self._active_alerts.get(alert_id)
    
    def get_statistics(self) -> dict:
        """获取告警统计"""
        with self._lock:
            alerts = list(self._alerts)
            active = list(self._active_alerts.values())
        
        # 按级别统计
        level_counts = {}
        for alert in alerts:
            level_counts[alert.level] = level_counts.get(alert.level, 0) + 1
        
        # 按类型统计
        type_counts = {}
        for alert in alerts:
            type_counts[alert.type.value] = type_counts.get(alert.type.value, 0) + 1
        
        return {
            'total': len(alerts),
            'active': len(active),
            'resolved': len(alerts) - len(active),
            'by_level': level_counts,
            'by_type': type_counts
        }
    
    def clear_history(self):
        """清空历史记录"""
        with self._lock:
            self._alerts.clear()
            logger.info("告警历史已清空")
    
    def set_alert_callback(self, callback: Callable[[Alert], None]):
        """设置告警回调"""
        self._on_alert_callback = callback
    
    def set_resolve_callback(self, callback: Callable[[Alert], None]):
        """设置恢复回调"""
        self._on_resolve_callback = callback
