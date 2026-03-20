# Orbbec 相机设置指南

本指南详细介绍如何在相机位置控制系统中设置和使用奥比中光（Orbbec）深度相机。

## 目录

- [硬件要求](#硬件要求)
- [软件安装](#软件安装)
- [配置说明](#配置说明)
- [使用示例](#使用示例)
- [性能优化](#性能优化)
- [常见问题](#常见问题)
- [技术规格](#技术规格)

## 硬件要求

### 支持的相机型号

- **奥比中光咪咕款** - 主要测试型号
- Orbbec Astra 系列
- Orbbec Femto 系列
- 其他支持 Orbbec SDK 的型号

### 系统要求

- **平台**: Jetson Nano / Ubuntu 18.04+
- **USB**: USB 3.0 接口（推荐）或 USB 2.0
- **内存**: 至少 2GB RAM
- **Python**: 3.8+

## 软件安装

### 1. 安装 Orbbec SDK

```bash
# 使用 pip 安装
pip install pyorbbecsdk>=1.5.7

# 验证安装
python -c "import pyorbbecsdk; print(pyorbbecsdk.__version__)"
```

### 2. 安装系统依赖

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y libusb-1.0-0-dev libudev-dev

# 添加 USB 规则（可选，避免权限问题）
sudo tee /etc/udev/rules.d/99-orbbec.rules > /dev/null <<EOF
SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 3. 测试相机连接

```bash
# 检查 USB 设备
lsusb | grep -i orbbec

# 运行测试脚本
python -c "
from src.camera.factory import CameraFactory
camera = CameraFactory.create_camera('orbbec')
if camera:
    print(f'✅ 成功连接: {camera.camera_model}')
    camera.close()
else:
    print('❌ 未找到 Orbbec 相机')
"
```

## 配置说明

### 基本配置

编辑 `config/system_config.yaml`：

```yaml
camera:
  type: "orbbec"  # 或 "auto" 自动检测
  
  # Orbbec 特定配置
  orbbec:
    color_width: 1920
    color_height: 1080
    depth_width: 640
    depth_height: 480
    fps: 30
    
    # 深度处理
    depth_filter_size: 5      # 滤波窗口大小（3, 5, 7）
    min_depth: 0.6            # 最小有效深度（米）
    max_depth: 6.0            # 最大有效深度（米）
    
    # 对齐模式
    align_mode: "D2C"         # 深度对齐到彩色
```

### 高级配置

```yaml
camera:
  orbbec:
    # 曝光控制
    auto_exposure: true
    exposure: -1              # -1 为自动
    
    # 增益控制
    gain: 16                  # 0-128
    
    # 白平衡
    auto_white_balance: true
    white_balance: -1         # -1 为自动
```

### 视觉伺服参数

系统会自动根据相机类型调整视觉伺服参数：

```python
# Orbbec 参数（自动应用）
min_distance = 0.6m    # vs RealSense 0.3m
max_distance = 6.0m    # vs RealSense 8.0m
confidence = 0.7       # vs RealSense 0.8
filter_size = 5        # vs RealSense 3
```

## 使用示例

### 基本使用

```python
from src.camera.factory import CameraFactory

# 创建 Orbbec 相机
camera = CameraFactory.create_camera("orbbec")

# 初始化
success, error = camera.initialize()
if not success:
    print(f"初始化失败: {error}")
    exit(1)

# 采集图像
image_pair, error = camera.capture()
if image_pair:
    print(f"彩色图: {image_pair.rgb.shape}")
    print(f"深度图: {image_pair.depth.shape}")
    
# 查询深度
depth_m = camera.get_depth_at_point(960, 540, image_pair.depth)
print(f"中心点深度: {depth_m:.2f}m")

# 关闭相机
camera.close()
```

### 自动检测模式

```python
# 自动检测并创建相机（优先 Orbbec）
camera = CameraFactory.create_camera("auto")

if camera:
    print(f"检测到相机: {camera.camera_type}")
    print(f"型号: {camera.camera_model}")
else:
    print("未找到支持的相机")
```

### 与目标检测集成

```python
from src.camera.factory import CameraFactory
from src.vision.detector import ObjectDetector, DetectionConfig

# 创建相机和检测器
camera = CameraFactory.create_camera("orbbec")
detector = ObjectDetector(DetectionConfig(threshold=0.5))

camera.initialize()
detector.load_model()

# 采集和检测
image_pair, _ = camera.capture()
result = detector.detect(image_pair.rgb)

print(f"检测到 {len(result.targets)} 个目标")
if result.selected_target:
    target = result.selected_target
    print(f"选中目标: {target.class_name}")
    print(f"位置: ({target.center_x}, {target.center_y})")
    print(f"距离: {target.distance:.2f}m")

# 清理
detector.unload()
camera.close()
```

## 性能优化

### 1. 深度滤波优化

Orbbec 相机的深度图分辨率较低（640×480），系统自动应用以下优化：

- **中值滤波**: 5×5 窗口，去除噪点
- **坐标转换**: 自动处理彩色图（1920×1080）到深度图（640×480）的坐标映射
- **有效性检查**: 过滤无效深度值（0 值）

### 2. 帧率优化

```python
# 配置等待帧数（减少可提高响应速度）
image_pair, _ = camera.capture(wait_frames=3)  # 默认 5
```

### 3. 分辨率调整

如果性能不足，可以降低分辨率：

```yaml
camera:
  orbbec:
    color_width: 1280
    color_height: 720
    # 深度分辨率固定为 640×480
```

### 4. 深度范围限制

限制深度范围可以提高精度：

```yaml
camera:
  orbbec:
    min_depth: 1.0   # 只关注 1-4 米范围
    max_depth: 4.0
```

## 常见问题

### Q1: 相机初始化失败

**症状**: `initialize()` 返回 False

**解决方案**:
```bash
# 1. 检查 SDK 安装
pip show pyorbbecsdk

# 2. 检查 USB 连接
lsusb | grep -i orbbec

# 3. 检查权限
sudo chmod 666 /dev/bus/usb/*/***

# 4. 重新插拔 USB
```

### Q2: 深度图像全黑或有大量噪点

**原因**: 
- 环境光照过强（结构光被干扰）
- 距离过近或过远
- 表面反光

**解决方案**:
```python
# 1. 调整深度滤波
camera._depth_processor.filter_size = 7  # 增大滤波窗口

# 2. 限制深度范围
camera._depth_processor.min_depth = 0.8
camera._depth_processor.max_depth = 5.0

# 3. 改善环境
# - 避免阳光直射
# - 使用漫反射表面
# - 调整相机角度
```

### Q3: 深度查询返回 0

**原因**: 查询点没有有效深度数据

**解决方案**:
```python
# 使用区域查询代替点查询
depth_m = camera.get_depth_in_region(
    x=900, y=500,
    width=120, height=120,
    depth_image=image_pair.depth,
    method='median'  # 使用中值更稳定
)
```

### Q4: 检测精度下降

**原因**: 深度分辨率较低影响远距离目标

**解决方案**:
```python
# 1. 优先检测近距离目标
config = DetectionConfig(
    selection_strategy=SelectionStrategy.NEAREST
)

# 2. 调整检测阈值
config.threshold = 0.6  # 提高阈值

# 3. 限制工作距离
# 在 1-4 米范围内效果最佳
```

### Q5: 与 RealSense 切换

**问题**: 如何在两种相机间切换？

**解决方案**:
```yaml
# 方法 1: 配置文件
camera:
  type: "auto"  # 自动检测

# 方法 2: 代码指定
camera = CameraFactory.create_camera("realsense")  # 或 "orbbec"

# 方法 3: 列出所有相机
cameras = CameraFactory.list_available_cameras()
# 选择需要的相机类型
```

## 技术规格

### Orbbec 咪咕款规格

| 参数 | 规格 |
|------|------|
| **彩色传感器** | |
| 分辨率 | 1920×1080 |
| 帧率 | 30 fps |
| 视场角 | 60° × 49.5° |
| **深度传感器** | |
| 分辨率 | 640×480 |
| 帧率 | 30 fps |
| 技术 | 结构光 |
| 工作距离 | 0.6m - 6.0m |
| 深度精度 | ±2mm @ 1m |
| **接口** | |
| USB | USB 2.0 / 3.0 |
| 功耗 | < 2.5W |
| **环境** | |
| 工作温度 | 0°C - 40°C |
| 存储温度 | -20°C - 60°C |

### 与 RealSense D415 对比

| 特性 | Orbbec 咪咕款 | RealSense D415 |
|------|---------------|----------------|
| 深度技术 | 结构光 | 主动立体视觉 |
| 彩色分辨率 | 1920×1080 | 1920×1080 |
| 深度分辨率 | 640×480 | 1280×720 |
| 最小距离 | 0.6m | 0.3m |
| 最大距离 | 6.0m | 8.0m |
| 室外性能 | 较差 | 较好 |
| 价格 | 较低 | 较高 |
| 功耗 | 较低 | 较高 |

### 适用场景

**Orbbec 适合**:
- 室内环境
- 近距离操作（0.6-4m）
- 成本敏感项目
- 低功耗要求

**RealSense 适合**:
- 室外环境
- 远距离操作（3-8m）
- 高精度要求
- 复杂光照条件

## 更新日志

### v2.0 (2026-02-26)
- ✅ 添加 Orbbec 相机支持
- ✅ 实现自动相机检测
- ✅ 深度处理优化
- ✅ 视觉伺服参数自适应
- ✅ 完整测试覆盖

### v1.0 (2026-01-15)
- 初始版本，仅支持 RealSense

## 参考资料

- [Orbbec SDK 文档](https://github.com/orbbec/pyorbbecsdk)
- [相机迁移计划](ORBBEC_MIGRATION_PLAN.md)
- [系统主文档](../README.md)

## 技术支持

如有问题，请：
1. 查看本文档的常见问题部分
2. 运行测试套件诊断问题
3. 查看系统日志 `logs/camera.log`
4. 提交 Issue 并附上日志信息
