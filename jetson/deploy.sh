#!/bin/bash
# 一键部署脚本 - 智能相机位置控制系统
# 适用于 Jetson Nano / Ubuntu 18.04 / macOS

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

# 检查工作目录
check_working_directory() {
    if [ ! -f "requirements.txt" ]; then
        log_error "请在 jetson 目录下运行此脚本"
        log_error "当前目录: $(pwd)"
        log_info "正确用法: cd jetson && ./deploy.sh"
        exit 1
    fi
    log_success "工作目录检查通过"
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
            log_success "检测到 Ubuntu/Debian 系统 (版本: $VER)"
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

    # 仅支持 Python 3.6（TensorRT 要求）
    if command -v python3.6 &> /dev/null; then
        PYTHON_CMD="python3.6"
        PYTHON_VERSION=$($PYTHON_CMD --version | awk '{print $2}')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -eq 6 ]; then
            log_success "Python 3.6 已找到: $PYTHON_VERSION"
            log_info "TensorRT 完全支持 Python 3.6"
            return
        else
            log_error "python3.6 命令存在但版本不正确: $PYTHON_VERSION"
            exit 1
        fi
    fi

    # 尝试 python3 命令
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
        PYTHON_VERSION=$($PYTHON_CMD --version | awk '{print $2}')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -eq 6 ]; then
            log_success "Python 3.6 已找到: $PYTHON_VERSION"
            log_info "TensorRT 完全支持 Python 3.6"
            return
        else
            log_error "本项目仅支持 Python 3.6（TensorRT 要求）"
            log_error "当前版本: $PYTHON_VERSION"
            log_info ""
            log_info "Jetson Nano 默认已安装 Python 3.6"
            log_info "如果未安装，请运行:"
            log_info "  sudo apt-get update"
            log_info "  sudo apt-get install python3.6 python3.6-venv python3.6-dev"
            exit 1
        fi
    fi

    # 未找到 Python 3.6
    log_error "未找到 Python 3.6"
    log_error "本项目仅支持 Python 3.6（TensorRT 要求）"
    log_info ""
    log_info "Jetson Nano 默认已安装 Python 3.6"
    log_info "如果未安装，请运行:"
    log_info "  sudo apt-get update"
    log_info "  sudo apt-get install python3.6 python3.6-venv python3.6-dev"
    exit 1
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
    
    # 激活虚拟环境并验证
    source $VENV_DIR/bin/activate
    
    # 验证虚拟环境是否正确激活
    if [[ "$VIRTUAL_ENV" != *"$(pwd)/venv"* ]]; then
        log_error "虚拟环境激活失败"
        exit 1
    fi
    
    log_success "已激活虚拟环境: $(which python)"
}

# 安装 Python 依赖
install_python_dependencies() {
    log_info "安装 Python 依赖..."

    # 升级 pip（带重试机制）
    local max_retries=3
    local retry_count=0

    while [ $retry_count -lt $max_retries ]; do
        if pip install --upgrade pip setuptools wheel; then
            break
        else
            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $max_retries ]; then
                log_warning "pip 升级失败，重试 $retry_count/$max_retries..."
                sleep 2
            else
                log_error "pip 升级失败，请检查网络连接"
                exit 1
            fi
        fi
    done

    # 根据硬件平台选择依赖文件
    local requirements_file="requirements.txt"
    if [ "$HARDWARE" = "jetson_nano" ] || [ "$HARDWARE" = "jetson" ]; then
        if [ -f "requirements-jetson.txt" ]; then
            requirements_file="requirements-jetson.txt"
            log_info "检测到 Jetson 平台，使用 requirements-jetson.txt"
        else
            log_warning "未找到 requirements-jetson.txt，使用默认 requirements.txt"
        fi
    fi

    # 安装基础依赖（带重试机制）
    if [ -f "$requirements_file" ]; then
        log_info "安装 $requirements_file 中的依赖..."
        retry_count=0
        while [ $retry_count -lt $max_retries ]; do
            if pip install -r $requirements_file; then
                break
            else
                retry_count=$((retry_count + 1))
                if [ $retry_count -lt $max_retries ]; then
                    log_warning "依赖安装失败，重试 $retry_count/$max_retries..."
                    sleep 2
                else
                    log_error "依赖安装失败，请检查网络连接或 $requirements_file"
                    exit 1
                fi
            fi
        done
    else
        log_error "未找到 $requirements_file"
        exit 1
    fi
    
    # 根据硬件平台安装特定依赖
    if [ "$HARDWARE" = "jetson_nano" ]; then
        log_info "安装 Jetson Nano 特定依赖..."

        # Jetson Nano 使用 TensorRT（已预装）
        log_success "TensorRT 已在 Jetson Nano 上预装"
        log_info "验证 TensorRT 安装..."
        python -c "import tensorrt; print(f'TensorRT 版本: {tensorrt.__version__}')" || {
            log_warning "TensorRT 导入失败，请检查安装"
            log_info "Jetson Nano 默认已安装 TensorRT"
        }

    elif [ "$HARDWARE" = "jetson" ]; then
        log_info "安装 Jetson 特定依赖..."
        log_success "TensorRT 已在 Jetson 平台上预装"

    else
        log_info "桌面平台不支持 TensorRT"
        log_error "本项目仅支持 Jetson 平台（TensorRT 要求）"
        exit 1
    fi
    
    log_success "Python 依赖安装完成"
}

# 安装相机 SDK
install_camera_sdk() {
    log_info "安装相机 SDK..."

    # 检查是否为非交互模式
    local install_realsense="n"
    local install_orbbec="n"

    if [ "$NON_INTERACTIVE" = "true" ]; then
        log_info "非交互模式：跳过相机 SDK 安装"
        log_info "如需安装，请参考以下说明"
    else
        # Jetson 平台特殊说明
        if [ "$HARDWARE" = "jetson_nano" ] || [ "$HARDWARE" = "jetson" ]; then
            log_warning "=========================================="
            log_warning "Jetson 平台相机 SDK 安装说明"
            log_warning "=========================================="
            log_warning "pyrealsense2 和 pyorbbecsdk 在 Jetson 平台上"
            log_warning "可能没有预编译的 Python 3.13 包"
            log_warning ""
            log_warning "建议方案:"
            log_warning "1. 使用 Python 3.6-3.9 (Jetson Nano 默认 Python)"
            log_warning "2. 从源码编译 SDK"
            log_warning "3. 使用 Docker 容器"
            log_warning "=========================================="
            echo ""
        fi

        # Intel RealSense
        read -p "是否尝试安装 Intel RealSense SDK? (y/n): " install_realsense
        if [ "$install_realsense" = "y" ]; then
            log_info "尝试安装 pyrealsense2..."
            if pip install pyrealsense2; then
                log_success "pyrealsense2 安装成功"
            else
                log_warning "pyrealsense2 安装失败"
                log_info "请参考官方文档从源码编译:"
                log_info "  https://github.com/IntelRealSense/librealsense/blob/master/doc/installation_jetson.md"
            fi
        fi

        # Orbbec
        read -p "是否尝试安装 Orbbec SDK? (y/n): " install_orbbec
        if [ "$install_orbbec" = "y" ]; then
            log_info "尝试安装 pyorbbecsdk..."
            if pip install pyorbbecsdk; then
                log_success "pyorbbecsdk 安装成功"
            else
                log_warning "pyorbbecsdk 安装失败"
                log_info "请参考官方文档从源码编译:"
                log_info "  https://github.com/orbbec/pyorbbecsdk"
            fi
        fi
    fi

    log_success "相机 SDK 安装流程完成"
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
    
    if [ "$NON_INTERACTIVE" = "true" ]; then
        log_info "非交互模式：跳过模型下载"
        log_info "请手动下载模型或使用: python scripts/model_setup.py download yolov5s"
    else
        read -p "是否下载 YOLOv5s ONNX 模型? (y/n): " download_yolo
        if [ "$download_yolo" = "y" ]; then
            log_info "尝试使用 model_setup.py 下载模型..."
            
            # 使用 model_setup.py 下载模型
            if [ -f "scripts/model_setup.py" ]; then
                python scripts/model_setup.py download yolov5s || {
                    log_warning "自动下载失败，请手动下载模型"
                    log_info "方法1: python scripts/model_setup.py download yolov5s"
                    log_info "方法2: python scripts/convert_to_onnx.py --model yolov5s.pt --output models/yolov5s.onnx"
                }
            else
                log_warning "未找到 model_setup.py，请手动下载模型"
                log_info "  python scripts/convert_to_onnx.py --model yolov5s.pt --output models/yolov5s.onnx"
            fi
        fi
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
    
    if [ "$NON_INTERACTIVE" = "true" ]; then
        log_info "非交互模式：跳过测试"
    else
        read -p "是否运行集成测试? (y/n): " run_test
        if [ "$run_test" = "y" ]; then
            log_info "运行 ONNX Runtime 集成测试..."
            python scripts/test_onnx_support.py || log_warning "ONNX 测试失败"
            
            log_info "运行单元测试..."
            pytest tests/ -v || log_warning "部分测试失败"
        fi
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
        
        if [ "$NON_INTERACTIVE" = "true" ]; then
            log_info "非交互模式：跳过系统服务创建"
        else
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
    
    # 检查工作目录
    check_working_directory
    
    # 检测环境
    detect_os
    detect_hardware
    check_python
    
    # 安装依赖
    if [ "$NON_INTERACTIVE" = "true" ]; then
        log_info "非交互模式：自动安装系统依赖"
        install_system_dependencies
    else
        read -p "是否安装系统依赖? (y/n): " install_sys
        if [ "$install_sys" = "y" ]; then
            install_system_dependencies
        fi
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

# 解析命令行参数
while [ "$1" != "" ]; do
    case $1 in
        -y | --yes )    NON_INTERACTIVE="true"
                       ;;
        -h | --help )   echo "用法: ./deploy.sh [-y|--yes]"
                       echo "  -y, --yes  非交互模式，自动安装所有依赖"
                       exit
                       ;;
        * )             echo "未知参数: $1"
                       exit 1
    esac
    shift
done

# 运行主函数
main

