"""
Camera factory.

Jetson strategy:
- Orbbec: force OpenNI2 Python backend (depth-only stable path)
- Web preview color is captured by UVC/OpenCV in main.py mixed pipeline.
"""

from typing import Optional, Dict, Any
import importlib
import logging

from .base_controller import BaseCameraController

logger = logging.getLogger(__name__)


class CameraFactory:
    """Create camera controllers by type."""

    @staticmethod
    def create_camera(
        camera_type: str = "auto",
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[BaseCameraController]:
        if camera_type == "realsense":
            return CameraFactory._create_realsense(config)
        if camera_type == "orbbec":
            return CameraFactory._create_orbbec(config)
        if camera_type == "auto":
            return CameraFactory._auto_detect(config)

        logger.error(f"Unsupported camera type: {camera_type}")
        return None

    @staticmethod
    def _create_realsense(config: Optional[Dict[str, Any]] = None) -> Optional[BaseCameraController]:
        controller = None
        success = False
        try:
            from .realsense_controller import RealSenseController

            controller = RealSenseController()
            success, error = controller.initialize()
            if success:
                logger.info(f"RealSense initialized: {controller.camera_model}")
                return controller

            logger.warning(f"RealSense initialize failed: {error}")
            return None
        except ImportError as e:
            logger.warning(f"RealSense controller import failed: {e}")
            return None
        except Exception as e:
            logger.error(f"RealSense creation failed: {e}")
            return None
        finally:
            if controller is not None and not success:
                try:
                    controller.close()
                except Exception:
                    pass

    @staticmethod
    def _create_orbbec(config: Optional[Dict[str, Any]] = None) -> Optional[BaseCameraController]:
        """
        Force single stable backend: OpenNI2 Python depth-only controller.
        """

        def try_create_controller(
            module_name: str,
            class_name: str,
            backend_name: str,
        ) -> Optional[BaseCameraController]:
            controller = None
            success = False
            try:
                module = importlib.import_module(f".{module_name}", package="camera")
                controller_class = getattr(module, class_name)

                controller = controller_class()
                success, error = controller.initialize()
                if success:
                    logger.info(f"Orbbec initialized ({backend_name}): {controller.camera_model}")
                    return controller

                logger.warning(f"Orbbec initialize failed ({backend_name}): {error}")
                return None
            except ImportError as e:
                logger.debug(f"Orbbec controller import failed ({backend_name}): {e}")
                return None
            except Exception as e:
                logger.warning(f"Orbbec creation failed ({backend_name}): {e}")
                return None
            finally:
                if controller is not None and not success:
                    try:
                        controller.close()
                    except Exception:
                        pass

        backends = [
            ("orbbec_controller_openni2_python", "OrbbecControllerOpenNI2Python", "OpenNI2 Python"),
        ]

        for module_name, class_name, backend_name in backends:
            logger.info(f"Trying Orbbec backend: {backend_name}")
            controller = try_create_controller(module_name, class_name, backend_name)
            if controller is not None:
                return controller

        logger.error("OpenNI2 Python backend initialization failed.")
        return None

    @staticmethod
    def _auto_detect(config: Optional[Dict[str, Any]] = None) -> Optional[BaseCameraController]:
        logger.info("Auto-detecting camera...")

        logger.info("Trying Orbbec...")
        controller = CameraFactory._create_orbbec(config)
        if controller is not None:
            logger.info("Auto-detect success: Orbbec")
            return controller

        logger.info("Trying RealSense...")
        controller = CameraFactory._create_realsense(config)
        if controller is not None:
            logger.info("Auto-detect success: RealSense")
            return controller

        logger.error("Auto-detect failed: no supported camera found")
        return None

    @staticmethod
    def list_available_cameras() -> list:
        available = []

        controller = CameraFactory._create_orbbec()
        if controller is not None:
            available.append({"type": controller.camera_type, "model": controller.camera_model})
            controller.close()

        controller = CameraFactory._create_realsense()
        if controller is not None:
            available.append({"type": controller.camera_type, "model": controller.camera_model})
            controller.close()

        return available
