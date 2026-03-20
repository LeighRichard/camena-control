#!/bin/bash
# Jetson Nano B01 - Orbbec 相机修复脚本
# 解决 USB 权限和驱动问题

set -e

echo "========================================"
echo "Jetson Nano B01 - Orbbec 相机修复"
echo "========================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. 检查是否为 Jetson 平台
log_info "检查硬件平台..."
if [ -f /proc/device-tree/model ]; then
    MODEL=$(cat /proc/device-tree/model)
    if [[ "$MODEL" == *"Jetson"* ]]; then
        log_info "检测到: $MODEL"
    else
        log_warn "未检测到 Jetson 设备,但继续执行"
    fi
else
    log_warn "无法检测硬件平台"
fi

# 2. 检查 Python 版本
log_info "检查 Python 版本..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
log_info "Python 版本: $PYTHON_VERSION"

if [[ "$PYTHON_VERSION" != *"3.6"* ]]; then
    log_warn "建议使用 Python 3.6 (当前: $PYTHON_VERSION)"
fi

# 3. 安装系统依赖
log_info "安装系统依赖..."
# 跳过 apt-get update 以避免软件源过期问题
# sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    libusb-1.0-0-dev \
    libudev-dev \
    udev 2>/dev/null || {
    log_warn "系统依赖安装失败,尝试继续..."
}

# 4. 创建 USB udev 规则
log_info "配置 USB 权限..."
sudo tee /etc/udev/rules.d/99-orbbec.rules > /dev/null <<EOF
# Orbbec 相机 USB 权限规则
SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666", GROUP="plugdev"
KERNEL=="video*", MODE="0666", GROUP="plugdev"
EOF

log_info "udev 规则已创建: /etc/udev/rules.d/99-orbbec.rules"

# 5. 重新加载 udev 规则
log_info "重新加载 udev 规则..."
sudo udevadm control --reload-rules
sudo udevadm trigger

# 6. 添加用户到 plugdev 组
log_info "添加用户到 plugdev 组..."
sudo usermod -a -G plugdev $USER

# 7. 检查 USB 设备
log_info "检查 USB 设备..."
lsusb_output=$(lsusb 2>/dev/null || echo "")
if echo "$lsusb_output" | grep -qi "2bc5\|orbbec"; then
    log_info "找到 Orbbec 设备:"
    echo "$lsusb_output" | grep -i "2bc5\|orbbec"
else
    log_warn "未找到 Orbbec 设备 (Vendor ID: 2bc5)"
    log_info "请检查:"
    log_info "  1. 相机是否已连接"
    log_info "  2. USB 线缆是否正常"
    log_info "  3. 尝试不同的 USB 端口 (推荐 USB 3.0)"
fi

# 8. 检查 pyorbbecsdk 安装
log_info "检查 pyorbbecsdk 安装..."
if python3 -c "import pyorbbecsdk" 2>/dev/null; then
    log_info "pyorbbecsdk 已安装"
    python3 -c "import pyorbbecsdk; print(f'版本: {pyorbbecsdk.__version__ if hasattr(pyorbbecsdk, \"__version__\") else \"未知\"}')"
else
    log_warn "pyorbbecsdk 未安装"
    log_info "安装命令: pip3 install pyorbbecsdk"
    
    read -p "是否现在安装 pyorbbecsdk? (y/n): " install_sdk
    if [ "$install_sdk" = "y" ]; then
        log_info "安装 pyorbbecsdk..."
        pip3 install pyorbbecsdk || {
            log_error "安装失败"
            log_info "Jetson Nano 可能需要从源码编译"
            log_info "参考: https://github.com/orbbec/pyorbbecsdk"
        }
    fi
fi

# 9. 设置 USB 设备权限 (临时方案)
log_info "设置 USB 设备权限..."
for dev in /dev/bus/usb/*/*; do
    if [ -e "$dev" ]; then
        sudo chmod 666 "$dev" 2>/dev/null || true
    fi
done

# 10. 运行诊断脚本
log_info "运行诊断脚本..."
if [ -f "scripts/diagnose_orbbec.py" ]; then
    python3 scripts/diagnose_orbbec.py
else
    log_warn "诊断脚本不存在: scripts/diagnose_orbbec.py"
fi

echo ""
echo "========================================"
echo "修复完成!"
echo "========================================"
echo ""
echo "重要提示:"
echo "  1. 请重新插拔相机或重启系统"
echo "  2. 如果使用虚拟环境,请激活后再运行程序"
echo "  3. 运行诊断: python3 scripts/diagnose_orbbec.py"
echo "  4. 运行主程序: python3 main.py"
echo ""
echo "如果问题仍然存在:"
echo "  - 检查 USB 连接 (尝试 USB 3.0 端口)"
echo "  - 检查相机供电"
echo "  - 查看系统日志: dmesg | tail -50"
echo "  - 使用 sudo 运行程序 (临时方案)"
echo ""
