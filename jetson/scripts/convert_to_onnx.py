#!/usr/bin/env python3
"""
将PyTorch模型转换为ONNX格式

用法:
    python convert_to_onnx.py --model yolov5s.pt --output yolov5s.onnx
    python convert_to_onnx.py --model yolov5s.pt --output yolov5s.onnx --size 640 --batch 1
"""

import argparse
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def convert_yolov5_to_onnx(
    model_path: str,
    output_path: str,
    input_size: int = 640,
    batch_size: int = 1,
    opset_version: int = 11,
    simplify: bool = True
):
    """
    将YOLOv5 PyTorch模型转换为ONNX格式
    
    Args:
        model_path: PyTorch模型路径 (.pt)
        output_path: 输出ONNX路径 (.onnx)
        input_size: 输入尺寸
        batch_size: 批大小
        opset_version: ONNX opset版本
        simplify: 是否使用onnx-simplifier简化模型
    """
    try:
        import torch
        import torch.onnx
    except ImportError:
        logger.error("请安装PyTorch: pip install torch torchvision")
        return False
    
    if not os.path.exists(model_path):
        logger.error(f"模型文件不存在: {model_path}")
        return False
    
    logger.info(f"开始转换模型: {model_path}")
    logger.info(f"输入尺寸: {input_size}x{input_size}, 批大小: {batch_size}")
    
    try:
        # 加载模型
        logger.info("加载PyTorch模型...")
        
        # 尝试使用YOLOv5的加载方式
        try:
            # 如果是YOLOv5官方模型
            sys.path.insert(0, os.path.dirname(model_path))
            from models.experimental import attempt_load
            model = attempt_load(model_path, map_location='cpu')
            model.eval()
        except:
            # 普通PyTorch模型
            model = torch.load(model_path, map_location='cpu')
            if hasattr(model, 'model'):
                model = model.model
            model.eval()
        
        # 创建示例输入
        dummy_input = torch.randn(batch_size, 3, input_size, input_size)
        
        # 导出为ONNX
        logger.info(f"导出ONNX模型 (opset {opset_version})...")
        torch.onnx.export(
            model,
            dummy_input,
            output_path,
            export_params=True,
            opset_version=opset_version,
            do_constant_folding=True,
            input_names=['images'],
            output_names=['output'],
            dynamic_axes={
                'images': {0: 'batch_size'},
                'output': {0: 'batch_size'}
            } if batch_size == 1 else None
        )
        
        logger.info(f"✅ ONNX模型已保存: {output_path}")
        
        # 验证模型
        logger.info("验证ONNX模型...")
        verify_onnx_model(output_path, dummy_input, model)
        
        # 简化模型
        if simplify:
            try:
                import onnx
                from onnxsim import simplify as onnx_simplify
                
                logger.info("简化ONNX模型...")
                onnx_model = onnx.load(output_path)
                simplified_model, check = onnx_simplify(onnx_model)
                
                if check:
                    onnx.save(simplified_model, output_path)
                    logger.info("✅ 模型简化成功")
                else:
                    logger.warning("⚠️ 模型简化验证失败，保留原始模型")
            except ImportError:
                logger.warning("⚠️ onnx-simplifier未安装，跳过简化步骤")
                logger.info("安装方法: pip install onnx-simplifier")
        
        # 显示模型信息
        display_model_info(output_path)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 模型转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_onnx_model(onnx_path: str, dummy_input, pytorch_model):
    """验证ONNX模型"""
    try:
        import onnx
        import onnxruntime as ort
        import numpy as np
        
        # 检查ONNX模型格式
        onnx_model = onnx.load(onnx_path)
        onnx.checker.check_model(onnx_model)
        logger.info("✅ ONNX模型格式正确")
        
        # 比较PyTorch和ONNX Runtime的输出
        logger.info("比较PyTorch和ONNX Runtime输出...")
        
        # PyTorch推理
        with torch.no_grad():
            pytorch_output = pytorch_model(dummy_input)
            if isinstance(pytorch_output, (list, tuple)):
                pytorch_output = pytorch_output[0]
            pytorch_output = pytorch_output.numpy()
        
        # ONNX Runtime推理
        ort_session = ort.InferenceSession(onnx_path)
        onnx_output = ort_session.run(
            None,
            {'images': dummy_input.numpy()}
        )[0]
        
        # 比较输出
        max_diff = np.max(np.abs(pytorch_output - onnx_output))
        mean_diff = np.mean(np.abs(pytorch_output - onnx_output))
        
        logger.info(f"最大差异: {max_diff:.6f}")
        logger.info(f"平均差异: {mean_diff:.6f}")
        
        if max_diff < 1e-4:
            logger.info("✅ 输出一致性验证通过")
        else:
            logger.warning(f"⚠️ 输出差异较大: {max_diff:.6f}")
        
    except Exception as e:
        logger.warning(f"⚠️ 验证失败: {e}")


def display_model_info(onnx_path: str):
    """显示ONNX模型信息"""
    try:
        import onnx
        import os
        
        model = onnx.load(onnx_path)
        
        # 文件大小
        file_size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
        
        # 输入信息
        input_info = []
        for input_tensor in model.graph.input:
            shape = [dim.dim_value for dim in input_tensor.type.tensor_type.shape.dim]
            input_info.append(f"{input_tensor.name}: {shape}")
        
        # 输出信息
        output_info = []
        for output_tensor in model.graph.output:
            shape = [dim.dim_value for dim in output_tensor.type.tensor_type.shape.dim]
            output_info.append(f"{output_tensor.name}: {shape}")
        
        logger.info("\n" + "="*50)
        logger.info("ONNX模型信息:")
        logger.info("="*50)
        logger.info(f"文件大小: {file_size_mb:.2f} MB")
        logger.info(f"输入: {', '.join(input_info)}")
        logger.info(f"输出: {', '.join(output_info)}")
        logger.info("="*50 + "\n")
        
    except Exception as e:
        logger.warning(f"⚠️ 无法显示模型信息: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='将PyTorch模型转换为ONNX格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本转换
  python convert_to_onnx.py --model yolov5s.pt --output yolov5s.onnx

  # 指定输入尺寸和批大小
  python convert_to_onnx.py --model yolov5s.pt --output yolov5s.onnx --size 640 --batch 1

  # 不简化模型
  python convert_to_onnx.py --model yolov5s.pt --output yolov5s.onnx --no-simplify
        """
    )
    
    parser.add_argument('--model', type=str, required=True,
                        help='PyTorch模型路径 (.pt)')
    parser.add_argument('--output', type=str, required=True,
                        help='输出ONNX路径 (.onnx)')
    parser.add_argument('--size', type=int, default=640,
                        help='输入尺寸 (default: 640)')
    parser.add_argument('--batch', type=int, default=1,
                        help='批大小 (default: 1)')
    parser.add_argument('--opset', type=int, default=11,
                        help='ONNX opset版本 (default: 11)')
    parser.add_argument('--no-simplify', action='store_true',
                        help='不使用onnx-simplifier简化模型')
    
    args = parser.parse_args()
    
    # 执行转换
    success = convert_yolov5_to_onnx(
        model_path=args.model,
        output_path=args.output,
        input_size=args.size,
        batch_size=args.batch,
        opset_version=args.opset,
        simplify=not args.no_simplify
    )
    
    if success:
        logger.info("🎉 模型转换成功！")
        logger.info(f"\n使用方法:")
        logger.info(f"  detector.load_model('{args.output}')")
        sys.exit(0)
    else:
        logger.error("❌ 模型转换失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
