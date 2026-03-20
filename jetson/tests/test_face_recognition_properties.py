"""
人脸识别模块属性测试

Property 测试：
- FaceInfo 数据一致性
- FaceDatabase 存储和检索
- FaceRecognizer 检测结果格式
- 相似度计算正确性
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings, assume
import tempfile
import shutil
import os

import sys
# 添加 src 目录到路径
src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.insert(0, src_path)

# 直接导入 face_recognition 模块文件，避免通过 __init__.py 触发循环导入
import importlib.util
spec = importlib.util.spec_from_file_location(
    "face_recognition_module",
    os.path.join(src_path, "vision", "face_recognition.py")
)
face_recognition_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(face_recognition_module)

FaceInfo = face_recognition_module.FaceInfo
FaceRecognitionConfig = face_recognition_module.FaceRecognitionConfig
FaceDetectionResult = face_recognition_module.FaceDetectionResult
FaceDatabase = face_recognition_module.FaceDatabase
FaceRecognizer = face_recognition_module.FaceRecognizer


# ============================================================================
# 策略定义
# ============================================================================

@st.composite
def valid_bounding_box(draw, max_width=1280, max_height=720):
    """生成有效的边界框"""
    w = draw(st.integers(40, min(200, max_width // 2)))
    h = draw(st.integers(50, min(250, max_height // 2)))
    x = draw(st.integers(0, max_width - w))
    y = draw(st.integers(0, max_height - h))
    return (x, y, w, h)


@st.composite
def valid_face_info(draw):
    """生成有效的 FaceInfo"""
    bbox = draw(valid_bounding_box())
    x, y, w, h = bbox
    return FaceInfo(
        id=draw(st.integers(1, 10000)),
        name=draw(st.sampled_from(['Alice', 'Bob', 'Unknown', '张三', '李四'])),
        confidence=draw(st.floats(0.0, 1.0)),
        bounding_box=bbox,
        center_x=x + w / 2,
        center_y=y + h / 2,
        distance=draw(st.floats(0, 5000))
    )


# ============================================================================
# FaceInfo 属性测试
# ============================================================================

class TestFaceInfoProperties:
    """FaceInfo 数据类属性测试"""
    
    @given(face=valid_face_info())
    @settings(max_examples=50)
    def test_area_calculation(self, face):
        """
        Property: 面积计算应正确
        """
        x, y, w, h = face.bounding_box
        assert face.area == w * h
    
    @given(face=valid_face_info())
    @settings(max_examples=50)
    def test_center_within_bbox(self, face):
        """
        Property: 中心点应在边界框内
        """
        x, y, w, h = face.bounding_box
        
        assert x <= face.center_x <= x + w
        assert y <= face.center_y <= y + h
    
    @given(face=valid_face_info())
    @settings(max_examples=50)
    def test_to_dict_contains_required_fields(self, face):
        """
        Property: to_dict 应包含所有必需字段
        """
        d = face.to_dict()
        
        required_fields = ['id', 'name', 'confidence', 'bounding_box', 
                          'center_x', 'center_y', 'distance']
        for field in required_fields:
            assert field in d
    
    @given(face=valid_face_info())
    @settings(max_examples=50)
    def test_confidence_in_valid_range(self, face):
        """
        Property: 置信度应在 [0, 1] 范围内
        """
        assert 0.0 <= face.confidence <= 1.0


# ============================================================================
# FaceDetectionResult 属性测试
# ============================================================================

class TestFaceDetectionResultProperties:
    """检测结果属性测试"""
    
    def test_empty_result(self):
        """空结果应正确处理"""
        result = FaceDetectionResult(
            faces=[],
            detection_time=10.0,
            recognition_time=5.0
        )
        
        assert result.face_count == 0
        assert len(result.known_faces) == 0
        assert len(result.unknown_faces) == 0
    
    def test_known_unknown_partition(self):
        """已知和未知人脸应正确分类"""
        faces = [
            FaceInfo(1, 'Alice', 0.9, (0, 0, 100, 100), 50, 50),
            FaceInfo(2, 'Unknown', 0.5, (200, 0, 100, 100), 250, 50),
            FaceInfo(3, 'Bob', 0.8, (400, 0, 100, 100), 450, 50),
        ]
        
        result = FaceDetectionResult(faces=faces, detection_time=10, recognition_time=5)
        
        assert result.face_count == 3
        assert len(result.known_faces) == 2
        assert len(result.unknown_faces) == 1
        
        known_names = [f.name for f in result.known_faces]
        assert 'Alice' in known_names
        assert 'Bob' in known_names
        assert 'Unknown' not in known_names


# ============================================================================
# FaceDatabase 属性测试
# ============================================================================

class TestFaceDatabaseProperties:
    """人脸数据库属性测试"""
    
    @pytest.fixture
    def temp_database(self):
        """创建临时数据库目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_empty_database(self, temp_database):
        """空数据库应正确初始化"""
        db = FaceDatabase(temp_database)
        
        assert len(db.get_all_names()) == 0
    
    def test_add_and_retrieve_face(self, temp_database):
        """添加人脸后应能检索"""
        db = FaceDatabase(temp_database)
        
        # 创建随机特征向量
        embedding = np.random.randn(128).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        success = db.add_face('TestUser', embedding)
        assert success
        
        assert 'TestUser' in db.get_all_names()
        assert db.get_face_count('TestUser') == 1
    
    def test_find_match_returns_correct_name(self, temp_database):
        """匹配应返回正确的人名"""
        db = FaceDatabase(temp_database)
        
        # 添加一个人脸
        embedding = np.random.randn(128).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        db.add_face('Alice', embedding)
        
        # 使用相同的特征向量查找
        name, similarity = db.find_match(embedding, threshold=0.5)
        
        assert name == 'Alice'
        assert similarity > 0.99  # 应该非常相似
    
    def test_find_match_unknown_for_different_embedding(self, temp_database):
        """不同特征向量应返回 Unknown"""
        db = FaceDatabase(temp_database)
        
        # 添加一个人脸
        embedding1 = np.random.randn(128).astype(np.float32)
        embedding1 = embedding1 / np.linalg.norm(embedding1)
        db.add_face('Alice', embedding1)
        
        # 使用完全不同的特征向量查找
        embedding2 = np.random.randn(128).astype(np.float32)
        embedding2 = embedding2 / np.linalg.norm(embedding2)
        
        name, similarity = db.find_match(embedding2, threshold=0.9)
        
        # 随机向量相似度通常很低
        assert name == 'Unknown' or similarity < 0.9
    
    def test_remove_face(self, temp_database):
        """删除人脸应生效"""
        db = FaceDatabase(temp_database)
        
        embedding = np.random.randn(128).astype(np.float32)
        db.add_face('ToDelete', embedding)
        
        assert 'ToDelete' in db.get_all_names()
        
        success = db.remove_face('ToDelete')
        assert success
        assert 'ToDelete' not in db.get_all_names()
    
    @given(
        a=st.lists(st.floats(-1, 1), min_size=128, max_size=128),
        b=st.lists(st.floats(-1, 1), min_size=128, max_size=128)
    )
    @settings(max_examples=30)
    def test_cosine_similarity_range(self, a, b):
        """
        Property: 余弦相似度应在 [-1, 1] 范围内
        """
        # 创建临时数据库
        temp_dir = tempfile.mkdtemp()
        try:
            db = FaceDatabase(temp_dir)
            
            vec_a = np.array(a, dtype=np.float32)
            vec_b = np.array(b, dtype=np.float32)
            
            # 避免零向量
            assume(np.linalg.norm(vec_a) > 0.01)
            assume(np.linalg.norm(vec_b) > 0.01)
            
            similarity = db._cosine_similarity(vec_a, vec_b)
            
            assert -1.0 <= similarity <= 1.0 + 1e-6  # 允许小误差
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# FaceRecognizer 属性测试
# ============================================================================

class TestFaceRecognizerProperties:
    """人脸识别器属性测试"""
    
    @pytest.fixture
    def recognizer(self):
        """创建识别器实例"""
        temp_dir = tempfile.mkdtemp()
        config = FaceRecognitionConfig(database_path=temp_dir)
        recognizer = FaceRecognizer(config)
        yield recognizer
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_backend_selection(self, recognizer):
        """后端应正确选择"""
        backend = recognizer.get_backend()
        assert backend in ['insightface', 'face_recognition', 'simulation']
    
    def test_detect_returns_valid_result(self, recognizer):
        """检测应返回有效结果"""
        # 创建测试图像
        image = np.random.randint(0, 256, (720, 1280, 3), dtype=np.uint8)
        
        result = recognizer.detect_and_recognize(image)
        
        assert isinstance(result, FaceDetectionResult)
        assert result.detection_time >= 0
        assert result.recognition_time >= 0
    
    def test_detect_with_depth(self, recognizer):
        """带深度图的检测"""
        image = np.random.randint(0, 256, (720, 1280, 3), dtype=np.uint8)
        depth = np.random.randint(500, 3000, (720, 1280), dtype=np.uint16)
        
        result = recognizer.detect_and_recognize(image, depth)
        
        assert isinstance(result, FaceDetectionResult)
        # 如果检测到人脸，应该有深度信息
        for face in result.faces:
            # 深度可能为 0（如果中心点超出范围）或有效值
            assert face.distance >= 0
    
    def test_get_registered_names_initially_empty(self, recognizer):
        """初始时应无注册人脸"""
        names = recognizer.get_registered_names()
        assert len(names) == 0
    
    def test_web_status_format(self, recognizer):
        """Web 状态应包含必需字段"""
        status = recognizer.get_web_status()
        
        assert 'backend' in status
        assert 'registered_count' in status
        assert 'registered_names' in status
        assert 'config' in status
    
    def test_handle_web_command_get_registered(self, recognizer):
        """Web 命令：获取已注册人脸"""
        result = recognizer.handle_web_command('get_registered')
        
        assert result['success']
        assert 'names' in result
    
    def test_handle_web_command_unknown(self, recognizer):
        """Web 命令：未知命令应返回错误"""
        result = recognizer.handle_web_command('unknown_command')
        
        assert not result['success']
        assert 'message' in result


# ============================================================================
# 配置属性测试
# ============================================================================

class TestFaceRecognitionConfigProperties:
    """配置属性测试"""
    
    @given(
        detection_threshold=st.floats(0.1, 0.9),
        recognition_threshold=st.floats(0.1, 0.9)
    )
    @settings(max_examples=30)
    def test_config_thresholds_valid(self, detection_threshold, recognition_threshold):
        """
        Property: 阈值应在有效范围内
        """
        config = FaceRecognitionConfig(
            detection_threshold=detection_threshold,
            recognition_threshold=recognition_threshold
        )
        
        assert 0 < config.detection_threshold < 1
        assert 0 < config.recognition_threshold < 1
    
    def test_default_config_values(self):
        """默认配置应有合理值"""
        config = FaceRecognitionConfig()
        
        assert config.detection_threshold > 0
        assert config.recognition_threshold > 0
        assert config.min_face_size > 0
        assert config.detection_scale > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
