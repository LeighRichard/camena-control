# Jetson Nano B01 运行问题解决方案

## 当前状态

✅ 程序已成功启动
✅ Web 服务器运行在 http://0.0.0.0:8080
⚠️ 相机初始化失败
⚠️ 串口连接失败

---

## 问题 1: Python 3.6 兼容性

### 错误信息
```
__init__() got an unexpected keyword argument 'text'
```

### 解决方案
已修复!需要更新代码:

```bash
cd ~/projects/camena-control/jetson
git pull origin main
```

---

## 问题 2: 相机初始化失败

### 错误信息
```
ROS OpenNI2 不可用,请确保已安装并设置 ROS 环境
uvc_open failed: [Path: 1-2.2.1-5.0, Return Code: -6]
```

### 解决方案

#### 方案 A: 使用 ROS OpenNI2 (推荐)

**步骤 1: 设置 ROS 环境**
```bash
source /opt/ros/melodic/setup.bash
```

**步骤 2: 检查 ROS OpenNI2**
```bash
# 检查 openni2_camera 包
rospack find openni2_camera

# 如果未找到,安装
sudo apt-get install ros-melodic-openni2-camera
```

**步骤 3: 测试相机**
```bash
# 启动相机节点
roslaunch openni2_camera openni2_camera.launch

# 在另一个终端检查话题
rostopic list | grep camera
rostopic echo /camera/rgb/image_raw -n 1
```

**步骤 4: 运行程序**
```bash
# 确保 ROS 环境已设置
source /opt/ros/melodic/setup.bash

# 运行程序
python3 main.py
```

---

#### 方案 B: 修复 pyorbbecsdk USB 权限

**错误原因**: 错误码 -6 表示 USB 设备访问被拒绝

**解决步骤**:

**步骤 1: 检查 USB 设备**
```bash
lsusb | grep 2bc5
```

**步骤 2: 创建 udev 规则**
```bash
# 创建规则文件
sudo tee /etc/udev/rules.d/99-orbbec-usb.rules > /dev/null << 'EOF'
# Orbbec 相机
SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"
SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", ATTR{idProduct}=="*", MODE="0666"
EOF

# 重新加载规则
sudo udevadm control --reload-rules
sudo udevadm trigger

# 重新插拔相机
```

**步骤 3: 添加用户到 plugdev 组**
```bash
sudo usermod -a -G plugdev $USER
# 注销并重新登录
```

**步骤 4: 测试**
```bash
python3 main.py
```

---

## 问题 3: 串口连接失败

### 错误信息
```
could not open port /dev/ttyUSB0: [Errno 2] No such file or directory
```

### 解决方案

#### 步骤 1: 检查串口设备
```bash
# 列出所有串口设备
ls -l /dev/ttyUSB* /dev/ttyACM* 2>/dev/null

# 或使用 dmesg
dmesg | grep tty
```

#### 步骤 2: 如果设备存在但权限不足
```bash
# 添加用户到 dialout 组
sudo usermod -a -G dialout $USER

# 注销并重新登录
```

#### 步骤 3: 如果设备不存在
检查:
- USB 转串口线是否连接
- 驱动是否安装
- 设备是否被识别

```bash
# 检查 USB 设备
lsusb

# 检查内核模块
lsmod | grep usbserial
```

#### 步骤 4: 修改配置文件
如果串口设备路径不同,修改配置:

```bash
nano config/system_config.yaml
```

修改:
```yaml
comm:
  enabled: true
  required: false
  port: "/dev/ttyUSB1"  # 改为实际设备路径
  baudrate: 115200
```

---

## 快速测试方案

### 测试相机 (使用 ROS)

**终端 1: 启动 ROS 核心**
```bash
roscore
```

**终端 2: 启动相机**
```bash
source /opt/ros/melodic/setup.bash
roslaunch openni2_camera openni2_camera.launch
```

**终端 3: 检查话题**
```bash
source /opt/ros/melodic/setup.bash
rostopic list
rostopic echo /camera/rgb/image_raw -n 1
```

**终端 4: 运行程序**
```bash
cd ~/projects/camena-control/jetson
source /opt/ros/melodic/setup.bash
source py36/bin/activate
python3 main.py
```

---

## 完整启动流程

### 方案 1: 使用 ROS OpenNI2

```bash
# 1. 设置 ROS 环境
source /opt/ros/melodic/setup.bash

# 2. 激活虚拟环境
cd ~/projects/camena-control/jetson
source py36/bin/activate

# 3. 更新代码
git pull origin main

# 4. 运行程序
python3 main.py
```

### 方案 2: 不使用相机 (仅测试)

```bash
# 修改配置,禁用相机
nano config/system_config.yaml

# 修改:
# camera:
#   enabled: false
#   required: false

# 运行程序
python3 main.py
```

---

## 验证清单

运行前请检查:

- [ ] ROS 环境已设置 (`echo $ROS_DISTRO` 显示 `melodic`)
- [ ] 虚拟环境已激活 (`which python3` 显示 py36 路径)
- [ ] 代码已更新 (`git log -1` 显示最新提交)
- [ ] 相机已连接 (`lsusb | grep 2bc5`)
- [ ] 串口设备存在 (`ls -l /dev/ttyUSB*`)

---

## 常见问题

### Q1: ROS 环境未设置

**问题**: `roslaunch: command not found`

**解决**:
```bash
source /opt/ros/melodic/setup.bash

# 添加到 .bashrc
echo "source /opt/ros/melodic/setup.bash" >> ~/.bashrc
```

### Q2: cv_bridge 未安装

**问题**: `ImportError: No module named cv_bridge`

**解决**:
```bash
sudo apt-get install ros-melodic-cv-bridge
```

### Q3: 相机权限问题

**问题**: `uvc_open failed: Return Code: -6`

**解决**:
```bash
# 创建 udev 规则
sudo tee /etc/udev/rules.d/99-orbbec-usb.rules > /dev/null << 'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Q4: 串口权限问题

**问题**: `Permission denied: '/dev/ttyUSB0'`

**解决**:
```bash
sudo usermod -a -G dialout $USER
# 注销并重新登录
```

---

## 下一步

1. **更新代码**: `git pull origin main`
2. **设置 ROS**: `source /opt/ros/melodic/setup.bash`
3. **测试相机**: `roslaunch openni2_camera openni2_camera.launch`
4. **运行程序**: `python3 main.py`

---

## 需要帮助?

如果问题仍然存在,请提供:

1. `lsusb` 输出
2. `ls -l /dev/ttyUSB*` 输出
3. `rospack find openni2_camera` 输出
4. `echo $ROS_DISTRO` 输出
5. 完整的错误日志

---

**更新日期**: 2026-03-19
