#!/usr/bin/env python3
"""
数据标注命令行工具

用法:
    python annotate.py create my_project --name "My Dataset"
    python annotate.py import my_project ./images/
    python annotate.py add-class my_project person
    python annotate.py export my_project ./output --format yolo
    python annotate.py stats my_project
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.tools.annotation_tool import AnnotationTool, AnnotationProject

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def cmd_create(args):
    """创建项目"""
    tool = AnnotationTool()
    project = tool.create_project(args.project_dir, args.name or "New Project")
    project.save()
    
    print(f"✅ 项目已创建: {args.project_dir}")
    print(f"   名称: {project.name}")
    return 0


def cmd_import(args):
    """导入图像"""
    tool = AnnotationTool(args.project_dir)
    
    if not tool.project:
        print(f"❌ 无法加载项目: {args.project_dir}")
        return 1
    
    if os.path.isdir(args.path):
        count = tool.project.import_directory(args.path)
        print(f"✅ 导入了 {count} 张图像")
    else:
        result = tool.project.import_image(args.path)
        if result:
            print(f"✅ 导入图像: {args.path}")
        else:
            print(f"❌ 导入失败: {args.path}")
            return 1
    
    tool.project.save()
    return 0


def cmd_add_class(args):
    """添加类别"""
    tool = AnnotationTool(args.project_dir)
    
    if not tool.project:
        print(f"❌ 无法加载项目: {args.project_dir}")
        return 1
    
    class_info = tool.project.add_class(args.class_name, args.color)
    tool.project.save()
    
    print(f"✅ 添加类别: {class_info.name} (ID={class_info.id})")
    return 0


def cmd_list_classes(args):
    """列出类别"""
    tool = AnnotationTool(args.project_dir)
    
    if not tool.project:
        print(f"❌ 无法加载项目: {args.project_dir}")
        return 1
    
    print(f"\n类别列表 ({len(tool.project.classes)} 个):")
    print("-" * 40)
    
    for cls in tool.project.classes.values():
        print(f"  [{cls.id}] {cls.name} ({cls.count} 个标注) {cls.color}")
    
    return 0


def cmd_list_images(args):
    """列出图像"""
    tool = AnnotationTool(args.project_dir)
    
    if not tool.project:
        print(f"❌ 无法加载项目: {args.project_dir}")
        return 1
    
    print(f"\n图像列表 ({len(tool.project.images)} 张):")
    print("-" * 60)
    
    for img_path, img_ann in tool.project.images.items():
        status = "✓" if img_ann.is_verified else " "
        print(f"  [{status}] {img_ann.filename} - {img_ann.annotation_count} 个标注")
    
    return 0


def cmd_export(args):
    """导出数据集"""
    tool = AnnotationTool(args.project_dir)
    
    if not tool.project:
        print(f"❌ 无法加载项目: {args.project_dir}")
        return 1
    
    print(f"\n导出数据集...")
    print(f"  格式: {args.format}")
    print(f"  输出: {args.output}")
    
    if args.format == 'yolo':
        success, msg = tool.project.export_yolo(args.output, args.split)
    elif args.format == 'coco':
        success, msg = tool.project.export_coco(args.output)
    else:
        print(f"❌ 不支持的格式: {args.format}")
        return 1
    
    if success:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")
        return 1
    
    return 0


def cmd_stats(args):
    """显示统计信息"""
    tool = AnnotationTool(args.project_dir)
    
    if not tool.project:
        print(f"❌ 无法加载项目: {args.project_dir}")
        return 1
    
    stats = tool.project.get_statistics()
    
    print(f"\n项目统计: {stats['name']}")
    print("=" * 50)
    print(f"  总图像数: {stats['total_images']}")
    print(f"  已标注图像: {stats['annotated_images']}")
    print(f"  已验证图像: {stats['verified_images']}")
    print(f"  总标注数: {stats['total_annotations']}")
    print(f"  类别数: {stats['total_classes']}")
    
    if stats['class_distribution']:
        print(f"\n类别分布:")
        for name, count in stats['class_distribution'].items():
            bar_len = min(30, count // 5 + 1)
            bar = "█" * bar_len
            print(f"    {name}: {count} {bar}")
    
    print(f"\n  创建时间: {stats['created_at']}")
    print(f"  修改时间: {stats['modified_at']}")
    
    return 0


def cmd_auto_annotate(args):
    """使用模型自动标注"""
    tool = AnnotationTool(args.project_dir)
    
    if not tool.project:
        print(f"❌ 无法加载项目: {args.project_dir}")
        return 1
    
    print(f"\n自动标注...")
    print(f"  模型: {args.model}")
    print(f"  置信度阈值: {args.threshold}")
    
    try:
        from src.vision.detector import ObjectDetector, DetectionConfig
        import numpy as np
        
        # 加载检测器
        config = DetectionConfig(
            model_path=args.model,
            threshold=args.threshold
        )
        detector = ObjectDetector(config)
        success, msg = detector.load_model()
        
        if not success:
            print(f"❌ 加载模型失败: {msg}")
            return 1
        
        # 确保类别存在
        class_names = detector.get_class_names()
        for name in class_names:
            if not tool.project.get_class_by_name(name):
                tool.project.add_class(name)
        
        # 遍历图像
        annotated_count = 0
        for img_path in tool.project.get_image_list():
            full_path = tool.project.project_dir / img_path
            
            try:
                import cv2
                image = cv2.imread(str(full_path))
                if image is None:
                    continue
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            except:
                continue
            
            # 检测
            result = detector.detect(image_rgb)
            
            # 添加标注
            for target in result.targets:
                x, y, w, h = target.bounding_box
                img_ann = tool.project.images[img_path]
                
                # 转换为归一化坐标
                bbox_norm = (
                    x / img_ann.image_width,
                    y / img_ann.image_height,
                    w / img_ann.image_width,
                    h / img_ann.image_height
                )
                
                cls = tool.project.get_class_by_name(target.class_name)
                if cls:
                    tool.project.add_annotation(
                        img_path, cls.id,
                        bbox_norm[0], bbox_norm[1], bbox_norm[2], bbox_norm[3]
                    )
                    annotated_count += 1
            
            print(f"  {img_path}: {len(result.targets)} 个目标")
        
        tool.project.save()
        print(f"\n✅ 自动标注完成: {annotated_count} 个标注")
        
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        return 1
    except Exception as e:
        print(f"❌ 自动标注失败: {e}")
        return 1
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='数据标注工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s create my_dataset --name "My Dataset"
  %(prog)s import my_dataset ./images/
  %(prog)s add-class my_dataset person
  %(prog)s add-class my_dataset car
  %(prog)s stats my_dataset
  %(prog)s export my_dataset ./output --format yolo
  %(prog)s auto-annotate my_dataset --model models/yolov5s.engine
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # create
    p_create = subparsers.add_parser('create', help='创建项目')
    p_create.add_argument('project_dir', help='项目目录')
    p_create.add_argument('--name', '-n', help='项目名称')
    
    # import
    p_import = subparsers.add_parser('import', help='导入图像')
    p_import.add_argument('project_dir', help='项目目录')
    p_import.add_argument('path', help='图像文件或目录')
    
    # add-class
    p_class = subparsers.add_parser('add-class', help='添加类别')
    p_class.add_argument('project_dir', help='项目目录')
    p_class.add_argument('class_name', help='类别名称')
    p_class.add_argument('--color', '-c', help='显示颜色')
    
    # list-classes
    p_lc = subparsers.add_parser('list-classes', help='列出类别')
    p_lc.add_argument('project_dir', help='项目目录')
    
    # list-images
    p_li = subparsers.add_parser('list-images', help='列出图像')
    p_li.add_argument('project_dir', help='项目目录')
    
    # export
    p_export = subparsers.add_parser('export', help='导出数据集')
    p_export.add_argument('project_dir', help='项目目录')
    p_export.add_argument('output', help='输出路径')
    p_export.add_argument('--format', '-f', choices=['yolo', 'coco'], default='yolo')
    p_export.add_argument('--split', '-s', type=float, default=0.8, help='训练集比例')
    
    # stats
    p_stats = subparsers.add_parser('stats', help='显示统计')
    p_stats.add_argument('project_dir', help='项目目录')
    
    # auto-annotate
    p_auto = subparsers.add_parser('auto-annotate', help='自动标注')
    p_auto.add_argument('project_dir', help='项目目录')
    p_auto.add_argument('--model', '-m', required=True, help='模型路径')
    p_auto.add_argument('--threshold', '-t', type=float, default=0.5, help='置信度阈值')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    commands = {
        'create': cmd_create,
        'import': cmd_import,
        'add-class': cmd_add_class,
        'list-classes': cmd_list_classes,
        'list-images': cmd_list_images,
        'export': cmd_export,
        'stats': cmd_stats,
        'auto-annotate': cmd_auto_annotate,
    }
    
    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
