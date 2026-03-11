# Jetson Nano 安装 Python 3.9 完整指南

## 问题说明

Jetson Nano 默认的 Ubuntu 18.04 软件源中没有 Python 3.9 包,需要使用其他方法安装。

## 解决方案

### 方案一: 使用 deadsnakes PPA (推荐)

**注意**: Jetson Nano 是 ARM64 架构,deadsnakes PPA 可能不支持 ARM64。如果失败,请使用方案二。

```bash
# 1. 更新软件源
sudo apt-get update

# 2. 安装依赖
sudo apt-get install -y software-properties-common

# 3. 添加 deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update

# 4. 尝试安装 Python 3.9
sudo apt-get install -y python3.9 python3.9-venv python3.9-dev python3.9-distutils

# 5. 验证安装
python3.9 --version
```

**如果上述命令报错 "无法找到软件包",说明 PPA 不支持 ARM64,请使用方案二。**

### 方案二: 从源码编译安装 (推荐用于 Jetson Nano)

这是最可靠的方法,适用于 ARM64 架构。

#### 步骤 1: 安装编译依赖

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    zlib1g-dev \
    libncurses5-dev \
    libgdbm-dev \
    libnss3-dev \
    libssl-dev \
    libreadline-dev \
    libffi-dev \
    libsqlite3-dev \
    wget \
    libbz2-dev \
    liblzma-dev \
    uuid-dev
```

#### 步骤 2: 下载 Python 3.9 源码

```bash
# 创建临时目录
mkdir -p ~/python_build
cd ~/python_build

# 下载 Python 3.9.18 (最新稳定版)
wget https://www.python.org/ftp/python/3.9.18/Python-3.9.18.tgz

# 解压
tar -xf Python-3.9.18.tgz
cd Python-3.9.18
```

#### 步骤 3: 配置编译选项

```bash
# 配置 (启用优化)
./configure --enable-optimizations --with-lto --with-computed-gotos --with-system-ffi
```

**注意**: `--enable-optimizations` 会增加编译时间,但能提升 Python 性能约 10-20%。

#### 步骤 4: 编译

```bash
# 使用 4 个核心编译 (Jetson Nano 有 4 个 CPU 核心)
make -j4
```

**编译时间**: 约 30-60 分钟 (取决于是否启用优化)

#### 步骤 5: 安装

```bash
# 安装 (使用 altinstall 避免覆盖系统 Python)
sudo make altinstall
```

**重要**: 使用 `altinstall` 而不是 `install`,这样不会覆盖系统默认的 Python 3.6。

#### 步骤 6: 验证安装

```bash
# 检查版本
python3.9 --version
# 应该显示: Python 3.9.18

# 检查安装位置
which python3.9
# 应该显示: /usr/local/bin/python3.9

# 检查 pip
python3.9 -m pip --version
```

#### 步骤 7: 安装 pip (如果需要)

```bash
# 下载 get-pip.py
wget https://bootstrap.pypa.io/get-pip.py

# 使用 Python 3.9 安装 pip
sudo python3.9 get-pip.py
```

#### 步骤 8: 清理编译文件 (可选)

```bash
cd ~
rm -rf ~/python_build
```

### 方案三: 使用 pyenv (适合开发者)

pyenv 可以方便地管理多个 Python 版本。

#### 安装 pyenv

```bash
# 安装依赖
sudo apt-get install -y \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    curl \
    llvm \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libffi-dev \
    liblzma-dev \
    python-openssl \
    git

# 安装 pyenv
curl https://pyenv.run | bash

# 添加到 shell 配置
echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc

# 重新加载配置
source ~/.bashrc
```

#### 使用 pyenv 安装 Python 3.9

```bash
# 安装 Python 3.9.18
pyenv install 3.9.18

# 设置为全局版本 (可选)
pyenv global 3.9.18

# 或在项目目录设置局部版本
cd ~/camena-control/jetson
pyenv local 3.9.18

# 验证
python --version
```

## 验证安装

安装完成后,运行以下命令验证:

```bash
# 检查 Python 3.9
python3.9 --version

# 检查 pip
python3.9 -m pip --version

# 检查虚拟环境
python3.9 -m venv --help
```

## 常见问题

### Q1: 编译时内存不足怎么办?

**A**: Jetson Nano 只有 4GB 内存,编译时可能内存不足。解决方案:

1. **增加交换空间**
   ```bash
   sudo fallocate -l 4G /var/swapfile
   sudo chmod 600 /var/swapfile
   sudo mkswap /var/swapfile
   sudo swapon /var/swapfile
   ```

2. **减少并行编译数**
   ```bash
   make -j2  # 只使用 2 个核心
   ```

3. **禁用优化** (更快但性能稍差)
   ```bash
   ./configure  # 不加 --enable-optimizations
   make -j4
   sudo make altinstall
   ```

### Q2: 编译时间太长怎么办?

**A**: 可以禁用优化来加快编译:

```bash
./configure  # 不加 --enable-optimizations
make -j4
sudo make altinstall
```

编译时间约 10-15 分钟,但 Python 性能会降低约 10-20%。

### Q3: 如何卸载 Python 3.9?

**A**: 如果从源码安装,可以手动删除:

```bash
sudo rm -rf /usr/local/bin/python3.9
sudo rm -rf /usr/local/bin/pip3.9
sudo rm -rf /usr/local/lib/python3.9
sudo rm -rf /usr/local/include/python3.9
```

### Q4: 为什么不用 apt 安装?

**A**: Jetson Nano 的 Ubuntu 18.04 默认软件源只有 Python 3.6,没有更新的版本。ARM64 架构的 PPA 支持也有限。

### Q5: 编译失败怎么办?

**A**: 检查是否安装了所有依赖:

```bash
sudo apt-get install -y \
    build-essential zlib1g-dev libncurses5-dev libgdbm-dev \
    libnss3-dev libssl-dev libreadline-dev libffi-dev \
    libsqlite3-dev wget libbz2-dev liblzma-dev uuid-dev
```

然后清理并重新编译:

```bash
make clean
./configure --enable-optimizations
make -j4
sudo make altinstall
```

## 推荐方案

对于 Jetson Nano,我推荐:

1. **先尝试方案一** (deadsnakes PPA) - 最简单
2. **如果失败,使用方案二** (从源码编译) - 最可靠
3. **如果需要管理多个版本,使用方案三** (pyenv) - 最灵活

## 下一步

安装 Python 3.9 后,可以继续部署:

```bash
cd ~/camena-control/jetson
./cleanup.sh  # 清理旧环境
./deploy.sh   # 重新部署
```

## 参考资源

- [Python 官方下载](https://www.python.org/downloads/)
- [pyenv GitHub](https://github.com/pyenv/pyenv)
- [Jetson Nano 开发者论坛](https://forums.developer.nvidia.com/c/agx-autonomous-machines/jetson-embedded-systems/70)
