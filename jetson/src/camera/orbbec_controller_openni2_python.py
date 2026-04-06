"""
Orbbec camera controller based on OpenNI2 Python binding (depth-only mode).

This controller intentionally only owns the depth stream so that UVC color
can be captured by OpenCV in a separate path without USB resource conflicts.
"""

from typing import Optional, Tuple
from enum import Enum
import logging
import os
import time
import threading

import numpy as np

from .base_controller import BaseCameraController, ImagePair, CameraConfig
from .depth_processor import DepthProcessor

logger = logging.getLogger(__name__)


class CameraStatus(Enum):
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    READY = "ready"
    CAPTURING = "capturing"
    ERROR = "error"


class OrbbecControllerOpenNI2Python(BaseCameraController):
    # Stable low-latency defaults for web mixed preview pipeline.
    MIN_STABLE_FRAMES = 0
    DEFAULT_WAIT_FRAMES = 0
    DEFAULT_COLOR_WIDTH = 640
    DEFAULT_COLOR_HEIGHT = 480
    DEFAULT_DEPTH_WIDTH = 640
    DEFAULT_DEPTH_HEIGHT = 480
    DEFAULT_FPS = 30

    def __init__(self):
        self._status = CameraStatus.DISCONNECTED
        self._camera_config = CameraConfig(
            width=self.DEFAULT_COLOR_WIDTH,
            height=self.DEFAULT_COLOR_HEIGHT,
            fps=self.DEFAULT_FPS,
        )
        self._last_error = ""
        self._device_info = {}

        self._openni2 = None
        self._device = None
        self._depth_stream = None
        self._capture_lock = threading.Lock()

        self._depth_processor = DepthProcessor(
            color_size=(self.DEFAULT_COLOR_WIDTH, self.DEFAULT_COLOR_HEIGHT),
            depth_size=(self.DEFAULT_DEPTH_WIDTH, self.DEFAULT_DEPTH_HEIGHT),
            filter_size=5,
            min_depth=0.6,
            max_depth=8.0,
        )

    @property
    def camera_type(self) -> str:
        return "orbbec-openni2-python"

    @property
    def camera_model(self) -> str:
        if self._device_info:
            return self._device_info.get("name", "Unknown Orbbec")
        return "Orbbec Camera (Depth Only)"

    def _find_openni2_path(self) -> Optional[str]:
        candidates = [
            os.environ.get("OPENNI2_REDIST", ""),
            os.path.expanduser("~/OpenNI-Linux-Arm64-2.3/Redist"),
            "/usr/local/lib/OpenNI2",
            "/usr/lib/OpenNI2",
            "/opt/OpenNI2",
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def _setup_openni2_env(self) -> Tuple[bool, str]:
        redist_path = self._find_openni2_path()
        if not redist_path:
            return False, "OpenNI2 Redist path not found"

        os.environ["OPENNI2_REDIST"] = redist_path
        current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        if redist_path not in current_ld_path:
            os.environ["LD_LIBRARY_PATH"] = f"{redist_path}:{current_ld_path}".strip(":")
        return True, redist_path

    def initialize(self) -> Tuple[bool, str]:
        if (
            self._status in (CameraStatus.READY, CameraStatus.CAPTURING)
            and self._device is not None
            and self._depth_stream is not None
            and self._openni2 is not None
        ):
            return True, ""

        self._status = CameraStatus.INITIALIZING

        try:
            if self._device is not None or self._depth_stream is not None or self._openni2 is not None:
                self.close()

            ok, redist_path = self._setup_openni2_env()
            if not ok:
                self._status = CameraStatus.ERROR
                return False, redist_path

            try:
                from primesense import openni2
            except ImportError:
                import openni2

            try:
                openni2.initialize(redist_path)
            except TypeError:
                openni2.initialize()
            except Exception as init_error:
                if "already initialized" not in str(init_error).lower():
                    raise

            self._device = openni2.Device.open_any()
            if not self._device:
                self._status = CameraStatus.ERROR
                return False, "Unable to open Orbbec device"

            info = self._device.get_device_info()
            dev_name = getattr(info, "name", b"Orbbec Camera")
            if isinstance(dev_name, bytes):
                dev_name = dev_name.decode("utf-8", errors="ignore")
            else:
                dev_name = str(dev_name)

            try:
                if self._device.is_image_registration_mode_supported(
                    openni2.IMAGE_REGISTRATION_DEPTH_TO_COLOR
                ):
                    self._device.set_image_registration_mode(openni2.IMAGE_REGISTRATION_DEPTH_TO_COLOR)
            except Exception:
                pass

            self._depth_stream = self._device.create_depth_stream()
            self._depth_stream.start()

            self._openni2 = openni2
            self._device_info = {"name": dev_name, "vendor": "Orbbec"}
            self._status = CameraStatus.READY
            logger.info(f"OpenNI2 depth-only backend ready: {dev_name}")
            return True, ""

        except Exception as e:
            self._status = CameraStatus.ERROR
            self._last_error = str(e)
            logger.error(f"OpenNI2 depth-only initialize failed: {e}")
            return False, str(e)

    def capture(
        self,
        wait_frames: int = None,
        position: Tuple[float, float, float] = None,
    ) -> Tuple[Optional[ImagePair], str]:
        if self._status != CameraStatus.READY:
            return None, f"camera not ready: {self._status.value}"

        wait_frames = self.DEFAULT_WAIT_FRAMES if wait_frames is None else wait_frames
        if wait_frames < 0:
            return None, f"invalid wait_frames: {wait_frames}"

        self._status = CameraStatus.CAPTURING
        try:
            # OpenNI2 depth stream read is not thread-safe.
            # Web preview loop and API requests may capture concurrently.
            with self._capture_lock:
                for _ in range(wait_frames):
                    if self._depth_stream:
                        self._depth_stream.read_frame()

                if not self._depth_stream:
                    self._status = CameraStatus.READY
                    return None, "depth stream is not available"

                depth_frame = self._depth_stream.read_frame()
                depth_data = depth_frame.get_buffer_as_uint16()
                depth_image = np.frombuffer(depth_data, dtype=np.uint16).reshape(
                    (depth_frame.height, depth_frame.width)
                ).copy()

            h, w = depth_image.shape
            dummy_rgb = np.zeros((h, w, 3), dtype=np.uint8)

            image_pair = ImagePair(
                rgb=dummy_rgb,
                depth=depth_image,
                timestamp=time.time(),
                position=position,
            )

            self._status = CameraStatus.READY
            return image_pair, ""
        except Exception as e:
            self._status = CameraStatus.READY
            logger.error(f"Depth capture failed: {e}")
            return None, str(e)

    def configure(self, config: CameraConfig) -> Tuple[bool, str]:
        self._camera_config = config
        return True, ""

    def get_status(self) -> str:
        return self._status.value

    def get_config(self) -> CameraConfig:
        return self._camera_config

    def get_intrinsics(self) -> Optional[dict]:
        return None

    def get_depth_at_point(self, x: int, y: int, depth_image: np.ndarray) -> float:
        if depth_image is None:
            return 0.0
        return self._depth_processor.get_depth_at_color_point(
            color_x=x,
            color_y=y,
            depth_image=depth_image,
            use_filter=True,
        )

    def get_depth_in_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        depth_image: np.ndarray,
        method: str = "median",
    ) -> float:
        if depth_image is None:
            return 0.0

        cx = x + width // 2
        cy = y + height // 2
        dx, dy = self._depth_processor.color_to_depth_coords(cx, cy)
        dw = int(width * self._depth_processor.scale_x)
        dh = int(height * self._depth_processor.scale_y)
        return self._depth_processor.get_depth_in_region(
            center_x=dx,
            center_y=dy,
            width=dw,
            height=dh,
            depth_image=depth_image,
            method=method,
        )

    def close(self):
        try:
            if self._depth_stream:
                self._depth_stream.stop()
                self._depth_stream = None
            if self._device:
                self._device.close()
                self._device = None
            if self._openni2:
                self._openni2.unload()
                self._openni2 = None
            self._status = CameraStatus.DISCONNECTED
        except Exception:
            pass
