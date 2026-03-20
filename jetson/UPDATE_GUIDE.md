# Jetson Nano B01 更新指南

## 快速更新步骤

### 方法一: 一键更新脚本

在 Jetson Nano 上执行以下命令:

```bash
cd ~/projects/camena-control/jetson && \
git pull origin main && \
source /opt/ros/melodic/setup.bash && \
source py36/bin/activate && \
echo "更新完成!"
```

---

### 方法二: 分步更新

#### 步骤 1: 进入项目目录

```bash
cd ~/projects/camena-control/jetson
```

#### 步骤 2: 拉取最新代码

```bash
git pull origin main
```

预期输出:
```
remote: Enumerating objects: 15, done.
remote: Counting objects: 100% (15/15), done.
remote: Compressing objects: 100% (8/8), done.
remote: Total 10 (delta 4), reused 8 (delta 2), pack-reused 0
Unpacking objects: 100% (10/10), done.
From https://github.com/LeighRichard/camena-control
 * [new ref]         refs/heads/main -> origin/main
Updating 4ac6309..76b98dc
Fast-forward
 FIX_REPORT.md                    | 285 +++++++++++++
 main.py                          |   6 +-
 src/camera/orbbec_controller_ros.py | 412 ++++++++++++++++++-
 src/utils/config.py              |  87 ++++-
 src/utils/config_validator.py    |   5 +-
 test_config.py                   |  56 +++
 6 files changed, 705 insertions(+), 20 deletions(-)
 create mode 100644 FIX_REPORT.md
 create mode 100644 test_config.py
```

#### 步骤 3: 设置 ROS 环境

```bash
source /opt/ros/melodic/setup.bash
```

#### 步骤 4: 激活虚拟环境

```bash
source py36/bin/activate
```

#### 步骤 5: 验证更新

```bash
# 检查配置解析
python3 test_config.py
```

预期输出:
```
============================================================
测试配置解析
============================================================

相机配置:
  类型: auto
  启用: True
  必需: False

Orbbec 配置:
  彩色分辨率: 1920x1080
  彩色帧率: 30
  深度分辨率: 640x480
  深度帧率: 30
  对齐模式: D2C_HW
  深度范围: 600-8000

RealSense 配置:
  分辨率: 1280x720
  帧率: 30
  深度启用: True

向后兼容属性:
  通用宽度: 1280
  通用高度: 720
  通用帧率: 30

============================================================
配置解析测试通过
============================================================
```

---

## 完整运行流程

### 1. 启动相机测试

```bash
# 确保 ROS 环境已设置
source /opt/ros/melodic/setup.bash

# 激活虚拟环境
source py36/bin/activate

# 运行主程序
python3 main.py
```

### 2. 检查相机连接

如果遇到相机问题,检查以下内容:

```bash
# 检查 USB 设备
lsusb | grep 2bc5

# 检查 ROS 节点
rostopic list | grep camera

# 检查相机数据
rostopic echo /camera/rgb/image_raw -n 1
```

---

## 更新内容说明

### 本次更新包含:

1. **配置解析修复**
   - 支持嵌套的 Orbbec/RealSense 配置
   - 新增配置类: `OrbbecConfig`, `RealSenseConfig`
   - 保持向后兼容性

2. **ROS 控制器完善**
   - 实现完整的图像采集功能
   - ROS 话题订阅 (`/camera/rgb/image_raw`, `/camera/depth/image_raw`)
   - 图像回调处理
   - 深度查询功能

3. **其他修复**
   - 视觉伺服初始化检查
   - Windows 兼容性
   - subprocess 参数更新

---

## 常见问题

### Q1: git pull 失败

**问题**: `fatal: unable to access 'https://github.com/...'`

**解决**:
```bash
# 检查网络连接
ping github.com

# 或使用 SSH
git remote set-url origin git@github.com:LeighRichard/camena-control.git
git pull origin main
```

### Q2: ROS 环境未设置

**问题**: `roslaunch: command not found`

**解决**:
```bash
# 设置 ROS 环境
source /opt/ros/melodic/setup.bash

# 添加到 .bashrc (可选)
echo "source /opt/ros/melodic/setup.bash" >> ~/.bashrc
```

### Q3: cv_bridge 未安装

**问题**: `ImportError: No module named cv_bridge`

**解决**:
```bash
# 安装 cv_bridge
sudo apt-get update
sudo apt-get install ros-melodic-cv-bridge
```

### Q4: 相机未检测到

**问题**: `未收到相机数据,请检查相机连接`

**解决**:
```bash
# 检查 USB 连接
lsusb

# 检查相机权限
ls -l /dev/bus/usb/*/*

# 重启 ROS 节点
rosnode kill /camera/driver
```

---

## 验证清单

更新完成后,请验证以下内容:

- [ ] 代码已成功拉取 (`git log -1` 显示 `76b98dc`)
- [ ] 配置解析测试通过 (`python3 test_config.py`)
- [ ] ROS 环境已设置 (`rostopic list` 可用)
- [ ] 虚拟环境已激活 (`which python3` 显示 py36 路径)
- [ ] 相机可正常连接 (`lsusb | grep 2bc5`)

---

## 下一步

更新完成后,您可以:

1. **测试相机**: `python3 main.py`
2. **查看修复报告**: `cat FIX_REPORT.md`
3. **检查配置**: `cat config/system_config.yaml`

---

## 需要帮助?

如果遇到问题,请提供:
1. 错误信息截图
2. `git log -1` 输出
3. `python3 test_config.py` 输出
4. `lsusb` 输出

---

**更新日期**: 2026-03-19  
**提交 ID**: 76b98dc  
**仓库**: https://github.com/LeighRichard/camena-control
