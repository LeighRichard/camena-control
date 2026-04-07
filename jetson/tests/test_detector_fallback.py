import os
import sys
from unittest.mock import patch

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from vision.detector import DetectionConfig, DetectionResult, ObjectDetector


def test_missing_engine_uses_fallback_detector():
    detector = ObjectDetector(DetectionConfig(model_path="models/missing.engine"))

    def fake_loader(primary_error):
        detector._is_loaded = True
        detector._simulation_mode = False
        detector._inference_engine = "opencv-haar-face"
        detector._fallback_reason = primary_error
        detector._last_load_error = None
        return True, "opencv-haar-face"

    with patch.object(detector, "_load_opencv_haar_face_detector", side_effect=fake_loader), patch.object(
        detector,
        "_load_face_recognition_detector",
        return_value=(False, "unused"),
    ):
        success, _ = detector.load_model()

    status = detector.get_runtime_status()
    assert success is True
    assert status["loaded"] is True
    assert status["simulation_mode"] is False
    assert status["inference_engine"] == "opencv-haar-face"
    assert status["fallback_active"] is True
    assert "模型文件不存在" in (status["fallback_reason"] or "")


def test_detect_dispatches_to_opencv_fallback_backend():
    detector = ObjectDetector()
    detector._is_loaded = True
    detector._inference_engine = "opencv-haar-face"

    expected = DetectionResult(targets=[], selected_target=None, inference_time=1.0)
    sample = np.zeros((32, 32, 3), dtype=np.uint8)

    with patch.object(detector, "_detect_with_opencv_haar_face", return_value=expected) as patched:
        result = detector.detect(sample)

    patched.assert_called_once()
    assert result is expected
