# Jetson Nano B01 - Orbbec 相机修复指南

**文档版本**: 1.0  
**适用平台**: Jetson Nano B01  
**目标问题**: Orbbec 相机初始化失败  
**更新日期**: 2026-03-16

---

## 📋 问题概述

### 症状

运行程序时出现以下错误:

```
[error][8880][UsbEnumeratorLibusb.cpp:159] Invalid descriptor index: 0
[error][8880][UsbEnumeratorLibusb.cpp:420] Failed to query USB device serial number
[error][8880][ObLibuvcDevicePort.cpp:282] setXu failed, error code=-9
E camera.factory       创建奥比中光相机失败: catching classes that do not inherit from BaseException is not allowed
```

### 根本原因

1. **USB 权限不足**: `setXu failed, error code=-9` 表示无法访问 USB 设备
2. **异常处理错误**: `OBException` 类未正确继承 `BaseException`,导致异常捕获失败
3. **USB 描述符问题**: SDK 底层的 USB 枚举错误(非关键)

---

## 🔧 解决方案

### 方案一: 自动修复脚本 (推荐)

**步骤 1: 进入项目目录**

```bash
cd ~/projects/camena-control/jetson
```

**步骤 2: 运行修复脚本**

```bash
# 添加执行权限
chmod +x scripts/fix_orbbec_jetson.sh

# 运行修复脚本
./scripts/fix_orbbec_jetson.sh
```

修复脚本会自动完成:
- ✅ 安装系统依赖 (libusb, libudev)
- ✅ 配置 USB udev 规则
- ✅ 设置设备权限
- ✅ 检查 pyorbbecsdk 安装
- ✅ 运行诊断测试

**步骤 3: 重新插拔相机或重启系统**

```bash
# 方法 1: 重新插拔相机 USB

# 方法 2: 重启系统
sudo reboot
```

**步骤 4: 验证修复**

```bash
# 激活虚拟环境 (如果使用)
source py36/bin/activate

# 运行诊断脚本
python3 scripts/diagnose_orbbec.py

# 运行主程序
python3 main.py
```

---

### 方案二: 手动修复

如果自动脚本无法执行,可以手动执行以下步骤:

#### 1. 安装系统依赖

```bash
sudo apt-get update
sudo apt-get install -y libusb-1.0-0-dev libudev-dev udev
```

#### 2. 配置 USB 权限

```bash
# 创建 udev 规则
sudo tee /etc/udev/rules.d/99-orbbec.rules > /dev/null <<EOF
# Orbbec 相机 USB 权限规则
SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666", GROUP="plugdev"
KERNEL=="video*", MODE="0666", GROUP="plugdev"
EOF

# 重新加载规则
sudo udevadm control --reload-rules
sudo udevadm trigger

# 添加用户到 plugdev 组
sudo usermod -a -G plugdev $USER
```

#### 3. 设置临时权限 (立即生效)

```bash
# 设置所有 USB 设备权限
for dev in /dev/bus/usb/*/*; do
    if [ -e "$dev" ]; then
        sudo chmod 666 "$dev" 2>/dev/null || true
    fi
done
```

#### 4. 重新插拔相机或重启

```bash
sudo reboot
```

#### 5. 验证

```bash
# 检查 USB 设备
lsusb | grep -i 2bc5

# 运行诊断
python3 scripts/diagnose_orbbec.py
```

---

### 方案三: 使用 sudo (临时方案)

如果上述方案无效,可以使用 sudo 运行程序:

```bash
sudo python3 main.py
```

⚠️ **注意**: 这只是临时方案,不建议长期使用。

---

## 📊 诊断工具

### 使用诊断脚本

```bash
python3 scripts/diagnose_orbbec.py
```

诊断脚本会检查:
1. ✅ Python 环境和版本
2. ✅ pyorbbecsdk 安装和版本
3. ✅ 系统依赖 (libusb)
4. ✅ USB 设备检测
5. ✅ USB 权限配置
6. ✅ 相机初始化测试
7. ✅ 图像采集测试

### 查看系统日志

```bash
# 查看内核日志
dmesg | tail -50

# 查看 USB 设备
lsusb -t

# 查看设备权限
ls -l /dev/bus/usb/*/*
```

---

## 🐛 故障排查

### 问题 1: 未找到 Orbbec 设备

**症状**: `lsusb` 中没有 Vendor ID 为 `2bc5` 的设备

**解决方案**:
```bash
# 1. 检查物理连接
#    - USB 线缆是否插好
#    - 尝试不同的 USB 端口 (推荐 USB 3.0)
#    - 检查相机供电

# 2. 检查 USB 端口
lsusb -t

# 3. 查看内核日志
dmesg | grep -i usb | tail -20
```

### 问题 2: pyorbbecsdk 未安装

**症状**: `ImportError: No module named 'pyorbbecsdk'`

**解决方案**:
```bash
# 安装 pyorbbecsdk
pip3 install pyorbbecsdk

# 如果安装失败,可能需要从源码编译
git clone https://github.com/orbbec/pyorbbecsdk.git
cd pyorbbecsdk
pip3 install .
```

### 问题 3: 权限仍然不足

**症状**: 仍然出现 `setXu failed, error code=-9`

**解决方案**:
```bash
# 1. 检查 udev 规则是否生效
cat /etc/udev/rules.d/99-orbbec.rules

# 2. 手动设置权限
lsusb | grep 2bc5
# 假设设备在 Bus 001 Device 005
sudo chmod 666 /dev/bus/usb/001/005

# 3. 重启 udev
sudo systemctl restart udev

# 4. 重新插拔相机
```

### 问题 4: Python 版本不兼容

**症状**: pyorbbecsdk 安装失败或运行时错误

**解决方案**:
```bash
# Jetson Nano 推荐使用 Python 3.6
python3 --version

# 如果不是 3.6,创建虚拟环境
python3.6 -m venv py36
source py36/bin/activate
pip install pyorbbecsdk
```

### 问题 5: 相机初始化超时

**症状**: 初始化过程中卡住或超时

**解决方案**:
```bash
# 1. 检查 USB 带宽
#    - 使用 USB 3.0 端口 (蓝色)
#    - 避免使用 USB Hub

# 2. 降低分辨率或帧率
#    编辑 config/system_config.yaml:
camera:
  orbbec:
    color:
      width: 1280
      height: 720
      fps: 15
    depth:
      width: 640
      height: 480
      fps: 15

# 3. 检查系统负载
htop
```

---

## ✅ 验证成功

成功修复后,应该看到以下输出:

```
02:38:37 I camera.factory       开始自动检测相机...
02:38:37 I camera.factory       尝试检测奥比中光相机...
02:38:37 I camera.factory       成功创建奥比中光相机: Orbbec Camera
02:38:37 I camera.factory       ✅ 自动检测成功: 奥比中光相机
```

---

## 📝 代码修改说明

### 修改文件

**文件**: `jetson/src/camera/orbbec_controller.py`

### 修改内容

1. **移除 OBException 导入** (第 15-23 行)
   ```python
   # 修改前
   from pyorbbecsdk import (
       Pipeline, Config, 
       OBSensorType, OBFormat, OBAlignMode,
       OBException  # ❌ 移除
   )
   
   # 修改后
   from pyorbbecsdk import (
       Pipeline, Config, 
       OBSensorType, OBFormat, OBAlignMode
   )
   ```

2. **修改异常处理** (第 177-192 行)
   ```python
   # 修改前
   except OBException as e:  # ❌ 可能导致错误
       ...
   except Exception as e:
       ...
   
   # 修改后
   except Exception as e:
       # 检查是否是 OBException 类型（更安全的检查方式）
       if ORBBEC_AVAILABLE and hasattr(e, '__class__') and e.__class__.__name__ == 'OBException':
           # OBException 处理
           ...
       else:
           # 其他异常处理
           ...
   ```

### 修改原因

`OBException` 类可能没有正确继承 Python 的 `BaseException`,导致直接捕获时出现错误:
```
catching classes that do not inherit from BaseException is not allowed
```

通过运行时类型检查,避免了这个问题。

---

## 🔗 相关文档

- [Orbbec 相机设置指南](ORBBEC_SETUP.md)
- [Orbbec 迁移方案](ORBBEC_MIGRATION_PLAN.md)
- [Jetson Nano 部署指南](../JETSON_DEPLOYMENT_GUIDE.md)

---

## 💡 最佳实践

### 1. USB 连接

- ✅ 使用 USB 3.0 端口 (蓝色接口)
- ✅ 直接连接,避免使用 USB Hub
- ✅ 确保供电充足

### 2. 系统配置

- ✅ 定期更新系统: `sudo apt-get update && sudo apt-get upgrade`
- ✅ 保持 pyorbbecsdk 最新版本
- ✅ 使用 Python 3.6 虚拟环境

### 3. 运行环境

- ✅ 激活虚拟环境后再运行
- ✅ 避免同时运行多个相机程序
- ✅ 监控系统资源使用

### 4. 故障预防

- ✅ 定期检查 USB 连接
- ✅ 定期检查系统日志
- ✅ 备份配置文件

---

## 📞 技术支持

如果问题仍然存在,请:

1. 运行诊断脚本并保存输出:
   ```bash
   python3 scripts/diagnose_orbbec.py > diagnostic_output.txt 2>&1
   ```

2. 收集系统信息:
   ```bash
   # 系统版本
   cat /etc/nv_tegra_release
   
   # Python 版本
   python3 --version
   
   # USB 设备
   lsusb > usb_devices.txt
   
   # 内核日志
   dmesg | tail -100 > kernel_log.txt
   ```

3. 提交 Issue 并附上:
   - 诊断输出
   - 系统信息
   - 错误日志
   - 相机型号

---

**文档维护**: 如有问题或建议,请提交 Issue 或 Pull Request。
