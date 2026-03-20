"""
WiFi 热点模式配置模块

实现：
- Jetson Nano WiFi AP 模式配置
- 网络接口管理
- DHCP 服务配置
"""

from typing import Optional, Tuple
from dataclasses import dataclass
import subprocess
import logging
import os

logger = logging.getLogger(__name__)


@dataclass
class HotspotConfig:
    """热点配置"""
    ssid: str = "CameraControl"
    password: str = "camera123"
    channel: int = 6
    interface: str = "wlan0"
    ip_address: str = "192.168.4.1"
    netmask: str = "255.255.255.0"
    dhcp_start: str = "192.168.4.10"
    dhcp_end: str = "192.168.4.100"
    dhcp_lease: str = "12h"


class HotspotManager:
    """WiFi 热点管理器"""
    
    def __init__(self, config: Optional[HotspotConfig] = None):
        self.config = config or HotspotConfig()
        self._is_active = False
    
    def is_supported(self) -> bool:
        """检查系统是否支持热点模式"""
        # 检查是否在 Linux 系统
        if os.name != 'posix':
            return False
        
        # 检查 NetworkManager 或 hostapd
        try:
            result = subprocess.run(
                ['which', 'nmcli'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True
            
            result = subprocess.run(
                ['which', 'hostapd'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def start(self) -> Tuple[bool, str]:
        """
        启动热点
        
        Returns:
            (成功标志, 消息)
        """
        if self._is_active:
            return True, "热点已在运行"
        
        if not self.is_supported():
            return False, "系统不支持热点模式"
        
        # 尝试使用 NetworkManager
        success, msg = self._start_with_nmcli()
        if success:
            self._is_active = True
            return True, msg
        
        # 回退到 hostapd
        success, msg = self._start_with_hostapd()
        if success:
            self._is_active = True
        
        return success, msg
    
    def _start_with_nmcli(self) -> Tuple[bool, str]:
        """使用 NetworkManager 启动热点"""
        try:
            # 删除已存在的连接
            subprocess.run(
                ['nmcli', 'connection', 'delete', self.config.ssid],
                capture_output=True
            )
            
            # 创建热点
            result = subprocess.run([
                'nmcli', 'device', 'wifi', 'hotspot',
                'ifname', self.config.interface,
                'ssid', self.config.ssid,
                'password', self.config.password
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"热点已启动: {self.config.ssid}")
                return True, f"热点 '{self.config.ssid}' 已启动"
            
            return False, f"nmcli 错误: {result.stderr}"
        except FileNotFoundError:
            return False, "nmcli 未安装"
        except Exception as e:
            return False, str(e)
    
    def _start_with_hostapd(self) -> Tuple[bool, str]:
        """使用 hostapd 启动热点"""
        try:
            # 生成 hostapd 配置
            hostapd_conf = f"""
interface={self.config.interface}
driver=nl80211
ssid={self.config.ssid}
hw_mode=g
channel={self.config.channel}
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={self.config.password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""
            
            conf_path = '/tmp/hostapd.conf'
            with open(conf_path, 'w') as f:
                f.write(hostapd_conf)
            
            # 配置网络接口
            subprocess.run([
                'ip', 'addr', 'add',
                f'{self.config.ip_address}/{self.config.netmask}',
                'dev', self.config.interface
            ], capture_output=True)
            
            subprocess.run([
                'ip', 'link', 'set', self.config.interface, 'up'
            ], capture_output=True)
            
            # 启动 hostapd
            result = subprocess.Popen(
                ['hostapd', conf_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 启动 dnsmasq 作为 DHCP 服务器
            self._start_dnsmasq()
            
            logger.info(f"热点已启动 (hostapd): {self.config.ssid}")
            return True, f"热点 '{self.config.ssid}' 已启动"
            
        except FileNotFoundError:
            return False, "hostapd 未安装"
        except Exception as e:
            return False, str(e)
    
    def _start_dnsmasq(self):
        """启动 DHCP 服务"""
        try:
            dnsmasq_conf = f"""
interface={self.config.interface}
dhcp-range={self.config.dhcp_start},{self.config.dhcp_end},{self.config.netmask},{self.config.dhcp_lease}
"""
            conf_path = '/tmp/dnsmasq.conf'
            with open(conf_path, 'w') as f:
                f.write(dnsmasq_conf)
            
            subprocess.Popen(
                ['dnsmasq', '-C', conf_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except Exception as e:
            logger.warning(f"DHCP 服务启动失败: {e}")
    
    def stop(self) -> Tuple[bool, str]:
        """
        停止热点
        
        Returns:
            (成功标志, 消息)
        """
        if not self._is_active:
            return True, "热点未运行"
        
        try:
            # 尝试使用 NetworkManager 停止
            subprocess.run(
                ['nmcli', 'connection', 'down', self.config.ssid],
                capture_output=True
            )
            
            # 停止 hostapd 和 dnsmasq
            subprocess.run(['pkill', 'hostapd'], capture_output=True)
            subprocess.run(['pkill', 'dnsmasq'], capture_output=True)
            
            self._is_active = False
            logger.info("热点已停止")
            return True, "热点已停止"
            
        except Exception as e:
            return False, str(e)
    
    def get_status(self) -> dict:
        """获取热点状态"""
        return {
            "active": self._is_active,
            "ssid": self.config.ssid,
            "interface": self.config.interface,
            "ip_address": self.config.ip_address,
            "supported": self.is_supported()
        }
    
    def get_connected_clients(self) -> list:
        """获取已连接的客户端"""
        clients = []
        
        if not self._is_active:
            return clients
        
        try:
            # 从 ARP 表获取连接的设备
            result = subprocess.run(
                ['arp', '-n'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n')[1:]:
                    parts = line.split()
                    if len(parts) >= 3:
                        ip = parts[0]
                        mac = parts[2]
                        if ip.startswith('192.168.4.'):
                            clients.append({
                                "ip": ip,
                                "mac": mac
                            })
        except Exception as e:
            logger.warning(f"获取客户端列表失败: {e}")
        
        return clients


def setup_hotspot_routes(app, hotspot_manager: HotspotManager):
    """
    设置热点相关的 API 路由
    
    Args:
        app: Flask 应用
        hotspot_manager: 热点管理器实例
    """
    from flask import jsonify, request
    
    @app.route("/api/hotspot/status", methods=["GET"])
    def hotspot_status():
        """获取热点状态"""
        return jsonify(hotspot_manager.get_status())
    
    @app.route("/api/hotspot/start", methods=["POST"])
    def start_hotspot():
        """启动热点"""
        data = request.get_json() or {}
        
        # 更新配置
        if "ssid" in data:
            hotspot_manager.config.ssid = data["ssid"]
        if "password" in data:
            hotspot_manager.config.password = data["password"]
        
        success, msg = hotspot_manager.start()
        if success:
            return jsonify({"status": "started", "message": msg})
        return jsonify({"error": msg}), 500
    
    @app.route("/api/hotspot/stop", methods=["POST"])
    def stop_hotspot():
        """停止热点"""
        success, msg = hotspot_manager.stop()
        if success:
            return jsonify({"status": "stopped", "message": msg})
        return jsonify({"error": msg}), 500
    
    @app.route("/api/hotspot/clients", methods=["GET"])
    def hotspot_clients():
        """获取已连接的客户端"""
        return jsonify({"clients": hotspot_manager.get_connected_clients()})
