#!/usr/bin/env python3
"""
OpenNI2 图像采集脚本
使用 OpenNI2 提供的 NiViewer 或自定义采集

这个脚本演示如何使用 OpenNI2 采集图像
"""

import os
import sys
import subprocess
import time
import signal

def find_niviewer():
    """查找 NiViewer2 可执行文件"""
    possible_paths = [
        os.path.expanduser("~/OpenNI-Linux-Arm64-2.3/Bin/NiViewer2"),
        os.path.expanduser("~/OpenNI-Linux-Arm64-2.3/Bin/NiViewer"),
        "/usr/bin/NiViewer2",
        "/usr/bin/NiViewer",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # 搜索 OpenNI2 目录
    openni2_path = os.path.expanduser("~/OpenNI-Linux-Arm64-2.3")
    if os.path.exists(openni2_path):
        for root, dirs, files in os.walk(openni2_path):
            if 'NiViewer2' in files:
                return os.path.join(root, 'NiViewer2')
            if 'NiViewer' in files:
                return os.path.join(root, 'NiViewer')
    
    return None

def capture_images(output_dir="captured_images"):
    """
    使用 NiViewer 采集图像
    
    Args:
        output_dir: 输出目录
    """
    niviewer = find_niviewer()
    
    if not niviewer:
        print("错误: 未找到 NiViewer")
        print("请确保 OpenNI2 已正确安装")
        return False
    
    print(f"找到 NiViewer: {niviewer}")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 设置环境变量
    openni2_path = os.path.dirname(os.path.dirname(niviewer))
    redist_path = os.path.join(openni2_path, "Redist")
    
    env = os.environ.copy()
    env['OPENNI2_REDIST'] = redist_path
    
    print(f"OPENNI2_REDIST: {redist_path}")
    print(f"启动 NiViewer...")
    print("提示: 在 NiViewer 中按 's' 保存图像,按 'q' 退出")
    
    # 启动 NiViewer
    try:
        process = subprocess.Popen(
            [niviewer],
            env=env,
            cwd=output_dir
        )
        
        # 等待进程结束
        process.wait()
        
        print(f"NiViewer 已退出")
        print(f"图像保存在: {output_dir}")
        
        return True
        
    except KeyboardInterrupt:
        print("\n收到中断信号,停止 NiViewer...")
        process.terminate()
        process.wait()
        return True
    except Exception as e:
        print(f"错误: {e}")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("OpenNI2 图像采集工具")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = "captured_images"
    
    success = capture_images(output_dir)
    
    if success:
        print("\n✓ 图像采集完成")
    else:
        print("\n✗ 图像采集失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
