# OpenNI2 Python 绑定安装指南

由于 PyPI 上没有 `openni2` 包,需要从源码编译 Python 绑定。

## 方法 1: 从 GitHub 编译 OpenNI2 Python 绑定

```bash
# 1. 安装编译依赖
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    python3-dev \
    libusb-1.0-0-dev \
    libudev-dev \
    freeglut3-dev \
    doxygen

# 2. 克隆 OpenNI2 仓库
cd ~
git clone https://github.com/OpenNI/OpenNI2.git
cd OpenNI2

# 3. 编译 OpenNI2
mkdir -p build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr
make -j$(nproc)
sudo make install

# 4. 编译 Python 绑定
cd ../Wrappers/OpenNI.py
python3 setup.py build
sudo python3 setup.py install
```

## 方法 2: 使用 ROS OpenNI2 (推荐)

如果您使用 ROS,可以安装 ROS 的 OpenNI2 包:

```bash
# Ubuntu 18.04 (Melodic)
sudo apt-get install -y ros-melodic-openni2-launch

# Ubuntu 20.04 (Noetic)
sudo apt-get install -y ros-noetic-openni2-launch

# 设置 ROS 环境
source /opt/ros/melodic/setup.bash  # 或 noetic

# 测试
python3 -c "import openni2; print('OK')"
```

## 方法 3: 使用 PyOpenNI (替代方案)

```bash
pip install PyOpenNI
```

## 方法 4: 修复 pyorbbecsdk 权限问题 (最简单)

既然您的 OpenNI2 可以正常工作,问题可能是 pyorbbecsdk 的权限问题。尝试:

```bash
# 1. 设置 USB 权限
sudo tee /etc/udev/rules.d/99-orbbec.rules > /dev/null <<EOF
SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"
KERNEL=="video*", MODE="0666"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger

# 2. 设置当前 USB 设备权限
for dev in /dev/bus/usb/*/*; do sudo chmod 666 "$dev" 2>/dev/null; done

# 3. 重新插拔相机

# 4. 测试
python3 main.py
```

## 验证安装

```bash
# 测试 OpenNI2
python3 -c "
import openni2
openni2.initialize()
print('OpenNI2 版本:', openni2.__version__)
device = openni2.Device.open_any()
print('设备:', device)
openni2.unload()
"
```

## 推荐方案

根据您的情况,我推荐:

1. **首选**: 修复 pyorbbecsdk 权限问题 (方法 4)
2. **次选**: 使用 ROS OpenNI2 (方法 2)
3. **备选**: 从源码编译 (方法 1)

方法 4 最简单,因为:
- 您的系统已经安装了 OpenNI2 库
- pyorbbecsdk 已安装在您的虚拟环境中
- 只是权限问题导致的初始化失败
