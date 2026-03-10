"""
相机工厂 - 根据配置创建相应的相机控制器

支持自动检测和手动指定相机类型
"""

from typing import Optional
import logging

from .base_controller import BaseCameraController

logger = logging.getLogger(__name__)


class CameraFactory:
    """相机工厂类"""
    
    @staticmethod
    def create_camera(camera_type: str = "auto") -> Optional[BaseCameraController]:
        """
        创建相机控制器
        
        Args:
            camera_type: 相机类型
                - "realsense": Intel RealSense 系列
                - "orbbec": 奥比中光系列
                - "auto": 自动检测（优先 Orbbec，后备 RealSense）
            
        Returns:
            相机控制器实例，失败返回 None
        """
        if camera_type == "realsense":
            return CameraFactory._create_realsense()
        
        elif camera_type == "orbbec":
            return CameraFactory._create_orbbec()
        
        elif camera_type == "auto":
            return CameraFactory._auto_detect()
        
        else:
            logger.error(f"不支持的相机类型: {camera_type}")
            return None
    
    @staticmethod
    def _create_realsense() -> Optional[BaseCameraController]:
        """
        创建 RealSense 相机控制器
        
        Returns:
            RealSense 控制器实例，失败返回 None
        """
        try:
            from .realsense_controller import RealSenseController
            
            controller = RealSenseController()
            success, error = controller.initialize()
            
            if success:
                logger.info(f"成功创建 RealSense 相机: {controller.camera_model}")
                return controller
            else:
                logger.warning(f"RealSense 相机初始化失败: {error}")
                controller.close()
                return None
                
        except ImportError as e:
            logger.warning(f"无法导入 RealSense 控制器: {e}")
            return None
        except Exception as e:
            logger.error(f"创建 RealSense 相机失败: {e}")
            return None
    
    @staticmethod
    def _create_orbbec() -> Optional[BaseCameraController]:
        """
        创建 Orbbec 相机控制器
        
        Returns:
            Orbbec 控制器实例，失败返回 None
        """
        try:
            from .orbbec_controller import OrbbecController
            
            controller = OrbbecController()
            success, error = controller.initialize()
            
            if success:
                logger.info(f"成功创建奥比中光相机: {controller.camera_model}")
                return controller
            else:
                logger.warning(f"奥比中光相机初始化失败: {error}")
                controller.close()
                return None
                
        except ImportError as e:
            logger.warning(f"无法导入 Orbbec 控制器: {e}")
            return None
        except Exception as e:
            logger.error(f"创建奥比中光相机失败: {e}")
            return None
    
    @staticmethod
    def _auto_detect() -> Optional[BaseCameraController]:
        """
        自动检测并创建相机控制器
        
        检测顺序:
        1. 优先尝试 Orbbec（成本更低，国产化）
        2. 后备尝试 RealSense
        
        Returns:
            相机控制器实例，失败返回 None
        """
        logger.info("开始自动检测相机...")
        
        # 优先尝试 Orbbec
        logger.info("尝试检测奥比中光相机...")
        controller = CameraFactory._create_orbbec()
        if controller is not None:
            logger.info("✅ 自动检测成功: 奥比中光相机")
            return controller
        
        # 尝试 RealSense
        logger.info("尝试检测 RealSense 相机...")
        controller = CameraFactory._create_realsense()
        if controller is not None:
            logger.info("✅ 自动检测成功: RealSense 相机")
            return controller
        
        # 都失败
        logger.error("❌ 自动检测失败: 未找到支持的相机")
        return None
    
    @staticmethod
    def list_available_cameras() -> list:
        """
        列出所有可用的相机
        
        Returns:
            可用相机列表，每项包含 type 和 model
        """
        available = []
        
        # 检测 Orbbec
        controller = CameraFactory._create_orbbec()
        if controller is not None:
            available.append({
                'type': controller.camera_type,
                'model': controller.camera_model
            })
            controller.close()
        
        # 检测 RealSense
        controller = CameraFactory._create_realsense()
        if controller is not None:
            available.append({
                'type': controller.camera_type,
                'model': controller.camera_model
            })
            controller.close()
        
        return available
