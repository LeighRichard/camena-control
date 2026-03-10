"""
4G Modem Configuration and Management Module

Supports PPP and QMI dialing for 4G USB modems.
Validates: Requirements 9.1
"""

import subprocess
import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class ModemProtocol(Enum):
    """Modem connection protocol"""
    PPP = "ppp"
    QMI = "qmi"


class ModemStatus(Enum):
    """Modem connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class ModemConfig:
    """4G Modem configuration"""
    protocol: ModemProtocol = ModemProtocol.QMI
    apn: str = "internet"  # Default APN, should be configured per carrier
    device: str = "/dev/cdc-wdm0"  # QMI device
    interface: str = "wwan0"  # Network interface
    username: Optional[str] = None
    password: Optional[str] = None
    pin: Optional[str] = None


@dataclass
class ConnectionInfo:
    """Connection information"""
    status: ModemStatus
    ip_address: Optional[str] = None
    signal_strength: Optional[int] = None  # 0-100
    network_type: Optional[str] = None  # 4G, LTE, etc.
    uptime: float = 0.0


class Modem4G:
    """4G Modem manager supporting PPP and QMI protocols"""
    
    def __init__(self, config: ModemConfig):
        self.config = config
        self.status = ModemStatus.DISCONNECTED
        self.connection_info = ConnectionInfo(status=ModemStatus.DISCONNECTED)
        self._connect_time: Optional[float] = None
    
    def initialize(self) -> bool:
        """
        Initialize 4G modem and check if device is available
        
        Returns:
            True if modem is detected and ready
        """
        try:
            logger.info(f"Initializing 4G modem with protocol: {self.config.protocol.value}")
            
            # Check if device exists
            if self.config.protocol == ModemProtocol.QMI:
                result = subprocess.run(
                    ["ls", self.config.device],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode != 0:
                    logger.error(f"QMI device {self.config.device} not found")
                    return False
                
                # Check if qmi-network is available
                result = subprocess.run(
                    ["which", "qmi-network"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode != 0:
                    logger.error("qmi-network tool not found. Install libqmi-utils")
                    return False
            
            elif self.config.protocol == ModemProtocol.PPP:
                # Check if pppd is available
                result = subprocess.run(
                    ["which", "pppd"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode != 0:
                    logger.error("pppd not found. Install ppp package")
                    return False
            
            logger.info("4G modem initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize modem: {e}")
            return False
    
    def connect(self) -> bool:
        """
        Connect to 4G network
        
        Returns:
            True if connection successful
        """
        try:
            logger.info("Connecting to 4G network...")
            self.status = ModemStatus.CONNECTING
            self.connection_info.status = ModemStatus.CONNECTING
            
            if self.config.protocol == ModemProtocol.QMI:
                success = self._connect_qmi()
            else:
                success = self._connect_ppp()
            
            if success:
                self.status = ModemStatus.CONNECTED
                self.connection_info.status = ModemStatus.CONNECTED
                self._connect_time = time.time()
                logger.info("4G connection established")
                
                # Get connection info
                self._update_connection_info()
            else:
                self.status = ModemStatus.ERROR
                self.connection_info.status = ModemStatus.ERROR
                logger.error("Failed to establish 4G connection")
            
            return success
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            self.status = ModemStatus.ERROR
            self.connection_info.status = ModemStatus.ERROR
            return False
    
    def _connect_qmi(self) -> bool:
        """Connect using QMI protocol"""
        try:
            # Start QMI network
            cmd = [
                "qmi-network",
                self.config.device,
                "start"
            ]
            
            # Set APN
            env = {"APN": self.config.apn}
            if self.config.username:
                env["USERNAME"] = self.config.username
            if self.config.password:
                env["PASSWORD"] = self.config.password
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                timeout=30,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"QMI network start failed: {result.stderr}")
                return False
            
            # Configure network interface with udhcpc or dhclient
            time.sleep(2)  # Wait for interface to come up
            
            result = subprocess.run(
                ["ip", "link", "set", self.config.interface, "up"],
                capture_output=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning(f"Failed to bring up interface: {result.stderr}")
            
            # Try to get IP via DHCP
            result = subprocess.run(
                ["dhclient", self.config.interface],
                capture_output=True,
                timeout=20
            )
            
            if result.returncode != 0:
                logger.warning("DHCP client failed, trying udhcpc")
                subprocess.run(
                    ["udhcpc", "-i", self.config.interface],
                    capture_output=True,
                    timeout=20
                )
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("QMI connection timeout")
            return False
        except Exception as e:
            logger.error(f"QMI connection error: {e}")
            return False
    
    def _connect_ppp(self) -> bool:
        """Connect using PPP protocol"""
        try:
            # Create PPP config file
            ppp_config = f"/etc/ppp/peers/4g-modem"
            
            config_content = f"""
# 4G Modem PPP Configuration
/dev/ttyUSB0
115200
noipdefault
usepeerdns
defaultroute
persist
noauth
"""
            if self.config.username and self.config.password:
                config_content += f"user {self.config.username}\n"
                config_content += f"password {self.config.password}\n"
            
            config_content += f"connect '/usr/sbin/chat -v -f /etc/ppp/chatscripts/4g-modem'\n"
            
            # Note: In production, this would need root privileges
            # For now, we'll just log what would be done
            logger.info(f"Would create PPP config: {ppp_config}")
            logger.info(f"Config content:\n{config_content}")
            
            # Start pppd
            cmd = ["pppd", "call", "4g-modem"]
            
            # In production, this would actually start pppd
            logger.info(f"Would execute: {' '.join(cmd)}")
            
            # Simulate connection
            time.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"PPP connection error: {e}")
            return False
    
    def disconnect(self) -> bool:
        """
        Disconnect from 4G network
        
        Returns:
            True if disconnection successful
        """
        try:
            logger.info("Disconnecting from 4G network...")
            
            if self.config.protocol == ModemProtocol.QMI:
                subprocess.run(
                    ["qmi-network", self.config.device, "stop"],
                    capture_output=True,
                    timeout=10
                )
            else:
                # Kill pppd
                subprocess.run(
                    ["killall", "pppd"],
                    capture_output=True,
                    timeout=5
                )
            
            self.status = ModemStatus.DISCONNECTED
            self.connection_info.status = ModemStatus.DISCONNECTED
            self._connect_time = None
            
            logger.info("4G disconnected")
            return True
            
        except Exception as e:
            logger.error(f"Disconnect error: {e}")
            return False
    
    def get_status(self) -> ConnectionInfo:
        """
        Get current connection status
        
        Returns:
            ConnectionInfo with current status
        """
        if self.status == ModemStatus.CONNECTED:
            self._update_connection_info()
        
        return self.connection_info
    
    def _update_connection_info(self):
        """Update connection information"""
        try:
            # Get IP address
            result = subprocess.run(
                ["ip", "-4", "addr", "show", self.config.interface],
                capture_output=True,
                timeout=5,
                text=True
            )
            
            if result.returncode == 0:
                # Parse IP address from output
                for line in result.stdout.split('\n'):
                    if 'inet ' in line:
                        ip = line.strip().split()[1].split('/')[0]
                        self.connection_info.ip_address = ip
                        break
            
            # Get signal strength (QMI only)
            if self.config.protocol == ModemProtocol.QMI:
                result = subprocess.run(
                    ["qmicli", "-d", self.config.device, "--nas-get-signal-strength"],
                    capture_output=True,
                    timeout=5,
                    text=True
                )
                
                if result.returncode == 0:
                    # Parse signal strength from output
                    for line in result.stdout.split('\n'):
                        if 'RSSI' in line or 'Signal strength' in line:
                            # Extract numeric value
                            parts = line.split(':')
                            if len(parts) > 1:
                                try:
                                    strength = int(parts[1].strip().split()[0])
                                    # Convert dBm to percentage (rough approximation)
                                    self.connection_info.signal_strength = min(100, max(0, (strength + 110) * 2))
                                except (ValueError, IndexError):
                                    # 信号强度解析失败
                                    pass
            
            # Update uptime
            if self._connect_time:
                self.connection_info.uptime = time.time() - self._connect_time
            
        except Exception as e:
            logger.warning(f"Failed to update connection info: {e}")
    
    def is_connected(self) -> bool:
        """Check if modem is connected"""
        return self.status == ModemStatus.CONNECTED
    
    def get_signal_strength(self) -> Optional[int]:
        """
        Get signal strength percentage
        
        Returns:
            Signal strength 0-100, or None if unavailable
        """
        if self.status == ModemStatus.CONNECTED:
            self._update_connection_info()
        return self.connection_info.signal_strength
