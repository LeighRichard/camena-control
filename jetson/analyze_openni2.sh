#!/bin/bash

echo "=========================================="
echo "OpenNI2 文件夹分析脚本"
echo "=========================================="
echo ""

# 查找 OpenNI2 文件夹
echo "1. 查找 OpenNI-Linux-Arm64-2.3 文件夹..."
OPENNI_DIR=$(find ~ -name "OpenNI-Linux-Arm64-2.3" -type d 2>/dev/null | head -1)

if [ -z "$OPENNI_DIR" ]; then
    echo "✗ 未找到 OpenNI-Linux-Arm64-2.3 文件夹"
    echo ""
    echo "请提供文件夹路径:"
    echo "  例如: /home/richard/OpenNI-Linux-Arm64-2.3"
    echo ""
    read -p "输入路径: " OPENNI_DIR
fi

if [ ! -d "$OPENNI_DIR" ]; then
    echo "✗ 文件夹不存在: $OPENNI_DIR"
    exit 1
fi

echo "✓ 找到文件夹: $OPENNI_DIR"

# 分析文件夹结构
echo ""
echo "=========================================="
echo "2. 文件夹结构"
echo "=========================================="
echo "目录内容:"
ls -la "$OPENNI_DIR"

# 查找可执行文件
echo ""
echo "=========================================="
echo "3. 可执行文件"
echo "=========================================="
echo "查找可执行文件..."
find "$OPENNI_DIR" -type f -executable | while read file; do
    echo "  $file"
done

# 查找 NiViewer
echo ""
echo "=========================================="
echo "4. NiViewer 程序"
echo "=========================================="
NIVIEWER=$(find "$OPENNI_DIR" -name "NiViewer" -o -name "NiViewer2" | head -1)
if [ -n "$NIVIEWER" ]; then
    echo "✓ 找到 NiViewer: $NIVIEWER"
    ls -la "$NIVIEWER"
    file "$NIVIEWER"
else
    echo "✗ 未找到 NiViewer"
fi

# 查找库文件
echo ""
echo "=========================================="
echo "5. 库文件"
echo "=========================================="
echo "查找 .so 库文件..."
find "$OPENNI_DIR" -name "*.so*" | while read lib; do
    echo "  $lib"
done

# 查找驱动
echo ""
echo "=========================================="
echo "6. OpenNI2 驱动"
echo "=========================================="
DRIVERS_DIR=$(find "$OPENNI_DIR" -name "Drivers" -type d | head -1)
if [ -n "$DRIVERS_DIR" ]; then
    echo "✓ 找到驱动目录: $DRIVERS_DIR"
    echo "驱动文件:"
    ls -la "$DRIVERS_DIR"
else
    echo "✗ 未找到驱动目录"
fi

# 查找配置文件
echo ""
echo "=========================================="
echo "7. 配置文件"
echo "=========================================="
echo "查找配置文件..."
find "$OPENNI_DIR" -name "*.ini" -o -name "*.xml" -o -name "*.json" | while read config; do
    echo "  $config"
done

# 查找 Redist 文件夹
echo ""
echo "=========================================="
echo "8. Redist 文件夹"
echo "=========================================="
REDIST_DIR="$OPENNI_DIR/Redist"
if [ -d "$REDIST_DIR" ]; then
    echo "✓ Redist 文件夹存在"
    echo "内容:"
    ls -la "$REDIST_DIR"
else
    echo "✗ Redist 文件夹不存在"
fi

# 分析环境变量
echo ""
echo "=========================================="
echo "9. 环境变量设置"
echo "=========================================="
echo "OpenNI2 需要的环境变量:"
echo ""
echo "OPENNI2_REDIST=$REDIST_DIR"
echo "LD_LIBRARY_PATH=$OPENNI_DIR/lib:\$LD_LIBRARY_PATH"
echo ""

# 生成运行脚本
echo ""
echo "=========================================="
echo "10. 生成运行脚本"
echo "=========================================="

# NiViewer 运行脚本
cat > run_niviewer.sh << EOF
#!/bin/bash
echo "运行 NiViewer..."
export OPENNI2_REDIST="$REDIST_DIR"
export LD_LIBRARY_PATH="$OPENNI_DIR/lib:\$LD_LIBRARY_PATH"
if [ -n "$NIVIEWER" ]; then
    "$NIVIEWER"
else
    echo "NiViewer 未找到"
fi
EOF
chmod +x run_niviewer.sh
echo "✓ 已生成: run_niviewer.sh"

# Python 测试脚本
cat > test_openni2_python.py << EOF
#!/usr/bin/env python3
import os
import sys
import ctypes

# 设置环境变量
os.environ['OPENNI2_REDIST'] = '$REDIST_DIR'
os.environ['LD_LIBRARY_PATH'] = '$OPENNI_DIR/lib:' + os.environ.get('LD_LIBRARY_PATH', '')

# 添加库路径
try:
    import numpy as np
    import cv2
    
    print("测试 OpenNI2 Python 绑定...")
    print(f"OPENNI2_REDIST: {os.environ['OPENNI2_REDIST']}")
    print(f"LD_LIBRARY_PATH: {os.environ['LD_LIBRARY_PATH']}")
    
    # 尝试加载 OpenNI2 库
    lib_path = "$OPENNI_DIR/lib/libOpenNI2.so"
    if os.path.exists(lib_path):
        print(f"✓ 找到库文件: {lib_path}")
        # 这里可以添加更多测试代码
    else:
        print(f"✗ 库文件不存在: {lib_path}")
        
except ImportError as e:
    print(f"✗ 导入错误: {e}")
except Exception as e:
    print(f"✗ 错误: {e}")
EOF
chmod +x test_openni2_python.py
echo "✓ 已生成: test_openni2_python.py"

# 环境设置脚本
cat > setup_openni2_env.sh << EOF
#!/bin/bash
echo "设置 OpenNI2 环境变量..."
export OPENNI2_REDIST="$REDIST_DIR"
export LD_LIBRARY_PATH="$OPENNI_DIR/lib:\$LD_LIBRARY_PATH"
echo "✓ 环境已设置"
echo "OPENNI2_REDIST=\$OPENNI2_REDIST"
echo "LD_LIBRARY_PATH=\$LD_LIBRARY_PATH"
EOF
chmod +x setup_openni2_env.sh
echo "✓ 已生成: setup_openni2_env.sh"

echo ""
echo "=========================================="
echo "分析完成!"
echo "=========================================="
echo ""
echo "关键信息:"
echo "  OpenNI2 目录: $OPENNI_DIR"
echo "  Redist 目录: $REDIST_DIR"
echo "  NiViewer: $NIVIEWER"
echo ""
echo "运行脚本:"
echo "  1. ./run_niviewer.sh - 运行 NiViewer"
echo "  2. python3 test_openni2_python.py - 测试 Python"
echo "  3. source ./setup_openni2_env.sh - 设置环境"
echo ""
echo "下一步:"
echo "  1. 运行 ./run_niviewer.sh 测试 NiViewer"
echo "  2. 如果成功,我们将使用相同的方法"
