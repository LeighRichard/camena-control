# 模型设置指南

本文档介绍如何设置深度学习模型，包括目标检测和人脸识别。

## 快速开始

### 1. 目标检测模型（YOLOv5/YOLOv8）

```bash
cd jetson

# 一键设置推荐模型（YOLOv5s + FP16 量化）
python scripts/model_setup.py setup yolov5s

# 或者选择更轻量的模型（适合资源受限设备）
python scripts/model_setup.py setup yolov5n
```

### 2. 人脸识别

```bash
# 自动检测环境并安装最佳方案
python scripts/setup_face_recognition.py

# 或指定后端
python scripts/setup_face_recognition.py --backend insightface  # GPU 加速
python scripts/setup_face_recognition.py --backend face_recognition  # CPU
```

## 目标检测模型

### 可用模型

| 模型 | 大小 | 速度 | 精度 | 推荐场景 |
|------|------|------|------|----------|
| yolov5n | 4MB | 最快 | 较低 | 资源受限设备 |
| yolov5s | 14MB | 快 | 中等 | **推荐** - 平衡方案 |
| yolov5m | 42MB | 中等 | 较高 | 精度优先 |
| yolov8n | 6MB | 最快 | 较低 | 最新架构 |
| yolov8s | 22MB | 快 | 中等 | 最新架构 |

### 命令行工具

```bash
# 列出所有可用模型
python scripts/model_setup.py list

# 查看管理器状态
python scripts/model_setup.py status

# 下载模型
python scripts/model_setup.py download yolov5s

# 转换为 TensorRT（FP16 量化）
python scripts/model_setup.py convert yolov5s

# 转换为 TensorRT（FP32，不量化）
python scripts/model_setup.py convert yolov5s --fp32

# 一键设置（下载 + 转换）
python scripts/model_setup.py setup yolov5s

# 性能测试
python scripts/model_setup.py benchmark yolov5s

# 查看模型信息
python scripts/model_setup.py info yolov5s

# 删除模型
python scripts/model_setup.py delete yolov5s
```

### 在代码中使用

```python
from src.models import ModelManager

# 创建管理器
manager = ModelManager("models")

# 一键设置模型
success, msg = manager.setup_default_model("yolov5s", use_fp16=True)

# 获取模型路径
model_path = manager.get_best_model_path()
print(f"模型路径: {model_path}")

# 性能测试
success, results = manager.benchmark_model("yolov5s")
print(f"推理速度: {results['avg_time_ms']:.2f}ms ({results['fps']:.1f} FPS)")
```

### 配置文件

设置完成后，更新 `config/system_config.yaml`:

```yaml
detection:
  enabled: true
  model_path: "models/engines/yolov5s_fp16.engine"
  confidence_threshold: 0.5
  nms_threshold: 0.45
```

## 人脸识别

### 后端选择

| 后端 | GPU 加速 | 安装难度 | 精度 | 推荐 |
|------|----------|----------|------|------|
| insightface | ✅ | 简单 | 高 | **有 GPU 时推荐** |
| face_recognition | ❌ | 中等 | 高 | CPU 环境推荐 |

### 安装

```bash
# 检查当前环境
python scripts/setup_face_recognition.py --check

# 自动安装（根据环境选择最佳方案）
python scripts/setup_face_recognition.py

# 指定 InsightFace（需要 CUDA）
python scripts/setup_face_recognition.py --backend insightface

# 指定 face_recognition（纯 CPU）
python scripts/setup_face_recognition.py --backend face_recognition
```

### 配置文件

```yaml
face_recognition:
  enabled: true
  database_path: "face_database"
  detection_threshold: 0.5
  recognition_threshold: 0.6
  backend: "auto"  # auto, insightface, face_recognition
```

### 注册人脸

```python
from src.vision.face_recognition import FaceRecognizer
import cv2

# 创建识别器
recognizer = FaceRecognizer()

# 从图像注册人脸
image = cv2.imread("person.jpg")
image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

success, msg = recognizer.register_face("张三", image_rgb)
print(msg)

# 查看已注册的人脸
names = recognizer.get_registered_names()
print(f"已注册: {names}")
```

## TensorRT 转换说明

### 为什么需要转换？

- **ONNX**: 通用格式，跨平台兼容
- **TensorRT**: NVIDIA 优化格式，推理速度提升 2-10 倍

### 量化选项

| 精度 | 内存占用 | 速度 | 精度损失 |
|------|----------|------|----------|
| FP32 | 100% | 基准 | 无 |
| FP16 | ~50% | ~2x | 极小 |
| INT8 | ~25% | ~4x | 较小（需要校准） |

**推荐使用 FP16**：在 Jetson 上提供最佳的速度/精度平衡。

### 转换要求

- NVIDIA GPU
- TensorRT 8.x+
- CUDA 11.x+
- PyCUDA

在 Jetson 上，这些通常已预装在 JetPack 中。

## 故障排除

### TensorRT 不可用

```
警告: TensorRT 不可用，模型转换功能将受限
```

解决方案：
1. 确保安装了 JetPack（Jetson）或 CUDA Toolkit（桌面 GPU）
2. 安装 TensorRT: `pip install tensorrt`
3. 安装 PyCUDA: `pip install pycuda`

### 模型下载失败

```
下载失败: <urlopen error ...>
```

解决方案：
1. 检查网络连接
2. 手动下载模型文件到 `models/onnx/` 目录
3. 使用代理或镜像源

### InsightFace 安装失败

```
ImportError: No module named 'insightface'
```

解决方案：
```bash
# 安装依赖
pip install onnxruntime-gpu  # 或 onnxruntime（CPU）
pip install insightface

# 如果仍然失败，尝试
pip install insightface --no-deps
pip install albumentations prettytable
```

### face_recognition 安装失败

```
error: dlib requires cmake
```

解决方案：
```bash
# Ubuntu
sudo apt install cmake libboost-all-dev

# 然后重新安装
pip install dlib face_recognition
```

## 性能参考

在 Jetson Nano 上的典型性能：

| 模型 | 精度 | 推理时间 | FPS |
|------|------|----------|-----|
| yolov5n | FP16 | ~25ms | ~40 |
| yolov5s | FP16 | ~45ms | ~22 |
| yolov5m | FP16 | ~90ms | ~11 |

*实际性能取决于具体硬件和配置*

## 下一步

1. 运行 `python scripts/model_setup.py setup yolov5s` 设置目标检测
2. 运行 `python scripts/setup_face_recognition.py` 设置人脸识别
3. 更新 `config/system_config.yaml` 中的模型路径
4. 运行 `python main.py` 启动系统
