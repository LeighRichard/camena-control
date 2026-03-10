#!/usr/bin/env python3
"""
模型设置脚本 - 命令行工具

用法:
    python model_setup.py list              # 列出可用模型
    python model_setup.py download yolov5s  # 下载模型
    python model_setup.py convert yolov5s   # 转换为 TensorRT
    python model_setup.py setup yolov5s     # 一键设置（下载+转换）
    python model_setup.py benchmark yolov5s # 性能测试
    python model_setup.py info yolov5s      # 查看模型信息
    python model_setup.py delete yolov5s    # 删除模型
"""

import sys
import os
import argparse
import logging

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.model_manager import ModelManager, ModelStatus, ModelType

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_progress(message: str):
    """打印进度信息"""
    print(f"  → {message}")


def cmd_list(manager: ModelManager, args):
    """列出模型"""
    print("\n" + "=" * 60)
    print("可用的预定义模型:")
    print("=" * 60)
    
    available = manager.list_available_models()
    for model in available:
        status_icon = {
            ModelStatus.NOT_DOWNLOADED: "⬜",
            ModelStatus.DOWNLOADED: "📦",
            ModelStatus.READY: "✅",
            ModelStatus.ERROR: "❌"
        }.get(model.status, "❓")
        
        print(f"\n{status_icon} {model.name}")
        print(f"   描述: {model.description}")
        print(f"   大小: {model.file_size_mb:.1f}MB")
        print(f"   输入: {model.input_size}")
        print(f"   状态: {model.status.value}")
    
    print("\n" + "-" * 60)
    print("已安装的模型:")
    print("-" * 60)
    
    installed = manager.list_installed_models()
    if not installed:
        print("  (无)")
    else:
        for model in installed:
            print(f"\n  • {model.name} [{model.status.value}]")
            if model.engine_path:
                print(f"    引擎: {model.engine_path}")
            if model.inference_time_ms > 0:
                print(f"    推理: {model.inference_time_ms:.2f}ms ({1000/model.inference_time_ms:.1f} FPS)")
    
    print()


def cmd_download(manager: ModelManager, args):
    """下载模型"""
    model_name = args.model_name
    
    print(f"\n下载模型: {model_name}")
    print("-" * 40)
    
    def progress(p):
        bar_len = 30
        filled = int(bar_len * p)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  下载进度: [{bar}] {p*100:.1f}%", end="", flush=True)
    
    success, msg = manager.download_model(model_name, progress_callback=progress)
    print()  # 换行
    
    if success:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")
        return 1
    
    return 0


def cmd_convert(manager: ModelManager, args):
    """转换模型"""
    model_name = args.model_name
    use_fp16 = not args.fp32
    
    print(f"\n转换模型: {model_name}")
    print(f"精度: {'FP16' if use_fp16 else 'FP32'}")
    print("-" * 40)
    
    success, msg = manager.convert_to_tensorrt(
        model_name,
        use_fp16=use_fp16,
        progress_callback=print_progress
    )
    
    if success:
        print(f"\n✅ {msg}")
    else:
        print(f"\n❌ {msg}")
        return 1
    
    return 0


def cmd_setup(manager: ModelManager, args):
    """一键设置"""
    model_name = args.model_name
    use_fp16 = not args.fp32
    
    print(f"\n一键设置模型: {model_name}")
    print(f"精度: {'FP16' if use_fp16 else 'FP32'}")
    print("=" * 40)
    
    success, msg = manager.setup_default_model(
        model_name,
        use_fp16=use_fp16,
        progress_callback=print_progress
    )
    
    if success:
        print(f"\n✅ {msg}")
        
        # 显示模型信息
        model_info = manager.get_model_info(model_name)
        if model_info and model_info.engine_path:
            print(f"\n模型路径: {model_info.engine_path}")
            print(f"可在配置文件中设置:")
            print(f"  detection:")
            print(f"    model_path: \"{model_info.engine_path}\"")
    else:
        print(f"\n❌ {msg}")
        return 1
    
    return 0


def cmd_benchmark(manager: ModelManager, args):
    """性能测试"""
    model_name = args.model_name
    iterations = args.iterations
    
    print(f"\n性能测试: {model_name}")
    print(f"迭代次数: {iterations}")
    print("-" * 40)
    
    success, results = manager.benchmark_model(model_name, num_iterations=iterations)
    
    if success:
        print(f"\n📊 测试结果:")
        print(f"   模型: {results['model_name']}")
        print(f"   精度: {results['precision']}")
        print(f"   输入: {results['input_size']}")
        print(f"   平均: {results['avg_time_ms']:.2f}ms")
        print(f"   最小: {results['min_time_ms']:.2f}ms")
        print(f"   最大: {results['max_time_ms']:.2f}ms")
        print(f"   标准差: {results['std_time_ms']:.2f}ms")
        print(f"   FPS: {results['fps']:.1f}")
        print(f"   引擎大小: {results['engine_size_mb']:.1f}MB")
    else:
        print(f"\n❌ 测试失败: {results.get('error', '未知错误')}")
        return 1
    
    return 0


def cmd_info(manager: ModelManager, args):
    """查看模型信息"""
    model_name = args.model_name
    
    model_info = manager.get_model_info(model_name)
    
    if not model_info:
        print(f"❌ 模型未找到: {model_name}")
        return 1
    
    print(f"\n模型信息: {model_name}")
    print("=" * 40)
    print(f"  类型: {model_info.model_type.value}")
    print(f"  版本: {model_info.version}")
    print(f"  描述: {model_info.description}")
    print(f"  状态: {model_info.status.value}")
    print(f"  精度: {model_info.precision}")
    print(f"  输入尺寸: {model_info.input_size}")
    print(f"  类别数: {model_info.num_classes}")
    
    if model_info.onnx_path:
        print(f"  ONNX: {model_info.onnx_path}")
    if model_info.engine_path:
        print(f"  引擎: {model_info.engine_path}")
    if model_info.file_size_mb > 0:
        print(f"  文件大小: {model_info.file_size_mb:.1f}MB")
    if model_info.inference_time_ms > 0:
        print(f"  推理时间: {model_info.inference_time_ms:.2f}ms")
    
    return 0


def cmd_delete(manager: ModelManager, args):
    """删除模型"""
    model_name = args.model_name
    
    if not args.yes:
        confirm = input(f"确定要删除模型 {model_name}? [y/N]: ")
        if confirm.lower() != 'y':
            print("已取消")
            return 0
    
    success, msg = manager.delete_model(model_name)
    
    if success:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")
        return 1
    
    return 0


def cmd_status(manager: ModelManager, args):
    """显示状态"""
    status = manager.get_status()
    
    print("\n模型管理器状态")
    print("=" * 40)
    print(f"  模型目录: {status['models_dir']}")
    print(f"  TensorRT: {'✅ 可用' if status['tensorrt_available'] else '❌ 不可用'}")
    print(f"  已安装模型: {status['total_models']}")
    print(f"  已就绪模型: {status['ready_models']}")
    print(f"  已下载模型: {status['downloaded_models']}")
    print(f"  预定义模型: {status['available_predefined']}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='模型管理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s list                    列出所有可用模型
  %(prog)s setup yolov5s           一键设置 YOLOv5s（推荐）
  %(prog)s setup yolov5n           一键设置 YOLOv5n（更轻量）
  %(prog)s download yolov5s        仅下载模型
  %(prog)s convert yolov5s         转换为 TensorRT
  %(prog)s benchmark yolov5s       性能测试
  %(prog)s info yolov5s            查看模型信息
  %(prog)s delete yolov5s          删除模型
        """
    )
    
    parser.add_argument(
        '--models-dir', '-d',
        default='models',
        help='模型目录 (默认: models)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # list 命令
    subparsers.add_parser('list', help='列出可用模型')
    
    # status 命令
    subparsers.add_parser('status', help='显示管理器状态')
    
    # download 命令
    p_download = subparsers.add_parser('download', help='下载模型')
    p_download.add_argument('model_name', help='模型名称')
    
    # convert 命令
    p_convert = subparsers.add_parser('convert', help='转换为 TensorRT')
    p_convert.add_argument('model_name', help='模型名称')
    p_convert.add_argument('--fp32', action='store_true', help='使用 FP32（默认 FP16）')
    
    # setup 命令
    p_setup = subparsers.add_parser('setup', help='一键设置（下载+转换）')
    p_setup.add_argument('model_name', help='模型名称')
    p_setup.add_argument('--fp32', action='store_true', help='使用 FP32（默认 FP16）')
    
    # benchmark 命令
    p_bench = subparsers.add_parser('benchmark', help='性能测试')
    p_bench.add_argument('model_name', help='模型名称')
    p_bench.add_argument('--iterations', '-n', type=int, default=100, help='迭代次数')
    
    # info 命令
    p_info = subparsers.add_parser('info', help='查看模型信息')
    p_info.add_argument('model_name', help='模型名称')
    
    # delete 命令
    p_delete = subparsers.add_parser('delete', help='删除模型')
    p_delete.add_argument('model_name', help='模型名称')
    p_delete.add_argument('-y', '--yes', action='store_true', help='跳过确认')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # 创建管理器
    manager = ModelManager(args.models_dir)
    
    # 执行命令
    commands = {
        'list': cmd_list,
        'status': cmd_status,
        'download': cmd_download,
        'convert': cmd_convert,
        'setup': cmd_setup,
        'benchmark': cmd_benchmark,
        'info': cmd_info,
        'delete': cmd_delete,
    }
    
    return commands[args.command](manager, args)


if __name__ == '__main__':
    sys.exit(main())
