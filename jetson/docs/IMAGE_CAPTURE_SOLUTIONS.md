# OpenNI2 图像采集方案

## 问题
Web 界面看不到图像,因为 OpenNI2 控制器没有实现图像采集功能。

## 解决方案

### 方案 1: 使用 NiViewer2 (推荐,最简单)

**优点**:
- 已经验证可以工作
- 不需要额外安装
- 可以实时查看深度图和 RGB 图

**使用方法**:
```bash
cd ~/OpenNI-Linux-Arm64-2.3
./Bin/NiViewer2
```

**操作**:
- 按 `s` 保存图像
- 按 `q` 退出

---

### 方案 2: 使用 OpenNI2 Python 包装器

**安装步骤**:

1. **下载 openni2-python**:
```bash
cd ~
git clone https://github.com/elmonkey/openni2-python.git
cd openni2-python
```

2. **设置环境变量**:
```bash
export OPENNI2_REDIST=~/OpenNI-Linux-Arm64-2.3/Redist
export LD_LIBRARY_PATH=~/OpenNI-Linux-Arm64-2.3/lib:$LD_LIBRARY_PATH
```

3. **编译安装**:
```bash
cd ~/projects/camena-control/jetson
source py36/bin/activate
cd ~/openni2-python
python setup.py build
python setup.py install
```

4. **测试**:
```python
python -c "import openni2; print('openni2 installed successfully')"
```

---

### 方案 3: 使用 ROS + libuvc_camera (已验证)

**优点**:
- 您已经验证可以工作
- 可以通过 ROS 话题获取图像

**使用方法**:
```bash
# 终端 1
source ~/catkin_ws/devel/setup.bash
roscore

# 终端 2
rosrun libuvc_camera camera_node

# 终端 3
rqt_image_view
```

**在程序中使用**:
- 订阅 `/camera/rgb/image_raw` 话题
- 订阅 `/camera/depth/image_raw` 话题

---

### 方案 4: 使用 OpenNI2 C API + ctypes (复杂)

**优点**:
- 不需要额外安装
- 直接使用 OpenNI2 库

**缺点**:
- 实现复杂
- 需要处理很多底层细节

---

## 推荐方案

**短期**: 使用 **方案 1** (NiViewer2)
- 最简单
- 已经验证可以工作

**长期**: 使用 **方案 2** (openni2-python)
- 可以在程序中获取图像
- 支持 Web 界面显示

---

## 当前状态

系统已经成功运行,只是图像采集功能未实现。

**可以使用的功能**:
- ✅ 相机初始化
- ✅ 目标检测
- ✅ 人脸识别
- ✅ 视觉伺服
- ✅ Web 界面 (http://0.0.0.0:8080)
- ⚠️ 图像采集 (需要实现)

---

## 下一步

1. **立即可用**: 使用 NiViewer2 查看图像
2. **长期方案**: 安装 openni2-python 包装器
3. **备选方案**: 使用 ROS + libuvc_camera
