"""
OTA 更新模块

提供远程软件和固件更新功能
"""

from .ota_manager import OTAManager, UpdateInfo, UpdateStatus

__all__ = ['OTAManager', 'UpdateInfo', 'UpdateStatus']
