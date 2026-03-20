#!/bin/bash
# 更新代码脚本

echo "正在更新代码..."
cd ~/projects/camena-control/jetson
git fetch origin
git reset --hard origin/main
echo "代码已更新到最新版本"
echo "请运行: python3 main.py"
