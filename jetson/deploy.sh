#!/bin/bash
# 一键部署脚本 - 智能相机位置控制系统
# 适用于 Jetson Nano / Ubuntu / macOS

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示横幅
show_banner() {
    echo "========================================"
    echo "  智能相机位置控制系统 - 一键部署"
    echo "  Smart Camera Position Control System"
    echo "========================================"
    echo ""
}

# 检测操作系统
detect_os() {
    log_info "检测操作系统..."
    
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
        
        if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
            PKG_MANAGER="apt-get"
            log_success "检测到 Ubuntu/Debian 系统"
        elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
            PKG_MANAGER="yum"
            log_success "检测到 CentOS/RHEL 系统"
        else
            log_warning "未知的 Linux 发行版: $OS"
            PKG_MANAGER="apt-get"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macOS"
        PKG_MANAGER="brew"
        log_success "检测到 macOS 系统"
    else
        log_error "不支持的操作系统"
        exit 1
    fi
}

# 检测硬件平台
detect_hardware() {
    log_info "检测硬件平台..."
    
    if [ -f /proc/device-tree/model ]; then
        MODEL=$(cat /proc/device-tree/model)
        if [[ "$MODEL" == *"Jetson Nano"* ]]; then
            HARDWARE="jetson_nano"
            log_success "检测到 Jetson Nano"
        elif [[ "$MODEL" == *"Jetson"* ]]; then
            HARDWARE="jetson"
            log_success "检测到 Jetson 设备: $MODEL"
        else
            HARDWARE="unknown"
            log_info "硬件平台: $MODEL"
        fi
    else
        HARDWARE="desktop"
        log_info "检测到桌面/服务器平台"
    fi
}

# 检查 Python 版本
check_python() {
    log_info "检查 Python 版本..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 6 ]; then
            PYTHON_CMD="python3"
            log_success "Python 版本: $PYTHON_VERSION"
        else
            log_error "需要 Python 3.6 或更高版本，当前版本: $PYTHON_VERSION"
            exit 1
        fi
    else
        log_error "未找到 Python 3"
        exit 1
    fi
}

# 安装系统依赖
install_system_dependencies() {
    log_info "安装系统依赖..."
    
    if [ "$PKG_MANAGER" = "apt-get" ]; then
        sudo apt-get update
        sudo apt-get install -y \
            python3-pip \
            python3-venv \
            git \
            curl \
            wget \
            libusb-1.0-0-dev \
            libudev-dev \
            libssl-dev \
            libffi-dev
    elif [ "$PKG_MANAGER" = "yum" ]; then
        sudo yum groupinstall -y "Development Tools"
        sudo yum install -y \
            python3-pip \
            git \
            curl \
            wget \
            libusb1-devel \
            systemd-devel \
            openssl-devel \
            libffi-devel
    elif [ "$PKG_MANAGER" = "brew" ]; then
        brew install python3 git curl wget
    fi
    
    log_success "系统依赖安装完成"
}

# 创建虚拟环境
create_virtualenv() {
    log_info "创建 Python 虚拟环境..."
    
    VENV_DIR="venv"
    
    if [ -d "$VENV_DIR" ]; then
        log_warning "虚拟环境已存在，跳过创建"
    else
        $PYTHON_CMD -m venv $VENV_DIR
        log_success "虚拟环境创建完成"
    fi
    
    # 激活虚拟环境
    source $VENV_DIR/bin/activate
    log_info "已激活虚拟环境"
}

# 安装 Python 依赖
install_python_dependencies() {
    log_info "安装 Python 依赖..."
    
    # 升级 pip
    pip install --upgrade pip setuptools wheel
    
    # 安装基础依赖
    if [ -f "requirements.txt" ]; then
        log_info "安装 requirements.txt 中的依赖..."
        pip install -r requirements.txt
    else
        log_error "未找到 requirements.txt"
        exit 1
    fi
    
    # 根据硬件平台安装特定依赖
    if [ "$HARDWARE" = "jetson_nano" ]; then
        log_info "安装 Jetson Nano 特定依赖..."
        
        # Jetson Nano 使用 ONNX Runtime
        pip install onnxruntime-gpu || pip install onnxruntime
        
    elif [ "$HARDWARE" = "jetson" ]; then
        log_info "安装 Jetson 特定依赖..."
        pip install onnxruntime-gpu || pip install onnxruntime
        
    else
        log_info "安装桌面平台依赖..."
        
        # 桌面平台优先使用 GPU 版本
        if command -v nvidia-smi &> /dev/null; then
            log_info "检测到 NVIDIA GPU，安装 GPU 版本依赖..."
            pip install onnxruntime-gpu
        else
            log_info "未检测到 GPU，安装 CPU 版本依赖..."
            pip install onnxruntime
        fi
    fi
    
    log_success "Python 依赖安装完成"
}

# 安装相机 SDK
install_camera_sdk() {
    log_info "安装相机 SDK..."
    
    # Intel RealSense
    read -p "是否安装 Intel RealSense SDK? (y/n): " install_realsense
    if [ "$install_realsense" = "y" ]; then
        log_info "安装 pyrealsense2..."
        pip install pyrealsense2 || log_warning "pyrealsense2 安装失败，可能需要手动安装"
    fi
    
    # Orbbec
    read -p "是否安装 Orbbec SDK? (y/n): " install_orbbec
    if [ "$install_orbbec" = "y" ]; then
        log_info "安装 pyorbbecsdk..."
        pip install pyorbbecsdk || log_warning "pyorbbecsdk 安装失败，可能需要手动安装"
    fi
    
    log_success "相机 SDK 安装完成"
}

# 创建必要的目录
create_directories() {
    log_info "创建必要的目录..."
    
    mkdir -p models
    mkdir -p logs
    mkdir -p data
    mkdir -p config
    
    log_success "目录创建完成"
}

# 下载预训练模型
download_models() {
    log_info "下载预训练模型..."
    
    # 检查是否已有模型
    if [ -f "models/yolov5s.onnx" ]; then
        log_warning "模型文件已存在，跳过下载"
        return
    fi
    
    read -p "是否下载 YOLOv5s ONNX 模型? (y/n): " download_yolo
    if [ "$download_yolo" = "y" ]; then
        log_info "下载 YOLOv5s ONNX 模型..."
        
        # 这里可以添加模型下载逻辑
        # 例如从 GitHub Releases 或其他源下载
        
        log_warning "请手动下载模型或使用转换脚本:"
        log_info "  python scripts/convert_to_onnx.py --model yolov5s.pt --output models/yolov5s.onnx"
    fi
}

# 配置系统
configure_system() {
    log_info "配置系统..."
    
    # 复制配置文件模板
    if [ -f "config/system_config.yaml.example" ]; then
        if [ ! -f "config/system_config.yaml" ]; then
            cp config/system_config.yaml.example config/system_config.yaml
            log_success "已创建配置文件: config/system_config.yaml"
        else
            log_warning "配置文件已存在，跳过"
        fi
    fi
    
    # 复制环境变量模板
    if [ -f ".env.example" ]; then
        if [ ! -f ".env" ]; then
            cp .env.example .env
            log_success "已创建环境变量文件: .env"
        else
            log_warning "环境变量文件已存在，跳过"
        fi
    fi
    
    log_success "系统配置完成"
}

# 运行测试
run_tests() {
    log_info "运行测试..."
    
    read -p "是否运行集成测试? (y/n): " run_test
    if [ "$run_test" = "y" ]; then
        log_info "运行 ONNX Runtime 集成测试..."
        python scripts/test_onnx_support.py
        
        log_info "运行单元测试..."
        pytest tests/ -v || log_warning "部分测试失败"
    fi
    
    log_success "测试完成"
}

# 创建启动脚本
create_startup_script() {
    log_info "创建启动脚本..."
    
    cat > start.sh << 'EOF'
#!/bin/bash
# 启动脚本

# 激活虚拟环境
source venv/bin/activate

# 启动系统
python main.py
EOF
    
    chmod +x start.sh
    
    log_success "启动脚本创建完成: start.sh"
}

# 创建系统服务（仅 Linux）
create_system_service() {
    if [[ "$OSTYPE" != "darwin"* ]]; then
        log_info "创建系统服务..."
        
        read -p "是否创建 systemd 服务? (y/n): " create_service
        if [ "$create_service" = "y" ]; then
            SERVICE_FILE="/etc/systemd/system/camera-control.service"
            
            sudo tee $SERVICE_FILE > /dev/null << EOF
[Unit]
Description=Smart Camera Position Control System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python $(pwd)/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
            
            sudo systemctl daemon-reload
            sudo systemctl enable camera-control
            
            log_success "系统服务创建完成"
            log_info "使用以下命令管理服务:"
            log_info "  sudo systemctl start camera-control   # 启动"
            log_info "  sudo systemctl stop camera-control    # 停止"
            log_info "  sudo systemctl status camera-control  # 状态"
        fi
    fi
}

# 显示部署总结
show_summary() {
    echo ""
    echo "========================================"
    echo "  部署完成！"
    echo "========================================"
    echo ""
    echo "项目目录: $(pwd)"
    echo "Python 环境: $(which python)"
    echo ""
    echo "快速开始:"
    echo "  1. 激活虚拟环境: source venv/bin/activate"
    echo "  2. 编辑配置文件: config/system_config.yaml"
    echo "  3. 运行系统: python main.py"
    echo "  或使用启动脚本: ./start.sh"
    echo ""
    echo "文档:"
    echo "  - 快速开始: QUICKSTART_ONNX.md"
    echo "  - 使用指南: docs/ONNX_RUNTIME_USAGE_GUIDE.md"
    echo "  - 技术方案: docs/TENSORRT_PYTHON_COMPATIBILITY_SOLUTION.md"
    echo ""
    echo "工具:"
    echo "  - 模型转换: python scripts/convert_to_onnx.py"
    echo "  - 性能测试: python scripts/benchmark_detector.py"
    echo "  - 集成测试: python scripts/test_onnx_support.py"
    echo ""
    echo "GitHub: https://github.com/LeighRichard/camena-control"
    echo ""
}

# 主函数
main() {
    show_banner
    
    # 检测环境
    detect_os
    detect_hardware
    check_python
    
    # 安装依赖
    read -p "是否安装系统依赖? (y/n): " install_sys
    if [ "$install_sys" = "y" ]; then
        install_system_dependencies
    fi
    
    # 创建虚拟环境
    create_virtualenv
    
    # 安装 Python 依赖
    install_python_dependencies
    
    # 安装相机 SDK
    install_camera_sdk
    
    # 创建目录
    create_directories
    
    # 下载模型
    download_models
    
    # 配置系统
    configure_system
    
    # 运行测试
    run_tests
    
    # 创建启动脚本
    create_startup_script
    
    # 创建系统服务
    create_system_service
    
    # 显示总结
    show_summary
}

# 运行主函数
main
