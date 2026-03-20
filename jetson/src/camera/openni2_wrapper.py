"""
OpenNI2 Python Wrapper - 使用 ctypes 调用 OpenNI2

参考 SimpleViewer 示例，创建简化的 Python 接口
"""

import os
import ctypes
import numpy as np
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# OpenNI2 常量
ONI_SENSOR_DEPTH = 2
ONI_SENSOR_COLOR = 1
ONI_PIXEL_FORMAT_DEPTH_1_MM = 100
ONI_PIXEL_FORMAT_RGB888 = 200


class OpenNI2Wrapper:
    """
    OpenNI2 简化包装器
    
    直接使用 OpenNI2 C 风格 API（如果可用）
    或通过环境变量找到库
    """
    
    def __init__(self):
        self._lib = None
        self._device = None
        self._depth_stream = None
        self._color_stream = None
        self._initialized = False
    
    def _find_library(self) -> Optional[str]:
        """查找 OpenNI2 库"""
        paths = [
            # 项目中的库
            os.path.expanduser("~/projects/camena-control/Arm64-Release/Arm64-Release/libOpenNI2.so"),
            os.path.expanduser("~/projects/camena-control/SimpleViewer/SimpleViewer/Bin/Arm64-Release/libOpenNI2.so"),
            # 系统安装
            os.path.expanduser("~/OpenNI-Linux-Arm64-2.3/Redist/libOpenNI2.so"),
            "/usr/local/lib/libOpenNI2.so",
            "/usr/lib/libOpenNI2.so",
        ]
        
        for path in paths:
            if os.path.exists(path):
                logger.info(f"找到 OpenNI2 库: {path}")
                return path
        return None
    
    def _find_drivers(self) -> Optional[str]:
        """查找驱动目录"""
        paths = [
            os.path.expanduser("~/projects/camena-control/Arm64-Release/Arm64-Release/OpenNI2/Drivers"),
            os.path.expanduser("~/projects/camena-control/SimpleViewer/SimpleViewer/Bin/Arm64-Release/OpenNI2/Drivers"),
            os.path.expanduser("~/OpenNI-Linux-Arm64-2.3/Redist/OpenNI2/Drivers"),
            "/usr/local/lib/OpenNI2/Drivers",
            "/usr/lib/OpenNI2/Drivers",
        ]
        
        for path in paths:
            if os.path.exists(path):
                logger.info(f"找到驱动目录: {path}")
                return path
        return None
    
    def initialize(self) -> Tuple[bool, str]:
        """初始化 OpenNI2"""
        if self._initialized:
            return True, ""
        
        # 设置环境变量
        lib_path = self._find_library()
        if not lib_path:
            return False, "未找到 libOpenNI2.so"
        
        drivers_path = self._find_drivers()
        if not drivers_path:
            return False, "未找到 OpenNI2 驱动"
        
        # 设置 OPENNI2_REDIST
        redist = os.path.dirname(lib_path)
        os.environ['OPENNI2_REDIST'] = redist
        
        # 更新 LD_LIBRARY_PATH
        lib_dir = os.path.dirname(lib_path)
        current_ld = os.environ.get('LD_LIBRARY_PATH', '')
        if lib_dir not in current_ld:
            os.environ['LD_LIBRARY_PATH'] = f"{lib_dir}:{current_ld}"
        
        logger.info(f"OPENNI2_REDIST: {redist}")
        
        # 加载库
        try:
            self._lib = ctypes.CDLL(lib_path)
            logger.info("✓ OpenNI2 库加载成功")
        except OSError as e:
            return False, f"加载库失败: {e}"
        
        self._initialized = True
        return True, ""
    
    def is_available(self) -> bool:
        """检查 OpenNI2 是否可用"""
        return self._lib is not None
    
    def close(self):
        """关闭"""
        self._lib = None
        self._initialized = False


# 全局实例
_wrapper = None


def get_wrapper() -> Optional[OpenNI2Wrapper]:
    """获取全局 OpenNI2 包装器"""
    global _wrapper
    if _wrapper is None:
        _wrapper = OpenNI2Wrapper()
    return _wrapper
