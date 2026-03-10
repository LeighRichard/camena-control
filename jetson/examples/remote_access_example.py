#!/usr/bin/env python3
"""
Remote Access Example

Demonstrates how to set up and use remote access features:
- 4G connectivity
- Network tunnel (FRP/ngrok)
- Authentication
- Adaptive streaming
"""

import sys
import os
import time
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from network.remote_access_manager import RemoteAccessManager
from web.app import WebServer, WebConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Main function"""
    logger.info("=== Remote Access Example ===")
    
    # Initialize remote access manager
    logger.info("Initializing remote access manager...")
    manager = RemoteAccessManager(config_path="config/remote_access.yaml")
    
    if not manager.initialize():
        logger.error("Failed to initialize remote access")
        return 1
    
    # Start remote access services
    logger.info("Starting remote access services...")
    if not manager.start():
        logger.error("Failed to start remote access services")
        return 1
    
    # Get status
    status = manager.get_status()
    logger.info(f"Remote access status: {status}")
    
    # Get public URL if available
    public_url = manager.get_public_url()
    if public_url:
        logger.info(f"Public URL: {public_url}")
    else:
        logger.info("No public URL available (tunnel not configured or not connected)")
    
    # Create web server with remote access features
    logger.info("Creating web server...")
    web_config = WebConfig(
        host="0.0.0.0",
        port=5000,
        enable_auth=True,
        enable_adaptive_streaming=True
    )
    
    web_server = WebServer(config=web_config)
    
    # Inject remote access components
    if manager.auth_manager:
        web_server.app.auth_manager = manager.auth_manager
    
    if manager.adaptive_streaming:
        web_server.app.adaptive_streaming = manager.adaptive_streaming
    
    # Start web server
    logger.info("Starting web server...")
    web_server.run(threaded=True)
    
    logger.info("=" * 50)
    logger.info("Remote access system is running!")
    logger.info("=" * 50)
    
    if public_url:
        logger.info(f"Access via: {public_url}")
    else:
        logger.info(f"Access via: http://localhost:5000")
    
    logger.info("Default credentials:")
    logger.info("  Admin: admin / admin123")
    logger.info("  Operator: operator / operator123")
    logger.info("  Viewer: viewer / viewer123")
    logger.info("=" * 50)
    logger.info("Press Ctrl+C to stop...")
    
    try:
        # Keep running
        while True:
            time.sleep(10)
            
            # Print status update
            status = manager.get_status()
            
            if status.get("modem"):
                modem_status = status["modem"]
                logger.info(f"4G: {modem_status['status']}, Signal: {modem_status.get('signal_strength', 'N/A')}%")
            
            if status.get("tunnel"):
                tunnel_status = status["tunnel"]
                logger.info(f"Tunnel: {tunnel_status['status']}, URL: {tunnel_status.get('public_url', 'N/A')}")
            
            if status.get("streaming"):
                streaming_status = status["streaming"]
                logger.info(f"Streaming: {streaming_status['quality']}, {streaming_status['resolution']} @ {streaming_status['fps']}fps")
    
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    
    finally:
        # Cleanup
        logger.info("Stopping remote access services...")
        manager.stop()
        web_server.stop()
        logger.info("Shutdown complete")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
