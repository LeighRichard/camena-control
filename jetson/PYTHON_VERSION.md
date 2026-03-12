# Python 版本要求

## 项目仅支持 Python 3.6

本项目**仅支持 Python 3.6**，这是 TensorRT 的要求。

### 为什么仅支持 Python 3.6？

1. **TensorRT 要求**
   - TensorRT 的 Python 绑定仅支持 Python 3.6
   - TensorRT 是 NVIDIA 官方推理引擎，性能最优
   - 无法在更高版本的 Python 上使用 TensorRT

2. **Jetson Nano 默认版本**
   - Jetson Nano 默认安装 Python 3.6
   - 无需额外安装或编译 Python
   - 与 Jetson 平台完美兼容

3. **最高性能**
   - TensorRT 是 NVIDIA 官方推理引擎
   - 针对 Jetson 平台深度优化
   - FPS 可达 45-50（YOLOv5s）

### 版本要求

- **唯一支持版本**: Python 3.6.x
- **不支持**: Python 3.7, 3.8, 3.9, 3.10, 3.11
- **原因**: TensorRT Python 绑定限制

## 安装 Python 3.6

### Jetson Nano（默认已安装）

Jetson Nano 默认已安装 Python 3.6，无需额外操作：

```bash
# 检查版本
python3 --version
# 应该显示: Python 3.6.x

# 或
python3.6 --version
```

如果未安装：

```bash
sudo apt-get update
sudo apt-get install python3.6 python3.6-venv python3.6-dev
```

### 其他平台

**本项目仅支持 Jetson 平台**，不支持 Windows、macOS 或其他 Linux 发行版。

## 验证安装

```bash
# 检查 Python 版本
python3 --version
# 必须显示: Python 3.6.x

# 检查 TensorRT
python3 -c "import tensorrt; print(f'TensorRT 版本: {tensorrt.__version__}')"
# 应该显示: TensorRT 8.x.x
```

## 常见问题

### Q: 为什么不支持 Python 3.7+？

**A**: TensorRT 的 Python 绑定仅支持 Python 3.6。这是 NVIDIA 的限制，无法绕过。

### Q: 我可以使用 ONNX Runtime 吗？

**A**: 不可以。本项目仅支持 TensorRT，不支持 ONNX Runtime 或其他推理引擎。

### Q: 如何在 Python 3.6 上安装依赖？

**A**: 所有依赖包都支持 Python 3.6：

```bash
pip install -r requirements-jetson.txt
```

## 参考资源

- [TensorRT 文档](https://docs.nvidia.com/deeplearning/tensorrt/)
- [Jetson Nano 开发者指南](https://developer.nvidia.com/embedded/learn/get-started-jetson-nano-devkit)

### Linux (Ubuntu/Debian)

1. **使用 apt 安装**
   ```bash
   sudo apt-get update
   sudo apt-get install python3.9 python3.9-venv python3.9-dev python3.9-distutils
   ```

2. **使用 deadsnakes PPA (推荐)**
   ```bash
   sudo apt-get install software-properties-common
   sudo add-apt-repository ppa:deadsnakes/ppa
   sudo apt-get update
   sudo apt-get install python3.9 python3.9-venv python3.9-dev python3.9-distutils
   ```

3. **验证安装**
   ```bash
   python3.9 --version
   # 应该显示: Python 3.9.x
   ```

### Jetson Nano

Jetson Nano 通常预装 Python 3.6,需要额外安装 Python 3.9:

```bash
# 方法 1: 使用 deadsnakes PPA
sudo apt-get install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.9 python3.9-venv python3.9-dev python3.9-distutils

# 方法 2: 从源码编译 (如果 PPA 不可用)
# 参考: JETSON_DEPLOYMENT_GUIDE.md
```

## 项目配置文件

所有配置文件已统一设置为 Python 3.9:

### 1. pyproject.toml
```toml
requires-python = ">=3.9,<3.10"
```

### 2. requirements.txt
```txt
# 项目统一使用 Python 3.9
```

### 3. requirements-jetson.txt
```txt
# 推荐使用 Python 3.9 (最佳兼容性)
```

## 部署脚本

部署脚本会自动检测并使用 Python 3.9:

### Linux/macOS (deploy.sh)
- 优先检测 `python3.9`
- 如果未找到,检查其他 Python 3 版本
- 如果版本不匹配,给出警告和安装建议

### Windows (deploy.bat)
- 优先检测 `python3.9`
- 检查默认 `python` 命令
- 严格验证版本为 3.9.x
- 提供下载链接和安装指导

## 常见问题

### Q1: 我已经安装了 Python 3.10/3.11/3.12,可以使用吗?

**A**: 不建议。项目配置为严格使用 Python 3.9,使用其他版本可能导致:
- 依赖包兼容性问题
- 相机 SDK 无法安装
- PyTorch 版本不匹配

### Q2: 可以同时安装多个 Python 版本吗?

**A**: 可以。你可以同时安装 Python 3.9 和其他版本:
- **Windows**: 安装时选择不同目录,使用 `py -3.9` 命令
- **Linux**: 使用 `python3.9` 命令指定版本
- **虚拟环境**: 为项目创建独立的 Python 3.9 虚拟环境

### Q3: 如何在已有 Python 环境中切换到 3.9?

**A**: 创建虚拟环境时指定 Python 3.9:
```bash
# Linux/macOS
python3.9 -m venv venv
source venv/bin/activate

# Windows
python3.9 -m venv venv
venv\Scripts\activate
```

### Q4: 部署脚本检测不到 Python 3.9?

**A**: 确保:
1. Python 3.9 已正确安装
2. 已添加到系统 PATH
3. 可以在命令行运行 `python3.9 --version` (Linux) 或 `python --version` (Windows)

## 验证 Python 版本

运行以下命令验证 Python 版本:

```bash
# Linux/macOS
python3.9 --version

# Windows
python --version

# 在虚拟环境中
python --version
```

应该显示: `Python 3.9.x`

## 相关文档

- [Jetson Nano 部署指南](JETSON_DEPLOYMENT_GUIDE.md)
- [快速开始指南](QUICKSTART_ONNX.md)
- [使用指南](docs/ONNX_RUNTIME_USAGE_GUIDE.md)
