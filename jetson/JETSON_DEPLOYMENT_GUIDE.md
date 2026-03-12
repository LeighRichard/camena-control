# Jetson Nano 部署指南

## 重要说明

**本项目仅支持 Python 3.6 和 TensorRT**

- **Python 版本**: 仅支持 Python 3.6（TensorRT 要求）
- **推理引擎**: 仅支持 TensorRT（Jetson Nano 自带）
- **平台**: 仅支持 Jetson 平台（Jetson Nano / Xavier NX / AGX）

## 为什么仅支持 Python 3.6 和 TensorRT？

1. **TensorRT 要求**: TensorRT 的 Python 绑定仅支持 Python 3.6
2. **最高性能**: TensorRT 是 NVIDIA 的官方推理引擎，性能最优
3. **Jetson 优化**: TensorRT 针对 Jetson 平台深度优化
4. **无需安装**: Jetson Nano 自带 TensorRT，无需额外安装

## 部署步骤

### 前置要求: 确认环境

**Jetson Nano 默认环境已满足所有要求**

```bash
# 检查 Python 版本
python3 --version
# 应该显示: Python 3.6.x

# 检查 TensorRT
python3 -c "import tensorrt; print(f'TensorRT 版本: {tensorrt.__version__}')"
# 应该显示: TensorRT 8.x.x
```

如果未安装 Python 3.6，运行以下命令：

```bash
sudo apt-get update
sudo apt-get install python3.6 python3.6-venv python3.6-dev
```

### 方案一: 使用部署脚本(推荐)

```bash
cd ~/camena-control/jetson
./deploy.sh
```

脚本会:
- 严格检查 Python 3.6 是否已安装
- 检测 Jetson 平台
- 验证 TensorRT 安装
- 使用 `requirements-jetson.txt` 安装依赖
- 提供相机 SDK 安装指导

### 方案二: 手动部署

```bash
# 1. 确认 Python 3.6 已安装
python3 --version
# 应该显示: Python 3.6.x

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install --upgrade pip setuptools wheel
pip install -r requirements-jetson.txt

# 4. 验证 TensorRT
python -c "import tensorrt; print(f'TensorRT 版本: {tensorrt.__version__}')"

# 5. (可选) 安装相机 SDK
# 参考: https://github.com/IntelRealSense/librealsense/blob/master/doc/installation_jetson.md
```

## TensorRT 说明

### TensorRT 优势

1. **最高性能**: FPS 可达 45-50（YOLOv5s）
2. **低延迟**: 20-22ms 推理时间
3. **低内存**: 800MB 内存占用
4. **FP16 支持**: 支持半精度浮点运算

### TensorRT 性能对比

| 推理引擎 | FPS (YOLOv5s) | 内存占用 | 延迟 | Python版本 |
|---------|---------------|----------|------|-----------|
| TensorRT FP16 | 45-50 | 800MB | 20-22ms | 3.6 |
| TensorRT FP32 | 35-40 | 900MB | 25-28ms | 3.6 |

### TensorRT 模型转换

将 PyTorch 模型转换为 TensorRT 引擎：

```bash
# 1. 导出 ONNX 模型
python scripts/export_onnx.py --model yolov5s.pt --output yolov5s.onnx

# 2. 转换为 TensorRT 引擎
trtexec --onnx=yolov5s.onnx --saveEngine=yolov5s.engine --fp16
```

## 相机 SDK 安装方案

### Intel RealSense

**方案 1: 使用 pip 安装**
```bash
# 在虚拟环境中安装
source venv/bin/activate
pip install pyrealsense2
```

**方案 2: 从源码编译**
```bash
# 安装依赖
sudo apt-get install libusb-1.0-0-dev pkg-config libgtk-3-dev
sudo apt-get install libglfw3-dev libgl1-mesa-dev libglu1-mesa-dev

# 克隆源码
git clone https://github.com/IntelRealSense/librealsense.git
cd librealsense

# 编译安装
mkdir build && cd build
cmake .. -DBUILD_PYTHON_BINDINGS=bool:true -DPYTHON_EXECUTABLE=$(which python3)
make -j4
sudo make install
```

**方案 3: 使用 Docker**
```bash
# 使用官方 Docker 镜像
docker pull intelrealsense/realsense-ros
```

### Orbbec

**方案 1: 从源码编译**
```bash
git clone https://github.com/orbbec/pyorbbecsdk.git
cd pyorbbecsdk
mkdir build && cd build
cmake .. -DPYTHON_EXECUTABLE=$(which python3)
make -j4
sudo make install
```

## PyTorch 安装 (Jetson Nano + Python 3.6)

PyTorch 在 Jetson Nano 上需要特殊安装:

```bash
# 访问 NVIDIA 论坛获取最新版本
# https://forums.developer.nvidia.com/t/pytorch-for-jetson/72048

# 示例: 安装 PyTorch 1.10 for Python 3.6
wget https://nvidia.box.com/shared/static/fjtbno0vpo67625sh1u4ftr8rnjwhf6r.whl -O torch-1.10.0-cp36-cp36m-linux_aarch64.whl
pip install torch-1.10.0-cp36-cp36m-linux_aarch64.whl

# 安装 torchvision
sudo apt-get install libjpeg-dev zlib1g-dev libpython3-dev libopenblas-dev libavcodec-dev libavformat-dev libswscale-dev
git clone --branch v0.11.1 https://github.com/pytorch/vision torchvision
cd torchvision
export BUILD_VERSION=0.11.1
python3 setup.py install --user
```

## 性能优化建议

### 1. 启用 Jetson Nano 性能模式

```bash
# 最大性能模式
sudo nvpmodel -m 0
sudo jetson_clocks

# 检查状态
sudo jetson_clocks --show
```

### 2. 增加交换空间(可选)

```bash
# 创建 4GB 交换文件
sudo fallocate -l 4G /var/swapfile
sudo chmod 600 /var/swapfile
sudo mkswap /var/swapfile
sudo swapon /var/swapfile

# 添加到 /etc/fstab 实现开机自动挂载
echo '/var/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
```

### 3. 使用 FP16 模型

TensorRT 支持 FP16（半精度）运算，可以显著提升性能：

```bash
# 转换为 FP16 引擎
trtexec --onnx=model.onnx --saveEngine=model.engine --fp16
```

## 常见问题

### Q1: 为什么仅支持 Python 3.6？

**A**: TensorRT 的 Python 绑定仅支持 Python 3.6:
- TensorRT 是 NVIDIA 官方推理引擎
- Python 3.6 是 Jetson Nano 默认版本
- 无需额外安装或编译

### Q2: 我可以使用其他推理引擎吗？

**A**: 不可以。本项目仅支持 TensorRT:
- TensorRT 性能最优
- 针对 Jetson 平台深度优化
- Jetson Nano 自带，无需安装

### Q3: 如何检查 TensorRT 是否正常工作？

**A**: 运行以下命令:
```bash
python -c "import tensorrt; print(f'TensorRT 版本: {tensorrt.__version__}')"
# 应该显示: TensorRT 8.x.x
```

### Q4: 内存不足

**问题**: Jetson Nano 只有 4GB 内存
**解决**:
1. 增加交换空间(见上文)
2. 使用轻量级模型(YOLOv5s, MobileNet)
3. 降低推理分辨率
4. 使用 FP16 模型

### Q5: GPU 加速不生效

**问题**: TensorRT 使用 CPU
**解决**:
```bash
# 检查 CUDA 是否可用
python -c "import torch; print(torch.cuda.is_available())"

# 检查 TensorRT
python -c "import tensorrt as trt; print(trt.get_version())"
```

## 验证安装

```bash
# 验证 TensorRT
python -c "import tensorrt; print(f'TensorRT 版本: {tensorrt.__version__}')"

# 运行性能测试
python scripts/benchmark_detector.py --engine model.engine
```

## 参考资源

- [Jetson Nano 开发者指南](https://developer.nvidia.com/embedded/learn/get-started-jetson-nano-devkit)
- [TensorRT 文档](https://docs.nvidia.com/deeplearning/tensorrt/)
- [PyTorch for Jetson](https://forums.developer.nvidia.com/t/pytorch-for-jetson/72048)
- [RealSense Jetson 安装](https://github.com/IntelRealSense/librealsense/blob/master/doc/installation_jetson.md)
- [Jetson 性能优化](https://docs.nvidia.com/jetson/l4t/index.html#page/Tegra%2520Linux%2520Driver%2520Package%2520Development%2520Guide%2Fpower_mgmt_nano_group.html%23)
