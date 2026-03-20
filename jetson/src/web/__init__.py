"""Web 界面模块 - 提供 REST API 和状态监控界面"""

from .app import create_app, WebServer, WebConfig
from .video_stream import (
    VideoStreamService,
    FrameProcessor,
    OverlayConfig,
    DetectionTarget,
    StreamStatus
)
from .hotspot import HotspotManager, HotspotConfig, setup_hotspot_routes

__all__ = [
    "create_app",
    "WebServer", 
    "WebConfig",
    "VideoStreamService",
    "FrameProcessor",
    "OverlayConfig",
    "DetectionTarget",
    "StreamStatus",
    "HotspotManager",
    "HotspotConfig",
    "setup_hotspot_routes"
]
