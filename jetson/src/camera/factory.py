"""
相机工厂 - 根据配置创建相应的相机控制器

支持自动检测和手动指定相机类型
"""

from typing import Optional, Dict, Any
import logging

from .base_controller import BaseCameraController

logger = logging.getLogger(__name__)


class CameraFactory:
    """相机工厂类"""

    @staticmethod
    def create_camera(camera_type: str = "auto", config: Optional[Dict[str, Any]] = None) -> Optional[BaseCameraController]:
        """
        创建相机控制器

        Args:
            camera_type: 相机类型
                - "realsense": Intel RealSense 系列
                - "orbbec": 奥比中光系列
                - "auto": 自动检测（优先 Orbbec，后备 RealSense）
            config: 相机配置字典（可选）

        Returns:
            相机控制器实例，失败返回 None
        """
        if camera_type == "realsense":
            return CameraFactory._create_realsense(config)

        elif camera_type == "orbbec":
            return CameraFactory._create_orbbec(config)

        elif camera_type == "auto":
            return CameraFactory._auto_detect(config)

        else:
            logger.error(f"不支持的相机类型: {camera_type}")
            return None
    
    @staticmethod
    def _create_realsense(config: Optional[Dict[str, Any]] = None) -> Optional[BaseCameraController]:
        """
        创建 RealSense 相机控制器

        Args:
            config: 相机配置字典（可选）

        Returns:
            RealSense 控制器实例，失败返回 None
        """
        controller = None
        try:
            from .realsense_controller import RealSenseController

            controller = RealSenseController()
            success, error = controller.initialize()

            if success:
                logger.info(f"成功创建 RealSense 相机: {controller.camera_model}")
                return controller
            else:
                logger.warning(f"RealSense 相机初始化失败: {error}")
                return None

        except ImportError as e:
            logger.warning(f"无法导入 RealSense 控制器: {e}")
            return None
        except Exception as e:
            logger.error(f"创建 RealSense 相机失败: {e}")
            return None
        finally:
            # 确保失败时清理资源
            if controller is not None:
                try:
                    controller.close()
                except Exception:
                    pass

    @staticmethod
    def _create_orbbec(config: Optional[Dict[str, Any]] = None) -> Optional[BaseCameraController]:
        """
        创建 Orbbec 相机控制器

        优先级: OpenNI2直接访问 > 简化版 > libuvc_camera > ROS OpenNI2 > pyorbbecsdk

        Args:
            config: 相机配置字典（可选）

        Returns:
            Orbbec 控制器实例，失败返回 None
        """
        def try_create_controller(module_name: str, class_name: str, backend_name: str) -> Optional[BaseCameraController]:
            """尝试创建指定后端的控制器"""
            controller = None
            try:
                # 使用 importlib 动态导入模块
                import importlib
                module = importlib.import_module(f'.{module_name}', package='camera')
                controller_class = getattr(module, class_name)
                
                controller = controller_class()
                success, error = controller.initialize()
                
                if success:
                    logger.info(f"成功创建奥比中光相机 ({backend_name}): {controller.camera_model}")
                    return controller
                else:
                    logger.warning(f"奥比中光相机 ({backend_name}) 初始化失败: {error}")
                    return None
                    
            except ImportError as e:
                logger.debug(f"无法导入 Orbbec ({backend_name}) 控制器: {e}")
                return None
            except Exception as e:
                logger.warning(f"创建 Orbbec ({backend_name}) 相机失败: {e}")
                return None
            finally:
                # 确保失败时清理资源
                if controller is not None:
                    try:
                        controller.close()
                    except Exception:
                        pass
        
        # 按优先级尝试不同的后端
        backends = [
            ('orbbec_controller_openni2_python', 'OrbbecControllerOpenNI2Python', 'OpenNI2 Python'),
            ('orbbec_controller_ros', 'OrbbecControllerROS', 'ROS OpenNI2'),
            ('orbbec_controller_openni2_direct', 'OrbbecControllerOpenNI2Direct', 'OpenNI2直接'),
            ('orbbec_controller_simple', 'OrbbecControllerSimple', '简化版'),
            ('orbbec_controller_libuvc', 'OrbbecControllerLibUVC', 'libuvc'),
            ('orbbec_controller', 'OrbbecController', 'pyorbbecsdk'),
        ]
        
        for module_name, class_name, backend_name in backends:
            logger.info(f"尝试使用 {backend_name} 后端...")
            controller = try_create_controller(module_name, class_name, backend_name)
            if controller is not None:
                return controller

        return None

    @staticmethod
    def _auto_detect(config: Optional[Dict[str, Any]] = None) -> Optional[BaseCameraController]:
        """
        自动检测并创建相机控制器

        检测顺序:
        1. 优先尝试 Orbbec（成本更低，国产化）
        2. 后备尝试 RealSense

        Args:
            config: 相机配置字典（可选）

        Returns:
            相机控制器实例，失败返回 None
        """
        logger.info("开始自动检测相机...")

        # 优先尝试 Orbbec
        logger.info("尝试检测奥比中光相机...")
        controller = CameraFactory._create_orbbec(config)
        if controller is not None:
            logger.info("✅ 自动检测成功: 奥比中光相机")
            return controller

        # 尝试 RealSense
        logger.info("尝试检测 RealSense 相机...")
        controller = CameraFactory._create_realsense(config)
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
