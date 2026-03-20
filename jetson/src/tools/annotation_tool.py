"""
数据标注工具 - 用于训练自定义目标检测模型

功能：
1. 图像管理 - 导入、浏览、删除图像
2. 边界框标注 - 绘制、编辑、删除标注
3. 类别管理 - 添加、编辑、删除类别
4. 导出格式 - YOLO、COCO、Pascal VOC
5. 项目管理 - 保存、加载标注项目
"""

import os
import json
import shutil
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


@dataclass
class BoundingBox:
    """边界框"""
    x: float        # 左上角 X (归一化 0-1)
    y: float        # 左上角 Y (归一化 0-1)
    width: float    # 宽度 (归一化 0-1)
    height: float   # 高度 (归一化 0-1)
    
    @property
    def center_x(self) -> float:
        return self.x + self.width / 2
    
    @property
    def center_y(self) -> float:
        return self.y + self.height / 2
    
    @property
    def x2(self) -> float:
        return self.x + self.width
    
    @property
    def y2(self) -> float:
        return self.y + self.height
    
    def to_yolo(self) -> Tuple[float, float, float, float]:
        """转换为 YOLO 格式 (center_x, center_y, width, height)"""
        return (self.center_x, self.center_y, self.width, self.height)
    
    def to_pixel(self, img_width: int, img_height: int) -> Tuple[int, int, int, int]:
        """转换为像素坐标 (x, y, w, h)"""
        return (
            int(self.x * img_width),
            int(self.y * img_height),
            int(self.width * img_width),
            int(self.height * img_height)
        )
    
    @classmethod
    def from_pixel(cls, x: int, y: int, w: int, h: int, 
                   img_width: int, img_height: int) -> 'BoundingBox':
        """从像素坐标创建"""
        return cls(
            x=x / img_width,
            y=y / img_height,
            width=w / img_width,
            height=h / img_height
        )
    
    @classmethod
    def from_yolo(cls, cx: float, cy: float, w: float, h: float) -> 'BoundingBox':
        """从 YOLO 格式创建"""
        return cls(x=cx - w/2, y=cy - h/2, width=w, height=h)


@dataclass
class Annotation:
    """单个标注"""
    id: str                     # 唯一 ID
    class_id: int               # 类别 ID
    class_name: str             # 类别名称
    bbox: BoundingBox           # 边界框
    confidence: float = 1.0     # 置信度（手动标注为 1.0）
    is_difficult: bool = False  # 是否困难样本
    is_truncated: bool = False  # 是否被截断
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'class_id': self.class_id,
            'class_name': self.class_name,
            'bbox': {
                'x': self.bbox.x,
                'y': self.bbox.y,
                'width': self.bbox.width,
                'height': self.bbox.height
            },
            'confidence': self.confidence,
            'is_difficult': self.is_difficult,
            'is_truncated': self.is_truncated
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Annotation':
        bbox_data = data['bbox']
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            class_id=data['class_id'],
            class_name=data['class_name'],
            bbox=BoundingBox(
                x=bbox_data['x'],
                y=bbox_data['y'],
                width=bbox_data['width'],
                height=bbox_data['height']
            ),
            confidence=data.get('confidence', 1.0),
            is_difficult=data.get('is_difficult', False),
            is_truncated=data.get('is_truncated', False)
        )


@dataclass
class ImageAnnotation:
    """图像标注"""
    image_path: str                         # 图像路径
    image_width: int                        # 图像宽度
    image_height: int                       # 图像高度
    annotations: List[Annotation] = field(default_factory=list)
    is_verified: bool = False               # 是否已验证
    
    @property
    def filename(self) -> str:
        return Path(self.image_path).name
    
    @property
    def annotation_count(self) -> int:
        return len(self.annotations)
    
    def add_annotation(self, class_id: int, class_name: str, bbox: BoundingBox) -> Annotation:
        """添加标注"""
        ann = Annotation(
            id=str(uuid.uuid4()),
            class_id=class_id,
            class_name=class_name,
            bbox=bbox
        )
        self.annotations.append(ann)
        return ann
    
    def remove_annotation(self, annotation_id: str) -> bool:
        """删除标注"""
        for i, ann in enumerate(self.annotations):
            if ann.id == annotation_id:
                self.annotations.pop(i)
                return True
        return False
    
    def to_dict(self) -> dict:
        return {
            'image_path': self.image_path,
            'image_width': self.image_width,
            'image_height': self.image_height,
            'annotations': [a.to_dict() for a in self.annotations],
            'is_verified': self.is_verified
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ImageAnnotation':
        return cls(
            image_path=data['image_path'],
            image_width=data['image_width'],
            image_height=data['image_height'],
            annotations=[Annotation.from_dict(a) for a in data.get('annotations', [])],
            is_verified=data.get('is_verified', False)
        )


@dataclass
class ClassInfo:
    """类别信息"""
    id: int
    name: str
    color: str = "#FF0000"      # 显示颜色
    count: int = 0              # 标注数量
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'count': self.count
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ClassInfo':
        return cls(**data)


class AnnotationProject:
    """标注项目"""
    
    # 预定义颜色
    COLORS = [
        "#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF",
        "#FF8000", "#8000FF", "#00FF80", "#FF0080", "#80FF00", "#0080FF"
    ]
    
    def __init__(self, project_dir: str, name: str = "Untitled"):
        self.project_dir = Path(project_dir)
        self.name = name
        self.created_at = datetime.now().isoformat()
        self.modified_at = self.created_at
        
        # 类别
        self.classes: Dict[int, ClassInfo] = {}
        self._next_class_id = 0
        
        # 图像标注
        self.images: Dict[str, ImageAnnotation] = {}
        
        # 目录结构
        self.images_dir = self.project_dir / "images"
        self.labels_dir = self.project_dir / "labels"
        
        # 创建目录
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(exist_ok=True)
        self.labels_dir.mkdir(exist_ok=True)
    
    # ==================== 类别管理 ====================
    
    def add_class(self, name: str, color: str = None) -> ClassInfo:
        """添加类别"""
        class_id = self._next_class_id
        self._next_class_id += 1
        
        if color is None:
            color = self.COLORS[class_id % len(self.COLORS)]
        
        class_info = ClassInfo(id=class_id, name=name, color=color)
        self.classes[class_id] = class_info
        self._mark_modified()
        
        logger.info(f"添加类别: {name} (ID={class_id})")
        return class_info
    
    def remove_class(self, class_id: int) -> bool:
        """删除类别（同时删除相关标注）"""
        if class_id not in self.classes:
            return False
        
        # 删除相关标注
        for img_ann in self.images.values():
            img_ann.annotations = [
                a for a in img_ann.annotations if a.class_id != class_id
            ]
        
        del self.classes[class_id]
        self._mark_modified()
        return True
    
    def rename_class(self, class_id: int, new_name: str) -> bool:
        """重命名类别"""
        if class_id not in self.classes:
            return False
        
        old_name = self.classes[class_id].name
        self.classes[class_id].name = new_name
        
        # 更新标注中的类别名
        for img_ann in self.images.values():
            for ann in img_ann.annotations:
                if ann.class_id == class_id:
                    ann.class_name = new_name
        
        self._mark_modified()
        logger.info(f"重命名类别: {old_name} -> {new_name}")
        return True
    
    def get_class_by_name(self, name: str) -> Optional[ClassInfo]:
        """按名称获取类别"""
        for cls in self.classes.values():
            if cls.name == name:
                return cls
        return None
    
    def get_class_names(self) -> List[str]:
        """获取所有类别名称（按 ID 排序）"""
        return [self.classes[i].name for i in sorted(self.classes.keys())]
    
    # ==================== 图像管理 ====================
    
    def import_image(self, image_path: str, copy: bool = True) -> Optional[ImageAnnotation]:
        """导入图像"""
        src_path = Path(image_path)
        
        if not src_path.exists():
            logger.error(f"图像不存在: {image_path}")
            return None
        
        # 获取图像尺寸
        try:
            width, height = self._get_image_size(str(src_path))
        except Exception as e:
            logger.error(f"无法读取图像尺寸: {e}")
            return None
        
        # 复制或链接图像
        if copy:
            dst_path = self.images_dir / src_path.name
            if dst_path.exists():
                # 添加时间戳避免重名
                stem = src_path.stem
                suffix = src_path.suffix
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dst_path = self.images_dir / f"{stem}_{timestamp}{suffix}"
            shutil.copy2(src_path, dst_path)
            rel_path = str(dst_path.relative_to(self.project_dir))
        else:
            rel_path = str(src_path)
        
        # 创建标注对象
        img_ann = ImageAnnotation(
            image_path=rel_path,
            image_width=width,
            image_height=height
        )
        self.images[rel_path] = img_ann
        self._mark_modified()
        
        logger.info(f"导入图像: {src_path.name} ({width}x{height})")
        return img_ann
    
    def import_directory(self, directory: str, extensions: List[str] = None) -> int:
        """批量导入目录中的图像"""
        if extensions is None:
            extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        
        dir_path = Path(directory)
        count = 0
        
        for ext in extensions:
            for img_path in dir_path.glob(f"*{ext}"):
                if self.import_image(str(img_path)):
                    count += 1
            for img_path in dir_path.glob(f"*{ext.upper()}"):
                if self.import_image(str(img_path)):
                    count += 1
        
        logger.info(f"批量导入完成: {count} 张图像")
        return count
    
    def remove_image(self, image_path: str, delete_file: bool = False) -> bool:
        """删除图像"""
        if image_path not in self.images:
            return False
        
        if delete_file:
            full_path = self.project_dir / image_path
            if full_path.exists():
                full_path.unlink()
        
        del self.images[image_path]
        self._mark_modified()
        return True
    
    def get_image(self, image_path: str) -> Optional[ImageAnnotation]:
        """获取图像标注"""
        return self.images.get(image_path)
    
    def get_image_list(self) -> List[str]:
        """获取所有图像路径"""
        return list(self.images.keys())
    
    def _get_image_size(self, image_path: str) -> Tuple[int, int]:
        """获取图像尺寸"""
        try:
            import cv2
            img = cv2.imread(image_path)
            return img.shape[1], img.shape[0]
        except ImportError:
            pass
        
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                return img.size
        except ImportError:
            pass
        
        # 简单的 JPEG/PNG 头解析
        with open(image_path, 'rb') as f:
            header = f.read(24)
            
            # PNG
            if header[:8] == b'\x89PNG\r\n\x1a\n':
                width = int.from_bytes(header[16:20], 'big')
                height = int.from_bytes(header[20:24], 'big')
                return width, height
            
            # JPEG
            if header[:2] == b'\xff\xd8':
                f.seek(0)
                f.read(2)
                while True:
                    marker = f.read(2)
                    if marker[0] != 0xff:
                        break
                    if marker[1] in (0xc0, 0xc2):
                        f.read(3)
                        height = int.from_bytes(f.read(2), 'big')
                        width = int.from_bytes(f.read(2), 'big')
                        return width, height
                    else:
                        length = int.from_bytes(f.read(2), 'big')
                        f.read(length - 2)
        
        raise ValueError("无法解析图像尺寸")

    # ==================== 标注操作 ====================
    
    def add_annotation(
        self, 
        image_path: str, 
        class_id: int,
        x: float, y: float, width: float, height: float
    ) -> Optional[Annotation]:
        """添加标注"""
        if image_path not in self.images:
            return None
        if class_id not in self.classes:
            return None
        
        img_ann = self.images[image_path]
        bbox = BoundingBox(x=x, y=y, width=width, height=height)
        ann = img_ann.add_annotation(
            class_id=class_id,
            class_name=self.classes[class_id].name,
            bbox=bbox
        )
        
        # 更新类别计数
        self.classes[class_id].count += 1
        self._mark_modified()
        
        return ann
    
    def remove_annotation(self, image_path: str, annotation_id: str) -> bool:
        """删除标注"""
        if image_path not in self.images:
            return False
        
        img_ann = self.images[image_path]
        
        # 找到标注以更新计数
        for ann in img_ann.annotations:
            if ann.id == annotation_id:
                if ann.class_id in self.classes:
                    self.classes[ann.class_id].count -= 1
                break
        
        result = img_ann.remove_annotation(annotation_id)
        if result:
            self._mark_modified()
        return result
    
    def update_annotation(
        self, 
        image_path: str, 
        annotation_id: str,
        x: float = None, y: float = None, 
        width: float = None, height: float = None,
        class_id: int = None
    ) -> bool:
        """更新标注"""
        if image_path not in self.images:
            return False
        
        img_ann = self.images[image_path]
        
        for ann in img_ann.annotations:
            if ann.id == annotation_id:
                if x is not None:
                    ann.bbox.x = x
                if y is not None:
                    ann.bbox.y = y
                if width is not None:
                    ann.bbox.width = width
                if height is not None:
                    ann.bbox.height = height
                if class_id is not None and class_id in self.classes:
                    # 更新计数
                    if ann.class_id in self.classes:
                        self.classes[ann.class_id].count -= 1
                    self.classes[class_id].count += 1
                    ann.class_id = class_id
                    ann.class_name = self.classes[class_id].name
                
                self._mark_modified()
                return True
        
        return False
    
    # ==================== 项目保存/加载 ====================
    
    def save(self) -> bool:
        """保存项目"""
        try:
            project_file = self.project_dir / "project.json"
            
            data = {
                'name': self.name,
                'created_at': self.created_at,
                'modified_at': self.modified_at,
                'classes': [c.to_dict() for c in self.classes.values()],
                'next_class_id': self._next_class_id,
                'images': [img.to_dict() for img in self.images.values()]
            }
            
            with open(project_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"项目已保存: {project_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存项目失败: {e}")
            return False
    
    @classmethod
    def load(cls, project_dir: str) -> Optional['AnnotationProject']:
        """加载项目"""
        project_path = Path(project_dir)
        project_file = project_path / "project.json"
        
        if not project_file.exists():
            logger.error(f"项目文件不存在: {project_file}")
            return None
        
        try:
            with open(project_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            project = cls(project_dir, name=data.get('name', 'Untitled'))
            project.created_at = data.get('created_at', project.created_at)
            project.modified_at = data.get('modified_at', project.modified_at)
            project._next_class_id = data.get('next_class_id', 0)
            
            # 加载类别
            for cls_data in data.get('classes', []):
                class_info = ClassInfo.from_dict(cls_data)
                project.classes[class_info.id] = class_info
            
            # 加载图像标注
            for img_data in data.get('images', []):
                img_ann = ImageAnnotation.from_dict(img_data)
                project.images[img_ann.image_path] = img_ann
            
            logger.info(f"项目已加载: {project.name} ({len(project.images)} 张图像)")
            return project
            
        except Exception as e:
            logger.error(f"加载项目失败: {e}")
            return None
    
    def _mark_modified(self):
        """标记已修改"""
        self.modified_at = datetime.now().isoformat()
    
    # ==================== 导出功能 ====================
    
    def export_yolo(self, output_dir: str, split_ratio: float = 0.8) -> Tuple[bool, str]:
        """
        导出为 YOLO 格式
        
        目录结构:
        output_dir/
        ├── images/
        │   ├── train/
        │   └── val/
        ├── labels/
        │   ├── train/
        │   └── val/
        └── data.yaml
        """
        try:
            output_path = Path(output_dir)
            
            # 创建目录
            (output_path / "images" / "train").mkdir(parents=True, exist_ok=True)
            (output_path / "images" / "val").mkdir(parents=True, exist_ok=True)
            (output_path / "labels" / "train").mkdir(parents=True, exist_ok=True)
            (output_path / "labels" / "val").mkdir(parents=True, exist_ok=True)
            
            # 分割数据集
            image_list = list(self.images.keys())
            import random
            random.shuffle(image_list)
            
            split_idx = int(len(image_list) * split_ratio)
            train_images = image_list[:split_idx]
            val_images = image_list[split_idx:]
            
            # 导出图像和标签
            for img_path in train_images:
                self._export_yolo_image(img_path, output_path, "train")
            
            for img_path in val_images:
                self._export_yolo_image(img_path, output_path, "val")
            
            # 创建 data.yaml
            class_names = self.get_class_names()
            yaml_content = f"""# YOLO Dataset Configuration
# Generated by Annotation Tool

path: {output_path.absolute()}
train: images/train
val: images/val

nc: {len(class_names)}
names: {class_names}
"""
            
            with open(output_path / "data.yaml", 'w') as f:
                f.write(yaml_content)
            
            msg = f"导出完成: {len(train_images)} 训练, {len(val_images)} 验证"
            logger.info(msg)
            return True, msg
            
        except Exception as e:
            return False, f"导出失败: {e}"
    
    def _export_yolo_image(self, image_path: str, output_path: Path, split: str):
        """导出单张图像的 YOLO 格式"""
        img_ann = self.images[image_path]
        
        # 复制图像
        src_img = self.project_dir / image_path
        dst_img = output_path / "images" / split / Path(image_path).name
        if src_img.exists():
            shutil.copy2(src_img, dst_img)
        
        # 创建标签文件
        label_name = Path(image_path).stem + ".txt"
        label_path = output_path / "labels" / split / label_name
        
        with open(label_path, 'w') as f:
            for ann in img_ann.annotations:
                cx, cy, w, h = ann.bbox.to_yolo()
                f.write(f"{ann.class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
    
    def export_coco(self, output_file: str) -> Tuple[bool, str]:
        """导出为 COCO JSON 格式"""
        try:
            coco_data = {
                "info": {
                    "description": self.name,
                    "date_created": self.created_at
                },
                "licenses": [],
                "categories": [],
                "images": [],
                "annotations": []
            }
            
            # 类别
            for cls in self.classes.values():
                coco_data["categories"].append({
                    "id": cls.id,
                    "name": cls.name,
                    "supercategory": "object"
                })
            
            # 图像和标注
            ann_id = 1
            for img_id, (img_path, img_ann) in enumerate(self.images.items(), 1):
                coco_data["images"].append({
                    "id": img_id,
                    "file_name": Path(img_path).name,
                    "width": img_ann.image_width,
                    "height": img_ann.image_height
                })
                
                for ann in img_ann.annotations:
                    x, y, w, h = ann.bbox.to_pixel(
                        img_ann.image_width, img_ann.image_height
                    )
                    coco_data["annotations"].append({
                        "id": ann_id,
                        "image_id": img_id,
                        "category_id": ann.class_id,
                        "bbox": [x, y, w, h],
                        "area": w * h,
                        "iscrowd": 0
                    })
                    ann_id += 1
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(coco_data, f, indent=2)
            
            msg = f"导出完成: {output_file}"
            logger.info(msg)
            return True, msg
            
        except Exception as e:
            return False, f"导出失败: {e}"
    
    # ==================== 统计信息 ====================
    
    def get_statistics(self) -> dict:
        """获取项目统计信息"""
        total_annotations = sum(img.annotation_count for img in self.images.values())
        annotated_images = sum(1 for img in self.images.values() if img.annotation_count > 0)
        verified_images = sum(1 for img in self.images.values() if img.is_verified)
        
        class_distribution = {}
        for cls in self.classes.values():
            class_distribution[cls.name] = cls.count
        
        return {
            'name': self.name,
            'total_images': len(self.images),
            'annotated_images': annotated_images,
            'verified_images': verified_images,
            'total_annotations': total_annotations,
            'total_classes': len(self.classes),
            'class_distribution': class_distribution,
            'created_at': self.created_at,
            'modified_at': self.modified_at
        }


class AnnotationTool:
    """
    标注工具主类
    
    提供命令行和 API 接口
    """
    
    def __init__(self, project_dir: str = None):
        self.project: Optional[AnnotationProject] = None
        
        if project_dir:
            self.load_or_create_project(project_dir)
    
    def load_or_create_project(self, project_dir: str, name: str = None) -> AnnotationProject:
        """加载或创建项目"""
        project_path = Path(project_dir)
        project_file = project_path / "project.json"
        
        if project_file.exists():
            self.project = AnnotationProject.load(project_dir)
        else:
            self.project = AnnotationProject(project_dir, name or "New Project")
        
        return self.project
    
    def create_project(self, project_dir: str, name: str) -> AnnotationProject:
        """创建新项目"""
        self.project = AnnotationProject(project_dir, name)
        return self.project
    
    def get_project(self) -> Optional[AnnotationProject]:
        """获取当前项目"""
        return self.project
    
    def close_project(self, save: bool = True):
        """关闭项目"""
        if self.project and save:
            self.project.save()
        self.project = None
