#!/bin/bash
echo "设置 OpenNI2 环境变量..."
export OPENNI2_REDIST="/home/richard/OpenNI-Linux-Arm64-2.3/Redist"
export LD_LIBRARY_PATH="/home/richard/OpenNI-Linux-Arm64-2.3/lib:$LD_LIBRARY_PATH"
echo "✓ 环境已设置"
echo "OPENNI2_REDIST=$OPENNI2_REDIST"
echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
