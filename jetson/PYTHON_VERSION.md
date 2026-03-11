# Python 版本要求

## 项目统一使用 Python 3.9

本项目统一使用 **Python 3.9** 作为开发和运行环境。

### 为什么选择 Python 3.9?

1. **最佳兼容性**
   - 所有依赖包都有良好的 Python 3.9 支持
   - Intel RealSense SDK (pyrealsense2) 完全支持
   - Orbbec SDK (pyorbbecsdk) 完全支持
   - PyTorch 和 ONNX Runtime 完全支持

2. **Jetson Nano 优化**
   - NVIDIA 为 Jetson Nano 提供了 Python 3.9 的预编译包
   - 性能稳定,内存占用合理
   - 避免了 Python 3.13 的兼容性问题

3. **长期支持**
   - Python 3.9 是一个成熟稳定的版本
   - 官方支持到 2025 年 10 月
   - 社区支持广泛

### 版本要求

- **最低版本**: Python 3.9.0
- **最高版本**: Python 3.9.x (不支持 3.10+)
- **推荐版本**: Python 3.9.18 (最新稳定版)

## 安装 Python 3.9

### Windows

1. **官方安装包**
   ```
   下载地址: https://www.python.org/downloads/release/python-3918/
   选择: Windows installer (64-bit)
   ```

2. **安装时勾选**
   - ✅ Add Python 3.9 to PATH
   - ✅ Install pip
   - ✅ Install for all users

3. **验证安装**
   ```cmd
   python --version
   # 应该显示: Python 3.9.x
   ```

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
