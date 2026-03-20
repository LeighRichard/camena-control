#!/bin/bash

echo "=========================================="
echo "Orbbec 相机诊断脚本"
echo "=========================================="
echo ""
echo "此脚本将测试所有可能的相机访问方法"
echo ""

# 设置 ROS 环境
source /opt/ros/melodic/setup.bash 2>/dev/null

# 1. 检查相机连接
echo "=========================================="
echo "1. 检查相机连接"
echo "=========================================="
CAMERA=$(lsusb | grep 2bc5)
if [ -n "$CAMERA" ]; then
    echo "✓ 相机已连接:"
    echo "  $CAMERA"
    BUS=$(echo "$CAMERA" | awk '{print $2}')
    DEVICE=$(echo "$CAMERA" | awk '{print $4}' | tr -d ':')
    echo "  Bus: $BUS, Device: $DEVICE"
    echo "  设备路径: /dev/bus/usb/$BUS/$DEVICE"
else
    echo "✗ 未检测到 Orbbec 相机"
    echo "  请检查相机连接"
    exit 1
fi

# 2. 检查视频设备
echo ""
echo "=========================================="
echo "2. 检查视频设备"
echo "=========================================="
VIDEO_DEVICES=$(ls /dev/video* 2>/dev/null)
if [ -n "$VIDEO_DEVICES" ]; then
    echo "✓ 视频设备:"
    echo "$VIDEO_DEVICES"
    for dev in $VIDEO_DEVICES; do
        echo "  $dev:"
        v4l2-ctl --device=$dev --info 2>/dev/null | head -5
    done
else
    echo "✗ 未找到视频设备"
fi

# 3. 检查 USB 权限
echo ""
echo "=========================================="
echo "3. 检查 USB 权限"
echo "=========================================="
if [ -n "$BUS" ] && [ -n "$DEVICE" ]; then
    USB_DEV="/dev/bus/usb/$BUS/$DEVICE"
    echo "设备: $USB_DEV"
    ls -l $USB_DEV
    
    if [ -r "$USB_DEV" ] && [ -w "$USB_DEV" ]; then
        echo "✓ 设备可读写"
    else
        echo "✗ 设备权限不足"
        echo "  修复: sudo chmod 666 $USB_DEV"
    fi
fi

# 4. 检查 OpenNI2
echo ""
echo "=========================================="
echo "4. 检查 OpenNI2"
echo "=========================================="
if [ -f "/usr/lib/libOpenNI2.so" ]; then
    echo "✓ OpenNI2 库已安装"
    ls -l /usr/lib/libOpenNI2.so
else
    echo "✗ OpenNI2 库未安装"
fi

if [ -d "/usr/lib/OpenNI2/Drivers" ]; then
    echo "✓ OpenNI2 驱动目录存在"
    echo "驱动文件:"
    ls -l /usr/lib/OpenNI2/Drivers/ | grep -E "\.so$"
else
    echo "✗ OpenNI2 驱动目录不存在"
fi

# 检查 OpenNI2 工具
if command -v NiViewer2 &> /dev/null; then
    echo "✓ NiViewer2 可用"
else
    echo "✗ NiViewer2 不可用"
    echo "  安装: sudo apt-get install openni2-utils"
fi

# 5. 检查 ROS
echo ""
echo "=========================================="
echo "5. 检查 ROS"
echo "=========================================="
if [ -n "$ROS_DISTRO" ]; then
    echo "✓ ROS 环境已设置: $ROS_DISTRO"
    
    # 检查 openni2_camera 包
    PKG_PATH=$(rospack find openni2_camera 2>/dev/null)
    if [ -n "$PKG_PATH" ]; then
        echo "✓ openni2_camera 包已安装"
        echo "  路径: $PKG_PATH"
    else
        echo "✗ openni2_camera 包未安装"
    fi
else
    echo "✗ ROS 环境未设置"
fi

# 6. 测试方法
echo ""
echo "=========================================="
echo "6. 测试相机访问方法"
echo "=========================================="

# 方法 1: OpenNI2 NiViewer2
echo ""
echo "方法 1: OpenNI2 NiViewer2"
echo "----------------------------------------"
if command -v NiViewer2 &> /dev/null; then
    echo "运行: NiViewer2"
    echo "这是最直接的测试方法"
    echo "如果成功,说明 OpenNI2 可以访问相机"
else
    echo "NiViewer2 未安装"
    echo "安装: sudo apt-get install openni2-utils"
fi

# 方法 2: ROS OpenNI2
echo ""
echo "方法 2: ROS OpenNI2"
echo "----------------------------------------"
if [ -n "$PKG_PATH" ]; then
    echo "运行步骤:"
    echo "  终端 1: roscore"
    echo "  终端 2: rosrun openni2_camera openni2_camera_node"
    echo "  终端 3: rostopic list | grep camera"
else
    echo "openni2_camera 未安装"
fi

# 方法 3: V4L2
echo ""
echo "方法 3: V4L2 (Video4Linux2)"
echo "----------------------------------------"
if [ -n "$VIDEO_DEVICES" ]; then
    echo "运行: v4l2-ctl --list-formats-ext"
    echo "或使用 Python OpenCV:"
    echo "  import cv2"
    echo "  cap = cv2.VideoCapture(0)"
    echo "  ret, frame = cap.read()"
else
    echo "无视频设备"
fi

# 方法 4: pyorbbecsdk
echo ""
echo "方法 4: pyorbbecsdk"
echo "----------------------------------------"
python3 -c "import pyorbbecsdk" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ pyorbbecsdk 已安装"
    echo "测试代码:"
    echo "  from pyorbbecsdk import Pipeline, Config"
    echo "  pipeline = Pipeline()"
    echo "  pipeline.start()"
else
    echo "✗ pyorbbecsdk 未安装"
fi

# 7. 生成测试脚本
echo ""
echo "=========================================="
echo "7. 生成测试脚本"
echo "=========================================="

# OpenNI2 测试脚本
cat > test_openni2.sh << 'EOF'
#!/bin/bash
echo "测试 OpenNI2 NiViewer2..."
if command -v NiViewer2 &> /dev/null; then
    NiViewer2
else
    echo "NiViewer2 未安装"
    echo "安装: sudo apt-get install openni2-utils"
fi
EOF
chmod +x test_openni2.sh
echo "✓ 已生成: test_openni2.sh"

# ROS 测试脚本
cat > test_ros.sh << 'EOF'
#!/bin/bash
source /opt/ros/melodic/setup.bash
echo "测试 ROS OpenNI2..."
echo "请确保 roscore 已在另一个终端运行"
sleep 2
rosrun openni2_camera openni2_camera_node
EOF
chmod +x test_ros.sh
echo "✓ 已生成: test_ros.sh"

# Python OpenCV 测试脚本
cat > test_opencv.py << 'EOF'
#!/usr/bin/env python3
import cv2
import sys

print("测试 OpenCV 视频捕获...")
print("可用设备:")
for i in range(10):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"  /dev/video{i}: 可用")
        ret, frame = cap.read()
        if ret:
            print(f"    分辨率: {frame.shape[1]}x{frame.shape[0]}")
        cap.release()

print("\n尝试打开 /dev/video0...")
cap = cv2.VideoCapture(0)
if cap.isOpened():
    print("✓ 成功打开 /dev/video0")
    ret, frame = cap.read()
    if ret:
        print(f"✓ 成功读取帧: {frame.shape}")
        cv2.imwrite("test_frame.jpg", frame)
        print("✓ 已保存: test_frame.jpg")
    else:
        print("✗ 无法读取帧")
    cap.release()
else:
    print("✗ 无法打开 /dev/video0")
EOF
chmod +x test_opencv.py
echo "✓ 已生成: test_opencv.py"

# pyorbbecsdk 测试脚本
cat > test_pyorbbecsdk.py << 'EOF'
#!/usr/bin/env python3
try:
    from pyorbbecsdk import Pipeline, Config
    print("测试 pyorbbecsdk...")
    
    pipeline = Pipeline()
    config = Config()
    
    print("尝试启动 pipeline...")
    pipeline.start(config)
    print("✓ Pipeline 启动成功")
    
    print("等待帧...")
    for i in range(10):
        frames = pipeline.wait_for_frames(1000)
        if frames:
            print(f"✓ 获取到帧 {i+1}")
            break
    
    pipeline.stop()
    print("✓ 测试成功")
    
except ImportError:
    print("✗ pyorbbecsdk 未安装")
except Exception as e:
    print(f"✗ 错误: {e}")
EOF
chmod +x test_pyorbbecsdk.py
echo "✓ 已生成: test_pyorbbecsdk.py"

echo ""
echo "=========================================="
echo "诊断完成!"
echo "=========================================="
echo ""
echo "测试脚本已生成:"
echo "  1. ./test_openni2.sh    - 测试 OpenNI2"
echo "  2. ./test_ros.sh        - 测试 ROS OpenNI2"
echo "  3. python3 test_opencv.py - 测试 OpenCV"
echo "  4. python3 test_pyorbbecsdk.py - 测试 pyorbbecsdk"
echo ""
echo "建议测试顺序:"
echo "  1. 先运行 ./test_openni2.sh (最直接)"
echo "  2. 如果成功,说明 OpenNI2 可以工作"
echo "  3. 然后测试 ROS 或 pyorbbecsdk"
