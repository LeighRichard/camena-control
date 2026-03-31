#!/usr/bin/env python3
import os
import sys
import ctypes

# 设置环境变量
os.environ['OPENNI2_REDIST'] = '/home/richard/OpenNI-Linux-Arm64-2.3/Redist'
os.environ['LD_LIBRARY_PATH'] = '/home/richard/OpenNI-Linux-Arm64-2.3/lib:' + os.environ.get('LD_LIBRARY_PATH', '')

# 添加库路径
try:
    import numpy as np
    import cv2
    
    print("测试 OpenNI2 Python 绑定...")
    print(f"OPENNI2_REDIST: {os.environ['OPENNI2_REDIST']}")
    print(f"LD_LIBRARY_PATH: {os.environ['LD_LIBRARY_PATH']}")
    
    # 尝试加载 OpenNI2 库
    lib_path = "/home/richard/OpenNI-Linux-Arm64-2.3/lib/libOpenNI2.so"
    if os.path.exists(lib_path):
        print(f"✓ 找到库文件: {lib_path}")
        # 这里可以添加更多测试代码
    else:
        print(f"✗ 库文件不存在: {lib_path}")
        
except ImportError as e:
    print(f"✗ 导入错误: {e}")
except Exception as e:
    print(f"✗ 错误: {e}")
