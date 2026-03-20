# 相机位置控制系统 - Jetson Nano 端

基于深度相机的相机位置控制与自动拍摄系统，使用深度学习进行农作物目标检测。

## 核心特性

- **TensorRT 推理引擎**: 最高性能，FPS可达45-50
- **Python 3.6 专用**: 完美兼容 Jetson Nano 默认环境
- **Jetson 平台专用**: 针对 Jetson Nano 优化
- **一键部署**: 自动化部署脚本

## 系统要求

- **硬件**: Jetson Nano / Jetson Xavier NX / Jetson AGX
- **操作系统**: JetPack 4.x (Ubuntu 18.04)
- **Python**: 仅支持 Python 3.6
- **推理引擎**: TensorRT 8.x（Jetson 自带）

## 快速开始

### 一键部署

**Jetson Nano:**
```bash
git clone https://github.com/LeighRichard/camena-control.git
cd camena-control/jetson
chmod +x deploy.sh
./deploy.sh
```

详细部署指南请查看: [JETSON_DEPLOYMENT_GUIDE.md](JETSON_DEPLOYMENT_GUIDE.md)

## 支持的深度相机

系统支持以下深度相机：
- **Intel RealSense D415/D435** - 原始支持
- **奥比中光咪咕款** - 新增支持（v2.0+）
- 自动检测和切换

## 项目结构

```
jetson/
├── src/
│   ├── camera/      # 相机控制模块（支持 RealSense 和 Orbbec）
│   ├── comm/        # 串口通信模块
│   ├── scheduler/   # 任务调度模块
│   ├── state/       # 状态管理模块
│   ├── vision/      # 视觉处理和目标检测模块（TensorRT）
│   └── web/         # Web 界面模块
├── tests/           # 测试代码
├── docs/            # 文档
│   └── ORBBEC_SETUP.md  # Orbbec 相机设置指南
└── pyproject.toml   # 项目配置
```

## 安装

### 基础安装

```bash
pip install -e ".[dev]"
```

### TensorRT（已预装）

Jetson Nano 自带 TensorRT，无需额外安装：

```bash
# 验证 TensorRT 安装
python -c "import tensorrt; print(f'TensorRT 版本: {tensorrt.__version__}')"
```

### 相机 SDK 安装

根据你使用的相机类型安装对应的 SDK：

**Intel RealSense:**
```bash
pip install pyrealsense2
```

**奥比中光 Orbbec:**
```bash
pip install pyorbbecsdk>=1.3.0
```

**两者都安装（推荐）:**
```bash
pip install pyrealsense2 pyorbbecsdk>=1.3.0
```

系统会自动检测可用的相机并使用。

## 快速开始

### 1. ONNX Runtime快速上手

```bash
# 安装ONNX Runtime
pip install onnxruntime-gpu

# 转换模型为ONNX格式
python scripts/convert_to_onnx.py --model models/yolov5s.pt --output models/yolov5s.onnx

# 验证安装
python scripts/test_onnx_support.py

# 性能测试
python scripts/benchmark_detector.py --model models/yolov5s.onnx
```

详细指南请查看: [ONNX Runtime快速开始](QUICKSTART_ONNX.md)

### 2. 配置相机类型

编辑 `config/system_config.yaml`：

```yaml
camera:
  type: "auto"  # 可选: "auto", "realsense", "orbbec"
  # ... 其他配置
```

- `auto`: 自动检测（优先 Orbbec，后备 RealSense）
- `realsense`: 强制使用 RealSense
- `orbbec`: 强制使用 Orbbec

### 3. 运行系统

```bash
python main.py
```

### 4. 查看相机信息

```python
from src.camera.factory import CameraFactory

# 列出所有可用相机
cameras = CameraFactory.list_available_cameras()
for cam in cameras:
    print(f"{cam['type']}: {cam['model']}")

# 自动创建相机
camera = CameraFactory.create_camera("auto")
if camera:
    print(f"使用相机: {camera.camera_type} - {camera.camera_model}")
```

## 运行测试

```bash
# 运行所有测试
pytest

# 运行相机相关测试
pytest tests/test_orbbec_controller.py
pytest tests/test_camera_factory.py
pytest tests/test_orbbec_integration.py

# 运行硬件测试（需要真实相机）
pytest -m hardware
```

## 文档

### ONNX Runtime相关
- [ONNX Runtime快速开始](QUICKSTART_ONNX.md) - 5分钟快速上手
- [ONNX Runtime使用指南](docs/ONNX_RUNTIME_USAGE_GUIDE.md) - 详细使用说明
- [TensorRT兼容性解决方案](docs/TENSORRT_PYTHON_COMPATIBILITY_SOLUTION.md) - 技术方案详解
- [实施总结](docs/ONNX_RUNTIME_IMPLEMENTATION_SUMMARY.md) - 完整实施报告

### 相机相关
- [Orbbec 相机设置指南](docs/ORBBEC_SETUP.md) - Orbbec 相机详细配置
- [迁移计划](docs/ORBBEC_MIGRATION_PLAN.md) - 从 RealSense 迁移到 Orbbec 的详细计划

## 相机特性对比

| 特性 | RealSense D415 | Orbbec 咪咕款 |
|------|----------------|---------------|
| 彩色分辨率 | 1920×1080 @ 30fps | 1920×1080 @ 30fps |
| 深度分辨率 | 1280×720 @ 30fps | 640×480 @ 30fps |
| 最小距离 | 0.3m | 0.6m |
| 最大距离 | 8.0m | 6.0m |
| 深度技术 | 主动立体视觉 | 结构光 |
| 价格 | 较高 | 较低 |

## 故障排除

### 相机未检测到

```bash
# 检查 SDK 安装
python -c "import pyorbbecsdk; print(pyorbbecsdk.__version__)"
python -c "import pyrealsense2; print(pyrealsense2.__version__)"

# 检查设备连接
lsusb | grep -i orbbec
lsusb | grep -i intel
```

### 深度图像质量问题

Orbbec 相机使用结构光技术，在以下情况下可能受影响：
- 强光环境（室外阳光直射）
- 反光表面
- 距离过近（< 0.6m）或过远（> 6m）

解决方案：
- 调整环境光照
- 使用深度滤波（系统已自动启用）
- 调整相机位置和角度

## 许可证

MIT License
