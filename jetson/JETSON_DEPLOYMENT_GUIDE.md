# Jetson Nano 部署指南

## 重要说明

**本项目要求使用 Python 3.9**

部署脚本会严格检查 Python 版本,只支持 Python 3.9.x,不支持其他版本。

## 问题诊断

### 已修复的问题

1. **BOM 编码问题**: `deploy.sh` 文件包含 UTF-8 BOM,导致 shebang 失效
   - 状态: ✅ 已修复
   - 解决方案: 已移除 BOM 标记

2. **依赖兼容性问题**: `pyrealsense2` 和 `pyorbbecsdk` 在 Python 3.13 + ARM 架构上没有预编译包
   - 状态: ✅ 已修复
   - 解决方案: 创建了 `requirements-jetson.txt`,移除了相机 SDK 依赖

3. **Python 版本统一**: 项目统一使用 Python 3.9
   - 状态: ✅ 已完成
   - 解决方案: 更新了所有配置文件和部署脚本

## 部署步骤

### 前置要求: 安装 Python 3.9

**必须先安装 Python 3.9,否则部署脚本会失败**

#### 方法 1: 使用 deadsnakes PPA (推荐)

```bash
sudo apt-get update
sudo apt-get install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.9 python3.9-venv python3.9-dev python3.9-distutils
```

#### 方法 2: 从源码编译

```bash
# 安装编译依赖
sudo apt-get install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev wget libbz2-dev

# 下载 Python 3.9
wget https://www.python.org/ftp/python/3.9.18/Python-3.9.18.tgz
tar -xf Python-3.9.18.tgz
cd Python-3.9.18

# 配置和编译
./configure --enable-optimizations
make -j4
sudo make altinstall

# 验证安装
python3.9 --version
```

### 方案一: 使用部署脚本(推荐)

```bash
cd ~/camena-control/jetson
./deploy.sh
```

脚本会:
- 严格检查 Python 3.9 是否已安装
- 检测 Jetson Nano 平台
- 使用 `requirements-jetson.txt` 安装依赖
- 提供相机 SDK 安装指导

**注意**: 如果未安装 Python 3.9,脚本会退出并显示安装说明。

### 方案二: 手动部署

```bash
# 1. 确认 Python 3.9 已安装
python3.9 --version
# 应该显示: Python 3.9.x

# 2. 创建虚拟环境
python3.9 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install --upgrade pip setuptools wheel
pip install -r requirements-jetson.txt

# 4. 安装 ONNX Runtime GPU 版本
pip install onnxruntime-gpu

# 5. (可选) 安装相机 SDK
# 参考: https://github.com/IntelRealSense/librealsense/blob/master/doc/installation_jetson.md
```

## Python 3.9 安装 (Jetson Nano)

**本项目强制要求 Python 3.9,不支持其他版本**

如果系统没有 Python 3.9,必须先安装才能继续部署。

### 方法 1: 使用 deadsnakes PPA (推荐)

```bash
sudo apt-get update
sudo apt-get install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.9 python3.9-venv python3.9-dev python3.9-distutils

# 验证安装
python3.9 --version
```

### 方法 2: 从源码编译

```bash
# 安装编译依赖
sudo apt-get install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev wget libbz2-dev

# 下载 Python 3.9
wget https://www.python.org/ftp/python/3.9.18/Python-3.9.18.tgz
tar -xf Python-3.9.18.tgz
cd Python-3.9.18

# 配置和编译
./configure --enable-optimizations
make -j4
sudo make altinstall

# 验证安装
python3.9 --version
```

**重要**: 安装完成后,运行 `python3.9 --version` 确认版本为 3.9.x

## 相机 SDK 安装方案

### Intel RealSense

**方案 1: 使用 Python 3.9 (推荐)**
```bash
# Python 3.9 有更好的包支持
python3.9 -m venv venv
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
cmake .. -DBUILD_PYTHON_BINDINGS=bool:true -DPYTHON_EXECUTABLE=$(which python3.9)
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
cmake .. -DPYTHON_EXECUTABLE=$(which python3.9)
make -j4
sudo make install
```

## PyTorch 安装 (Jetson Nano + Python 3.9)

PyTorch 在 Jetson Nano 上需要特殊安装:

```bash
# 访问 NVIDIA 论坛获取最新版本
# https://forums.developer.nvidia.com/t/pytorch-for-jetson/72048

# 示例: 安装 PyTorch 1.12 for Python 3.9
wget https://nvidia.box.com/shared/static/i8pukc49h3lhak4kkn67tggsj3oena0i.whl -O torch-1.12.0a0+2c916ef.nv22.3-cp39-cp39-linux_aarch64.whl
pip install torch-1.12.0a0+2c916ef.nv22.3-cp39-cp39-linux_aarch64.whl

# 安装 torchvision
sudo apt-get install libjpeg-dev zlib1g-dev libpython3-dev libopenblas-dev libavcodec-dev libavformat-dev libswscale-dev
git clone --branch v0.13.0 https://github.com/pytorch/vision torchvision
cd torchvision
export BUILD_VERSION=0.13.0
python3.9 setup.py install --user
```

## 性能优化建议

### 1. 使用 ONNX Runtime GPU 版本

```bash
pip install onnxruntime-gpu
```

### 2. 启用 Jetson Nano 性能模式

```bash
# 最大性能模式
sudo nvpmodel -m 0
sudo jetson_clocks

# 检查状态
sudo jetson_clocks --show
```

### 3. 增加交换空间(可选)

```bash
# 创建 4GB 交换文件
sudo fallocate -l 4G /var/swapfile
sudo chmod 600 /var/swapfile
sudo mkswap /var/swapfile
sudo swapon /var/swapfile

# 添加到 /etc/fstab 实现开机自动挂载
echo '/var/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
```

## 常见问题

### Q1: 为什么只支持 Python 3.9?

**A**: Python 3.9 是经过验证的最佳版本:
- 所有依赖包都有完整的 Python 3.9 支持
- Intel RealSense 和 Orbbec SDK 完全兼容
- PyTorch 和 ONNX Runtime 有预编译包
- Jetson Nano 平台优化良好
- 避免了 Python 3.13 等新版本的兼容性问题

### Q2: 我可以使用 Python 3.8 或 3.10 吗?

**A**: 不可以。部署脚本会严格检查版本,只接受 Python 3.9.x。使用其他版本会导致:
- 部署脚本直接退出
- 依赖包可能无法安装
- 运行时可能出现兼容性问题

### Q3: 如何检查当前 Python 版本?

**A**: 运行以下命令:
```bash
python3.9 --version
# 应该显示: Python 3.9.x
```

### Q4: 系统已有其他 Python 版本,如何处理?

**A**: 可以同时安装多个 Python 版本:
```bash
# 安装 Python 3.9
sudo apt-get install python3.9 python3.9-venv python3.9-dev

# 使用 Python 3.9 创建虚拟环境
python3.9 -m venv venv
source venv/bin/activate
```

### Q2: 内存不足

**问题**: Jetson Nano 只有 4GB 内存
**解决**:
1. 增加交换空间(见上文)
2. 使用轻量级模型(YOLOv5s, MobileNet)
3. 降低推理分辨率

### Q3: GPU 加速不生效

**问题**: ONNX Runtime 使用 CPU
**解决**:
```bash
# 检查 CUDA 是否可用
python -c "import torch; print(torch.cuda.is_available())"

# 检查 ONNX Runtime GPU
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
# 应该显示: ['CUDAExecutionProvider', 'CPUExecutionProvider']
```

## 验证安装

```bash
# 运行测试脚本
python scripts/test_onnx_support.py

# 运行性能测试
python scripts/benchmark_detector.py
```

## 参考资源

- [Jetson Nano 开发者指南](https://developer.nvidia.com/embedded/learn/get-started-jetson-nano-devkit)
- [PyTorch for Jetson](https://forums.developer.nvidia.com/t/pytorch-for-jetson/72048)
- [RealSense Jetson 安装](https://github.com/IntelRealSense/librealsense/blob/master/doc/installation_jetson.md)
- [Jetson 性能优化](https://docs.nvidia.com/jetson/l4t/index.html#page/Tegra%2520Linux%2520Driver%2520Package%2520Development%2520Guide%2Fpower_mgmt_nano_group.html%23)
