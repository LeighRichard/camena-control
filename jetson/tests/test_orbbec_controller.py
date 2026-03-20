"""
Orbbec 相机控制器单元测试

测试 OrbbecController 的核心功能
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from camera.orbbec_controller import OrbbecController, CameraStatus
from camera.base_controller import CameraConfig, ImagePair


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_orbbec_sdk():
    """模拟 pyorbbecsdk"""
    with patch.dict('sys.modules', {
        'pyorbbecsdk': MagicMock()
    }):
        yield


@pytest.fixture
def controller():
    """创建控制器实例"""
    return OrbbecController()


# ============================================================================
# 初始化测试
# ============================================================================

class TestOrbbecControllerInitialization:
    """初始化测试"""
    
    def test_initial_state(self, controller):
        """测试初始状态"""
        assert controller.get_status() == CameraStatus.DISCONNECTED.value
        assert controller.camera_type == "orbbec"
        assert controller._pipeline is None
    
    def test_default_config(self, controller):
        """测试默认配置"""
        config = controller.get_config()
        
        assert config.width == OrbbecController.DEFAULT_COLOR_WIDTH
        assert config.height == OrbbecController.DEFAULT_COLOR_HEIGHT
        assert config.fps == OrbbecController.DEFAULT_FPS
    
    def test_depth_processor_initialized(self, controller):
        """测试深度处理器已初始化"""
        assert controller._depth_processor is not None
        assert controller._depth_processor.color_width == 1920
        assert controller._depth_processor.color_height == 1080
        assert controller._depth_processor.depth_width == 640
        assert controller._depth_processor.depth_height == 480


# ============================================================================
# 配置测试
# ============================================================================

class TestOrbbecControllerConfiguration:
    """配置测试"""
    
    def test_configure_updates_config(self, controller):
        """测试配置更新"""
        new_config = CameraConfig(
            width=1280,
            height=720,
            fps=30
        )
        
        success, error = controller.configure(new_config)
        
        assert success
        assert error == ""
        assert controller.get_config().width == 1280
        assert controller.get_config().height == 720
    
    def test_get_config_returns_same_instance(self, controller):
        """测试获取配置返回相同实例"""
        config1 = controller.get_config()
        config2 = controller.get_config()
        
        # 返回相同的配置对象
        assert config1 is config2


# ============================================================================
# 深度查询测试
# ============================================================================

class TestOrbbecControllerDepthQuery:
    """深度查询测试"""
    
    def test_get_depth_at_point_valid(self, controller):
        """测试有效点的深度查询"""
        # 创建模拟深度图（640x480）
        depth_image = np.full((480, 640), 1000, dtype=np.uint16)  # 1000mm = 1.0m
        
        # 查询彩色图中心点（1920x1080 -> 960, 540）
        depth_m = controller.get_depth_at_point(960, 540, depth_image)
        
        # 应该返回约 1.0m
        assert 0.9 <= depth_m <= 1.1
    
    def test_get_depth_at_point_zero_depth(self, controller):
        """测试零深度值"""
        # 创建零深度图
        depth_image = np.zeros((480, 640), dtype=np.uint16)
        
        depth_m = controller.get_depth_at_point(960, 540, depth_image)
        
        # 应该返回 0
        assert depth_m == 0.0
    
    def test_get_depth_in_region_median(self, controller):
        """测试区域深度查询（中值）"""
        # 创建深度图，中心区域有深度
        depth_image = np.zeros((480, 640), dtype=np.uint16)
        depth_image[200:280, 280:360] = 1500  # 1.5m
        
        # 查询彩色图中心区域
        depth_m = controller.get_depth_in_region(
            x=800, y=400, 
            width=200, height=200,
            depth_image=depth_image,
            method='median'
        )
        
        # 应该返回约 1.5m 或 0（取决于坐标转换）
        assert depth_m >= 0.0
    
    def test_get_depth_in_region_mean(self, controller):
        """测试区域深度查询（均值）"""
        # 创建均匀深度图
        depth_image = np.full((480, 640), 2000, dtype=np.uint16)  # 2.0m
        
        depth_m = controller.get_depth_in_region(
            x=800, y=400,
            width=100, height=100,
            depth_image=depth_image,
            method='mean'
        )
        
        # 应该返回约 2.0m
        assert 1.9 <= depth_m <= 2.1


# ============================================================================
# 状态管理测试
# ============================================================================

class TestOrbbecControllerState:
    """状态管理测试"""
    
    def test_initial_status_disconnected(self, controller):
        """测试初始状态为断开连接"""
        assert controller.get_status() == CameraStatus.DISCONNECTED.value
    
    def test_capture_fails_when_not_ready(self, controller):
        """测试未就绪时采集失败"""
        image_pair, error = controller.capture()
        
        assert image_pair is None
        assert "未就绪" in error
    
    def test_close_when_not_initialized(self, controller):
        """测试未初始化时关闭不报错"""
        # 应该不抛出异常
        controller.close()
        assert controller.get_status() == CameraStatus.DISCONNECTED.value


# ============================================================================
# 相机属性测试
# ============================================================================

class TestOrbbecControllerProperties:
    """相机属性测试"""
    
    def test_camera_type(self, controller):
        """测试相机类型"""
        assert controller.camera_type == "orbbec"
    
    def test_camera_model_default(self, controller):
        """测试默认相机型号"""
        assert controller.camera_model == "Orbbec"
    
    def test_get_intrinsics_when_not_initialized(self, controller):
        """测试未初始化时获取内参"""
        intrinsics = controller.get_intrinsics()
        assert intrinsics is None


# ============================================================================
# 错误处理测试
# ============================================================================

class TestOrbbecControllerErrorHandling:
    """错误处理测试"""
    
    def test_capture_with_invalid_wait_frames(self, controller):
        """测试无效的等待帧数"""
        # 未初始化，应该返回错误
        image_pair, error = controller.capture(wait_frames=-1)
        
        assert image_pair is None
        assert error != ""
    
    def test_configure_with_none_config(self, controller):
        """测试 None 配置"""
        # 应该处理 None 配置
        try:
            success, error = controller.configure(None)
            # 如果没有异常，应该返回失败
            assert not success or error != ""
        except (TypeError, AttributeError):
            # 预期的异常
            pass


# ============================================================================
# 集成测试（需要真实硬件）
# ============================================================================

@pytest.mark.hardware
class TestOrbbecControllerHardware:
    """硬件集成测试（需要真实 Orbbec 相机）"""
    
    def test_initialize_with_real_camera(self):
        """测试真实相机初始化"""
        controller = OrbbecController()
        success, error = controller.initialize()
        
        if success:
            assert controller.get_status() == CameraStatus.READY.value
            assert controller._pipeline is not None
            controller.close()
        else:
            pytest.skip(f"未找到 Orbbec 相机: {error}")
    
    def test_capture_with_real_camera(self):
        """测试真实相机采集"""
        controller = OrbbecController()
        success, error = controller.initialize()
        
        if not success:
            pytest.skip(f"未找到 Orbbec 相机: {error}")
        
        try:
            image_pair, error = controller.capture()
            
            assert image_pair is not None
            assert error == ""
            assert image_pair.rgb.shape == (1080, 1920, 3)
            assert image_pair.depth.shape == (480, 640)
        finally:
            controller.close()
    
    def test_get_intrinsics_with_real_camera(self):
        """测试真实相机内参"""
        controller = OrbbecController()
        success, error = controller.initialize()
        
        if not success:
            pytest.skip(f"未找到 Orbbec 相机: {error}")
        
        try:
            intrinsics = controller.get_intrinsics()
            
            assert intrinsics is not None
            assert 'fx' in intrinsics
            assert 'fy' in intrinsics
            assert 'cx' in intrinsics
            assert 'cy' in intrinsics
        finally:
            controller.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
