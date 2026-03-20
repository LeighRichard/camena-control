#!/bin/bash
# OpenNI2 库文件检查脚本

echo "=== 检查 OpenNI2 库文件 ==="
echo ""

echo "[1] 查找 OpenNI2 库文件:"
find /usr -name "libOpenNI2*" 2>/dev/null

echo ""
echo "[2] 检查 /usr/lib 目录:"
ls -la /usr/lib/*openni* 2>/dev/null || echo "未找到"

echo ""
echo "[3] 检查 /usr/local/lib 目录:"
ls -la /usr/local/lib/*openni* 2>/dev/null || echo "未找到"

echo ""
echo "[4] 检查 pkg-config:"
pkg-config --modversion openni2 2>/dev/null || echo "pkg-config 未找到 openni2"

echo ""
echo "[5] 检查 OpenNI2 头文件:"
ls -la /usr/include/openni2/ 2>/dev/null || echo "未找到"

echo ""
echo "[6] 检查 Python OpenNI2 绑定:"
python3 -c "import openni2; print('OpenNI2 Python 绑定已安装')" 2>&1 || echo "OpenNI2 Python 绑定未安装"

echo ""
echo "[7] 检查 ROS OpenNI2 (如果使用 ROS):"
rospack find openni2_launch 2>/dev/null || echo "ROS OpenNI2 未找到"

echo ""
echo "=== 检查完成 ==="
