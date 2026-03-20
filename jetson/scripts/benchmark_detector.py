#!/usr/bin/env python3
"""
目标检测器性能基准测试

用法:
    python benchmark_detector.py --model models/yolov5s.engine
    python benchmark_detector.py --model models/yolov5s.engine --iterations 100
"""

import argparse
import time
import numpy as np
import logging
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vision.detector import ObjectDetector, DetectionConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def benchmark_detector(
    model_path: str,
    iterations: int = 100,
    warmup: int = 10,
    image_size: tuple = (720, 1280, 3)
):
    """
    性能基准测试
    
    Args:
        model_path: 模型路径
        iterations: 测试迭代次数
        warmup: 预热次数
        image_size: 测试图像尺寸 (H, W, C)
    """
    logger.info("="*60)
    logger.info("目标检测器性能基准测试")
    logger.info("="*60)
    logger.info(f"模型路径: {model_path}")
    logger.info(f"测试迭代: {iterations} 次")
    logger.info(f"预热次数: {warmup} 次")
    logger.info(f"图像尺寸: {image_size}")
    logger.info("="*60 + "\n")
    
    # 创建检测器
    config = DetectionConfig(model_path=model_path)
    detector = ObjectDetector(config)
    
    # 加载模型
    logger.info("加载模型...")
    success, msg = detector.load_model()
    
    if not success:
        logger.error(f"模型加载失败: {msg}")
        return
    
    logger.info(f"✅ 模型加载成功")
    logger.info(f"推理引擎: {detector.get_inference_engine()}")
    logger.info(f"模拟模式: {detector.is_simulation_mode()}")
    
    # 创建测试图像
    logger.info("\n创建测试图像...")
    test_image = np.random.randint(0, 255, image_size, dtype=np.uint8)
    logger.info(f"✅ 测试图像创建完成: {test_image.shape}")
    
    # 预热
    logger.info(f"\n预热中 ({warmup} 次)...")
    for i in range(warmup):
        result = detector.detect(test_image)
        if i == 0:
            logger.info(f"首次推理完成，检测到 {result.target_count} 个目标")
    
    logger.info("✅ 预热完成\n")
    
    # 正式测试
    logger.info(f"开始性能测试 ({iterations} 次)...")
    
    times = {
        'total': [],
        'preprocess': [],
        'inference': [],
        'postprocess': []
    }
    
    for i in range(iterations):
        result = detector.detect(test_image)
        
        times['total'].append(result.total_time)
        times['preprocess'].append(result.preprocess_time)
        times['inference'].append(result.inference_time)
        times['postprocess'].append(result.postprocess_time)
        
        # 每10次显示进度
        if (i + 1) % 10 == 0:
            logger.info(f"进度: {i+1}/{iterations}")
    
    # 计算统计数据
    logger.info("\n" + "="*60)
    logger.info("性能测试结果")
    logger.info("="*60)
    
    for stage, time_list in times.items():
        arr = np.array(time_list)
        logger.info(f"\n{stage.upper()} 阶段:")
        logger.info(f"  平均: {arr.mean():.2f} ms")
        logger.info(f"  最小: {arr.min():.2f} ms")
        logger.info(f"  最大: {arr.max():.2f} ms")
        logger.info(f"  标准差: {arr.std():.2f} ms")
        logger.info(f"  中位数: {np.median(arr):.2f} ms")
    
    # 计算FPS
    avg_total_time = np.mean(times['total'])
    fps = 1000.0 / avg_total_time
    
    logger.info("\n" + "-"*60)
    logger.info(f"平均总延迟: {avg_total_time:.2f} ms")
    logger.info(f"FPS: {fps:.2f}")
    logger.info("-"*60)
    
    # 性能分级
    if fps >= 30:
        grade = "优秀 ⭐⭐⭐⭐⭐"
    elif fps >= 20:
        grade = "良好 ⭐⭐⭐⭐"
    elif fps >= 10:
        grade = "一般 ⭐⭐⭐"
    elif fps >= 5:
        grade = "较差 ⭐⭐"
    else:
        grade = "很差 ⭐"
    
    logger.info(f"性能评级: {grade}")
    logger.info("="*60 + "\n")
    
    # 内存使用
    memory_info = detector.get_memory_usage()
    if memory_info['model_size_mb'] > 0:
        logger.info("内存使用:")
        logger.info(f"  模型大小: {memory_info['model_size_mb']:.2f} MB")
        logger.info(f"  估计GPU内存: {memory_info['estimated_gpu_mb']:.2f} MB")
    
    # 保存结果
    save_results(model_path, times, fps, detector.get_inference_engine())


def save_results(model_path: str, times: dict, fps: float, engine: str):
    """保存测试结果到文件"""
    result_file = os.path.splitext(model_path)[0] + '_benchmark.txt'
    
    with open(result_file, 'w') as f:
        f.write("="*60 + "\n")
        f.write("目标检测器性能基准测试结果\n")
        f.write("="*60 + "\n\n")
        f.write(f"模型: {model_path}\n")
        f.write(f"推理引擎: {engine}\n")
        f.write(f"FPS: {fps:.2f}\n\n")
        
        for stage, time_list in times.items():
            arr = np.array(time_list)
            f.write(f"{stage.upper()}:\n")
            f.write(f"  平均: {arr.mean():.2f} ms\n")
            f.write(f"  最小: {arr.min():.2f} ms\n")
            f.write(f"  最大: {arr.max():.2f} ms\n")
            f.write(f"  标准差: {arr.std():.2f} ms\n\n")
    
    logger.info(f"✅ 测试结果已保存: {result_file}")


def compare_engines(model_paths: list, iterations: int = 50):
    """比较不同推理引擎的性能"""
    logger.info("\n" + "="*60)
    logger.info("推理引擎性能对比")
    logger.info("="*60 + "\n")
    
    results = {}
    
    for model_path in model_paths:
        if not os.path.exists(model_path):
            logger.warning(f"模型不存在，跳过: {model_path}")
            continue
        
        logger.info(f"\n测试模型: {model_path}")
        
        config = DetectionConfig(model_path=model_path)
        detector = ObjectDetector(config)
        
        success, msg = detector.load_model()
        if not success:
            logger.error(f"加载失败: {msg}")
            continue
        
        engine = detector.get_inference_engine()
        logger.info(f"推理引擎: {engine}")
        
        # 测试
        test_image = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
        
        # 预热
        for _ in range(5):
            detector.detect(test_image)
        
        # 测试
        times = []
        for _ in range(iterations):
            result = detector.detect(test_image)
            times.append(result.total_time)
        
        avg_time = np.mean(times)
        fps = 1000.0 / avg_time
        
        results[model_path] = {
            'engine': engine,
            'avg_time': avg_time,
            'fps': fps
        }
        
        logger.info(f"平均延迟: {avg_time:.2f} ms")
        logger.info(f"FPS: {fps:.2f}")
    
    # 显示对比结果
    if len(results) > 1:
        logger.info("\n" + "="*60)
        logger.info("对比结果汇总")
        logger.info("="*60)
        logger.info(f"{'模型':<30} {'引擎':<15} {'延迟(ms)':<12} {'FPS':<10}")
        logger.info("-"*60)
        
        for model_path, data in results.items():
            model_name = os.path.basename(model_path)
            logger.info(f"{model_name:<30} {data['engine']:<15} {data['avg_time']:<12.2f} {data['fps']:<10.2f}")
        
        logger.info("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='目标检测器性能基准测试',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单模型测试
  python benchmark_detector.py --model models/yolov5s.onnx

  # 指定迭代次数
  python benchmark_detector.py --model models/yolov5s.onnx --iterations 100

  # 对比多个模型
  python benchmark_detector.py --compare models/yolov5s.onnx models/yolov5s.engine
        """
    )
    
    parser.add_argument('--model', type=str,
                        help='模型路径')
    parser.add_argument('--iterations', type=int, default=100,
                        help='测试迭代次数 (default: 100)')
    parser.add_argument('--warmup', type=int, default=10,
                        help='预热次数 (default: 10)')
    parser.add_argument('--compare', nargs='+',
                        help='对比多个模型的性能')
    
    args = parser.parse_args()
    
    if args.compare:
        compare_engines(args.compare, args.iterations)
    elif args.model:
        benchmark_detector(args.model, args.iterations, args.warmup)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
