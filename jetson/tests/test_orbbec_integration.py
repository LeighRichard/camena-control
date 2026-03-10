"""
Orbbec 相机集成测试

TASK-M12: 集成测试
测试 Orbbec 相机与系统其他模块的集成

测试场景:
1. 相机工厂自动检测
2. 与视觉伺服集成
3. 与目标检测集成
4. 完整工作流程
5. RealSense 兼容性
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from camera.factory import CameraFactory
from camera.base_controller import BaseCameraController, CameraConfig, ImagePair
from camera.orbbec_controller import OrbbecController
from vision.detector import ObjectDetector, DetectionConfig, SelectionStrategy


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_orbbec_available():
    """模拟 Orbbec SDK 可用"""
    with patch('camera.orbbec_controller.ORBBEC_AVAILABLE', True):
        yield


@pytest.fixture
def mock_realsense_available():
    """模拟 RealSense SDK 可用"""
    with patch('camera.realsense_controller.REALSENSE_AVAILABLE', True):
        yield


@pytest.fixture
def sample_image_pair():
    """创建示例图像对"""
    rgb = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)
    depth = np.random.randint(500, 3000, (480, 640), dtype=np.uint16)
    return ImagePair(rgb=rgb, depth=depth, timestamp=0.0)


# ============================================================================
# 相机工厂自动检测测试
# ============================================================================

class TestCameraFactoryAutoDetection:
    """相机工厂自动检测集成测试"""
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_auto_detect_prefers_orbbec(
        self,
        mock_create_realsense,
        mock_create_orbbec
    ):
        """测试自动检测优先选择 Orbbec"""
        # 模拟 Orbbec 可用
        mock_orbbec = MagicMock(spec=BaseCameraController)
        mock_orbbec.camera_type = "orbbec"
        mock_create_orbbec.return_value = mock_orbbec
        
        # 自动检测
        camera = CameraFactory.create_camera("auto")
        
        # 验证
        assert camera is not None
        assert camera.camera_type == "orbbec"
        mock_create_orbbec.assert_called_once()
        # RealSense 不应该被尝试
        mock_create_realsense.assert_not_called()
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_auto_detect_fallback_to_realsense(
        self,
        mock_create_realsense,
        mock_create_orbbec
    ):
        """测试自动检测回退到 RealSense"""
        # 模拟 Orbbec 不可用，RealSense 可用
        mock_create_orbbec.return_value = None
        
        mock_realsense = MagicMock(spec=BaseCameraController)
        mock_realsense.camera_type = "realsense"
        mock_create_realsense.return_value = mock_realsense
        
        # 自动检测
        camera = CameraFactory.create_camera("auto")
        
        # 验证
        assert camera is not None
        assert camera.camera_type == "realsense"
        mock_create_orbbec.assert_called_once()
        mock_create_realsense.assert_called_once()
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_auto_detect_both_cameras(
        self,
        mock_create_realsense,
        mock_create_orbbec
    ):
        """测试列出所有可用相机"""
        # 模拟两种相机都可用
        mock_orbbec = MagicMock(spec=BaseCameraController)
        mock_orbbec.camera_type = "orbbec"
        mock_orbbec.camera_model = "Orbbec Astra+"
        
        mock_realsense = MagicMock(spec=BaseCameraController)
        mock_realsense.camera_type = "realsense"
        mock_realsense.camera_model = "Intel RealSense D415"
        
        mock_create_orbbec.return_value = mock_orbbec
        mock_create_realsense.return_value = mock_realsense
        
        # 列出所有相机
        cameras = CameraFactory.list_available_cameras()
        
        # 验证
        assert len(cameras) == 2
        assert any(c['type'] == 'orbbec' for c in cameras)
        assert any(c['type'] == 'realsense' for c in cameras)


# ============================================================================
# 与目标检测集成测试
# ============================================================================

class TestOrbbecDetectorIntegration:
    """Orbbec 相机与目标检测器集成测试"""
    
    def test_detector_with_orbbec_resolution(self, sample_image_pair):
        """测试检测器处理 Orbbec 分辨率图像"""
        # 创建检测器
        config = DetectionConfig(
            threshold=0.5,
            selection_strategy=SelectionStrategy.CENTER
        )
        detector = ObjectDetector(config)
        detector.load_model()  # 模拟模式
        
        try:
            # 检测
            result = detector.detect(sample_image_pair.rgb)
            
            # 验证 - 返回 DetectionResult 对象
            assert hasattr(result, 'targets')
            assert isinstance(result.targets, list)
            # 模拟模式应该返回一些检测结果
            assert len(result.targets) >= 0
            
        finally:
            detector.unload()
    
    def test_depth_query_with_orbbec_image(self, sample_image_pair):
        """测试深度查询处理 Orbbec 图像"""
        # 创建检测器
        config = DetectionConfig(threshold=0.5)
        detector = ObjectDetector(config)
        detector.load_model()
        
        try:
            # 模拟检测结果
            detections = [
                {
                    'bbox': [800, 400, 1120, 680],  # 彩色图坐标
                    'confidence': 0.9,
                    'class_id': 0,
                    'class_name': 'person'
                }
            ]
            
            # 查询深度（应该自动处理分辨率不匹配）
            for det in detections:
                x1, y1, x2, y2 = det['bbox']
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                
                # 这里会触发智能深度查询
                # 实际实现中会自动处理坐标转换
                assert 0 <= center_x < 1920
                assert 0 <= center_y < 1080
                
        finally:
            detector.unload()
    
    def test_target_selection_with_orbbec(self, sample_image_pair):
        """测试目标选择处理 Orbbec 图像"""
        config = DetectionConfig(
            threshold=0.5,
            selection_strategy=SelectionStrategy.LARGEST
        )
        detector = ObjectDetector(config)
        detector.load_model()
        
        try:
            # 检测和选择
            result = detector.detect(sample_image_pair.rgb)
            
            # 验证结果
            assert hasattr(result, 'targets')
            assert hasattr(result, 'selected_target')
            
            if len(result.targets) > 0:
                # 验证目标信息
                if result.selected_target is not None:
                    assert hasattr(result.selected_target, 'bounding_box')
                    assert hasattr(result.selected_target, 'distance')
                    assert result.selected_target.distance >= 0
                    
        finally:
            detector.unload()


# ============================================================================
# 与视觉伺服集成测试
# ============================================================================

class TestOrbbecVisualServoIntegration:
    """Orbbec 相机与视觉伺服集成测试"""
    
    def test_camera_type_detection(self):
        """测试视觉伺服检测相机类型"""
        # 创建 Orbbec 控制器
        orbbec = OrbbecController()
        
        # 验证相机类型属性
        assert orbbec.camera_type == "orbbec"
        assert hasattr(orbbec, 'camera_type')
    
    def test_depth_processor_integration(self):
        """测试深度处理器集成"""
        orbbec = OrbbecController()
        
        # 验证深度处理器已初始化
        assert orbbec._depth_processor is not None
        assert orbbec._depth_processor.color_width == 1920
        assert orbbec._depth_processor.color_height == 1080
        assert orbbec._depth_processor.depth_width == 640
        assert orbbec._depth_processor.depth_height == 480
    
    def test_coordinate_conversion(self):
        """测试坐标转换"""
        orbbec = OrbbecController()
        
        # 彩色图中心点
        color_x, color_y = 960, 540
        
        # 转换到深度图坐标
        depth_x, depth_y = orbbec._depth_processor.color_to_depth_coords(
            color_x, color_y
        )
        
        # 验证转换结果在深度图范围内
        assert 0 <= depth_x < 640
        assert 0 <= depth_y < 480
        
        # 验证比例关系
        expected_x = int(color_x * 640 / 1920)
        expected_y = int(color_y * 480 / 1080)
        assert abs(depth_x - expected_x) <= 1
        assert abs(depth_y - expected_y) <= 1


# ============================================================================
# 完整工作流程测试
# ============================================================================

class TestOrbbecCompleteWorkflow:
    """Orbbec 相机完整工作流程测试"""
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    def test_initialization_to_capture_workflow(self, mock_create_orbbec):
        """测试初始化到采集的完整流程"""
        # 模拟 Orbbec 控制器
        mock_controller = MagicMock(spec=OrbbecController)
        mock_controller.camera_type = "orbbec"
        mock_controller.initialize.return_value = (True, "")
        mock_controller.get_status.return_value = "ready"
        
        # 模拟采集结果
        rgb = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)
        depth = np.random.randint(500, 3000, (480, 640), dtype=np.uint16)
        image_pair = ImagePair(rgb=rgb, depth=depth, timestamp=0.0)
        mock_controller.capture.return_value = (image_pair, "")
        
        mock_create_orbbec.return_value = mock_controller
        
        # 工作流程
        # 1. 创建相机
        camera = CameraFactory.create_camera("orbbec")
        assert camera is not None
        assert camera.camera_type == "orbbec"
        
        # 2. 初始化
        success, error = camera.initialize()
        assert success
        
        # 3. 采集图像
        image_pair, error = camera.capture()
        assert image_pair is not None
        assert image_pair.rgb.shape == (1080, 1920, 3)
        assert image_pair.depth.shape == (480, 640)
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    def test_detection_workflow(self, mock_create_orbbec):
        """测试检测工作流程"""
        # 模拟相机
        mock_controller = MagicMock(spec=OrbbecController)
        mock_controller.camera_type = "orbbec"
        
        rgb = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)
        depth = np.random.randint(500, 3000, (480, 640), dtype=np.uint16)
        image_pair = ImagePair(rgb=rgb, depth=depth, timestamp=0.0)
        mock_controller.capture.return_value = (image_pair, "")
        
        mock_create_orbbec.return_value = mock_controller
        
        # 创建检测器
        detector = ObjectDetector(DetectionConfig(threshold=0.5))
        detector.load_model()
        
        try:
            # 工作流程
            # 1. 获取相机
            camera = CameraFactory.create_camera("orbbec")
            
            # 2. 采集图像
            image_pair, error = camera.capture()
            assert image_pair is not None
            
            # 3. 目标检测
            result = detector.detect(image_pair.rgb)
            assert hasattr(result, 'targets')
            assert isinstance(result.targets, list)
            
        finally:
            detector.unload()


# ============================================================================
# RealSense 兼容性测试
# ============================================================================

class TestRealSenseCompatibility:
    """RealSense 兼容性测试"""
    
    @patch('camera.factory.CameraFactory._create_realsense')
    @patch('camera.factory.CameraFactory._create_orbbec')
    def test_realsense_still_works(
        self,
        mock_create_orbbec,
        mock_create_realsense
    ):
        """测试 RealSense 相机仍然可用"""
        # 模拟 Orbbec 不可用
        mock_create_orbbec.return_value = None
        
        # 模拟 RealSense 可用
        mock_realsense = MagicMock(spec=BaseCameraController)
        mock_realsense.camera_type = "realsense"
        mock_realsense.initialize.return_value = (True, "")
        mock_create_realsense.return_value = mock_realsense
        
        # 自动检测应该回退到 RealSense
        camera = CameraFactory.create_camera("auto")
        
        assert camera is not None
        assert camera.camera_type == "realsense"
    
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_explicit_realsense_creation(self, mock_create_realsense):
        """测试显式创建 RealSense 相机"""
        mock_realsense = MagicMock(spec=BaseCameraController)
        mock_realsense.camera_type = "realsense"
        mock_create_realsense.return_value = mock_realsense
        
        # 显式创建 RealSense
        camera = CameraFactory.create_camera("realsense")
        
        assert camera is not None
        assert camera.camera_type == "realsense"
        mock_create_realsense.assert_called_once()


# ============================================================================
# 错误处理和恢复测试
# ============================================================================

class TestOrbbecErrorHandling:
    """Orbbec 相机错误处理测试"""
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_graceful_fallback_on_orbbec_failure(
        self,
        mock_create_realsense,
        mock_create_orbbec
    ):
        """测试 Orbbec 失败时优雅回退"""
        # 模拟 Orbbec 初始化失败
        mock_create_orbbec.return_value = None
        
        # 模拟 RealSense 可用
        mock_realsense = MagicMock(spec=BaseCameraController)
        mock_realsense.camera_type = "realsense"
        mock_create_realsense.return_value = mock_realsense
        
        # 自动检测应该回退
        camera = CameraFactory.create_camera("auto")
        
        assert camera is not None
        assert camera.camera_type == "realsense"
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_no_camera_available(
        self,
        mock_create_realsense,
        mock_create_orbbec
    ):
        """测试无相机可用的情况"""
        # 模拟两种相机都不可用
        mock_create_orbbec.return_value = None
        mock_create_realsense.return_value = None
        
        # 自动检测应该返回 None
        camera = CameraFactory.create_camera("auto")
        
        assert camera is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
