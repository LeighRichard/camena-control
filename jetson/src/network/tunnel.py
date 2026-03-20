"""
Network Tunnel Module for Remote Access

Supports FRP (Fast Reverse Proxy) and ngrok for NAT traversal.
Implements auto-reconnection and health monitoring.
Validates: Requirements 9.2, 9.3, 9.6
"""

import subprocess
import time
import logging
import json
import os
import signal
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
from threading import Thread, Event
import requests


logger = logging.getLogger(__name__)


class TunnelType(Enum):
    """Tunnel service type"""
    FRP = "frp"
    NGROK = "ngrok"


class TunnelStatus(Enum):
    """Tunnel connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class FRPConfig:
    """FRP client configuration"""
    server_addr: str
    server_port: int = 7000
    token: Optional[str] = None
    local_port: int = 5000
    remote_port: int = 0  # 0 means auto-assign
    subdomain: Optional[str] = None
    custom_domains: Optional[str] = None


@dataclass
class NgrokConfig:
    """Ngrok configuration"""
    authtoken: str
    region: str = "us"  # us, eu, ap, au, sa, jp, in
    local_port: int = 5000


@dataclass
class TunnelInfo:
    """Tunnel connection information"""
    status: TunnelStatus
    public_url: Optional[str] = None
    local_port: int = 0
    uptime: float = 0.0
    reconnect_count: int = 0


class NetworkTunnel:
    """Network tunnel manager with auto-reconnection"""
    
    def __init__(self, tunnel_type: TunnelType, config: Dict[str, Any]):
        self.tunnel_type = tunnel_type
        self.config = config
        self.status = TunnelStatus.DISCONNECTED
        self.info = TunnelInfo(status=TunnelStatus.DISCONNECTED)
        
        self._process: Optional[subprocess.Popen] = None
        self._monitor_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._connect_time: Optional[float] = None
        self._status_callback: Optional[Callable[[TunnelStatus], None]] = None
        
        # Auto-reconnect settings
        self.auto_reconnect = True
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_attempts = 0  # 0 means infinite
    
    def set_status_callback(self, callback: Callable[[TunnelStatus], None]):
        """Set callback for status changes"""
        self._status_callback = callback
    
    def _update_status(self, status: TunnelStatus):
        """Update status and notify callback"""
        self.status = status
        self.info.status = status
        
        if self._status_callback:
            try:
                self._status_callback(status)
            except Exception as e:
                logger.error(f"Status callback error: {e}")
    
    def start(self) -> bool:
        """
        Start tunnel connection
        
        Returns:
            True if tunnel started successfully
        """
        try:
            logger.info(f"Starting {self.tunnel_type.value} tunnel...")
            self._update_status(TunnelStatus.CONNECTING)
            
            if self.tunnel_type == TunnelType.FRP:
                success = self._start_frp()
            else:
                success = self._start_ngrok()
            
            if success:
                self._update_status(TunnelStatus.CONNECTED)
                self._connect_time = time.time()
                
                # Start monitoring thread
                self._stop_event.clear()
                self._monitor_thread = Thread(target=self._monitor_connection, daemon=True)
                self._monitor_thread.start()
                
                logger.info(f"Tunnel started: {self.info.public_url}")
                return True
            else:
                self._update_status(TunnelStatus.ERROR)
                return False
                
        except Exception as e:
            logger.error(f"Failed to start tunnel: {e}")
            self._update_status(TunnelStatus.ERROR)
            return False
    
    def _start_frp(self) -> bool:
        """Start FRP client"""
        try:
            frp_config = FRPConfig(**self.config)
            
            # Create FRP config file
            config_path = "/tmp/frpc.ini"
            config_content = f"""[common]
server_addr = {frp_config.server_addr}
server_port = {frp_config.server_port}
"""
            
            if frp_config.token:
                config_content += f"token = {frp_config.token}\n"
            
            config_content += f"""
[web]
type = http
local_port = {frp_config.local_port}
"""
            
            if frp_config.remote_port > 0:
                config_content += f"remote_port = {frp_config.remote_port}\n"
            
            if frp_config.subdomain:
                config_content += f"subdomain = {frp_config.subdomain}\n"
                self.info.public_url = f"http://{frp_config.subdomain}.{frp_config.server_addr}"
            
            if frp_config.custom_domains:
                config_content += f"custom_domains = {frp_config.custom_domains}\n"
                self.info.public_url = f"http://{frp_config.custom_domains}"
            
            # Write config file
            with open(config_path, 'w') as f:
                f.write(config_content)
            
            # Start frpc
            cmd = ["frpc", "-c", config_path]
            
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a bit and check if process is still running
            time.sleep(2)
            
            if self._process.poll() is not None:
                # Process died
                stderr = self._process.stderr.read() if self._process.stderr else ""
                logger.error(f"FRP client failed to start: {stderr}")
                return False
            
            self.info.local_port = frp_config.local_port
            logger.info("FRP client started successfully")
            return True
            
        except Exception as e:
            logger.error(f"FRP start error: {e}")
            return False
    
    def _start_ngrok(self) -> bool:
        """Start ngrok tunnel"""
        try:
            ngrok_config = NgrokConfig(**self.config)
            
            # Configure ngrok authtoken
            subprocess.run(
                ["ngrok", "authtoken", ngrok_config.authtoken],
                capture_output=True,
                timeout=10
            )
            
            # Start ngrok
            cmd = [
                "ngrok", "http",
                str(ngrok_config.local_port),
                "--region", ngrok_config.region,
                "--log", "stdout"
            ]
            
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for ngrok to start and get public URL
            time.sleep(3)
            
            if self._process.poll() is not None:
                stderr = self._process.stderr.read() if self._process.stderr else ""
                logger.error(f"Ngrok failed to start: {stderr}")
                return False
            
            # Get public URL from ngrok API
            try:
                response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("tunnels"):
                        self.info.public_url = data["tunnels"][0]["public_url"]
                        logger.info(f"Ngrok public URL: {self.info.public_url}")
            except Exception as e:
                logger.warning(f"Failed to get ngrok URL: {e}")
            
            self.info.local_port = ngrok_config.local_port
            logger.info("Ngrok started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Ngrok start error: {e}")
            return False
    
    def stop(self):
        """Stop tunnel connection"""
        try:
            logger.info("Stopping tunnel...")
            
            # Stop monitoring
            self._stop_event.set()
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5)
            
            # Kill process
            if self._process:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
                
                self._process = None
            
            self._update_status(TunnelStatus.DISCONNECTED)
            self._connect_time = None
            self.info.public_url = None
            
            logger.info("Tunnel stopped")
            
        except Exception as e:
            logger.error(f"Error stopping tunnel: {e}")
    
    def _monitor_connection(self):
        """Monitor tunnel connection and auto-reconnect if needed"""
        logger.info("Starting tunnel monitor")
        
        while not self._stop_event.is_set():
            try:
                # Check if process is still running
                if self._process and self._process.poll() is not None:
                    logger.warning("Tunnel process died")
                    
                    if self.auto_reconnect:
                        self._reconnect()
                    else:
                        self._update_status(TunnelStatus.ERROR)
                        break
                
                # Update uptime
                if self._connect_time and self.status == TunnelStatus.CONNECTED:
                    self.info.uptime = time.time() - self._connect_time
                
                # Sleep before next check
                self._stop_event.wait(5)
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(5)
        
        logger.info("Tunnel monitor stopped")
    
    def _reconnect(self):
        """Attempt to reconnect"""
        attempt = 0
        
        while not self._stop_event.is_set():
            if self.max_reconnect_attempts > 0 and attempt >= self.max_reconnect_attempts:
                logger.error("Max reconnect attempts reached")
                self._update_status(TunnelStatus.ERROR)
                break
            
            attempt += 1
            self.info.reconnect_count += 1
            
            logger.info(f"Reconnecting... (attempt {attempt})")
            self._update_status(TunnelStatus.RECONNECTING)
            
            # Wait before reconnecting
            self._stop_event.wait(self.reconnect_delay)
            
            if self._stop_event.is_set():
                break
            
            # Try to reconnect
            if self.tunnel_type == TunnelType.FRP:
                success = self._start_frp()
            else:
                success = self._start_ngrok()
            
            if success:
                self._update_status(TunnelStatus.CONNECTED)
                self._connect_time = time.time()
                logger.info("Reconnected successfully")
                break
            else:
                logger.warning(f"Reconnect attempt {attempt} failed")
    
    def get_status(self) -> TunnelInfo:
        """Get current tunnel status"""
        if self._connect_time and self.status == TunnelStatus.CONNECTED:
            self.info.uptime = time.time() - self._connect_time
        return self.info
    
    def is_connected(self) -> bool:
        """Check if tunnel is connected"""
        return self.status == TunnelStatus.CONNECTED
    
    def get_public_url(self) -> Optional[str]:
        """Get public URL"""
        return self.info.public_url


class TunnelManager:
    """Manage multiple tunnel connections"""
    
    def __init__(self):
        self.tunnels: Dict[str, NetworkTunnel] = {}
    
    def add_tunnel(self, name: str, tunnel: NetworkTunnel):
        """Add a tunnel"""
        self.tunnels[name] = tunnel
    
    def start_all(self) -> Dict[str, bool]:
        """Start all tunnels"""
        results = {}
        for name, tunnel in self.tunnels.items():
            results[name] = tunnel.start()
        return results
    
    def stop_all(self):
        """Stop all tunnels"""
        for tunnel in self.tunnels.values():
            tunnel.stop()
    
    def get_status_all(self) -> Dict[str, TunnelInfo]:
        """Get status of all tunnels"""
        return {name: tunnel.get_status() for name, tunnel in self.tunnels.items()}
