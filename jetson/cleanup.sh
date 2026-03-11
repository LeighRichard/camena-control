#!/bin/bash
# 清理脚本 - 清除之前部署失败的环境

set -e

echo "========================================"
echo "  清理旧的部署环境"
echo "========================================"
echo ""

# 检查是否在 jetson 目录
if [ ! -f "requirements.txt" ]; then
    echo "错误: 请在 jetson 目录下运行此脚本"
    exit 1
fi

# 询问用户确认
read -p "是否清理旧的虚拟环境和缓存? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "开始清理..."

# 1. 删除虚拟环境
if [ -d "venv" ]; then
    echo "删除虚拟环境: venv/"
    rm -rf venv
    echo "  ✓ 已删除"
else
    echo "  - 虚拟环境不存在,跳过"
fi

# 2. 删除 Python 缓存
echo "清理 Python 缓存..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
echo "  ✓ 已清理"

# 3. 删除 pip 缓存 (可选)
read -p "是否清理 pip 缓存? (y/n): " clean_pip
if [ "$clean_pip" = "y" ]; then
    echo "清理 pip 缓存..."
    rm -rf ~/.cache/pip 2>/dev/null || true
    echo "  ✓ 已清理"
fi

# 4. 删除临时文件
echo "清理临时文件..."
rm -rf tmp/ 2>/dev/null || true
rm -rf .pytest_cache/ 2>/dev/null || true
rm -rf .coverage 2>/dev/null || true
echo "  ✓ 已清理"

echo ""
echo "========================================"
echo "  清理完成!"
echo "========================================"
echo ""
echo "现在可以运行部署脚本:"
echo "  ./deploy.sh"
echo ""
