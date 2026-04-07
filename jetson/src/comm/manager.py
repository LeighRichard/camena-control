"""
Jetson 侧串口通信管理器。
"""

from collections import deque
from glob import glob
import logging
import os
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from .protocol import (
    AxisType,
    Command,
    CommandType,
    ConfigParamId,
    FRAME_HEAD,
    FRAME_MIN_LEN,
    FRAME_TAIL,
    Response,
    config_param_from_value,
    config_raw_value,
    config_signed_value,
    decode_response,
    encode_command,
    config_pack_value,
)
from .unit_converter import MotionValidator

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """串口连接状态。"""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class CommConfig:
    """串口通信配置。"""

    port: str = "auto"
    baudrate: int = 115200
    timeout: float = 1.0
    retry_count: int = 3
    retry_delay: float = 0.1
    auto_reconnect: bool = True
    reconnect_interval: float = 2.0
    max_reconnect_attempts: int = 10
    heartbeat_interval: float = 5.0
    heartbeat_timeout: float = 3.0
    trace_protocol: bool = False
    trace_frames_hex: bool = False
    trace_history_size: int = 200


_AXIS_NAME_MAP = {
    AxisType.PAN: "pan",
    AxisType.TILT: "tilt",
    AxisType.RAIL: "rail",
}

_AXIS_LIMIT_PARAM_MAP = {
    AxisType.PAN: (ConfigParamId.PAN_MIN_LIMIT, ConfigParamId.PAN_MAX_LIMIT),
    AxisType.TILT: (ConfigParamId.TILT_MIN_LIMIT, ConfigParamId.TILT_MAX_LIMIT),
    AxisType.RAIL: (ConfigParamId.RAIL_MIN_LIMIT, ConfigParamId.RAIL_MAX_LIMIT),
}


class CommManager:
    """
    管理 Jetson 到 STM32 的串口链路。

    主要职责:
    - 连接生命周期管理
    - 同步命令收发
    - 异步接收回调
    - 断线重连与心跳保活
    - 面向上层的具名 CONFIG helper
    """

    def __init__(self, config: Optional[CommConfig] = None):
        self.config = config or CommConfig()
        self._serial = None
        self._connected_port: Optional[str] = None
        self._lock = threading.Lock()
        self._running = False
        self._recv_thread: Optional[threading.Thread] = None
        self._recv_callback: Optional[Callable[[Response], None]] = None
        self._recv_buffer = bytearray()
        self._trace_history = deque(maxlen=max(10, int(self.config.trace_history_size)))
        self._trace_lock = threading.Lock()

        self._state = ConnectionState.DISCONNECTED
        self._state_callbacks: List[Callable[[ConnectionState, Optional[str]], None]] = []
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_attempts = 0
        self._last_recv_time = 0.0
        self._heartbeat_thread: Optional[threading.Thread] = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    @staticmethod
    def _axis_name(axis: AxisType) -> str:
        mapping = {
            AxisType.PAN: "pan",
            AxisType.TILT: "tilt",
            AxisType.RAIL: "rail",
            AxisType.ALL: "all",
        }
        try:
            return mapping[AxisType(int(axis))]
        except Exception:
            return str(axis)

    def _describe_command(self, cmd: Command, wait_response: bool, attempt: int) -> str:
        parts = [
            f"seq={cmd.seq}",
            f"cmd={cmd.type.name.lower()}",
            f"axis={self._axis_name(cmd.axis)}",
            f"wait_response={wait_response}",
        ]

        if self.config.retry_count > 1:
            parts.append(f"attempt={attempt}")

        if cmd.type in (
            CommandType.POSITION,
            CommandType.SET_VELOCITY,
            CommandType.MOVE_ABSOLUTE,
        ):
            parts.append(f"value={cmd.value}")
        elif cmd.type == CommandType.CONFIG:
            try:
                param_id = config_param_from_value(cmd.value)
                raw_value = config_raw_value(cmd.value)
                signed_value = config_signed_value(cmd.value)
                parts.append(f"param={param_id.name.lower()}")
                parts.append(f"raw_value={raw_value}")
                if raw_value != signed_value:
                    parts.append(f"signed_value={signed_value}")
            except Exception:
                parts.append(f"packed_value={cmd.value}")

        return " ".join(parts)

    @staticmethod
    def _describe_response(response: Response, expected_seq: Optional[int] = None) -> str:
        parts = [
            f"seq={response.seq}",
            f"rsp={response.type.name.lower()}",
            f"status={response.status.name.lower()}",
        ]

        if expected_seq is not None:
            parts.append(f"expected_seq={expected_seq}")

        if getattr(response.type, "name", "") == "STATUS":
            parts.extend([
                f"pan={response.pan_pos}",
                f"tilt={response.tilt_pos}",
                f"rail={response.rail_pos}",
            ])

        return " ".join(parts)

    def _log_command_trace(self, cmd: Command, wait_response: bool, attempt: int):
        if not self.config.trace_protocol:
            return
        logger.info("[串口 TX] %s", self._describe_command(cmd, wait_response, attempt))

    def _log_response_trace(
        self,
        response: Response,
        source: str = "RX",
        expected_seq: Optional[int] = None,
    ):
        if not self.config.trace_protocol:
            return
        logger.info("[串口 %s] %s", source, self._describe_response(response, expected_seq))

    @staticmethod
    def _format_frame_hex(frame: bytes) -> str:
        return frame.hex(" ")

    def _log_frame_trace(self, frame: bytes, source: str):
        if not self.config.trace_frames_hex:
            return
        logger.info("[串口 %s] %s", source, self._format_frame_hex(frame))

    def _record_trace(self, record: dict):
        entry = {"timestamp": time.time(), **record}
        with self._trace_lock:
            self._trace_history.append(entry)

    def _record_command_event(
        self,
        cmd: Command,
        wait_response: bool,
        attempt: int,
        frame: bytes,
    ):
        record = {
            "source": "TX",
            "event": "command",
            "seq": int(cmd.seq),
            "command": cmd.type.name.lower(),
            "axis": self._axis_name(cmd.axis),
            "wait_response": bool(wait_response),
            "attempt": int(attempt),
            "frame_hex": self._format_frame_hex(frame),
        }

        if cmd.type in (
            CommandType.POSITION,
            CommandType.SET_VELOCITY,
            CommandType.MOVE_ABSOLUTE,
        ):
            record["value"] = int(cmd.value)
        elif cmd.type == CommandType.CONFIG:
            try:
                param_id = config_param_from_value(cmd.value)
                raw_value = config_raw_value(cmd.value)
                signed_value = config_signed_value(cmd.value)
                record["param"] = param_id.name.lower()
                record["raw_value"] = int(raw_value)
                record["signed_value"] = int(signed_value)
            except Exception:
                record["packed_value"] = int(cmd.value)

        self._record_trace(record)

    def _record_response_event(
        self,
        response: Response,
        source: str,
        frame: bytes,
        expected_seq: Optional[int] = None,
    ):
        record = {
            "source": source,
            "event": "response",
            "seq": int(response.seq),
            "response": response.type.name.lower(),
            "status": response.status.name.lower(),
            "frame_hex": self._format_frame_hex(frame),
        }

        if expected_seq is not None:
            record["expected_seq"] = int(expected_seq)

        if response.type.name == "STATUS":
            record["pan"] = int(response.pan_pos)
            record["tilt"] = int(response.tilt_pos)
            record["rail"] = int(response.rail_pos)

        self._record_trace(record)

    def _record_invalid_frame_event(self, frame: bytes, error: str):
        self._record_trace({
            "source": "RX-INVALID",
            "event": "invalid_frame",
            "error": error,
            "frame_hex": self._format_frame_hex(frame),
        })

    def get_trace_history(
        self,
        limit: Optional[int] = 100,
        source: Optional[str] = None,
        newest_first: bool = True,
    ) -> List[dict]:
        with self._trace_lock:
            records = list(self._trace_history)

        if source:
            source_key = str(source).strip().upper()
            records = [record for record in records if record.get("source", "").upper() == source_key]

        if newest_first:
            records.reverse()

        if limit is not None:
            records = records[: max(0, int(limit))]

        return records

    def clear_trace_history(self) -> int:
        with self._trace_lock:
            cleared = len(self._trace_history)
            self._trace_history.clear()
        return cleared

    def get_trace_diagnostics(self, limit: Optional[int] = 100, source: Optional[str] = None) -> dict:
        records = self.get_trace_history(limit=limit, source=source, newest_first=True)
        with self._trace_lock:
            total_records = len(self._trace_history)

        return {
            "connected": self.is_connected(),
            "state": self.state.value,
            "trace_protocol": self.config.trace_protocol,
            "trace_frames_hex": self.config.trace_frames_hex,
            "history_capacity": int(self._trace_history.maxlen or 0),
            "history_count": total_records,
            "returned_count": len(records),
            "records": records,
        }

    def _set_state(self, new_state: ConnectionState, reason: Optional[str] = None):
        if self._state == new_state:
            return

        old_state = self._state
        self._state = new_state
        logger.info(
            "连接状态变更: %s -> %s%s",
            old_state.value,
            new_state.value,
            f" ({reason})" if reason else "",
        )

        for callback in self._state_callbacks:
            try:
                callback(new_state, reason)
            except Exception as exc:
                logger.error("状态回调执行失败: %s", exc)

    def add_state_callback(self, callback: Callable[[ConnectionState, Optional[str]], None]):
        if callback not in self._state_callbacks:
            self._state_callbacks.append(callback)

    def remove_state_callback(self, callback: Callable[[ConnectionState, Optional[str]], None]):
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)

    @staticmethod
    def _normalize_port_name(port: Optional[str]) -> str:
        if port is None:
            return ""
        return str(port).strip()

    @staticmethod
    def _port_priority_key(candidate: Dict[str, str]) -> Tuple[int, str]:
        text = " ".join(
            str(candidate.get(field, "") or "").lower()
            for field in ("device", "description", "manufacturer", "hwid")
        )

        priority = 0
        if "stm" in text or "stmicro" in text:
            priority += 100
        if "virtual com" in text:
            priority += 80
        if "ttyacm" in text:
            priority += 70
        if "ttyusb" in text:
            priority += 60
        if "usb serial" in text:
            priority += 50
        if "cp210" in text or "ch340" in text or "ftdi" in text:
            priority += 40

        return (-priority, str(candidate.get("device", "")))

    def _enumerate_serial_candidates(self) -> List[Dict[str, str]]:
        candidates: List[Dict[str, str]] = []

        try:
            from serial.tools import list_ports

            for info in list_ports.comports():
                candidates.append(
                    {
                        "device": getattr(info, "device", "") or "",
                        "description": getattr(info, "description", "") or "",
                        "manufacturer": getattr(info, "manufacturer", "") or "",
                        "hwid": getattr(info, "hwid", "") or "",
                    }
                )
        except Exception as exc:
            logger.debug("枚举串口失败: %s", exc)

        if os.name != "nt":
            known_devices = {item.get("device") for item in candidates if item.get("device")}
            for pattern in ("/dev/ttyACM*", "/dev/ttyUSB*"):
                for device in sorted(glob(pattern)):
                    if device in known_devices:
                        continue
                    candidates.append(
                        {
                            "device": device,
                            "description": "serial device",
                            "manufacturer": "",
                            "hwid": "",
                        }
                    )
                    known_devices.add(device)

        candidates.sort(key=self._port_priority_key)
        return candidates

    def _resolve_port_candidates(self) -> List[str]:
        requested_port = self._normalize_port_name(self.config.port)
        requested_is_auto = requested_port.lower() == "auto"

        candidates: List[str] = []
        seen = set()

        def add_candidate(port_name: Optional[str]):
            port_name = self._normalize_port_name(port_name)
            if not port_name or port_name in seen:
                return
            seen.add(port_name)
            candidates.append(port_name)

        if requested_port and not requested_is_auto:
            add_candidate(requested_port)

        for info in self._enumerate_serial_candidates():
            add_candidate(info.get("device"))

        if requested_is_auto and not candidates:
            logger.warning("comm.port=auto，但当前没有发现可用串口设备")

        return candidates

    def _open_serial_connection(self):
        import serial

        candidates = self._resolve_port_candidates()
        if not candidates:
            raise RuntimeError("未发现可用串口设备，请检查 STM32 连接或显式设置 comm.port")

        errors = []
        logger.info("串口候选列表: %s", ", ".join(candidates))

        for port_name in candidates:
            try:
                serial_handle = serial.Serial(
                    port=port_name,
                    baudrate=self.config.baudrate,
                    timeout=self.config.timeout,
                )
                if (
                    self._normalize_port_name(self.config.port).lower() != "auto"
                    and port_name != self.config.port
                ):
                    logger.info(
                        "配置串口 %s 不可用，已自动切换到 %s",
                        self.config.port,
                        port_name,
                    )
                return serial_handle, port_name
            except Exception as exc:
                errors.append(f"{port_name}: {exc}")
                logger.debug("串口打开失败 %s: %s", port_name, exc)

        raise RuntimeError(" | ".join(errors))

    def get_connected_port(self) -> Optional[str]:
        return self._connected_port

    def connect(self) -> bool:
        self._set_state(ConnectionState.CONNECTING)

        try:
            self._serial, self._connected_port = self._open_serial_connection()
            self._running = True
            self._reconnect_attempts = 0
            self._last_recv_time = time.time()
            self._set_state(ConnectionState.CONNECTED)
            logger.info("串口已连接: %s", self._connected_port)

            if self.config.heartbeat_interval > 0:
                self._start_heartbeat()

            return True
        except Exception as exc:
            logger.error("串口连接失败: %s", exc)
            self._set_state(ConnectionState.ERROR, str(exc))
            if self.config.auto_reconnect:
                self._start_reconnect()
            return False

    def disconnect(self):
        self._running = False

        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=1.0)
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            self._reconnect_thread.join(timeout=1.0)
        if self._recv_thread and self._recv_thread.is_alive():
            self._recv_thread.join(timeout=1.0)

        if self._serial:
            self._serial.close()
            self._serial = None
        self._connected_port = None

        self._set_state(ConnectionState.DISCONNECTED, "手动断开")

    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def _start_reconnect(self):
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return

        self._reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self._reconnect_thread.start()

    def _reconnect_loop(self):
        while self._running or self._state == ConnectionState.ERROR:
            if (
                self.config.max_reconnect_attempts > 0
                and self._reconnect_attempts >= self.config.max_reconnect_attempts
            ):
                message = f"重连次数超过上限 ({self.config.max_reconnect_attempts})"
                logger.error(message)
                self._set_state(ConnectionState.ERROR, message)
                return

            self._reconnect_attempts += 1
            self._set_state(
                ConnectionState.RECONNECTING,
                f"第 {self._reconnect_attempts} 次重连",
            )
            logger.info("正在尝试重连（第 %s 次）...", self._reconnect_attempts)

            try:
                self._serial, self._connected_port = self._open_serial_connection()
                self._running = True
                self._reconnect_attempts = 0
                self._last_recv_time = time.time()
                self._set_state(ConnectionState.CONNECTED, "重连成功")
                logger.info("串口重连成功: %s", self._connected_port)

                if self.config.heartbeat_interval > 0:
                    self._start_heartbeat()

                return
            except Exception as exc:
                logger.warning("重连失败: %s", exc)

            time.sleep(self.config.reconnect_interval)

    def _start_heartbeat(self):
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return

        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        while self._running and self.is_connected():
            time.sleep(self.config.heartbeat_interval)
            if not self._running:
                break

            elapsed = time.time() - self._last_recv_time
            if elapsed <= self.config.heartbeat_timeout + self.config.heartbeat_interval:
                continue

            heartbeat_cmd = Command(type=CommandType.STATUS)
            response, error = self.send_command(heartbeat_cmd, wait_response=True)
            if response is not None:
                self._last_recv_time = time.time()
                continue

            logger.warning("心跳探测在 %.1f 秒后失败: %s", elapsed, error)
            self._handle_connection_lost("心跳探测失败")
            break

    def _handle_connection_lost(self, reason: str):
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._connected_port = None

        self._set_state(ConnectionState.ERROR, reason)
        if self.config.auto_reconnect:
            self._start_reconnect()

    def send_command(self, cmd: Command, wait_response: bool = True) -> Tuple[Optional[Response], str]:
        """
        发送命令，并按需等待具有相同序列号的响应。
        """

        if not self.is_connected():
            return None, "串口未连接"

        frame = encode_command(cmd, auto_seq=True)
        expected_seq = cmd.seq

        for attempt in range(self.config.retry_count):
            with self._lock:
                try:
                    self._serial.write(frame)
                    self._record_command_event(cmd, wait_response, attempt + 1, frame)
                    self._log_command_trace(cmd, wait_response, attempt + 1)
                    self._log_frame_trace(frame, source="TX-FRAME")

                    if not wait_response:
                        return None, ""

                    response = self._read_response_with_seq(expected_seq)
                    if response is not None:
                        self._last_recv_time = time.time()
                        return response, ""

                    logger.warning(
                        "命令发送失败（%s/%s）：响应超时或序列号不匹配",
                        attempt + 1,
                        self.config.retry_count,
                    )
                except Exception as exc:
                    logger.warning("命令发送失败（第 %s 次）: %s", attempt + 1, exc)
                    if not self.is_connected():
                        self._handle_connection_lost(f"发送命令时连接断开: {exc}")
                        return None, f"连接断开: {exc}"

            if attempt < self.config.retry_count - 1:
                time.sleep(self.config.retry_delay)

        return None, f"命令发送失败，已重试 {self.config.retry_count} 次"

    def send_config(
        self,
        axis: AxisType,
        param_id: ConfigParamId,
        raw_value: int,
        wait_response: bool = True,
    ) -> Tuple[Optional[Response], str]:
        """使用统一打包格式发送一条通用 CONFIG 命令。"""

        cmd = Command(
            type=CommandType.CONFIG,
            axis=axis,
            value=config_pack_value(param_id, raw_value),
        )
        return self.send_command(cmd, wait_response=wait_response)

    def configure_pid(
        self,
        axis: AxisType,
        p: Optional[float] = None,
        i: Optional[float] = None,
        d: Optional[float] = None,
    ) -> Tuple[Optional[Response], str]:
        """为单个轴配置 PID，编码规则为 `增益 * 100`。"""

        if axis == AxisType.ALL:
            return None, "PID 配置必须指定具体轴"

        updates = []
        if p is not None:
            if p < 0:
                return None, "PID P 不能为负数"
            updates.append((ConfigParamId.PID_P, int(round(p * 100))))
        if i is not None:
            if i < 0:
                return None, "PID I 不能为负数"
            updates.append((ConfigParamId.PID_I, int(round(i * 100))))
        if d is not None:
            if d < 0:
                return None, "PID D 不能为负数"
            updates.append((ConfigParamId.PID_D, int(round(d * 100))))

        if not updates:
            return None, "未提供任何 PID 字段"

        return self._send_config_updates(axis, updates)

    def configure_watchdog(
        self,
        timeout_ms: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> Tuple[Optional[Response], str]:
        """配置看门狗超时和使能状态。"""

        updates = []
        if timeout_ms is not None:
            if timeout_ms <= 0 or timeout_ms > 0xFFFF:
                return None, "看门狗超时必须在 1..65535 ms 范围内"
            updates.append((ConfigParamId.WATCHDOG_TIMEOUT_MS, int(timeout_ms)))
        if enabled is not None:
            updates.append((ConfigParamId.WATCHDOG_ENABLE, 1 if enabled else 0))

        if not updates:
            return None, "未提供任何看门狗字段"

        return self._send_config_updates(AxisType.ALL, updates)

    def configure_axis_limits(
        self,
        axis: AxisType,
        minimum: Optional[float] = None,
        maximum: Optional[float] = None,
    ) -> Tuple[Optional[Response], str]:
        """使用 Jetson 侧的人类可读单位配置各轴行程限位。"""

        if axis not in _AXIS_LIMIT_PARAM_MAP:
            return None, "限位配置只支持 pan、tilt 或 rail"

        axis_name = _AXIS_NAME_MAP[axis]
        min_param, max_param = _AXIS_LIMIT_PARAM_MAP[axis]
        updates = []

        if minimum is not None:
            valid, error = MotionValidator.validate_position(minimum, axis_name)
            if not valid:
                return None, error
            updates.append((min_param, self._position_to_limit_raw(axis, minimum)))

        if maximum is not None:
            valid, error = MotionValidator.validate_position(maximum, axis_name)
            if not valid:
                return None, error
            updates.append((max_param, self._position_to_limit_raw(axis, maximum)))

        if not updates:
            return None, "未提供任何限位字段"

        return self._send_config_updates(axis, updates)

    def _send_config_updates(
        self,
        axis: AxisType,
        updates: List[Tuple[ConfigParamId, int]],
    ) -> Tuple[Optional[Response], str]:
        response = None
        for param_id, raw_value in updates:
            response, error = self.send_config(axis, param_id, raw_value, wait_response=True)
            if response is None:
                return None, error
        return response, ""

    @staticmethod
    def _position_to_limit_raw(axis: AxisType, value: float) -> int:
        raw_value = int(round(value * 100))
        if axis == AxisType.RAIL:
            if raw_value < 0 or raw_value > 0xFFFF:
                raise ValueError("Rail 限位超出 16 位无符号范围")
            return raw_value
        if raw_value < -0x8000 or raw_value > 0x7FFF:
            raise ValueError("角度限位超出 16 位有符号范围")
        return raw_value

    def _read_response_with_seq(self, expected_seq: int) -> Optional[Response]:
        buffer = bytearray()
        start_time = time.time()

        while time.time() - start_time < self.config.timeout:
            try:
                if self._serial.in_waiting <= 0:
                    time.sleep(0.001)
                    continue

                byte = self._serial.read(1)
                if not byte:
                    continue

                buffer.extend(byte)
                if len(buffer) < FRAME_MIN_LEN or buffer[-1] != FRAME_TAIL:
                    continue

                frame = bytes(buffer)
                response, error = decode_response(frame)
                if response is not None:
                    self._log_frame_trace(frame, source="RX-FRAME")
                    if response.seq == expected_seq:
                        self._record_response_event(response, "RX", frame, expected_seq=expected_seq)
                        self._log_response_trace(response, source="RX", expected_seq=expected_seq)
                        return response
                    self._record_response_event(
                        response,
                        "RX-UNMATCHED",
                        frame,
                        expected_seq=expected_seq,
                    )
                    self._log_response_trace(response, source="RX-UNMATCHED", expected_seq=expected_seq)
                    logger.warning(
                        "序列号不匹配：期望 %s，收到 %s",
                        expected_seq,
                        response.seq,
                    )
                elif error:
                    self._record_invalid_frame_event(frame, error)
                    self._log_frame_trace(frame, source="RX-FRAME-INVALID")
                buffer.clear()
            except Exception as exc:
                logger.error("读取响应失败: %s", exc)
                break

        return None

    def start_async_receive(self, callback: Callable[[Response], None]):
        self._recv_callback = callback
        self._recv_thread = threading.Thread(target=self._async_receive_loop, daemon=True)
        self._recv_thread.start()

    def _async_receive_loop(self):
        while self._running and self.is_connected():
            try:
                if self._serial.in_waiting > 0:
                    byte = self._serial.read(1)
                    if byte:
                        self._recv_buffer.extend(byte)
                        self._last_recv_time = time.time()
                        self._process_recv_buffer()
                else:
                    time.sleep(0.001)
            except Exception as exc:
                logger.error("异步接收失败: %s", exc)
                if not self.is_connected():
                    self._handle_connection_lost(f"接收数据时连接断开: {exc}")
                    break
                time.sleep(0.1)

    def _process_recv_buffer(self):
        while len(self._recv_buffer) > 0 and self._recv_buffer[0] != FRAME_HEAD:
            self._recv_buffer.pop(0)

        if len(self._recv_buffer) < FRAME_MIN_LEN:
            return

        for index in range(FRAME_MIN_LEN - 1, len(self._recv_buffer)):
            if self._recv_buffer[index] != FRAME_TAIL:
                continue

            frame = bytes(self._recv_buffer[: index + 1])
            self._recv_buffer = self._recv_buffer[index + 1 :]

            response, error = decode_response(frame)
            if response is not None:
                self._record_response_event(response, "RX-ASYNC", frame)
                self._log_frame_trace(frame, source="RX-FRAME")
                self._log_response_trace(response, source="RX-ASYNC")
                if self._recv_callback:
                    self._recv_callback(response)
            elif error:
                self._record_invalid_frame_event(frame, error)
                self._log_frame_trace(frame, source="RX-FRAME-INVALID")
            break
