# 一键部署指南

## 概述

本项目提供了一键部署脚本，可以自动完成环境配置、依赖安装、系统配置等所有部署步骤。

## 支持的平台

- **Linux** (Ubuntu/Debian, CentOS/RHEL)
- **Jetson Nano** (NVIDIA Jetson 系列)
- **macOS**
- **Windows** (Windows 10/11)

## 快速开始

### Linux / macOS / Jetson Nano

```bash
# 1. 克隆项目
git clone https://github.com/LeighRichard/camena-control.git
cd camena-control/jetson

# 2. 添加执行权限
chmod +x deploy.sh

# 3. 运行部署脚本
./deploy.sh
```

### Windows

```cmd
# 1. 克隆项目
git clone https://github.com/LeighRichard/camena-control.git
cd camena-control\jetson

# 2. 运行部署脚本
deploy.bat
```

## 部署脚本功能

### 1. 环境检测
- ✅ 自动检测操作系统类型
- ✅ 检测硬件平台（Jetson Nano / 桌面）
- ✅ 检查 Python 版本（需要 3.6+）

### 2. 依赖安装
- ✅ 安装系统依赖（git, curl, wget 等）
- ✅ 创建 Python 虚拟环境
- ✅ 安装 Python 依赖包
- ✅ 根据平台自动选择 ONNX Runtime 版本（GPU/CPU）

### 3. 相机 SDK 安装
- ✅ Intel RealSense SDK (pyrealsense2)
- ✅ Orbbec SDK (pyorbbecsdk)
- ✅ 可选择安装

### 4. 系统配置
- ✅ 创建必要的目录结构
- ✅ 生成配置文件模板
- ✅ 创建环境变量文件

### 5. 测试验证
- ✅ 运行 ONNX Runtime 集成测试
- ✅ 运行单元测试套件

### 6. 服务部署
- ✅ 创建启动脚本
- ✅ 创建 systemd 服务（Linux）
- ✅ 配置开机自启动

## 部署后操作

### 1. 激活虚拟环境

**Linux/macOS:**
```bash
source venv/bin/activate
```

**Windows:**
```cmd
venv\Scripts\activate.bat
```

### 2. 编辑配置文件

```bash
# 编辑系统配置
nano config/system_config.yaml

# 编辑环境变量
nano .env
```

### 3. 运行系统

**方式一：直接运行**
```bash
python main.py
```

**方式二：使用启动脚本**

**Linux/macOS:**
```bash
./start.sh
```

**Windows:**
```cmd
start.bat
```

**方式三：使用系统服务（仅 Linux）**
```bash
# 启动服务
sudo systemctl start camera-control

# 查看状态
sudo systemctl status camera-control

# 停止服务
sudo systemctl stop camera-control

# 查看日志
sudo journalctl -u camera-control -f
```

## 高级配置

### 1. 模型转换

如果你有 PyTorch 模型，需要转换为 ONNX 格式：

```bash
python scripts/convert_to_onnx.py \
    --model models/yolov5s.pt \
    --output models/yolov5s.onnx
```

### 2. 性能测试

```bash
python scripts/benchmark_detector.py \
    --model models/yolov5s.onnx \
    --iterations 100
```

### 3. 集成测试

```bash
python scripts/test_onnx_support.py
```

## 故障排除

### 问题1: Python 版本不兼容

**错误信息**: `需要 Python 3.6 或更高版本`

**解决方案**:
```bash
# Ubuntu/Debian
sudo apt-get install python3.8 python3.8-venv

# macOS
brew install python@3.8

# Windows
# 从 python.org 下载安装 Python 3.8+
```

### 问题2: pip 安装失败

**错误信息**: `pip install failed`

**解决方案**:
```bash
# 升级 pip
python -m pip install --upgrade pip

# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题3: ONNX Runtime GPU 版本安装失败

**错误信息**: `onnxruntime-gpu installation failed`

**解决方案**:
```bash
# 安装 CPU 版本
pip install onnxruntime

# 或手动安装 GPU 版本
pip install onnxruntime-gpu==1.10.0
```

### 问题4: 相机 SDK 安装失败

**错误信息**: `pyrealsense2/pyorbbecsdk installation failed`

**解决方案**:
```bash
# Intel RealSense
# 参考: https://github.com/IntelRealSense/librealsense

# Orbbec
# 参考: https://github.com/orbbec/pyorbbecsdk
```

### 问题5: 权限问题

**错误信息**: `Permission denied`

**解决方案**:
```bash
# Linux/macOS
chmod +x deploy.sh
chmod +x start.sh

# 或使用 sudo
sudo ./deploy.sh
```

## 手动部署步骤

如果自动部署脚本失败，可以手动执行以下步骤：

### 1. 安装系统依赖

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv git curl wget
```

**CentOS/RHEL:**
```bash
sudo yum install -y python3-pip git curl wget
```

**macOS:**
```bash
brew install python3 git curl wget
```

**Windows:**
- 安装 Python 3.8+ (从 python.org)
- 安装 Git (从 git-scm.com)

### 2. 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate.bat  # Windows
```

### 3. 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install onnxruntime-gpu  # 或 onnxruntime
```

### 4. 配置系统

```bash
mkdir -p models logs data config
cp config/system_config.yaml.example config/system_config.yaml
cp .env.example .env
```

### 5. 运行测试

```bash
python scripts/test_onnx_support.py
pytest tests/ -v
```

### 6. 启动系统

```bash
python main.py
```

## 部署检查清单

- [ ] Python 3.6+ 已安装
- [ ] 虚拟环境已创建并激活
- [ ] 所有依赖已安装
- [ ] ONNX Runtime 已安装（GPU 或 CPU 版本）
- [ ] 相机 SDK 已安装（如需要）
- [ ] 配置文件已创建
- [ ] 测试已通过
- [ ] 系统可以正常启动

## 性能优化建议

### 1. Jetson Nano 优化

```bash
# 启用最大性能模式
sudo nvpmodel -m 0
sudo jetson_clocks

# 增加 swap 空间
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 2. GPU 加速

```bash
# 确保安装了 GPU 版本的 ONNX Runtime
pip install onnxruntime-gpu

# 验证 GPU 可用
python -c "import torch; print(torch.cuda.is_available())"
```

### 3. 内存优化

```bash
# 限制推理批大小
# 在 config/system_config.yaml 中设置:
# detection:
#   batch_size: 1
```

## 更新和维护

### 更新代码

```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

### 更新模型

```bash
# 下载新模型
python scripts/convert_to_onnx.py --model new_model.pt --output models/new_model.onnx

# 更新配置文件中的模型路径
# config/system_config.yaml
```

### 备份配置

```bash
# 备份配置文件
tar -czf config_backup.tar.gz config/ .env

# 恢复配置
tar -xzf config_backup.tar.gz
```

## 获取帮助

- **文档**: `docs/` 目录
- **快速开始**: `QUICKSTART_ONNX.md`
- **GitHub**: https://github.com/LeighRichard/camena-control
- **问题反馈**: GitHub Issues

## 许可证

MIT License
