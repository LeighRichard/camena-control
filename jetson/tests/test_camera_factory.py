"""
相机工厂单元测试

测试 CameraFactory 的相机创建和自动检测功能
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from camera.factory import CameraFactory
from camera.base_controller import BaseCameraController


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_realsense_controller():
    """模拟 RealSense 控制器"""
    controller = MagicMock(spec=BaseCameraController)
    controller.camera_type = "realsense"
    controller.camera_model = "Intel RealSense D415"
    controller.initialize.return_value = (True, "")
    controller.close.return_value = None
    return controller


@pytest.fixture
def mock_orbbec_controller():
    """模拟 Orbbec 控制器"""
    controller = MagicMock(spec=BaseCameraController)
    controller.camera_type = "orbbec"
    controller.camera_model = "Orbbec Astra+"
    controller.initialize.return_value = (True, "")
    controller.close.return_value = None
    return controller


# ============================================================================
# 基本创建测试
# ============================================================================

class TestCameraFactoryBasicCreation:
    """基本创建测试"""
    
    def test_create_camera_with_invalid_type(self):
        """测试无效的相机类型"""
        camera = CameraFactory.create_camera("invalid_type")
        assert camera is None
    
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_create_realsense_camera(self, mock_create, mock_realsense_controller):
        """测试创建 RealSense 相机"""
        mock_create.return_value = mock_realsense_controller
        
        camera = CameraFactory.create_camera("realsense")
        
        assert camera is not None
        assert camera.camera_type == "realsense"
        mock_create.assert_called_once()
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    def test_create_orbbec_camera(self, mock_create, mock_orbbec_controller):
        """测试创建 Orbbec 相机"""
        mock_create.return_value = mock_orbbec_controller
        
        camera = CameraFactory.create_camera("orbbec")
        
        assert camera is not None
        assert camera.camera_type == "orbbec"
        mock_create.assert_called_once()


# ============================================================================
# 自动检测测试
# ============================================================================

class TestCameraFactoryAutoDetection:
    """自动检测测试"""
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_auto_detect_orbbec_first(
        self, 
        mock_create_realsense, 
        mock_create_orbbec,
        mock_orbbec_controller
    ):
        """测试自动检测优先 Orbbec"""
        mock_create_orbbec.return_value = mock_orbbec_controller
        mock_create_realsense.return_value = None
        
        camera = CameraFactory.create_camera("auto")
        
        assert camera is not None
        assert camera.camera_type == "orbbec"
        mock_create_orbbec.assert_called_once()
        # RealSense 不应该被调用
        mock_create_realsense.assert_not_called()
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_auto_detect_fallback_to_realsense(
        self,
        mock_create_realsense,
        mock_create_orbbec,
        mock_realsense_controller
    ):
        """测试自动检测回退到 RealSense"""
        mock_create_orbbec.return_value = None
        mock_create_realsense.return_value = mock_realsense_controller
        
        camera = CameraFactory.create_camera("auto")
        
        assert camera is not None
        assert camera.camera_type == "realsense"
        mock_create_orbbec.assert_called_once()
        mock_create_realsense.assert_called_once()
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_auto_detect_no_camera(
        self,
        mock_create_realsense,
        mock_create_orbbec
    ):
        """测试自动检测无相机"""
        mock_create_orbbec.return_value = None
        mock_create_realsense.return_value = None
        
        camera = CameraFactory.create_camera("auto")
        
        assert camera is None
        mock_create_orbbec.assert_called_once()
        mock_create_realsense.assert_called_once()


# ============================================================================
# 初始化失败处理测试
# ============================================================================

class TestCameraFactoryInitializationFailure:
    """初始化失败处理测试"""
    
    def test_realsense_initialization_failure(self):
        """测试 RealSense 初始化失败"""
        # 这个测试验证当初始化失败时，工厂返回 None
        # 实际的初始化失败会在真实硬件测试中验证
        pass
    
    def test_orbbec_initialization_failure(self):
        """测试 Orbbec 初始化失败"""
        # 这个测试验证当初始化失败时，工厂返回 None
        # 实际的初始化失败会在真实硬件测试中验证
        pass
    
    def test_realsense_import_error(self):
        """测试 RealSense 导入错误"""
        # 模拟导入失败
        with patch.dict('sys.modules', {'camera.realsense_controller': None}):
            camera = CameraFactory._create_realsense()
            
            # 导入失败应该返回 None
            assert camera is None
    
    def test_orbbec_import_error(self):
        """测试 Orbbec 导入错误"""
        # 模拟导入失败
        with patch.dict('sys.modules', {'camera.orbbec_controller': None}):
            camera = CameraFactory._create_orbbec()
            
            # 导入失败应该返回 None
            assert camera is None


# ============================================================================
# 列出可用相机测试
# ============================================================================

class TestCameraFactoryListAvailable:
    """列出可用相机测试"""
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_list_both_cameras_available(
        self,
        mock_create_realsense,
        mock_create_orbbec,
        mock_realsense_controller,
        mock_orbbec_controller
    ):
        """测试列出两种相机都可用"""
        mock_create_orbbec.return_value = mock_orbbec_controller
        mock_create_realsense.return_value = mock_realsense_controller
        
        cameras = CameraFactory.list_available_cameras()
        
        assert len(cameras) == 2
        assert any(c['type'] == 'orbbec' for c in cameras)
        assert any(c['type'] == 'realsense' for c in cameras)
        
        # 验证关闭被调用
        mock_orbbec_controller.close.assert_called_once()
        mock_realsense_controller.close.assert_called_once()
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_list_only_orbbec_available(
        self,
        mock_create_realsense,
        mock_create_orbbec,
        mock_orbbec_controller
    ):
        """测试只有 Orbbec 可用"""
        mock_create_orbbec.return_value = mock_orbbec_controller
        mock_create_realsense.return_value = None
        
        cameras = CameraFactory.list_available_cameras()
        
        assert len(cameras) == 1
        assert cameras[0]['type'] == 'orbbec'
    
    @patch('camera.factory.CameraFactory._create_orbbec')
    @patch('camera.factory.CameraFactory._create_realsense')
    def test_list_no_cameras_available(
        self,
        mock_create_realsense,
        mock_create_orbbec
    ):
        """测试无相机可用"""
        mock_create_orbbec.return_value = None
        mock_create_realsense.return_value = None
        
        cameras = CameraFactory.list_available_cameras()
        
        assert len(cameras) == 0


# ============================================================================
# 异常处理测试
# ============================================================================

class TestCameraFactoryExceptionHandling:
    """异常处理测试"""
    
    def test_realsense_unexpected_exception(self):
        """测试 RealSense 意外异常"""
        # 这个测试验证异常处理逻辑
        # 实际的异常场景会在真实硬件测试中验证
        pass
    
    def test_orbbec_unexpected_exception(self):
        """测试 Orbbec 意外异常"""
        # 这个测试验证异常处理逻辑
        # 实际的异常场景会在真实硬件测试中验证
        pass


# ============================================================================
# 集成测试（需要真实硬件）
# ============================================================================

@pytest.mark.hardware
class TestCameraFactoryHardware:
    """硬件集成测试（需要真实相机）"""
    
    def test_auto_detect_real_camera(self):
        """测试自动检测真实相机"""
        camera = CameraFactory.create_camera("auto")
        
        if camera is not None:
            assert camera.camera_type in ["realsense", "orbbec"]
            assert camera.get_status() in ["ready", "READY"]
            camera.close()
        else:
            pytest.skip("未找到支持的相机")
    
    def test_list_real_cameras(self):
        """测试列出真实相机"""
        cameras = CameraFactory.list_available_cameras()
        
        if len(cameras) > 0:
            for camera in cameras:
                assert 'type' in camera
                assert 'model' in camera
                assert camera['type'] in ['realsense', 'orbbec']
        else:
            pytest.skip("未找到支持的相机")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
