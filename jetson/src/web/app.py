"""
Web 应用模块 - 提供 REST API 和 WebSocket 实时通信

实现：
- REST API 用于系统控制
- WebSocket 用于实时状态推送
- MJPEG 视频流服务
- JWT 身份认证
- 自适应视频流
"""

from typing import Optional, Callable
from dataclasses import dataclass, field
import threading
import time
import logging
import json
import os
import secrets

logger = logging.getLogger(__name__)


def get_secret_key() -> str:
    """
    获取密钥，优先从环境变量读取，否则生成随机密钥
    
    环境变量:
        CAMERA_CONTROL_SECRET_KEY: 自定义密钥
        SECRET_KEY: 通用密钥（备用）
    """
    # 优先使用专用环境变量
    secret_key = os.environ.get('CAMERA_CONTROL_SECRET_KEY')
    if secret_key:
        return secret_key
    
    # 备用：使用通用环境变量
    secret_key = os.environ.get('SECRET_KEY')
    if secret_key:
        return secret_key
    
    # 生成随机密钥并警告
    logger.warning(
        "未设置密钥环境变量 (CAMERA_CONTROL_SECRET_KEY 或 SECRET_KEY)，"
        "已生成随机密钥。重启后令牌将失效。"
    )
    return secrets.token_hex(32)


@dataclass
class SSLConfig:
    """SSL/TLS 配置"""
    enabled: bool = False
    cert_file: str = "certs/cert.pem"
    key_file: str = "certs/key.pem"


@dataclass
class WebConfig:
    """Web 服务配置"""
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    secret_key: str = field(default_factory=get_secret_key)
    video_fps: int = 15
    video_quality: int = 80
    enable_auth: bool = False  # 启用身份认证
    enable_adaptive_streaming: bool = True  # 启用自适应流
    ssl: SSLConfig = None  # SSL 配置
    
    def __post_init__(self):
        if self.ssl is None:
            self.ssl = SSLConfig()


def create_app(config: Optional[WebConfig] = None):
    """
    创建 Flask 应用
    
    Args:
        config: Web 服务配置
        
    Returns:
        Flask 应用实例
    """
    try:
        from flask import Flask, jsonify, request, Response, send_from_directory
        from flask_cors import CORS
    except ImportError:
        logger.error("Flask 未安装，请运行: pip install flask flask-cors")
        return None
    
    import os
    
    config = config or WebConfig()
    static_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app = Flask(__name__, static_folder=static_folder, static_url_path='/static')
    app.config["SECRET_KEY"] = config.secret_key
    CORS(app)
    
    # 身份认证管理器
    if config.enable_auth:
        from network.auth import AuthManager, Permission
        app.auth_manager = AuthManager(secret_key=config.secret_key)
    else:
        app.auth_manager = None

    # 自适应流管理器
    if config.enable_adaptive_streaming:
        from network.adaptive_streaming import AdaptiveStreaming, VideoQuality
        app.adaptive_streaming = AdaptiveStreaming(initial_quality=VideoQuality.MEDIUM)
        app.adaptive_streaming.start_monitoring()
    else:
        app.adaptive_streaming = None
    
    # 首页路由
    @app.route("/")
    def index():
        """首页"""
        return send_from_directory(static_folder, 'index.html')
    
    # 认证辅助函数
    def get_token_from_request():
        """从请求中获取 token"""
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header[7:]
        return request.args.get('token')
    
    def require_auth(permission=None):
        """认证装饰器"""
        def decorator(f):
            def wrapper(*args, **kwargs):
                if not app.auth_manager:
                    return f(*args, **kwargs)
                
                token = get_token_from_request()
                if not token:
                    return jsonify({"error": "未提供认证令牌"}), 401
                
                payload = app.auth_manager.verify_token(token)
                if not payload:
                    return jsonify({"error": "无效或过期的令牌"}), 401
                
                if permission and not app.auth_manager.check_permission(token, permission):
                    return jsonify({"error": "权限不足"}), 403
                
                return f(*args, **kwargs)
            wrapper.__name__ = f.__name__
            return wrapper
        return decorator
    
    # ==================== 认证 API ====================
    
    @app.route("/api/auth/login", methods=["POST"])
    def login():
        """用户登录"""
        if not app.auth_manager:
            return jsonify({"error": "认证未启用"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "缺少请求数据"}), 400
        
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            return jsonify({"error": "用户名和密码不能为空"}), 400
        
        token = app.auth_manager.login(username, password, request.remote_addr)
        if token:
            role = app.auth_manager.get_user_role(token)
            return jsonify({
                "token": token,
                "username": username,
                "role": role.value if role else None
            })
        
        return jsonify({"error": "用户名或密码错误"}), 401
    
    @app.route("/api/auth/logout", methods=["POST"])
    @require_auth()
    def logout():
        """用户登出"""
        if not app.auth_manager:
            return jsonify({"error": "认证未启用"}), 400
        
        token = get_token_from_request()
        if token:
            app.auth_manager.logout(token)
        
        return jsonify({"status": "logged_out"})
    
    @app.route("/api/auth/verify", methods=["GET"])
    def verify_token():
        """验证令牌"""
        if not app.auth_manager:
            return jsonify({"valid": True})
        
        token = get_token_from_request()
        if not token:
            return jsonify({"valid": False}), 401
        
        payload = app.auth_manager.verify_token(token)
        if payload:
            return jsonify({
                "valid": True,
                "username": payload.get("username"),
                "role": payload.get("role")
            })
        
        return jsonify({"valid": False}), 401
    
    @app.route("/api/auth/change_password", methods=["POST"])
    @require_auth()
    def change_password():
        """修改密码"""
        if not app.auth_manager:
            return jsonify({"error": "认证未启用"}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "缺少请求数据"}), 400
        
        token = get_token_from_request()
        payload = app.auth_manager.verify_token(token)
        username = payload.get("username")
        
        old_password = data.get("old_password")
        new_password = data.get("new_password")
        
        if not old_password or not new_password:
            return jsonify({"error": "旧密码和新密码不能为空"}), 400
        
        success = app.auth_manager.change_password(username, old_password, new_password)
        if success:
            return jsonify({"status": "password_changed"})
        
        return jsonify({"error": "密码修改失败"}), 400
    
    # 依赖注入（由外部设置）
    app.state_manager = None
    app.camera_controller = None
    app.comm_manager = None
    app.task_scheduler = None
    app.object_detector = None
    app.image_processor = None
    
    # 视频流配置
    app.video_fps = config.video_fps
    app.video_quality = config.video_quality
    app.latest_frame = None
    app.frame_lock = threading.Lock()

    def _get_detector_runtime_status():
        detector = app.object_detector
        if not detector:
            return {
                "enabled": False,
                "loaded": False,
                "simulation_mode": False,
                "inference_engine": None,
                "tensorrt_available": False,
                "model_path": None,
                "model_exists": False,
                "last_error": "检测器未初始化",
            }

        if hasattr(detector, "get_runtime_status"):
            status = detector.get_runtime_status()
        else:
            config_data = detector.get_config().to_dict() if hasattr(detector, "get_config") else {}
            status = {
                "loaded": detector.is_loaded() if hasattr(detector, "is_loaded") else True,
                "simulation_mode": (
                    detector.is_simulation_mode()
                    if hasattr(detector, "is_simulation_mode")
                    else False
                ),
                "inference_engine": (
                    detector.get_inference_engine()
                    if hasattr(detector, "get_inference_engine")
                    else None
                ),
                "tensorrt_available": None,
                "model_path": config_data.get("model_path"),
                "model_exists": None,
                "last_error": None,
            }

        return {"enabled": True, **status}

    def _normalize_comm_result(result, wait_response: bool):
        """兼容旧版和新版 send_command 返回格式。"""
        if isinstance(result, tuple) and len(result) == 2:
            first, second = result
            if isinstance(first, bool):
                if first:
                    return True, second, ""
                return False, None, str(second)

            response, error = first, second
            success = response is not None or (not wait_response and error == "")
            return success, response, error

        if isinstance(result, bool):
            return result, None, "" if result else "命令发送失败"

        if result is None:
            return (not wait_response), None, "" if not wait_response else "命令发送失败"

        return True, result, ""

    def _send_comm_command(cmd, wait_response: bool = True):
        """统一调用通信层，并兼容旧版 mock 的方法签名。"""
        if not app.comm_manager:
            return False, None, "通信管理器未初始化"

        try:
            try:
                result = app.comm_manager.send_command(cmd, wait_response=wait_response)
            except TypeError:
                result = app.comm_manager.send_command(cmd)
        except Exception as e:
            return False, None, str(e)

        return _normalize_comm_result(result, wait_response)

    def _parse_axis(axis_value, default="all"):
        from comm.protocol import AxisType

        if axis_value is None:
            axis_value = default

        if isinstance(axis_value, AxisType):
            return axis_value

        if isinstance(axis_value, int):
            return AxisType(axis_value)

        key = str(axis_value).strip().lower()
        mapping = {
            "pan": AxisType.PAN,
            "tilt": AxisType.TILT,
            "rail": AxisType.RAIL,
            "all": AxisType.ALL,
        }
        if key not in mapping:
            raise ValueError(f"不支持的轴名称: {axis_value}")
        return mapping[key]

    def _axis_name(axis):
        mapping = {
            0: "pan",
            1: "tilt",
            2: "rail",
            255: "all",
        }
        return mapping.get(int(axis), str(axis))

    def _parse_config_param(param_name):
        from comm.protocol import ConfigParamId

        key = str(param_name).strip().lower()
        mapping = {
            "max_velocity": ConfigParamId.MAX_VELOCITY,
            "max_accel": ConfigParamId.MAX_ACCEL,
            "pid_p": ConfigParamId.PID_P,
            "pid_i": ConfigParamId.PID_I,
            "pid_d": ConfigParamId.PID_D,
            "watchdog_timeout_ms": ConfigParamId.WATCHDOG_TIMEOUT_MS,
            "watchdog_enable": ConfigParamId.WATCHDOG_ENABLE,
            "pan_min_limit": ConfigParamId.PAN_MIN_LIMIT,
            "pan_max_limit": ConfigParamId.PAN_MAX_LIMIT,
            "tilt_min_limit": ConfigParamId.TILT_MIN_LIMIT,
            "tilt_max_limit": ConfigParamId.TILT_MAX_LIMIT,
            "rail_min_limit": ConfigParamId.RAIL_MIN_LIMIT,
            "rail_max_limit": ConfigParamId.RAIL_MAX_LIMIT,
        }
        if key not in mapping:
            raise ValueError(f"不支持的配置参数: {param_name}")
        return mapping[key]

    def _pack_limit_value(axis, value: float) -> int:
        raw_value = int(round(float(value) * 100))
        if int(axis) == 2:
            if raw_value < 0 or raw_value > 0xFFFF:
                raise ValueError("Rail 限位超出 16 位无符号范围")
            return raw_value

        if raw_value < -0x8000 or raw_value > 0x7FFF:
            raise ValueError("角度限位超出 16 位有符号范围")
        return raw_value

    def _send_config(axis, param_id, raw_value):
        from comm.protocol import Command, CommandType, config_pack_value

        cmd = Command(
            type=CommandType.CONFIG,
            axis=axis,
            value=config_pack_value(param_id, int(raw_value)),
        )
        return _send_comm_command(cmd, wait_response=True)
    
    # ==================== 系统状态 API ====================
    
    @app.route("/api/status", methods=["GET"])
    @require_auth()
    def get_status():
        """获取系统状态"""
        if app.state_manager:
            state = app.state_manager.get_full_state()
            state["runtime"] = {
                "detector": _get_detector_runtime_status(),
            }
            return jsonify(state)
        return jsonify({"error": "状态管理器未初始化"}), 500
    
    @app.route("/api/health", methods=["GET"])
    def health_check():
        """健康检查"""
        detector_status = _get_detector_runtime_status()
        return jsonify({
            "status": "ok",
            "timestamp": time.time(),
            "components": {
                "state_manager": app.state_manager is not None,
                "camera": app.camera_controller is not None,
                "comm": app.comm_manager is not None,
                "scheduler": app.task_scheduler is not None,
                "detector": app.object_detector is not None,
                "detector_loaded": detector_status.get("loaded", False)
            }
        })
    
    @app.route("/api/history", methods=["GET"])
    def get_history():
        """获取状态历史"""
        if app.state_manager:
            limit = request.args.get('limit', 100, type=int)
            path_filter = request.args.get('filter', None)
            return jsonify(app.state_manager.get_history(limit, path_filter))
        return jsonify({"error": "状态管理器未初始化"}), 500

    @app.route("/api/comm/diagnostics", methods=["GET"])
    @require_auth(Permission.CONFIGURE_SYSTEM if app.auth_manager else None)
    def get_comm_diagnostics():
        """获取最近的串口通信诊断记录。"""
        if not app.comm_manager:
            return jsonify({"error": "通信管理器未初始化"}), 500

        limit = request.args.get("limit", 100, type=int)
        source = request.args.get("source")
        if limit is not None and limit < 0:
            return jsonify({"error": "limit 不能为负数"}), 400

        if hasattr(app.comm_manager, "get_trace_diagnostics"):
            return jsonify(app.comm_manager.get_trace_diagnostics(limit=limit, source=source))

        return jsonify({"error": "通信管理器不支持诊断接口"}), 501

    @app.route("/api/comm/diagnostics/clear", methods=["POST"])
    @require_auth(Permission.CONFIGURE_SYSTEM if app.auth_manager else None)
    def clear_comm_diagnostics():
        """清空串口通信诊断记录。"""
        if not app.comm_manager:
            return jsonify({"error": "通信管理器未初始化"}), 500

        if hasattr(app.comm_manager, "clear_trace_history"):
            cleared = app.comm_manager.clear_trace_history()
            return jsonify({"status": "cleared", "cleared": cleared})

        return jsonify({"error": "通信管理器不支持诊断接口"}), 501
    
    # ==================== 运动控制 API ====================
    
    @app.route("/api/motion/position", methods=["GET"])
    def get_position():
        """获取当前位置"""
        if app.state_manager:
            state = app.state_manager.motion_state
            return jsonify({
                "pan": state.pan_position,
                "tilt": state.tilt_position,
                "rail": state.rail_position,
                "is_moving": state.is_moving,
                "is_stable": state.is_stable
            })
        return jsonify({"error": "状态管理器未初始化"}), 500
    
    @app.route("/api/motion/move", methods=["POST"])
    @require_auth(Permission.CONTROL_POSITION if app.auth_manager else None)
    def move_to():
        """移动到指定位置"""
        data = request.get_json()
        if not data:
            return jsonify({"error": "缺少请求数据"}), 400
        
        pan = data.get("pan")
        tilt = data.get("tilt")
        rail = data.get("rail")
        
        if app.comm_manager:
            # 手动控制接口逐轴发送 POSITION，并等待每条命令的响应，
            # 这样前端可以立即感知哪一轴下发失败。
            try:
                from comm.protocol import Command, CommandType, AxisType
                
                # 根据提供的参数发送位置命令
                # 注意：这里简化处理，实际应该分别发送三个轴的命令
                if pan is not None:
                    cmd = Command(
                        type=CommandType.POSITION,
                        axis=AxisType.PAN,
                        value=int(pan * 100)  # 转换为整数（假设单位是0.01度）
                    )
                    success, response, error = _send_comm_command(cmd, wait_response=True)
                    response = error if not success else response
                    if not success:
                        return jsonify({"error": f"Pan命令发送失败: {response}"}), 500
                
                if tilt is not None:
                    cmd = Command(
                        type=CommandType.POSITION,
                        axis=AxisType.TILT,
                        value=int(tilt * 100)
                    )
                    success, response, error = _send_comm_command(cmd, wait_response=True)
                    response = error if not success else response
                    if not success:
                        return jsonify({"error": f"Tilt命令发送失败: {response}"}), 500
                
                if rail is not None:
                    cmd = Command(
                        type=CommandType.POSITION,
                        axis=AxisType.RAIL,
                        value=int(rail * 100)  # 转换为整数（0.01mm）
                    )
                    success, response, error = _send_comm_command(cmd, wait_response=True)
                    response = error if not success else response
                    if not success:
                        return jsonify({"error": f"Rail命令发送失败: {response}"}), 500
                
                return jsonify({"status": "accepted", "command": "move_to"})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        return jsonify({"status": "accepted", "note": "通信管理器未初始化，命令未发送"})
    
    @app.route("/api/motion/stop", methods=["POST"])
    def stop_motion():
        """停止运动"""
        if app.comm_manager:
            try:
                from comm.protocol import Command, CommandType
                cmd = Command(type=CommandType.STOP)
                success, response, error = _send_comm_command(cmd, wait_response=True)
                response = error if not success else response
                if success:
                    return jsonify({"status": "stopped"})
                return jsonify({"error": f"命令发送失败: {response}"}), 500
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        return jsonify({"status": "stopped", "note": "通信管理器未初始化"})
    
    @app.route("/api/motion/home", methods=["POST"])
    def home_axis():
        """归零"""
        if app.comm_manager:
            try:
                from comm.protocol import Command, CommandType, AxisType
                cmd = Command(type=CommandType.HOME, axis=AxisType.ALL)
                success, response, error = _send_comm_command(cmd, wait_response=True)
                response = error if not success else response
                if success:
                    return jsonify({"status": "homing"})
                return jsonify({"error": f"命令发送失败: {response}"}), 500
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        return jsonify({"status": "homing", "note": "通信管理器未初始化"})
    
    # ==================== 相机控制 API ====================
    
    @app.route("/api/motion/config", methods=["GET", "POST"])
    @require_auth(Permission.CONFIGURE_SYSTEM if app.auth_manager else None)
    def motion_config():
        """查看或更新 STM32 运动控制 CONFIG 参数。"""
        if request.method == "GET":
            return jsonify({
                "supported_axes": ["pan", "tilt", "rail", "all"],
                "typed_updates": {
                    "pid": {
                        "axis_required": True,
                        "fields": ["p", "i", "d"],
                        "encoding": "gain * 100",
                    },
                    "limits": {
                        "axis_required": True,
                        "fields": ["min", "max"],
                        "unit": {
                            "pan": "degree",
                            "tilt": "degree",
                            "rail": "mm",
                        },
                        "encoding": "0.01 degree / 0.01 mm",
                    },
                    "watchdog": {
                        "axis_required": False,
                        "fields": ["timeout_ms", "enabled"],
                    },
                },
                "raw_params": [
                    "max_velocity",
                    "max_accel",
                    "pid_p",
                    "pid_i",
                    "pid_d",
                    "watchdog_timeout_ms",
                    "watchdog_enable",
                    "pan_min_limit",
                    "pan_max_limit",
                    "tilt_min_limit",
                    "tilt_max_limit",
                    "rail_min_limit",
                    "rail_max_limit",
                ],
            })

        if not app.comm_manager:
            return jsonify({"error": "通信管理器未初始化"}), 500

        data = request.get_json() or {}
        if not data:
            return jsonify({"error": "缺少配置数据"}), 400

        applied = []

        try:
            from comm.protocol import AxisType, ConfigParamId
            from comm.unit_converter import MotionValidator

            axis = _parse_axis(data.get("axis"), default="all")

            pid = data.get("pid") or {}
            if pid:
                if axis == AxisType.ALL:
                    return jsonify({"error": "PID 配置必须指定单个轴"}), 400

                pid_fields = {
                    "p": ConfigParamId.PID_P,
                    "i": ConfigParamId.PID_I,
                    "d": ConfigParamId.PID_D,
                }
                for field_name, param_id in pid_fields.items():
                    if field_name not in pid or pid[field_name] is None:
                        continue

                    gain = float(pid[field_name])
                    if gain < 0:
                        return jsonify({"error": f"PID {field_name.upper()} 不能为负数"}), 400

                    raw_value = int(round(gain * 100))
                    success, response, error = _send_config(axis, param_id, raw_value)
                    if not success:
                        return jsonify({"error": f"{field_name.upper()} 配置下发失败: {error}"}), 500

                    applied.append({
                        "axis": _axis_name(axis),
                        "param": param_id.name.lower(),
                        "value": gain,
                        "raw_value": raw_value,
                    })

            limits = data.get("limits") or {}
            if limits:
                if axis == AxisType.ALL:
                    return jsonify({"error": "限位配置必须指定单个轴"}), 400

                axis_name = _axis_name(axis)
                limit_params = {
                    AxisType.PAN: (ConfigParamId.PAN_MIN_LIMIT, ConfigParamId.PAN_MAX_LIMIT),
                    AxisType.TILT: (ConfigParamId.TILT_MIN_LIMIT, ConfigParamId.TILT_MAX_LIMIT),
                    AxisType.RAIL: (ConfigParamId.RAIL_MIN_LIMIT, ConfigParamId.RAIL_MAX_LIMIT),
                }
                min_param, max_param = limit_params[axis]

                if "min" in limits and limits["min"] is not None:
                    min_value = float(limits["min"])
                    valid, error = MotionValidator.validate_position(min_value, axis_name)
                    if not valid:
                        return jsonify({"error": error}), 400

                    raw_value = _pack_limit_value(axis, min_value)
                    success, response, error = _send_config(axis, min_param, raw_value)
                    if not success:
                        return jsonify({"error": f"最小限位下发失败: {error}"}), 500

                    applied.append({
                        "axis": axis_name,
                        "param": min_param.name.lower(),
                        "value": min_value,
                        "raw_value": raw_value,
                    })

                if "max" in limits and limits["max"] is not None:
                    max_value = float(limits["max"])
                    valid, error = MotionValidator.validate_position(max_value, axis_name)
                    if not valid:
                        return jsonify({"error": error}), 400

                    raw_value = _pack_limit_value(axis, max_value)
                    success, response, error = _send_config(axis, max_param, raw_value)
                    if not success:
                        return jsonify({"error": f"最大限位下发失败: {error}"}), 500

                    applied.append({
                        "axis": axis_name,
                        "param": max_param.name.lower(),
                        "value": max_value,
                        "raw_value": raw_value,
                    })

            watchdog = data.get("watchdog") or {}
            if watchdog:
                if "timeout_ms" in watchdog and watchdog["timeout_ms"] is not None:
                    timeout_ms = int(watchdog["timeout_ms"])
                    if timeout_ms <= 0 or timeout_ms > 0xFFFF:
                        return jsonify({"error": "看门狗超时必须在 1..65535 ms 范围内"}), 400

                    success, response, error = _send_config(
                        AxisType.ALL,
                        ConfigParamId.WATCHDOG_TIMEOUT_MS,
                        timeout_ms,
                    )
                    if not success:
                        return jsonify({"error": f"看门狗超时配置下发失败: {error}"}), 500

                    applied.append({
                        "axis": "all",
                        "param": "watchdog_timeout_ms",
                        "value": timeout_ms,
                        "raw_value": timeout_ms,
                    })

                if "enabled" in watchdog and watchdog["enabled"] is not None:
                    enabled = bool(watchdog["enabled"])
                    raw_value = 1 if enabled else 0
                    success, response, error = _send_config(
                        AxisType.ALL,
                        ConfigParamId.WATCHDOG_ENABLE,
                        raw_value,
                    )
                    if not success:
                        return jsonify({"error": f"看门狗使能配置下发失败: {error}"}), 500

                    applied.append({
                        "axis": "all",
                        "param": "watchdog_enable",
                        "value": enabled,
                        "raw_value": raw_value,
                    })

            raw_updates = data.get("raw") or []
            if raw_updates:
                if not isinstance(raw_updates, list):
                    return jsonify({"error": "raw 字段必须是数组"}), 400

                for item in raw_updates:
                    if not isinstance(item, dict):
                        return jsonify({"error": "raw 数组项必须是对象"}), 400
                    if "param" not in item or "value" not in item:
                        return jsonify({"error": "raw 配置项缺少 param 或 value"}), 400

                    item_axis = _parse_axis(item.get("axis"), default=_axis_name(axis))
                    param_id = _parse_config_param(item["param"])
                    raw_value = int(item["value"])

                    success, response, error = _send_config(item_axis, param_id, raw_value)
                    if not success:
                        return jsonify({"error": f"raw 配置下发失败: {error}"}), 500

                    applied.append({
                        "axis": _axis_name(item_axis),
                        "param": param_id.name.lower(),
                        "value": raw_value,
                        "raw_value": raw_value,
                    })

            if not applied:
                return jsonify({"error": "没有可应用的配置项"}), 400

            return jsonify({"status": "updated", "applied": applied})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/camera/status", methods=["GET"])
    def camera_status():
        """获取相机状态"""
        if app.camera_controller:
            status = app.camera_controller.get_status()
            # 兼容字符串和枚举类型
            status_value = status.value if hasattr(status, 'value') else status
            return jsonify({
                "status": status_value,
                "config": app.camera_controller.get_config().to_dict()
            })
        return jsonify({"error": "相机未初始化"}), 500
    
    @app.route("/api/camera/capture", methods=["POST"])
    @require_auth(Permission.CAPTURE_IMAGE if app.auth_manager else None)
    def capture():
        """拍摄"""
        if app.camera_controller:
            data = request.get_json() or {}
            wait_frames = data.get("wait_frames", 5)
            
            image_pair, error = app.camera_controller.capture(wait_frames=wait_frames)
            if image_pair:
                # 更新状态
                if app.state_manager:
                    app.state_manager.update_system_state(
                        capture_count=app.state_manager.system_state.capture_count + 1
                    )
                return jsonify({
                    "status": "captured",
                    "timestamp": image_pair.timestamp,
                    "size": [image_pair.rgb.shape[1], image_pair.rgb.shape[0]]
                })
            return jsonify({"error": error}), 500
        return jsonify({"error": "相机未初始化"}), 500
    
    @app.route("/api/camera/config", methods=["GET", "POST"])
    def camera_config():
        """获取/设置相机配置"""
        if not app.camera_controller:
            return jsonify({"error": "相机未初始化"}), 500
        
        if request.method == "GET":
            return jsonify(app.camera_controller.get_config().to_dict())
        else:
            data = request.get_json()
            if not data:
                return jsonify({"error": "缺少配置数据"}), 400
            
            try:
                from camera.base_controller import CameraConfig
                config = CameraConfig.from_dict(data)
                success, error = app.camera_controller.configure(config)
                if success:
                    return jsonify({"status": "updated", "config": config.to_dict()})
                return jsonify({"error": error}), 400
            except Exception as e:
                return jsonify({"error": str(e)}), 400
    
    @app.route("/api/camera/auto_exposure", methods=["POST"])
    def auto_exposure():
        """自动曝光调整"""
        if app.camera_controller:
            data = request.get_json() or {}
            target_brightness = data.get("target_brightness", 128.0)
            
            config, error = app.camera_controller.auto_exposure_adjust(target_brightness)
            if config:
                return jsonify({"status": "adjusted", "config": config.to_dict()})
            return jsonify({"error": error}), 500
        return jsonify({"error": "相机未初始化"}), 500
    
    # ==================== 自动拍摄 API ====================
    
    @app.route("/api/auto/status", methods=["GET"])
    def auto_status():
        """获取自动拍摄状态"""
        if app.task_scheduler:
            progress = app.task_scheduler.get_progress()
            return jsonify(progress.to_dict())
        return jsonify({"error": "调度器未初始化"}), 500
    
    @app.route("/api/auto/start", methods=["POST"])
    def start_auto_capture():
        """开始自动拍摄"""
        if app.task_scheduler:
            success, error = app.task_scheduler.start()
            if success:
                return jsonify({"status": "started"})
            return jsonify({"error": error}), 400
        return jsonify({"error": "调度器未初始化"}), 500
    
    @app.route("/api/auto/pause", methods=["POST"])
    def pause_auto_capture():
        """暂停自动拍摄"""
        if app.task_scheduler:
            success, error = app.task_scheduler.pause()
            if success:
                return jsonify({"status": "paused"})
            return jsonify({"error": error}), 400
        return jsonify({"error": "调度器未初始化"}), 500
    
    @app.route("/api/auto/resume", methods=["POST"])
    def resume_auto_capture():
        """恢复自动拍摄"""
        if app.task_scheduler:
            success, error = app.task_scheduler.resume()
            if success:
                return jsonify({"status": "resumed"})
            return jsonify({"error": error}), 400
        return jsonify({"error": "调度器未初始化"}), 500
    
    @app.route("/api/auto/stop", methods=["POST"])
    def stop_auto_capture():
        """停止自动拍摄"""
        if app.task_scheduler:
            success, error = app.task_scheduler.stop()
            if success:
                return jsonify({"status": "stopped"})
            return jsonify({"error": error}), 400
        return jsonify({"error": "调度器未初始化"}), 500
    
    @app.route("/api/auto/path", methods=["GET", "POST"])
    def path_config():
        """获取/设置路径配置"""
        if not app.task_scheduler:
            return jsonify({"error": "调度器未初始化"}), 500
        
        if request.method == "GET":
            if app.task_scheduler._path_config:
                return jsonify(app.task_scheduler._path_config.to_dict())
            return jsonify({"error": "未加载路径配置"}), 404
        else:
            data = request.get_json()
            if not data:
                return jsonify({"error": "缺少配置数据"}), 400
            
            try:
                from scheduler.task_scheduler import PathConfig
                config = PathConfig.from_dict(data)
                success, error = app.task_scheduler.load_path(config)
                if success:
                    return jsonify({"status": "loaded", "points": len(config.points)})
                return jsonify({"error": error}), 400
            except Exception as e:
                return jsonify({"error": str(e)}), 400
    
    # ==================== 目标检测 API ====================
    
    @app.route("/api/detection/targets", methods=["GET"])
    def get_targets():
        """获取检测到的目标"""
        if app.state_manager:
            state = app.state_manager.detection_state
            return jsonify({
                "targets": [
                    {
                        "id": t.id,
                        "class_name": t.class_name,
                        "confidence": t.confidence,
                        "bbox": t.bbox,
                        "center": t.center,
                        "depth": t.depth,
                        "selected": t.selected
                    }
                    for t in state.targets
                ],
                "selected_id": state.selected_target_id,
                "fps": state.fps
            })
        return jsonify({"targets": [], "selected_id": None, "fps": 0})
    
    @app.route("/api/detection/select", methods=["POST"])
    def select_target():
        """选择目标"""
        data = request.get_json()
        if not data:
            return jsonify({"error": "缺少请求数据"}), 400
        
        target_id = data.get("target_id")
        
        if app.state_manager:
            app.state_manager.select_target(target_id)
            return jsonify({"status": "selected", "target_id": target_id})
        
        return jsonify({"error": "状态管理器未初始化"}), 500
    
    @app.route("/api/detection/mode", methods=["GET", "POST"])
    def detection_mode():
        """获取/设置检测模式"""
        if not app.state_manager:
            return jsonify({"error": "状态管理器未初始化"}), 500
        
        if request.method == "GET":
            return jsonify({
                "mode": app.state_manager.system_state.target_mode.value
            })
        else:
            data = request.get_json()
            mode = data.get("mode", "auto")
            
            from state.models import TargetMode
            try:
                target_mode = TargetMode(mode)
                app.state_manager.update_system_state(target_mode=target_mode)
                return jsonify({"status": "updated", "mode": mode})
            except ValueError:
                return jsonify({"error": f"无效模式: {mode}"}), 400
    
    @app.route("/api/detection/config", methods=["GET", "POST"])
    def detection_config():
        """获取/设置检测配置"""
        if not app.object_detector:
            return jsonify({"error": "检测器未初始化"}), 500
        
        if request.method == "GET":
            return jsonify(app.object_detector.get_config().to_dict())
        else:
            data = request.get_json()
            if not data:
                return jsonify({"error": "缺少配置数据"}), 400
            
            try:
                from vision.detector import DetectionConfig
                config = DetectionConfig.from_dict(data)
                app.object_detector.set_config(config)
                return jsonify({"status": "updated"})
            except Exception as e:
                return jsonify({"error": str(e)}), 400
    
    # ==================== 人脸识别 API ====================
    
    # 人脸识别器（由外部注入）
    app.face_recognizer = None
    app.visual_servo = None
    
    # 系统监控（由外部注入）
    app.system_monitor = None
    app.alert_manager = None
    
    @app.route("/api/face/status", methods=["GET"])
    def face_status():
        """获取人脸识别状态"""
        if not app.face_recognizer:
            return jsonify({"error": "人脸识别器未初始化", "enabled": False}), 200
        
        return jsonify({
            "enabled": True,
            **app.face_recognizer.get_web_status()
        })
    
    @app.route("/api/face/registered", methods=["GET"])
    def get_registered_faces():
        """获取已注册的人脸列表"""
        if not app.face_recognizer:
            return jsonify({"error": "人脸识别器未初始化"}), 500
        
        names = app.face_recognizer.get_registered_names()
        return jsonify({
            "count": len(names),
            "names": names
        })
    
    @app.route("/api/face/register", methods=["POST"])
    @require_auth(Permission.CONTROL_POSITION if app.auth_manager else None)
    def register_face():
        """注册人脸"""
        if not app.face_recognizer:
            return jsonify({"error": "人脸识别器未初始化"}), 500
        
        # 支持两种方式：
        # 1. 上传图片文件
        # 2. 使用当前相机画面
        
        name = request.form.get("name") or request.args.get("name")
        if not name:
            data = request.get_json()
            if data:
                name = data.get("name")
        
        if not name:
            return jsonify({"error": "缺少人名参数"}), 400
        
        logger.info(f"收到人脸注册请求: name={name}")
        
        # 检查是否上传了图片
        if 'image' in request.files:
            file = request.files['image']
            try:
                import numpy as np
                from PIL import Image
                import io
                
                image = Image.open(io.BytesIO(file.read()))
                image_array = np.array(image.convert('RGB'))
                
                success, message = app.face_recognizer.register_face(name, image_array)
                return jsonify({"success": success, "message": message})
            except Exception as e:
                return jsonify({"error": f"图片处理失败: {str(e)}"}), 400
        
        # 优先使用视频流最新帧，避免和视频采集线程争用底层相机资源导致请求卡住
        latest_frame = None
        try:
            with app.frame_lock:
                latest_frame = app.latest_frame
        except Exception:
            latest_frame = None

        if latest_frame:
            try:
                import numpy as np
                from PIL import Image
                import io

                image = Image.open(io.BytesIO(latest_frame)).convert('RGB')
                image_array = np.array(image)

                # 混合预览可能是「左彩色 + 右深度伪彩」，注册仅使用左半边彩色图
                h, w = image_array.shape[:2]
                if w >= h * 2:
                    image_array = image_array[:, : w // 2, :]

                success, message = app.face_recognizer.register_face(name, image_array)
                return jsonify({"success": success, "message": message})
            except Exception as e:
                logger.warning(f"使用最新视频帧注册失败，回退到相机直采: {e}")

        # 回退：直接使用当前相机画面
        if app.camera_controller:
            image_pair, error = app.camera_controller.capture(wait_frames=0)
            if image_pair:
                success, message = app.face_recognizer.register_face(name, image_pair.rgb)
                return jsonify({"success": success, "message": message})
            return jsonify({"error": f"相机拍摄失败: {error}"}), 500
        
        return jsonify({"error": "请上传图片或确保相机已连接"}), 400
    
    @app.route("/api/face/unregister", methods=["POST"])
    @require_auth(Permission.CONTROL_POSITION if app.auth_manager else None)
    def unregister_face():
        """删除已注册的人脸"""
        if not app.face_recognizer:
            return jsonify({"error": "人脸识别器未初始化"}), 500
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "缺少请求数据"}), 400
        
        name = data.get("name")
        if not name:
            return jsonify({"error": "缺少人名参数"}), 400
        
        success, message = app.face_recognizer.unregister_face(name)
        return jsonify({"success": success, "message": message})
    
    @app.route("/api/face/detect", methods=["GET"])
    def detect_faces():
        """检测当前画面中的人脸"""
        if not app.face_recognizer:
            return jsonify({"error": "人脸识别器未初始化"}), 500
        
        if not app.camera_controller:
            return jsonify({"error": "相机未初始化"}), 500
        
        image_pair, error = app.camera_controller.capture(wait_frames=1)
        if not image_pair:
            return jsonify({"error": f"相机拍摄失败: {error}"}), 500
        
        result = app.face_recognizer.detect_and_recognize(image_pair.rgb, image_pair.depth)
        
        return jsonify({
            "face_count": result.face_count,
            "detection_time_ms": round(result.detection_time, 1),
            "recognition_time_ms": round(result.recognition_time, 1),
            "faces": [f.to_dict() for f in result.faces]
        })
    
    @app.route("/api/face/tracking/start", methods=["POST"])
    @require_auth(Permission.CONTROL_POSITION if app.auth_manager else None)
    def start_face_tracking():
        """开始人脸跟踪"""
        if not app.visual_servo:
            return jsonify({"error": "视觉伺服未初始化"}), 500
        
        data = request.get_json() or {}
        target_name = data.get("target_name")
        
        app.visual_servo.start_face_tracking(target_name)
        return jsonify({
            "status": "started",
            "target_name": target_name
        })
    
    @app.route("/api/face/tracking/stop", methods=["POST"])
    def stop_face_tracking():
        """停止人脸跟踪"""
        if not app.visual_servo:
            return jsonify({"error": "视觉伺服未初始化"}), 500
        
        app.visual_servo.stop()
        return jsonify({"status": "stopped"})
    
    @app.route("/api/face/tracking/status", methods=["GET"])
    def face_tracking_status():
        """获取人脸跟踪状态"""
        if not app.visual_servo:
            return jsonify({"error": "视觉伺服未初始化"}), 500
        
        return jsonify(app.visual_servo.get_face_tracking_status())
    
    # ==================== 视频流 API ====================
    
    @app.route("/api/video/stream")
    @require_auth(Permission.VIEW_CAMERA if app.auth_manager else None)
    def video_stream():
        """MJPEG 视频流（支持自适应质量）"""
        def generate():
            while True:
                with app.frame_lock:
                    frame = app.latest_frame
                
                if frame is not None:
                    # 记录帧大小用于带宽估算
                    if app.adaptive_streaming:
                        app.adaptive_streaming.record_frame(len(frame))
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                
                # 使用自适应帧率
                if app.adaptive_streaming:
                    profile = app.adaptive_streaming.get_current_profile()
                    time.sleep(1.0 / profile.fps)
                else:
                    time.sleep(1.0 / app.video_fps)
        
        return Response(
            generate(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
    
    @app.route("/api/video/quality", methods=["GET", "POST"])
    @require_auth()
    def video_quality():
        """获取/设置视频质量"""
        if not app.adaptive_streaming:
            return jsonify({"error": "自适应流未启用"}), 400
        
        if request.method == "GET":
            profile = app.adaptive_streaming.get_current_profile()
            stats = app.adaptive_streaming.get_stats()
            return jsonify({
                "quality": profile.name.value,
                "width": profile.width,
                "height": profile.height,
                "fps": profile.fps,
                "jpeg_quality": profile.jpeg_quality,
                "stats": {
                    "frames_sent": stats.frames_sent,
                    "bytes_sent": stats.bytes_sent,
                    "average_bitrate": stats.average_bitrate,
                    "quality_changes": stats.quality_changes
                }
            })
        else:
            data = request.get_json()
            quality_name = data.get("quality")
            
            if not quality_name:
                return jsonify({"error": "缺少质量参数"}), 400
            
            try:
                from network.adaptive_streaming import VideoQuality
                quality = VideoQuality(quality_name)
                app.adaptive_streaming.set_quality(quality)
                return jsonify({"status": "updated", "quality": quality_name})
            except ValueError:
                return jsonify({"error": f"无效质量: {quality_name}"}), 400
    
    @app.route("/api/video/snapshot", methods=["GET"])
    def video_snapshot():
        """获取当前帧快照"""
        with app.frame_lock:
            frame = app.latest_frame
        
        if frame:
            return Response(frame, mimetype='image/jpeg')
        return jsonify({"error": "无可用帧"}), 404
    
    # ==================== 系统监控 API ====================
    
    @app.route("/api/monitoring/metrics", methods=["GET"])
    @require_auth()
    def get_monitoring_metrics():
        """获取当前系统指标"""
        if not app.system_monitor:
            return jsonify({"error": "系统监控未初始化"}), 500
        
        metrics = app.system_monitor.get_current_metrics()
        if metrics:
            return jsonify(metrics.to_dict())
        return jsonify({"error": "暂无指标数据"}), 404
    
    @app.route("/api/monitoring/history", methods=["GET"])
    @require_auth()
    def get_monitoring_history():
        """获取系统指标历史"""
        if not app.system_monitor:
            return jsonify({"error": "系统监控未初始化"}), 500
        
        count = request.args.get('count', type=int)
        history = app.system_monitor.get_history(count)
        
        return jsonify({
            "count": len(history),
            "metrics": [m.to_dict() for m in history]
        })
    
    @app.route("/api/monitoring/status", methods=["GET"])
    @require_auth()
    def get_monitoring_status():
        """获取监控状态"""
        if not app.system_monitor:
            return jsonify({"error": "系统监控未初始化"}), 500
        
        return jsonify(app.system_monitor.get_status())
    
    @app.route("/api/monitoring/alerts", methods=["GET"])
    @require_auth()
    def get_alerts():
        """获取告警列表"""
        if not app.alert_manager:
            return jsonify({"error": "告警管理器未初始化"}), 500
        
        # 查询参数
        active_only = request.args.get('active', 'false').lower() == 'true'
        count = request.args.get('count', type=int)
        level = request.args.get('level')
        
        if active_only:
            alerts = app.alert_manager.get_active_alerts()
        else:
            alerts = app.alert_manager.get_alert_history(count=count, level=level)
        
        return jsonify({
            "count": len(alerts),
            "alerts": [a.to_dict() for a in alerts]
        })
    
    @app.route("/api/monitoring/alerts/<alert_id>/resolve", methods=["POST"])
    @require_auth(Permission.CONTROL_POSITION if app.auth_manager else None)
    def resolve_alert(alert_id):
        """解决告警"""
        if not app.alert_manager:
            return jsonify({"error": "告警管理器未初始化"}), 500
        
        data = request.get_json() or {}
        message = data.get("message")
        
        app.alert_manager.resolve_alert(alert_id, message)
        return jsonify({"status": "resolved", "alert_id": alert_id})
    
    @app.route("/api/monitoring/alerts/statistics", methods=["GET"])
    @require_auth()
    def get_alert_statistics():
        """获取告警统计"""
        if not app.alert_manager:
            return jsonify({"error": "告警管理器未初始化"}), 500
        
        return jsonify(app.alert_manager.get_statistics())
    
    @app.route("/api/monitoring/alerts/clear", methods=["POST"])
    @require_auth(Permission.CONTROL_POSITION if app.auth_manager else None)
    def clear_alert_history():
        """清空告警历史"""
        if not app.alert_manager:
            return jsonify({"error": "告警管理器未初始化"}), 500
        
        app.alert_manager.clear_history()
        return jsonify({"status": "cleared"})
    
    @app.route("/api/monitoring/webhook", methods=["POST"])
    def monitoring_webhook():
        """监控 Webhook 接收端点（用于测试）"""
        data = request.get_json()
        logger.info(f"收到监控 Webhook: {data}")
        return jsonify({"status": "received"})
    
    return app


class WebServer:
    """Web 服务器封装"""
    
    def __init__(self, config: Optional[WebConfig] = None):
        self.config = config or WebConfig()
        self.app = create_app(self.config)
        self._thread = None
        self._running = False
        self._video_thread = None
    
    def inject_dependencies(
        self, 
        state_manager=None, 
        camera_controller=None,
        comm_manager=None, 
        task_scheduler=None,
        object_detector=None,
        image_processor=None
    ):
        """注入依赖"""
        if self.app:
            self.app.state_manager = state_manager
            self.app.camera_controller = camera_controller
            self.app.comm_manager = comm_manager
            self.app.task_scheduler = task_scheduler
            self.app.object_detector = object_detector
            self.app.image_processor = image_processor
    
    def update_frame(self, frame_jpeg: bytes):
        """更新视频帧"""
        if self.app:
            with self.app.frame_lock:
                self.app.latest_frame = frame_jpeg
    
    def start_video_capture(self, capture_callback: Callable):
        """
        启动视频采集线程
        
        Args:
            capture_callback: 采集回调，返回 JPEG 字节
        """
        if self._video_thread and self._video_thread.is_alive():
            return
        
        self._running = True
        
        def video_loop():
            while self._running:
                try:
                    frame = capture_callback()
                    if frame:
                        self.update_frame(frame)
                except Exception as e:
                    logger.error(f"视频采集错误: {e}")
                
                time.sleep(1.0 / self.config.video_fps)
        
        self._video_thread = threading.Thread(target=video_loop, daemon=True)
        self._video_thread.start()
    
    def stop_video_capture(self):
        """停止视频采集"""
        self._running = False
        if self._video_thread:
            self._video_thread.join(timeout=1.0)
    
    def run(self, threaded: bool = True):
        """
        启动 Web 服务器
        
        Args:
            threaded: 是否在后台线程运行
        """
        if not self.app:
            logger.error("Flask 应用未创建")
            return
        
        protocol = "https" if (self.config.ssl and self.config.ssl.enabled) else "http"
        
        if threaded:
            self._thread = threading.Thread(
                target=self._run_server,
                daemon=True
            )
            self._thread.start()
            logger.info(f"Web 服务器已启动: {protocol}://{self.config.host}:{self.config.port}")
        else:
            self._run_server()
    
    def _run_server(self):
        """运行服务器（支持 HTTPS）"""
        ssl_context = None
        
        # 检查是否启用 SSL
        if self.config.ssl and self.config.ssl.enabled:
            import ssl
            import os
            
            cert_file = self.config.ssl.cert_file
            key_file = self.config.ssl.key_file
            
            # 检查证书文件是否存在
            if os.path.exists(cert_file) and os.path.exists(key_file):
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(cert_file, key_file)
                logger.info(f"已启用 HTTPS (证书: {cert_file})")
            else:
                logger.warning(f"SSL 证书文件不存在: {cert_file} 或 {key_file}，使用 HTTP")
        
        self.app.run(
            host=self.config.host,
            port=self.config.port,
            debug=self.config.debug,
            use_reloader=False,
            threaded=True,
            ssl_context=ssl_context
        )
    
    def stop(self):
        """停止服务器"""
        self.stop_video_capture()
        # Flask 开发服务器没有优雅停止方法
        # 生产环境应使用 gunicorn 或 uwsgi
        logger.info("Web 服务器停止请求（需要重启进程）")
