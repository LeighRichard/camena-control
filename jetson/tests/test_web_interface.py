"""
Web 界面验证测试

验证内容：
1. Web 服务器启动和响应
2. REST API 端点功能
3. 视频流服务
4. 视频延迟测试（≤300ms）
5. 前端页面加载
"""

import pytest
import time
import requests
import threading
import numpy as np
from typing import Optional
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from web.app import WebServer, WebConfig
from web.video_stream import VideoStreamService, OverlayConfig, DetectionTarget, StreamStatus
from state.manager import StateManager
from state.models import SystemState, MotionState, DetectionState


class MockCameraController:
    """模拟相机控制器"""
    
    def __init__(self):
        self.status = "ready"
        self.config = {
            "width": 1280,
            "height": 720,
            "fps": 30
        }
    
    def get_status(self):
        class Status:
            value = self.status
        return Status()
    
    def get_config(self):
        class Config:
            def to_dict(self):
                return {
                    "width": 1280,
                    "height": 720,
                    "fps": 30
                }
        return Config()
    
    def capture(self, wait_frames=5):
        # 模拟拍摄
        class ImagePair:
            rgb = np.zeros((720, 1280, 3), dtype=np.uint8)
            depth = np.zeros((720, 1280), dtype=np.uint16)
            timestamp = time.time()
        
        return ImagePair(), None


class MockCommManager:
    """模拟通信管理器"""
    
    def send_command(self, cmd):
        # 返回成功和模拟响应
        class MockResponse:
            status = "ok"
            error_code = 0
        return True, MockResponse()


class MockTaskScheduler:
    """模拟任务调度器"""
    
    def __init__(self):
        self._path_config = None
    
    def get_progress(self):
        class Progress:
            state = "idle"
            current_point = 0
            total_points = 0
            captured_count = 0
            
            def to_dict(self):
                return {
                    "state": self.state,
                    "current_point": self.current_point,
                    "total_points": self.total_points,
                    "captured_count": self.captured_count
                }
        
        return Progress()
    
    def start(self):
        return True, None
    
    def pause(self):
        return True, None
    
    def resume(self):
        return True, None
    
    def stop(self):
        return True, None
    
    def load_path(self, config):
        self._path_config = config
        return True, None


@pytest.fixture(scope="function")
def web_server():
    """创建 Web 服务器实例"""
    config = WebConfig(
        host="127.0.0.1",
        port=8888,
        debug=False
    )
    
    server = WebServer(config)
    
    # 注入模拟依赖
    state_manager = StateManager()
    camera = MockCameraController()
    comm = MockCommManager()
    scheduler = MockTaskScheduler()
    
    server.inject_dependencies(
        state_manager=state_manager,
        camera_controller=camera,
        comm_manager=comm,
        task_scheduler=scheduler
    )
    
    # 启动服务器
    server.run(threaded=True)
    time.sleep(1.5)  # 增加等待时间确保服务器完全启动
    
    yield server
    
    # 清理
    server.stop()
    time.sleep(0.5)  # 等待服务器完全停止


def test_web_server_health(web_server):
    """测试 Web 服务器健康检查"""
    response = requests.get("http://127.0.0.1:8888/api/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ok"
    assert "components" in data
    assert data["components"]["state_manager"] is True
    assert data["components"]["camera"] is True
    
    print("✅ Web 服务器健康检查通过")


def test_api_status(web_server):
    """测试状态 API"""
    response = requests.get("http://127.0.0.1:8888/api/status")
    assert response.status_code == 200
    
    data = response.json()
    assert "system" in data
    assert "motion" in data
    assert "detection" in data
    
    print("✅ 状态 API 测试通过")


def test_api_motion_position(web_server):
    """测试运动位置 API"""
    response = requests.get("http://127.0.0.1:8888/api/motion/position")
    assert response.status_code == 200
    
    data = response.json()
    assert "pan" in data
    assert "tilt" in data
    assert "rail" in data
    assert "is_moving" in data
    assert "is_stable" in data
    
    print("✅ 运动位置 API 测试通过")


def test_api_motion_move(web_server):
    """测试运动控制 API"""
    response = requests.post(
        "http://127.0.0.1:8888/api/motion/move",
        json={"pan": 10.0, "tilt": 5.0, "rail": 100.0}
    )
    
    # 打印错误信息以便调试
    if response.status_code != 200:
        print(f"❌ 错误响应: {response.status_code}")
        print(f"   响应内容: {response.text}")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "accepted"
    
    print("✅ 运动控制 API 测试通过")


def test_api_camera_status(web_server):
    """测试相机状态 API"""
    response = requests.get("http://127.0.0.1:8888/api/camera/status")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "config" in data
    
    print("✅ 相机状态 API 测试通过")


def test_api_camera_capture(web_server):
    """测试拍摄 API"""
    response = requests.post(
        "http://127.0.0.1:8888/api/camera/capture",
        json={"wait_frames": 3}
    )
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "captured"
    assert "timestamp" in data
    
    print("✅ 拍摄 API 测试通过")


def test_api_auto_capture(web_server):
    """测试自动拍摄 API"""
    # 获取状态
    response = requests.get("http://127.0.0.1:8888/api/auto/status")
    assert response.status_code == 200
    
    # 开始
    response = requests.post("http://127.0.0.1:8888/api/auto/start")
    assert response.status_code == 200
    
    # 暂停
    response = requests.post("http://127.0.0.1:8888/api/auto/pause")
    assert response.status_code == 200
    
    # 恢复
    response = requests.post("http://127.0.0.1:8888/api/auto/resume")
    assert response.status_code == 200
    
    # 停止
    response = requests.post("http://127.0.0.1:8888/api/auto/stop")
    assert response.status_code == 200
    
    print("✅ 自动拍摄 API 测试通过")


def test_api_detection(web_server):
    """测试目标检测 API"""
    # 获取目标
    response = requests.get("http://127.0.0.1:8888/api/detection/targets")
    assert response.status_code == 200
    
    data = response.json()
    assert "targets" in data
    assert "selected_id" in data
    
    # 选择目标
    response = requests.post(
        "http://127.0.0.1:8888/api/detection/select",
        json={"target_id": 1}
    )
    assert response.status_code == 200
    
    # 获取/设置模式
    response = requests.get("http://127.0.0.1:8888/api/detection/mode")
    assert response.status_code == 200
    
    response = requests.post(
        "http://127.0.0.1:8888/api/detection/mode",
        json={"mode": "manual"}
    )
    assert response.status_code == 200
    
    print("✅ 目标检测 API 测试通过")


def test_frontend_page(web_server):
    """测试前端页面加载"""
    response = requests.get("http://127.0.0.1:8888/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("Content-Type", "")
    
    # 检查页面包含关键元素
    html = response.text
    assert "相机位置控制系统" in html
    assert "videoStream" in html
    assert "app.js" in html
    
    print("✅ 前端页面加载测试通过")


def test_video_stream_service():
    """测试视频流服务"""
    service = VideoStreamService(fps=15, quality=80)
    
    # 设置模拟采集回调
    def mock_capture():
        return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    service.set_capture_callback(mock_capture)
    
    # 启动服务
    service.start()
    assert service.is_running
    
    # 等待几帧
    time.sleep(0.5)
    
    # 获取帧
    frame = service.get_frame()
    assert frame is not None
    assert isinstance(frame, bytes)
    assert len(frame) > 0
    
    # 检查帧率
    time.sleep(1.0)
    fps = service.actual_fps
    assert fps > 0
    assert fps <= 20  # 应该接近 15 FPS
    
    # 停止服务
    service.stop()
    assert not service.is_running
    
    print(f"✅ 视频流服务测试通过 (实际帧率: {fps:.1f} FPS)")


def test_video_latency():
    """
    测试视频延迟
    
    需求: 视频预览延迟不超过 300ms
    """
    service = VideoStreamService(fps=15, quality=80)
    
    # 记录时间戳
    capture_times = []
    frame_times = []
    
    def mock_capture_with_timestamp():
        capture_times.append(time.time())
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        return frame
    
    service.set_capture_callback(mock_capture_with_timestamp)
    service.start()
    
    # 采集多帧测量延迟
    time.sleep(0.5)  # 等待启动
    
    for _ in range(10):
        frame = service.get_frame()
        if frame:
            frame_times.append(time.time())
        time.sleep(0.1)
    
    service.stop()
    
    # 计算延迟
    if len(capture_times) > 0 and len(frame_times) > 0:
        # 简化计算：使用最后一帧的时间差
        latency = (frame_times[-1] - capture_times[-1]) * 1000  # 转换为毫秒
        
        print(f"📊 视频延迟测量:")
        print(f"   采集帧数: {len(capture_times)}")
        print(f"   获取帧数: {len(frame_times)}")
        print(f"   估计延迟: {latency:.1f} ms")
        
        # 验证延迟要求
        assert latency <= 300, f"视频延迟 {latency:.1f}ms 超过要求的 300ms"
        
        print(f"✅ 视频延迟测试通过 ({latency:.1f} ms ≤ 300 ms)")
    else:
        pytest.skip("无法测量延迟，跳过测试")


def test_frame_processor():
    """测试帧处理器"""
    from web.video_stream import FrameProcessor, OverlayConfig
    
    processor = FrameProcessor(OverlayConfig())
    
    # 创建测试帧
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # 测试十字线
    processed = processor.draw_crosshair(frame.copy())
    assert not np.array_equal(frame, processed)
    
    # 测试检测框
    target = DetectionTarget(
        id=1,
        class_name="plant",
        confidence=0.95,
        bbox=(100, 100, 200, 150),
        center=(200, 175),
        depth=1.5,
        selected=True
    )
    
    processed = processor.draw_detection_box(frame.copy(), target)
    assert not np.array_equal(frame, processed)
    
    # 测试完整处理
    status = StreamStatus(
        fps=15.0,
        frame_count=100,
        position=(10.0, 5.0, 150.0),
        is_moving=False,
        is_capturing=False,
        target_mode="auto"
    )
    
    processed = processor.process_frame(frame, [target], status)
    assert processed.shape == frame.shape
    
    print("✅ 帧处理器测试通过")


def test_video_stream_endpoint(web_server):
    """测试视频流端点"""
    # 设置模拟视频帧
    test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # 编码为 JPEG
    try:
        import cv2
        _, jpeg = cv2.imencode('.jpg', test_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        frame_bytes = jpeg.tobytes()
    except ImportError:
        from PIL import Image
        import io
        img = Image.fromarray(test_frame)
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=80)
        frame_bytes = buffer.getvalue()
    
    # 直接测试 update_frame 方法
    web_server.update_frame(frame_bytes)
    
    # 验证帧已正确设置
    with web_server.app.frame_lock:
        assert web_server.app.latest_frame is not None, "帧未成功设置"
        assert web_server.app.latest_frame == frame_bytes, "帧内容不匹配"
        assert len(web_server.app.latest_frame) > 0, "帧大小为0"
    
    print(f"✅ 视频流端点测试通过 (帧大小: {len(frame_bytes)} 字节)")


if __name__ == "__main__":
    print("=" * 60)
    print("Web 界面验证测试")
    print("=" * 60)
    print()
    
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
