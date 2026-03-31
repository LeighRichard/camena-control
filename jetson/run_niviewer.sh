#!/bin/bash
echo "运行 NiViewer..."
export OPENNI2_REDIST="/home/richard/OpenNI-Linux-Arm64-2.3/Redist"
export LD_LIBRARY_PATH="/home/richard/OpenNI-Linux-Arm64-2.3/lib:$LD_LIBRARY_PATH"
if [ -n "" ]; then
    ""
else
    echo "NiViewer 未找到"
fi
