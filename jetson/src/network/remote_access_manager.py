"""
Remote Access Manager

Integrates 4G modem, tunnel, authentication, and adaptive streaming.
Validates: Requirements 9.1, 9.2, 9.3, 9.5, 9.6, 9.7
"""

import logging
import yaml
import time
from typing import Optional, Dict, Any
from pathlib import Path

from network.modem_4g import Modem4G, ModemConfig, ModemProtocol
from network.tunnel import NetworkTunnel, TunnelType, TunnelStatus
from network.auth import AuthManager, UserRole
from network.adaptive_streaming import AdaptiveStreaming, VideoQuality


logger = logging.getLogger(__name__)


class RemoteAccessManager:
    """Manage all remote access components"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize remote access manager
        
        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        
        # Components
        self.modem: Optional[Modem4G] = None
        self.tunnel: Optional[NetworkTunnel] = None
        self.auth_manager: Optional[AuthManager] = None
        self.adaptive_streaming: Optional[AdaptiveStreaming] = None
        
        self._initialized = False
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not config_path:
            config_path = "config/remote_access.yaml"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return self._default_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "modem": {"enabled": False},
            "tunnel": {"enabled": False},
            "auth": {"enabled": True},
            "streaming": {"enabled": True, "initial_quality": "medium"}
        }
    
    def initialize(self) -> bool:
        """
        Initialize all components
        
        Returns:
            True if initialization successful
        """
        try:
            logger.info("Initializing remote access components...")
            
            # Initialize 4G modem
            if self.config.get("modem", {}).get("enabled", False):
                self._init_modem()
            
            # Initialize tunnel
            if self.config.get("tunnel", {}).get("enabled", False):
                self._init_tunnel()
            
            # Initialize authentication
            if self.config.get("auth", {}).get("enabled", True):
                self._init_auth()
            
            # Initialize adaptive streaming
            if self.config.get("streaming", {}).get("enabled", True):
                self._init_streaming()
            
            self._initialized = True
            logger.info("Remote access initialization complete")
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    def _init_modem(self):
        """Initialize 4G modem"""
        try:
            modem_config = self.config["modem"]
            
            protocol = ModemProtocol(modem_config.get("protocol", "qmi"))
            
            config = ModemConfig(
                protocol=protocol,
                apn=modem_config.get("apn", "internet"),
                device=modem_config.get("device", "/dev/cdc-wdm0"),
                interface=modem_config.get("interface", "wwan0"),
                username=modem_config.get("username"),
                password=modem_config.get("password"),
                pin=modem_config.get("pin")
            )
            
            self.modem = Modem4G(config)
            
            if self.modem.initialize():
                logger.info("4G modem initialized")
            else:
                logger.warning("4G modem initialization failed")
                self.modem = None
                
        except Exception as e:
            logger.error(f"Modem initialization error: {e}")
            self.modem = None
    
    def _init_tunnel(self):
        """Initialize network tunnel"""
        try:
            tunnel_config = self.config["tunnel"]
            
            tunnel_type = TunnelType(tunnel_config.get("type", "frp"))
            
            if tunnel_type == TunnelType.FRP:
                config = tunnel_config.get("frp", {})
            else:
                config = tunnel_config.get("ngrok", {})
            
            self.tunnel = NetworkTunnel(tunnel_type, config)
            
            # Set up auto-reconnect
            self.tunnel.auto_reconnect = tunnel_config.get("auto_reconnect", True)
            self.tunnel.reconnect_delay = tunnel_config.get("reconnect_delay", 5)
            self.tunnel.max_reconnect_attempts = tunnel_config.get("max_reconnect_attempts", 0)
            
            # Set status callback
            self.tunnel.set_status_callback(self._on_tunnel_status_change)
            
            logger.info(f"Tunnel initialized: {tunnel_type.value}")
            
        except Exception as e:
            logger.error(f"Tunnel initialization error: {e}")
            self.tunnel = None
    
    def _init_auth(self):
        """Initialize authentication"""
        try:
            auth_config = self.config.get("auth", {})
            
            secret_key = auth_config.get("secret_key")
            token_expiry = auth_config.get("token_expiry_hours", 24)
            
            self.auth_manager = AuthManager(
                secret_key=secret_key,
                token_expiry_hours=token_expiry
            )
            
            # Create additional users from config
            users = auth_config.get("users", [])
            for user_config in users:
                username = user_config.get("username")
                password = user_config.get("password")
                role_str = user_config.get("role", "viewer")
                
                if username and username != "admin":  # Skip admin (already created)
                    try:
                        role = UserRole(role_str)
                        self.auth_manager.create_user(username, password, role)
                    except ValueError:
                        logger.warning(f"Invalid role for user {username}: {role_str}")
            
            logger.info("Authentication initialized")
            
        except Exception as e:
            logger.error(f"Auth initialization error: {e}")
            self.auth_manager = None
    
    def _init_streaming(self):
        """Initialize adaptive streaming"""
        try:
            streaming_config = self.config.get("streaming", {})
            
            initial_quality_str = streaming_config.get("initial_quality", "medium")
            initial_quality = VideoQuality(initial_quality_str)
            
            self.adaptive_streaming = AdaptiveStreaming(initial_quality=initial_quality)
            
            # Configure adaptation parameters
            self.adaptive_streaming.adaptation_interval = streaming_config.get(
                "adaptation_interval", 5.0
            )
            self.adaptive_streaming.bandwidth_safety_margin = streaming_config.get(
                "bandwidth_safety_margin", 0.8
            )
            
            logger.info("Adaptive streaming initialized")
            
        except Exception as e:
            logger.error(f"Streaming initialization error: {e}")
            self.adaptive_streaming = None
    
    def _on_tunnel_status_change(self, status: TunnelStatus):
        """Callback for tunnel status changes"""
        logger.info(f"Tunnel status changed: {status.value}")
    
    def start(self) -> bool:
        """
        Start all remote access services
        
        Returns:
            True if all enabled services started successfully
        """
        if not self._initialized:
            logger.error("Not initialized, call initialize() first")
            return False
        
        try:
            logger.info("Starting remote access services...")
            
            # Connect 4G modem
            if self.modem:
                if not self.modem.connect():
                    logger.warning("4G connection failed")
                else:
                    logger.info("4G connected")
                    # Wait a bit for connection to stabilize
                    time.sleep(3)
            
            # Start tunnel
            if self.tunnel:
                if not self.tunnel.start():
                    logger.warning("Tunnel start failed")
                else:
                    logger.info(f"Tunnel started: {self.tunnel.get_public_url()}")
            
            # Start adaptive streaming monitoring
            if self.adaptive_streaming:
                self.adaptive_streaming.start_monitoring()
                logger.info("Adaptive streaming monitoring started")
            
            logger.info("Remote access services started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start services: {e}")
            return False
    
    def stop(self):
        """Stop all remote access services"""
        try:
            logger.info("Stopping remote access services...")
            
            # Stop adaptive streaming
            if self.adaptive_streaming:
                self.adaptive_streaming.stop_monitoring()
            
            # Stop tunnel
            if self.tunnel:
                self.tunnel.stop()
            
            # Disconnect modem
            if self.modem:
                self.modem.disconnect()
            
            logger.info("Remote access services stopped")
            
        except Exception as e:
            logger.error(f"Error stopping services: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all components
        
        Returns:
            Status dictionary
        """
        status = {
            "initialized": self._initialized,
            "modem": None,
            "tunnel": None,
            "auth": None,
            "streaming": None
        }
        
        if self.modem:
            conn_info = self.modem.get_status()
            status["modem"] = {
                "status": conn_info.status.value,
                "ip_address": conn_info.ip_address,
                "signal_strength": conn_info.signal_strength,
                "uptime": conn_info.uptime
            }
        
        if self.tunnel:
            tunnel_info = self.tunnel.get_status()
            status["tunnel"] = {
                "status": tunnel_info.status.value,
                "public_url": tunnel_info.public_url,
                "uptime": tunnel_info.uptime,
                "reconnect_count": tunnel_info.reconnect_count
            }
        
        if self.auth_manager:
            status["auth"] = {
                "enabled": True,
                "active_sessions": len(self.auth_manager.get_active_sessions()),
                "total_users": len(self.auth_manager.list_users())
            }
        
        if self.adaptive_streaming:
            stats = self.adaptive_streaming.get_stats()
            profile = self.adaptive_streaming.get_current_profile()
            status["streaming"] = {
                "quality": profile.name.value,
                "resolution": f"{profile.width}x{profile.height}",
                "fps": profile.fps,
                "frames_sent": stats.frames_sent,
                "average_bitrate": stats.average_bitrate,
                "quality_changes": stats.quality_changes
            }
        
        return status
    
    def get_public_url(self) -> Optional[str]:
        """Get public access URL"""
        if self.tunnel:
            return self.tunnel.get_public_url()
        return None
