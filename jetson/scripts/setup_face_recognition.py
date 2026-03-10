#!/usr/bin/env python3
"""
人脸识别环境设置脚本

自动安装和配置人脸识别所需的依赖：
1. insightface (推荐，GPU 加速)
2. face_recognition (备选，基于 dlib)

用法:
    python setup_face_recognition.py          # 自动选择最佳方案
    python setup_face_recognition.py --backend insightface
    python setup_face_recognition.py --backend face_recognition
    python setup_face_recognition.py --check  # 仅检查环境
"""

import sys
import os
import subprocess
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def check_package(package_name: str) -> bool:
    """检查包是否已安装"""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False


def check_cuda() -> bool:
    """检查 CUDA 是否可用"""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        pass
    
    # 检查 nvidia-smi
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_package(package: str, extra_args: list = None) -> bool:
    """安装 Python 包"""
    cmd = [sys.executable, '-m', 'pip', 'install', package]
    if extra_args:
        cmd.extend(extra_args)
    
    logger.info(f"  安装: {package}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"  安装失败: {result.stderr}")
            return False
        return True
    except Exception as e:
        logger.error(f"  安装错误: {e}")
        return False


def setup_insightface() -> bool:
    """设置 InsightFace"""
    logger.info("\n设置 InsightFace...")
    logger.info("-" * 40)
    
    # 安装依赖
    packages = [
        'onnxruntime-gpu' if check_cuda() else 'onnxruntime',
        'insightface',
    ]
    
    for pkg in packages:
        if not install_package(pkg):
            return False
    
    # 验证安装
    try:
        from insightface.app import FaceAnalysis
        
        logger.info("  初始化模型（首次运行会下载模型）...")
        app = FaceAnalysis(name='buffalo_sc')
        app.prepare(ctx_id=0 if check_cuda() else -1)
        
        logger.info("✅ InsightFace 设置成功！")
        return True
        
    except Exception as e:
        logger.error(f"❌ InsightFace 验证失败: {e}")
        return False


def setup_face_recognition() -> bool:
    """设置 face_recognition (dlib)"""
    logger.info("\n设置 face_recognition...")
    logger.info("-" * 40)
    
    # 检查 cmake
    try:
        subprocess.run(['cmake', '--version'], capture_output=True)
    except FileNotFoundError:
        logger.warning("  需要安装 cmake")
        logger.info("  Ubuntu: sudo apt install cmake")
        logger.info("  Windows: 从 cmake.org 下载安装")
    
    # 安装 dlib 和 face_recognition
    packages = ['dlib', 'face_recognition']
    
    for pkg in packages:
        if not install_package(pkg):
            logger.warning(f"  {pkg} 安装失败，尝试继续...")
    
    # 验证安装
    try:
        import face_recognition
        logger.info("✅ face_recognition 设置成功！")
        return True
    except ImportError as e:
        logger.error(f"❌ face_recognition 验证失败: {e}")
        return False


def check_environment():
    """检查当前环境"""
    logger.info("\n环境检查")
    logger.info("=" * 40)
    
    # Python 版本
    logger.info(f"Python: {sys.version}")
    
    # CUDA
    cuda_available = check_cuda()
    logger.info(f"CUDA: {'✅ 可用' if cuda_available else '❌ 不可用'}")
    
    # 检查已安装的包
    packages = {
        'insightface': 'InsightFace',
        'face_recognition': 'face_recognition',
        'onnxruntime': 'ONNX Runtime',
        'cv2': 'OpenCV',
        'numpy': 'NumPy',
    }
    
    logger.info("\n已安装的包:")
    for pkg, name in packages.items():
        installed = check_package(pkg)
        status = '✅' if installed else '❌'
        logger.info(f"  {status} {name}")
    
    # 推荐方案
    logger.info("\n推荐:")
    if check_package('insightface'):
        logger.info("  ✅ InsightFace 已就绪，推荐使用")
    elif check_package('face_recognition'):
        logger.info("  ✅ face_recognition 已就绪")
    else:
        if cuda_available:
            logger.info("  建议安装 InsightFace（GPU 加速）")
            logger.info("  运行: python setup_face_recognition.py --backend insightface")
        else:
            logger.info("  建议安装 face_recognition")
            logger.info("  运行: python setup_face_recognition.py --backend face_recognition")


def main():
    parser = argparse.ArgumentParser(description='人脸识别环境设置')
    parser.add_argument(
        '--backend', '-b',
        choices=['auto', 'insightface', 'face_recognition'],
        default='auto',
        help='选择后端 (默认: auto)'
    )
    parser.add_argument(
        '--check', '-c',
        action='store_true',
        help='仅检查环境'
    )
    
    args = parser.parse_args()
    
    if args.check:
        check_environment()
        return 0
    
    logger.info("\n" + "=" * 50)
    logger.info("人脸识别环境设置")
    logger.info("=" * 50)
    
    # 检查环境
    check_environment()
    
    # 选择后端
    backend = args.backend
    if backend == 'auto':
        if check_cuda():
            backend = 'insightface'
            logger.info("\n检测到 CUDA，将安装 InsightFace")
        else:
            backend = 'face_recognition'
            logger.info("\n未检测到 CUDA，将安装 face_recognition")
    
    # 安装
    if backend == 'insightface':
        success = setup_insightface()
    else:
        success = setup_face_recognition()
    
    if success:
        logger.info("\n" + "=" * 50)
        logger.info("设置完成！")
        logger.info("=" * 50)
        logger.info("\n在配置文件中设置:")
        logger.info("  face_recognition:")
        logger.info(f"    backend: \"{backend}\"")
        return 0
    else:
        logger.error("\n设置失败，请检查错误信息")
        return 1


if __name__ == '__main__':
    sys.exit(main())
