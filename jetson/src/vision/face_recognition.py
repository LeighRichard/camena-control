"""
人脸识别模块 - 人脸检测与识别（带记忆功能）

功能：
1. 人脸检测 - 使用 MTCNN 或 RetinaFace 检测人脸
2. 人脸识别 - 使用 FaceNet/ArcFace 提取特征向量
3. 人脸数据库 - 存储已知人脸的特征和名称
4. 实时识别 - 检测到人脸后与数据库比对

依赖：
- face_recognition (dlib)
- 或 insightface (更适合 Jetson)
"""

import os
import json
import time
import logging
import threading
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# 尝试导入人脸识别库
FACE_RECOGNITION_AVAILABLE = False
INSIGHTFACE_AVAILABLE = False

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
    logger.info("face_recognition 库可用")
except ImportError:
    pass

try:
    from insightface.app import FaceAnalysis
    INSIGHTFACE_AVAILABLE = True
    logger.info("insightface 库可用")
except ImportError:
    pass


@dataclass
class FaceInfo:
    """人脸信息"""
    id: int                                 # 检测 ID
    name: str                               # 人名（未知为 "Unknown"）
    confidence: float                       # 识别置信度 (0-1)
    bounding_box: Tuple[int, int, int, int] # (x, y, w, h)
    center_x: float                         # 中心 X
    center_y: float                         # 中心 Y
    distance: float = 0.0                   # 深度距离 (mm)
    embedding: Optional[np.ndarray] = None  # 特征向量（用于注册）
    
    @property
    def area(self) -> int:
        """边界框面积"""
        return self.bounding_box[2] * self.bounding_box[3]
    
    def to_dict(self) -> dict:
        """转换为字典（不含 embedding）"""
        return {
            'id': self.id,
            'name': self.name,
            'confidence': self.confidence,
            'bounding_box': self.bounding_box,
            'center_x': self.center_x,
            'center_y': self.center_y,
            'distance': self.distance
        }


@dataclass
class FaceRecognitionConfig:
    """人脸识别配置"""
    # 检测参数
    detection_threshold: float = 0.5        # 检测置信度阈值
    min_face_size: int = 40                 # 最小人脸尺寸（像素）
    
    # 识别参数
    recognition_threshold: float = 0.6      # 识别相似度阈值
    unknown_threshold: float = 0.4          # 低于此值标记为未知
    
    # 数据库路径
    database_path: str = "face_database"    # 人脸数据库目录
    
    # 性能参数
    detection_scale: float = 0.5            # 检测时的图像缩放比例
    use_gpu: bool = True                    # 使用 GPU 加速
    
    # 模型选择
    backend: str = "auto"                   # auto, face_recognition, insightface


@dataclass 
class FaceDetectionResult:
    """人脸检测结果"""
    faces: List[FaceInfo]                   # 检测到的人脸
    detection_time: float                   # 检测耗时 (ms)
    recognition_time: float                 # 识别耗时 (ms)
    
    @property
    def face_count(self) -> int:
        return len(self.faces)
    
    @property
    def known_faces(self) -> List[FaceInfo]:
        """已知人脸"""
        return [f for f in self.faces if f.name != "Unknown"]
    
    @property
    def unknown_faces(self) -> List[FaceInfo]:
        """未知人脸"""
        return [f for f in self.faces if f.name == "Unknown"]


class FaceDatabase:
    """
    人脸数据库 - 存储已知人脸的特征向量
    
    数据结构：
    face_database/
    ├── embeddings.json     # 特征向量索引
    ├── person_001/
    │   ├── info.json       # 人员信息
    │   ├── face_001.npy    # 特征向量
    │   └── face_001.jpg    # 原始人脸图像
    └── person_002/
        └── ...
    """
    
    def __init__(self, database_path: str):
        self._path = Path(database_path)
        self._path.mkdir(parents=True, exist_ok=True)
        
        # 内存中的特征向量缓存
        self._embeddings: Dict[str, List[np.ndarray]] = {}  # name -> [embeddings]
        self._names: List[str] = []
        
        # 加载数据库
        self._load_database()
    
    def _load_database(self):
        """加载数据库"""
        self._embeddings.clear()
        self._names.clear()
        
        # 遍历所有人员目录
        for person_dir in self._path.iterdir():
            if not person_dir.is_dir():
                continue
            
            info_file = person_dir / "info.json"
            if not info_file.exists():
                continue
            
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                
                name = info.get('name', person_dir.name)
                embeddings = []
                
                # 加载所有特征向量
                for npy_file in person_dir.glob("*.npy"):
                    embedding = np.load(npy_file)
                    embeddings.append(embedding)
                
                if embeddings:
                    self._embeddings[name] = embeddings
                    self._names.append(name)
                    logger.info(f"加载人脸: {name} ({len(embeddings)} 个样本)")
                    
            except Exception as e:
                logger.error(f"加载人脸数据失败 {person_dir}: {e}")
        
        logger.info(f"人脸数据库加载完成: {len(self._names)} 人")
    
    def add_face(self, name: str, embedding: np.ndarray, face_image: np.ndarray = None) -> bool:
        """
        添加人脸到数据库
        
        Args:
            name: 人名
            embedding: 特征向量
            face_image: 人脸图像（可选，用于保存）
            
        Returns:
            是否成功
        """
        try:
            # 创建人员目录
            safe_name = "".join(c for c in name if c.isalnum() or c in "_ -")
            person_dir = self._path / safe_name
            person_dir.mkdir(exist_ok=True)
            
            # 保存信息
            info_file = person_dir / "info.json"
            info = {'name': name, 'created': time.strftime('%Y-%m-%d %H:%M:%S')}
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump(info, f, ensure_ascii=False, indent=2)
            
            # 保存特征向量
            existing_count = len(list(person_dir.glob("*.npy")))
            npy_file = person_dir / f"face_{existing_count + 1:03d}.npy"
            np.save(npy_file, embedding)
            
            # 保存人脸图像
            if face_image is not None:
                try:
                    import cv2
                    jpg_file = person_dir / f"face_{existing_count + 1:03d}.jpg"
                    cv2.imwrite(str(jpg_file), cv2.cvtColor(face_image, cv2.COLOR_RGB2BGR))
                except ImportError:
                    pass
            
            # 更新内存缓存
            if name not in self._embeddings:
                self._embeddings[name] = []
                self._names.append(name)
            self._embeddings[name].append(embedding)
            
            logger.info(f"添加人脸成功: {name}")
            return True
            
        except Exception as e:
            logger.error(f"添加人脸失败: {e}")
            return False
    
    def remove_face(self, name: str) -> bool:
        """删除人脸"""
        try:
            safe_name = "".join(c for c in name if c.isalnum() or c in "_ -")
            person_dir = self._path / safe_name
            
            if person_dir.exists():
                import shutil
                shutil.rmtree(person_dir)
            
            if name in self._embeddings:
                del self._embeddings[name]
            if name in self._names:
                self._names.remove(name)
            
            logger.info(f"删除人脸成功: {name}")
            return True
            
        except Exception as e:
            logger.error(f"删除人脸失败: {e}")
            return False
    
    def find_match(self, embedding: np.ndarray, threshold: float = 0.6) -> Tuple[str, float]:
        """
        查找匹配的人脸
        
        Args:
            embedding: 待匹配的特征向量
            threshold: 相似度阈值
            
        Returns:
            (人名, 相似度)，未找到返回 ("Unknown", 0.0)
        """
        best_name = "Unknown"
        best_similarity = 0.0
        
        for name, embeddings in self._embeddings.items():
            for stored_embedding in embeddings:
                # 计算余弦相似度
                similarity = self._cosine_similarity(embedding, stored_embedding)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    if similarity >= threshold:
                        best_name = name
        
        return best_name, best_similarity
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算余弦相似度"""
        a = a.flatten()
        b = b.flatten()
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
    
    def get_all_names(self) -> List[str]:
        """获取所有已注册的人名"""
        return self._names.copy()
    
    def get_face_count(self, name: str) -> int:
        """获取某人的人脸样本数"""
        return len(self._embeddings.get(name, []))
    
    def reload(self):
        """重新加载数据库"""
        self._load_database()


class FaceRecognizer:
    """
    人脸识别器
    
    支持两种后端：
    1. face_recognition (dlib) - 简单易用，精度高
    2. insightface - 更适合 Jetson，支持 GPU 加速
    """
    
    def __init__(self, config: FaceRecognitionConfig = None):
        self._config = config or FaceRecognitionConfig()
        self._database = FaceDatabase(self._config.database_path)
        self._face_counter = 0
        self._backend = None
        self._model = None
        self._lock = threading.Lock()
        
        # 选择后端
        self._init_backend()
    
    def _init_backend(self):
        """初始化识别后端"""
        backend = self._config.backend
        
        if backend == "auto":
            # 自动选择：优先 insightface（GPU 加速）
            if INSIGHTFACE_AVAILABLE:
                backend = "insightface"
            elif FACE_RECOGNITION_AVAILABLE:
                backend = "face_recognition"
            else:
                backend = "simulation"
        
        self._backend = backend
        
        if backend == "insightface":
            self._init_insightface()
        elif backend == "face_recognition":
            self._init_face_recognition()
        else:
            logger.warning("无可用的人脸识别库，使用模拟模式")
            self._backend = "simulation"
    
    def _init_insightface(self):
        """初始化 InsightFace"""
        try:
            from insightface.app import FaceAnalysis
            
            # 使用 buffalo_l 模型（精度高）或 buffalo_sc（速度快）
            self._model = FaceAnalysis(
                name='buffalo_sc',  # 轻量级模型，适合 Jetson
                providers=['CUDAExecutionProvider', 'CPUExecutionProvider'] 
                    if self._config.use_gpu else ['CPUExecutionProvider']
            )
            self._model.prepare(ctx_id=0 if self._config.use_gpu else -1)
            logger.info("InsightFace 初始化成功")
            
        except Exception as e:
            logger.error(f"InsightFace 初始化失败: {e}")
            self._backend = "simulation"
    
    def _init_face_recognition(self):
        """初始化 face_recognition"""
        # face_recognition 不需要显式初始化
        logger.info("face_recognition 初始化成功")
    
    def detect_and_recognize(
        self, 
        image: np.ndarray, 
        depth: np.ndarray = None
    ) -> FaceDetectionResult:
        """
        检测并识别人脸
        
        Args:
            image: RGB 图像 (H, W, 3)
            depth: 深度图像 (H, W)，可选
            
        Returns:
            检测结果
        """
        with self._lock:
            detection_start = time.time()
            
            # 检测人脸
            if self._backend == "insightface":
                faces_data = self._detect_insightface(image)
            elif self._backend == "face_recognition":
                faces_data = self._detect_face_recognition(image)
            else:
                faces_data = self._detect_simulation(image)
            
            detection_time = (time.time() - detection_start) * 1000
            
            # 识别人脸
            recognition_start = time.time()
            faces = []
            
            for face_data in faces_data:
                self._face_counter += 1
                
                bbox = face_data['bbox']
                embedding = face_data.get('embedding')
                
                # 计算中心点
                center_x = bbox[0] + bbox[2] / 2
                center_y = bbox[1] + bbox[3] / 2
                
                # 获取深度
                distance = 0.0
                if depth is not None:
                    cx, cy = int(center_x), int(center_y)
                    if 0 <= cx < depth.shape[1] and 0 <= cy < depth.shape[0]:
                        distance = float(depth[cy, cx])
                
                # 识别身份
                name = "Unknown"
                confidence = 0.0
                
                if embedding is not None:
                    name, confidence = self._database.find_match(
                        embedding, 
                        self._config.recognition_threshold
                    )
                
                face = FaceInfo(
                    id=self._face_counter,
                    name=name,
                    confidence=confidence,
                    bounding_box=tuple(bbox),
                    center_x=center_x,
                    center_y=center_y,
                    distance=distance,
                    embedding=embedding
                )
                faces.append(face)
            
            recognition_time = (time.time() - recognition_start) * 1000
            
            return FaceDetectionResult(
                faces=faces,
                detection_time=detection_time,
                recognition_time=recognition_time
            )
    
    def _detect_insightface(self, image: np.ndarray) -> List[Dict]:
        """使用 InsightFace 检测"""
        results = []
        
        try:
            # InsightFace 需要 BGR 格式
            import cv2
            bgr_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
            
            faces = self._model.get(bgr_image)
            
            for face in faces:
                bbox = face.bbox.astype(int)
                x1, y1, x2, y2 = bbox
                
                results.append({
                    'bbox': (x1, y1, x2 - x1, y2 - y1),  # 转换为 (x, y, w, h)
                    'embedding': face.embedding,
                    'det_score': face.det_score
                })
                
        except Exception as e:
            logger.error(f"InsightFace 检测失败: {e}")
        
        return results
    
    def _detect_face_recognition(self, image: np.ndarray) -> List[Dict]:
        """使用 face_recognition 检测"""
        results = []
        
        try:
            # 缩放图像以提高速度
            scale = self._config.detection_scale
            if scale != 1.0:
                small_image = self._resize_image(image, scale)
            else:
                small_image = image
            
            # 检测人脸位置
            face_locations = face_recognition.face_locations(small_image, model='hog')
            
            # 提取特征向量
            face_encodings = face_recognition.face_encodings(small_image, face_locations)
            
            for location, encoding in zip(face_locations, face_encodings):
                top, right, bottom, left = location
                
                # 缩放回原始尺寸
                if scale != 1.0:
                    top = int(top / scale)
                    right = int(right / scale)
                    bottom = int(bottom / scale)
                    left = int(left / scale)
                
                results.append({
                    'bbox': (left, top, right - left, bottom - top),
                    'embedding': encoding,
                    'det_score': 1.0
                })
                
        except Exception as e:
            logger.error(f"face_recognition 检测失败: {e}")
        
        return results
    
    def _detect_simulation(self, image: np.ndarray) -> List[Dict]:
        """模拟检测（用于测试）"""
        h, w = image.shape[:2]
        
        # 随机生成 0-2 个人脸
        num_faces = np.random.randint(0, 3)
        results = []
        
        for _ in range(num_faces):
            # 随机人脸位置和大小
            face_w = np.random.randint(80, min(200, w // 2))
            face_h = int(face_w * 1.2)  # 人脸通常略高
            x = np.random.randint(0, max(1, w - face_w))
            y = np.random.randint(0, max(1, h - face_h))
            
            # 随机特征向量
            embedding = np.random.randn(128).astype(np.float32)
            embedding = embedding / np.linalg.norm(embedding)
            
            results.append({
                'bbox': (x, y, face_w, face_h),
                'embedding': embedding,
                'det_score': np.random.uniform(0.7, 0.99)
            })
        
        return results
    
    def _resize_image(self, image: np.ndarray, scale: float) -> np.ndarray:
        """缩放图像"""
        try:
            import cv2
            new_size = (int(image.shape[1] * scale), int(image.shape[0] * scale))
            return cv2.resize(image, new_size)
        except ImportError:
            # 简单的最近邻缩放
            h, w = image.shape[:2]
            new_h, new_w = int(h * scale), int(w * scale)
            y_indices = (np.arange(new_h) / scale).astype(int)
            x_indices = (np.arange(new_w) / scale).astype(int)
            return image[np.ix_(y_indices, x_indices)]
    
    # ==================== 人脸注册接口 ====================
    
    def register_face(
        self, 
        name: str, 
        image: np.ndarray,
        face_index: int = 0
    ) -> Tuple[bool, str]:
        """
        注册人脸
        
        Args:
            name: 人名
            image: 包含人脸的图像
            face_index: 如果图像中有多个人脸，选择第几个（从 0 开始）
            
        Returns:
            (成功标志, 消息)
        """
        # 检测人脸
        result = self.detect_and_recognize(image)
        
        if not result.faces:
            return False, "未检测到人脸"
        
        if face_index >= len(result.faces):
            return False, f"只检测到 {len(result.faces)} 个人脸，索引 {face_index} 无效"
        
        face = result.faces[face_index]
        
        if face.embedding is None:
            return False, "无法提取人脸特征"
        
        # 裁剪人脸图像
        x, y, w, h = face.bounding_box
        # 扩大裁剪区域
        pad = int(min(w, h) * 0.2)
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(image.shape[1], x + w + pad)
        y2 = min(image.shape[0], y + h + pad)
        face_image = image[y1:y2, x1:x2]
        
        # 添加到数据库
        success = self._database.add_face(name, face.embedding, face_image)
        
        if success:
            return True, f"成功注册人脸: {name}"
        else:
            return False, "保存人脸数据失败"
    
    def register_face_from_detection(self, name: str, face: FaceInfo) -> Tuple[bool, str]:
        """
        从检测结果注册人脸
        
        Args:
            name: 人名
            face: 检测到的人脸信息（必须包含 embedding）
            
        Returns:
            (成功标志, 消息)
        """
        if face.embedding is None:
            return False, "人脸信息中没有特征向量"
        
        success = self._database.add_face(name, face.embedding)
        
        if success:
            return True, f"成功注册人脸: {name}"
        else:
            return False, "保存人脸数据失败"
    
    def unregister_face(self, name: str) -> Tuple[bool, str]:
        """
        删除已注册的人脸
        
        Args:
            name: 人名
            
        Returns:
            (成功标志, 消息)
        """
        if name not in self._database.get_all_names():
            return False, f"未找到人脸: {name}"
        
        success = self._database.remove_face(name)
        
        if success:
            return True, f"成功删除人脸: {name}"
        else:
            return False, "删除人脸数据失败"
    
    def get_registered_names(self) -> List[str]:
        """获取所有已注册的人名"""
        return self._database.get_all_names()
    
    # ==================== 配置和状态 ====================
    
    def set_config(self, config: FaceRecognitionConfig):
        """设置配置"""
        self._config = config
        self._database = FaceDatabase(config.database_path)
    
    def get_config(self) -> FaceRecognitionConfig:
        """获取配置"""
        return self._config
    
    def get_backend(self) -> str:
        """获取当前使用的后端"""
        return self._backend
    
    def reload_database(self):
        """重新加载人脸数据库"""
        self._database.reload()
    
    # ==================== Web 接口 ====================
    
    def get_web_status(self) -> dict:
        """获取 Web 界面显示用的状态"""
        return {
            'backend': self._backend,
            'registered_count': len(self._database.get_all_names()),
            'registered_names': self._database.get_all_names(),
            'config': {
                'detection_threshold': self._config.detection_threshold,
                'recognition_threshold': self._config.recognition_threshold,
                'min_face_size': self._config.min_face_size
            }
        }
    
    def handle_web_command(self, command: str, params: dict = None) -> dict:
        """处理 Web 命令"""
        params = params or {}
        
        try:
            if command == 'get_registered':
                return {
                    'success': True,
                    'names': self._database.get_all_names()
                }
            
            elif command == 'unregister':
                name = params.get('name')
                if not name:
                    return {'success': False, 'message': '缺少人名参数'}
                success, msg = self.unregister_face(name)
                return {'success': success, 'message': msg}
            
            elif command == 'reload_database':
                self.reload_database()
                return {'success': True, 'message': '数据库已重新加载'}
            
            elif command == 'set_threshold':
                if 'detection' in params:
                    self._config.detection_threshold = float(params['detection'])
                if 'recognition' in params:
                    self._config.recognition_threshold = float(params['recognition'])
                return {'success': True, 'message': '阈值已更新'}
            
            else:
                return {'success': False, 'message': f'未知命令: {command}'}
                
        except Exception as e:
            return {'success': False, 'message': str(e)}
